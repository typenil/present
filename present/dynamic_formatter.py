import json
from dataclasses import dataclass, asdict, is_dataclass

from asciimatics.screen import Screen
from pygments.formatter import Formatter
from pygments.token import (
    Keyword,
    Name,
    Comment,
    String,
    Error,
    Number,
    Operator,
    Generic,
    Token,
    Whitespace,
)


class DataclassEncoder(json.JSONEncoder):
    def default(self, obj):
        if is_dataclass(obj):
            return asdict(obj)
        return json.JSONEncoder.default(self, obj)


@dataclass
class DynamicCharacter:
    text: str
    color: int = Screen.COLOUR_WHITE
    attr: int = Screen.A_NORMAL
    bg: int = Screen.COLOUR_BLACK

    @property
    def args(self) -> tuple:
        return (self.text, self.color, self.attr, self.bg)


ASCIIMATIC_COLORS = {
    Token: Screen.COLOUR_WHITE,
    Whitespace: Screen.COLOUR_WHITE,
    Comment: Screen.COLOUR_WHITE,
    Comment.Preproc: Screen.COLOUR_CYAN,
    Keyword: Screen.COLOUR_BLUE,
    Keyword.Type: Screen.COLOUR_CYAN,
    Operator.Word: Screen.COLOUR_MAGENTA,
    Name.Builtin: Screen.COLOUR_CYAN,
    Name.Function: Screen.COLOUR_GREEN,
    Name.Namespace: Screen.COLOUR_CYAN,
    Name.Class: Screen.COLOUR_GREEN,
    Name.Exception: Screen.COLOUR_CYAN,
    Name.Decorator: Screen.COLOUR_WHITE,
    Name.Variable: Screen.COLOUR_RED,
    Name.Constant: Screen.COLOUR_RED,
    Name.Attribute: Screen.COLOUR_CYAN,
    Name.Tag: Screen.COLOUR_BLUE,
    String: Screen.COLOUR_YELLOW,
    Number: Screen.COLOUR_BLUE,
    Generic.Deleted: Screen.COLOUR_RED,
    Generic.Inserted: Screen.COLOUR_GREEN,
    Generic.Heading: Screen.COLOUR_WHITE,
    Generic.Subheading: Screen.COLOUR_MAGENTA,
    Generic.Prompt: Screen.COLOUR_WHITE,
    Generic.Error: Screen.COLOUR_RED,
    Error: Screen.COLOUR_RED,
}


class DynamicFormatter(Formatter):
    name = "Dynamic Renderer Formatter"
    aliases = ["dynamic", "dynamicrenderer"]
    filenames = []

    def __init__(self, **options):
        Formatter.__init__(self, **options)
        self.colorscheme = (
            options.get("colorscheme", None) or ASCIIMATIC_COLORS
        )
        self.linenos = options.get("linenos", False)

    def format(self, tokensource, outfile):
        return Formatter.format(self, tokensource, outfile)

    def _write_lineno(self, outfile):
        self._lineno += 1
        outfile.write(
            "%s%04d: " % (self._lineno != 1 and "\n" or "", self._lineno)
        )

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

        lineno = 0

        characters = []

        def append_lineo():
            if self.linenos:
                characters.append(DynamicCharacter(text=str(lineno).zfill(2)))

        append_lineo()
        for ttype, value in tokensource:
            color = self._get_color(ttype)

            for line in value.splitlines(True):

                characters.append(DynamicCharacter(text=line, color=color))
                if line.endswith("\n"):
                    lineno += 1
                    append_lineo()

        outfile.write(json.dumps(characters, cls=DataclassEncoder))
