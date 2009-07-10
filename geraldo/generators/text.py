import datetime
from base import ReportGenerator

from geraldo.base import cm
from geraldo.utils import get_attr_value, calculate_size
from geraldo.widgets import Widget, Label, SystemField
from geraldo.graphics import Graphic, RoundRect, Rect, Line, Circle, Arc,\
        Ellipse, Image

# In development

DEFAULT_ROW_HEIGHT = 0.5*cm
DEFAULT_CHAR_WIDTH = 0.23*cm

# Default is Epson ESC/P2 standard
DEFAULT_ESCAPE_SET = {
        'line-feed': chr(10),
        'form-feed': chr(12),
        'carriage-return': chr(13),
        'condensed': chr(15),
        'cancel-condensed': chr(18),
        'line-spacing-big': chr(27)+chr(48),
        'line-spacing-normal': chr(27)+chr(49),
        'line-spacing-short': chr(27)+chr(50),
        'italic': chr(27)+chr(52),
        'cancel-italic': chr(27)+chr(53),
        }

class Paragraph(object):
    text = ''
    style = None
    height = None
    width = None

    def __init__(self, text, style=None):
        self.text = text
        self.style = style

    def wrapOn(self, page_size, width, height): # TODO: this should be more eficient with multiple lines
        self.height = height
        self.width = width

