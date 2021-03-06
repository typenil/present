import json
import os
import re
import shutil
from typing import Optional, List as ListType
from dataclasses import dataclass, field
from functools import cached_property

from asciimatics.effects import Print
from asciimatics.screen import Screen
from asciimatics.renderers import (
    ColourImageFile,
)

from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import terminal
from pyfiglet import Figlet
from loguru import logger

from .dynamic_formatter import (
    DynamicFormatter,
    DynamicCharacter,
    DataclassEncoder,
)
from .utils import normalize_name
from .effects import (
    COLORS,
    EFFECTS,
    SourceFile as SourceFileRenderer,
    Codio as CodioRenderer,
    Text as TestRenderer,
)


PrintList = ListType[Print]


@dataclass
class Renderable:
    obj: dict = field(default_factory=dict)
    fg: int = 0
    attr: int = 2  # Screen.A_NORMAL
    normal: int = 2  # Screen.A_NORMAL
    bg: int = 7

    @property
    def type(self) -> str:
        raise NotImplementedError()

    def _print_element(self, screen: Screen):
        return TestRenderer(self.render())

    def as_print_list(
        self,
        screen: Screen,
        row: int,
        fg_color: int = Screen.COLOUR_WHITE,
        bg_color: int = Screen.COLOUR_BLACK,
        attr: int = 0,
    ) -> PrintList:
        kwargs = dict(
            colour=fg_color,
            bg=bg_color,
            attr=attr,
            transparent=False,
        )

        if hasattr(self, "speed"):
            kwargs["speed"] = self.speed

        base = Print(screen, self._print_element(screen), row, **kwargs)
        return [base]

    def render(self):
        raise NotImplementedError()


@dataclass
class Heading(Renderable):
    type: str = "heading"

    @property
    def size(self):
        if self.obj["level"] == 1:
            f = Figlet()
            text = self.obj["children"][0]["text"]
            return len(f.renderText(text).splitlines())
        elif self.obj["level"] == 2:
            return 2
        else:
            return 1

    def render(self):
        text = self.obj["children"][0]["text"]

        if self.obj["level"] == 1:
            f = Figlet()
            return f.renderText(text)
        elif self.obj["level"] == 2:
            return "\n".join([text, "-" * len(text)])
        else:
            return text

    def as_print_list(
        self,
        screen: Screen,
        row: int,
        fg_color: int = Screen.COLOUR_WHITE,
        bg_color: int = Screen.COLOUR_BLACK,
        attr: int = 0,
    ) -> PrintList:
        if self.obj["level"] == 3:
            attr = Screen.A_BOLD
        return super().as_print_list(
            screen, row, fg_color=fg_color, bg_color=bg_color, attr=attr
        )


@dataclass
class List(Renderable):
    type: str = "list"

    def walk(self, obj, text=None, level=0):
        if text is None:
            text = []

        for child in obj.get("children", []):
            if child.get("text") is not None:
                text.append((" " * 2 * level) + "• " + child["text"])

            if "children" in obj:
                self.walk(child, text=text, level=level + 1)

        return text

    @property
    def size(self):
        return len(self.walk(self.obj))

    def render(self):
        return "\n".join(self.walk(self.obj))


@dataclass
class BlockCode(Renderable):
    type: str = "code"

    @staticmethod
    def pad(s, fill=" "):
        lines = s.splitlines()
        max_len = max(len(line) for line in lines)
        top = bottom = " " * (max_len + 2)

        lines = [line.ljust(max_len + 1, fill) for line in lines]
        lines = [" " + line for line in lines]
        lines.insert(0, top)
        lines.append(bottom)

        return "\n".join(lines)

    @property
    def size(self):
        return len(self.obj["text"].splitlines())

    @staticmethod
    def _highlight_code(code: str, language: Optional[str]) -> str:
        if not language:
            return code

        lexer = get_lexer_by_name(language, stripall=True)
        formatter = terminal.TerminalFormatter()
        return highlight(code, lexer, formatter)

    def render(self):
        language = self.obj.get("info")
        code = self.obj["text"]
        highlighted = self._highlight_code(code, language)
        return self.pad(highlighted)

    def as_print_list(
        self,
        screen: Screen,
        row: int,
        fg_color: int = Screen.COLOUR_WHITE,
        bg_color: int = Screen.COLOUR_BLACK,
        attr: int = 0,
    ) -> PrintList:
        return super().as_print_list(
            screen, row, Screen.COLOUR_WHITE, Screen.COLOUR_BLACK
        )


