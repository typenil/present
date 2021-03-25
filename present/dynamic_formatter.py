from dataclasses import dataclass

from asciimatics.screen import Screen
from pygments.formatter import Formatter


@dataclass
class DynamicCharacter:
    text: str
    x: int
    y: int
    color: int = Screen.COLOUR_WHITE
    attr: int = Screen.A_NORMAL
    bg: int = Screen.COLOUR_BLACK

    @property
    def args(self) -> tuple:
        return (self.text, self.x, self.y, self.color, self.attr, self.bg)

    

ASCIIMATIC_COLORS = {
    Token:          Screen.COLOR_DEFAULT, 

    Whitespace:        Screen.COLOUR_BLACK, 
    Comment:            Screen.COLOUR_BLACK,
    Comment.Preproc:    Screen.COLOUR_CYAN,
    Keyword:            Screen.COLOUR_BLUE,
    Keyword.Type:       Screen.COLOUR_CYAN,
    Operator.Word:      Screen.COLOUR_MAGENTA,
    Name.Builtin:       Screen.COLOUR_CYAN,
    Name.Function:      Screen.COLOUR_GREEN,
    Name.Namespace:     Screen.COLOUR_CYAN,
    Name.Class:         Screen.COLOUR_GREEN,
    Name.Exception:     Screen.COLOUR_CYAN,
    Name.Decorator:     Screen.COLOUR_BLACK,
    Name.Variable:      Screen.COLOUR_RED,
    Name.Constant:      Screen.COLOUR_RED,
    Name.Attribute:     Screen.COLOUR_CYAN,
    Name.Tag:           Screen.COLOUR_BLUE,
    String:             Screen.COLOUR_YELLOW,
    Number:             Screen.COLOUR_BLUE,

    Generic.Deleted:    Screen.COLOUR_RED,
    Generic.Inserted:   Screen.COLOUR_GREEN,
    Generic.Heading:    Screen.COLOUR_DEFAULT,
    Generic.Subheading: Screen.COLOUR_MAGENTA,
    Generic.Prompt:     Screen.COLOUR_DEFAULT,
    Generic.Error:      Screen.COLOUR_RED,

    Error:              Screen.COLOUR_RED,
}

class DynamicFormatter(Formatter):
    name = 'Dynamic Renderer Formatter'
    aliases = ['dynamic', 'dynamicrenderer']
    filenames = []

    def __init__(self, **options):
        Formatter.__init__(self, **options)
        self.colorscheme = options.get('colorscheme', None) or ASCIIMATIC_COLORS
        self.linenos = options.get('linenos', False)
        self._lineno = 0

    def format(self, tokensource, outfile):
        return Formatter.format(self, tokensource, outfile)

    def _write_lineno(self, outfile):
        self._lineno += 1
        outfile.write("%s%04d: " % (self._lineno != 1 and '\n' or '', self._lineno))

    def _get_color(self, ttype):
        # self.colorscheme is a dict containing usually generic types, so we
        # have to walk the tree of dots.  The base Token type must be a key,
        # even if it's empty string, as in the default above.
        color = self.colorscheme.get(ttype)
        while color is None:
            ttype = ttype.parent
            color = self.colorscheme.get(ttype)
        return color

    def format_unencoded(self, tokensource, outfile):
        # TODO figure out what "outfile" is. If we're forced to write to some sort of string,
        # that's not great. Maybe we could output as lines in a json array.
        # Ideallyh, we'll just be able to output List[DynamicCharacter]

            self._write_lineno(outfile)

        for ttype, value in tokensource:
            color = self._get_color(ttype)

            for line in value.splitlines(True):
                if color:
                    outfile.write(ansiformat(color, line.rstrip('\n')))
                else:
                    outfile.write(line.rstrip('\n'))
                if line.endswith('\n'):
                    if self.linenos:
                        self._write_lineno(outfile)
                    else:
                        outfile.write('\n')

        if self.linenos:
            outfile.write("\n")