class TextGenerator(ReportGenerator):
    """This is a generator to output data in text/plain format.
    
    Attributes:

        * 'row_height' - should be the equivalent height of a row plus the space
          between rows. This is important to calculate how many rows has a page.
        * 'character_width' - should be the equivalent width of a character. This
          is important to calculate how many columns has a page.
        * 'to_printer' - is a boolean variable you can inform to generate a text
          to matrix printer or not. This means escape characters will be in output
          or not.
        * 'escape_set' - is a dictionary with equivalence table to escape codes.
          As far as we know, escape codes can vary depending of model or printer
          manufacturer (i.e. Epson, Lexmark, HP, etc.). This attribute is useful
          to support this. Defaul is ESC/P2 standard (Epson matrix printers)
        * 'filename' - is the file path you can inform optionally to save text to.
        * 'encode_to' - you can inform the coding identifier to force Geraldo to
          encode the output string on it. Example: 'latin-1'
    """
    row_height = DEFAULT_ROW_HEIGHT
    character_width = DEFAULT_CHAR_WIDTH
    _to_printer = True
    _escape_set = DEFAULT_ESCAPE_SET
    encode_to = None
    manual_escape_codes = False

    escapes_report_start = ''
    escapes_report_end = ''
    escapes_page_start = ''
    escapes_page_end = ''

    def __init__(self, report, **kwargs):
        super(TextGenerator, self).__init__(report)

        # Specific attributes
        for k,v in kwargs.items():
            setattr(self, k, v)

        self.update_escape_chars()

    def execute(self):
        super(TextGenerator, self).execute()

        # Render pages
        self.render_bands()

        # Generate the pages
        text = self.generate_pages()

        # Encode
        if self.encode_to:
            text = text.encode(self.encode_to)

        # Saves to file or just returns the text
        if hasattr(self, 'filename'):
            fp = file(self.filename, 'w')
            fp.write(text)
            fp.close()
        else:
            return text

    def calculate_size(self, size):
        """Uses the function 'calculate_size' to calculate a size"""
        if isinstance(size, basestring):
            if size.endswith('*cols'):
                return int(size.split('*')[0]) * self.character_width
            elif size.endswith('*rows'):
                return int(size.split('*')[0]) * self.row_height
        
        return calculate_size(size)

    def make_paragraph(self, text, style=None): # TODO: make style with basic functions, like alignment, bold, emphasis (italic), etc
        """Uses the Paragraph class to return a new paragraph object"""
        return Paragraph(text, style)

    def wrap_paragraph_on(self, paragraph, width, height):
        """Wraps the paragraph on the height/width informed"""
        paragraph.wrapOn(self.report.page_size, width, height)

    def make_paragraph_style(self, band, style=None):
        """Merge report default_style + band default_style + widget style"""
        d_style = self.report.default_style.copy()

        if band.default_style:
            for k,v in band.default_style.items():
                d_style[k] = v

        if style:
            for k,v in style.items():
                d_style[k] = v

        import datetime

        return dict(name=datetime.datetime.now().strftime('%H%m%s'), **d_style)

    # METHODS THAT ARE TOTALLY SPECIFIC TO THIS GENERATOR AND MUST
    # OVERRIDE THE SUPERCLASS EQUIVALENT ONES

    def generate_pages(self):
        """Specific method that generates the pages"""
        self._generation_datetime = datetime.datetime.now()
        self._output = u''

        # Escapes
        self.add_escapes_report_start();

        for num, page in enumerate([page for page in self._rendered_pages if page.elements]):
            # Escapes
            self.add_escapes_page_start(num);

            _page_output = [u' ' * self.page_columns_count] * self.page_rows_count

            self._current_page_number = num

            # Loop at band widgets
            for element in page.elements:
                # Widget element
                if isinstance(element, Widget):
                    widget = element
                    self.generate_widget(widget, _page_output, num)

            # Adds the page output to output string
            self._output += u'\n'.join(_page_output)

            # Escapes
            self.add_escapes_page_end(num);

        # Escapes
        self.add_escapes_report_end();

        return self._output

    def generate_widget(self, widget, page_output, page_number=0):
        """Renders a widget element on canvas"""
        self.print_in_page_output(page_output, widget.text, widget.rect)

    def generate_graphic(self, graphic, page_output): # TODO: horizontal and vertical lines, rectangles and borders should be ok
        """Renders a graphic element"""
        pass

    def print_in_page_output(self, page_output, text, rect):
        """Changes the array page_output (a matrix with rows and cols equivalent
        to rows and cols in a matrix printer page) inserting the text value in
        the left/top coordinates."""

        # Make the real rect for this text
        text_rect = {
            'top': int(round(self.calculate_size(rect['top']) / self.row_height)),
            'left': int(round(self.calculate_size(rect['left']) / self.character_width)),
            'height': int(round(self.calculate_size(rect['height']) / self.row_height)),
            'width': int(round(self.calculate_size(rect['width']) / self.character_width)),
            'bottom': int(round(self.calculate_size(rect['bottom']) / self.row_height)),
            'right': int(round(self.calculate_size(rect['right']) / self.character_width)),
            }

        # Default height and width
        text_rect['height'] = text_rect['height'] or 1
        text_rect['width'] = text_rect['width'] or len(text)

        if text_rect['height'] and text_rect['width']:
            # Make a text with the exact width
            text = text.ljust(text_rect['width'])[:text_rect['width']] # Align to left - TODO: should have center and right justifying also

            # Inserts the text into the page output buffer
            _temp = page_output[text_rect['top']]
            _temp = _temp[:text_rect['left']] + text + _temp[text_rect['right']:]
            page_output[text_rect['top']] = _temp[:self.get_page_columns_count()]

    def add_escapes_report_start(self):
        """Adds the escape commands to the output variable"""
        self._output += self.escapes_report_start

    def add_escapes_report_end(self):
        """Adds the escape commands to the output variable"""
        self._output += self.escapes_report_end

    def add_escapes_page_start(self, num):
        """Adds the escape commands to the output variable"""
        self._output += self.escapes_page_start

    def add_escapes_page_end(self, num):
        """Adds the escape commands to the output variable"""
        self._output += self.escapes_page_end

    def update_escape_chars(self):
        """Sets the escape chars to be ran for some events on report generation"""
        if self.manual_escape_codes:
            return

        if self.to_printer:
            self.escapes_report_start = ''
            self.escapes_report_end = ''
            self.escapes_page_start = ''
            self.escapes_page_end = self.escape_set['form-feed']
        else:
            self.escapes_report_start = ''
            self.escapes_report_end = ''
            self.escapes_page_start = ''
            self.escapes_page_end = ''

    def get_escape_set(self):
        return self._escape_set

    def set_escape_set(self, val):
        self._escape_set = val
        self.update_escape_chars()

    escape_set = property(get_escape_set, set_escape_set)

    def get_to_printer(self):
        return self._to_printer

    def set_to_printer(self, val):
        self._to_printer = val
        self.update_escape_chars()

    to_printer = property(get_to_printer, set_to_printer)

    def get_page_rows_count(self):
        return int(round(self.calculate_size(self.report.page_size[1]) / self.row_height))
    page_rows_count = property(get_page_rows_count)

    def get_page_columns_count(self):
        return int(round(self.calculate_size(self.report.page_size[0]) / self.character_width))
    page_columns_count = property(get_page_columns_count)