@dataclass
class Codio(Renderable):
    type: str = "codio"

    @property
    def speed(self):
        speed = self.obj.get("speed", 5)

        if speed < 1:
            logger.warn("Codio speed < 1, setting it to 1")
            speed = 1
        elif speed > 10:
            logger.warn("Codio speed > 10, setting it to 10")
            speed = 10

        return 11 - speed

    @property
    def width(self):
        width = 0
        _terminal_width = int(shutil.get_terminal_size()[0] / 4)

        for line in self.obj["lines"]:
            prompt = line.get("prompt", "")
            inp = line.get("in", "")
            out = line.get("out", "")

            if line.get("progress") is not None and line["progress"]:
                magic_width = _terminal_width
            else:
                magic_width = 0

            width = max(
                width,
                magic_width,
                len(prompt),
                len(inp) + inp.count(" "),
                len(out) + out.count(" "),
            )

        return width + 4

    @property
    def size(self):
        lines = len(self.obj["lines"])

        for line in self.obj["lines"]:
            inp = line.get("in", "")
            out = line.get("out", "")
            if inp and out:
                lines += 1

        return lines + 2

    def render(self):
        code = []
        width = self.width

        for yaml_line in self.obj["lines"]:
            render_line = {}

            # if there is a progress bar, don't display prompt or add style
            if yaml_line.get("progress") is not None and yaml_line["progress"]:
                progress_char = yaml_line.get("progressChar", "█")
                render_line["prompt"] = ""
                render_line["in"] = progress_char * int(0.6 * width)
                render_line["out"] = ""
            else:
                prompt = yaml_line.get("prompt", "")
                inp = yaml_line.get("in", "")
                out = yaml_line.get("out", "")

                if not (prompt or inp or out):
                    continue

                # if only prompt is present, print it all at once
                if not inp and not out:
                    out = prompt
                    prompt = ""

                render_line["prompt"] = prompt
                render_line["in"] = inp
                render_line["out"] = out

                render_line["color"] = yaml_line.get("color")
                render_line["bold"] = yaml_line.get("bold")
                render_line["underline"] = yaml_line.get("underline")

            code.append(render_line)

        return code

    def _print_element(self, screen: Screen):
        return CodioRenderer(
            code=self.render(), width=self.width, height=self.size
        )


@dataclass
class SourceFile(Renderable):
    type: str = "source_file"
    dirname: Optional[str] = None

    @property
    def speed(self):
        speed = self.obj.get("speed", 5)

        if speed < 1:
            logger.warn("Codio speed < 1, setting it to 1")
            speed = 1
        elif speed > 10:
            logger.warn("Codio speed > 10, setting it to 10")
            speed = 10

        return 11 - speed

    @cached_property
    def language(self) -> Optional[str]:
        return self.obj.get("language", None)

    def __post_init__(self):
        src_path = (
            os.path.join(
                self.dirname,
                os.path.expanduser(self.obj["file"]),
            )
            if self.dirname
            else self.obj["file"]
        )

        with open(src_path, "r") as infile:
            lines = infile.readlines()
            self.obj["source"] = "".join(lines)
            self.width = self.get_width(lines)
            self.size = self.get_size(lines)

    @staticmethod
    def get_width(lines: ListType[str]) -> int:
        width = 0

        for line in lines:
            width = max(
                width,
                len(line),
            )

        return width + 4

    @staticmethod
    def get_size(lines: ListType[str]) -> int:
        return len(lines) + 2

    def render(self):
        if self.language:
            lexer = get_lexer_by_name(self.language, stripall=True)
            formatter = DynamicFormatter()
            return highlight(self.obj["source"], lexer, formatter)

        return json.dumps(
            [DynamicCharacter(text=self.obj["source"])], cls=DataclassEncoder
        )

    def _print_element(self, screen: Screen):
        return SourceFileRenderer(
            source=self.render(),
            width=self.width,
            height=self.size,
        )


@dataclass(init=False)
class Image(Renderable):
    type: str = "image"

    def __post_init__(self):
        src = self.obj.get("src")
        if not os.path.exists(src):
            raise FileNotFoundError(f"{src} does not exist")

    @property
    def size(self):
        # TODO: Support small, medium, large image sizes
        return int(shutil.get_terminal_size()[1] / 2)

    def render(self):
        raise NotImplementedError

    def _print_element(self, screen: Screen):
        return ColourImageFile(
            screen,
            self.obj["src"],
            self.size,
            fill_background=True,
            uni=screen.unicode_aware,
            dither=screen.unicode_aware,
        )


@dataclass
class BlockHtml(Renderable):
    type: str = "html"

    @property
    def size(self):
        raise NotImplementedError

    @property
    def style(self):
        _style = re.findall(r"((\w+)=(\w+))", self.obj["text"])
        return {s[1]: s[2] for s in _style}

    def render(self):
        raise NotImplementedError


@dataclass
class Text(Renderable):
    type: str = "text"

    @property
    def size(self):
        return 1

    def render(self):
        return self.obj["text"]


@dataclass
class Codespan(Renderable):
    type: str = "codespan"
    attr: int = 3  # Screen.A_REVERSE

    @property
    def size(self):
        raise NotImplementedError

    def render(self):
        return (
            f"${{{self.fg},{self.attr},{self.bg}}}"
            + self.obj["text"]
            + f"${{{self.fg},{self.normal},{self.bg}}}"
        )


@dataclass
class Strong(Renderable):
    type: str = "strong"
    attr: int = 1  # Screen.A_BOLD

    @property
    def size(self):
        raise NotImplementedError

    def render(self):
        return (
            f"${{{self.fg},{self.attr},{self.bg}}}"
            + self.obj["children"][0]["text"]
            + f"${{{self.fg},{self.normal},{self.bg}}}"
        )


@dataclass
class Emphasis(Renderable):
    type: str = "emphasis"

    @property
    def size(self):
        raise NotImplementedError

    def render(self):
        # TODO: add italic support
        return self.obj["children"][0]["text"]


@dataclass
class Link(Renderable):
    type: str = "link"

    @property
    def size(self):
        raise NotImplementedError

    def render(self):
        return f"{self.obj['children'][0]['text']} ({self.obj['link']})"


@dataclass
class Paragraph(Renderable):
    type: str = "paragraph"

    @property
    def size(self):
        # TODO: paragraph size should be sum of all element sizes in it
        return 1

    def render(self):
        text = ""

        for child in self.obj["children"]:
            e = RenderableFactory.create(
                child["type"], obj=child, fg=self.fg, bg=self.bg
            )
            text += e.render()

        return text


@dataclass
class BlockQuote(Renderable):
    type: str = "quote"

    @property
    def size(self):
        return len(self.obj["children"])

    def render(self):
        text = []

        for child in self.obj["children"]:
            p = Paragraph(obj=child, fg=self.fg, bg=self.bg)
            for t in p.render().split("\n"):
                text.append(f"▌ {t}")

        return "\n".join(text)


class RenderableFactory:
    RENDER_CLASSES = {
        normalize_name(klass.__name__): klass
        for klass in [
            Heading,
            List,
            BlockCode,
            Codio,
            Image,
            BlockHtml,
            Text,
            Codespan,
            Strong,
            Emphasis,
            Link,
            Paragraph,
            BlockQuote,
        ]
    }

    @classmethod
    def create(cls, name: str, obj: dict) -> Renderable:
        return cls.RENDER_CLASSES[normalize_name(name)](obj=obj)


class Slide:
    def __init__(self, elements=None):
        self._elements = []
        self._style = {}
        self.has_style = False
        self.has_effect = False
        self.has_image = False
        self.has_code = False
        self.has_codio = False
        self.effect = None
        self.fg_color = 0
        self.bg_color = 7
        self.elements = elements

    @property
    def style(self):
        return self._style

    @style.setter
    def style(self, style: dict):

        # TODO: support everything!
        if style.get("effect") is not None:
            if style["effect"] not in EFFECTS:
                raise ValueError(f"Effect {style['effect']} is not supported")
            self.has_effect = True
            self.effect = style["effect"]
            self.fg_color, self.bg_color = 7, 0

        for color_key in ("fg", "bg"):
            if style.get(color_key) is not None:
                try:
                    setattr(
                        self, f"{color_key}_color", COLORS[style[color_key]]
                    )
                except KeyError:
                    raise ValueError(
                        f"Color {style[color_key]} is not supported"
                    )

        if self.has_effect and (
            style.get("fg") is not None or style.get("bg") is not None
        ):
            raise ValueError(
                "Effects and colors on the same slide are not supported"
            )

        if self.has_effect and self.has_code:
            raise ValueError(
                "Effects and code on the same slide are not supported"
            )

        self._style = style.copy()

    @property
    def elements(self):
        return self._elements

    @elements.setter
    def elements(self, elements):
        renderable = []
        for e in elements:
            # TODO: raise warning if multiple styles
            if e.type == "code":
                self.has_code = True

            elif e.type == "codio":
                self.has_codio = True

            elif e.type == "html":
                if e.style:
                    self.has_style = True
                    self.style = e.style
                # remove html comments
                continue

            elif e.type == "image":
                self.has_image = True
            renderable.append(e)

        if self.has_effect:
            # apply fg and bg color to all elements
            for e in self.elements:
                e.fg = self.fg_color
                e.bg = self.bg_color

        self._elements = renderable

    def __repr__(self):
        return (
            f"<Slide elements={self.elements} "
            f"has_style={self.has_style} "
            f"has_code={self.has_code} "
            f"fg_color={self.fg_color} "
            f"bg_color={self.bg_color}>"
        )
