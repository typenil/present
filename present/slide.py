import os
import re
import shutil
from dataclasses import dataclass, field
from typing import List
from functools import cached_property

from pyfiglet import Figlet
from loguru import logger

from .effects import COLORS, EFFECTS


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

    def render(self):
        return self.pad(self.obj["text"])


@dataclass
class Codio(Renderable):
    type: str = "codio"

    @property
    def speed(self):
        _speed = self.obj["speed"]

        if _speed < 1:
            logger.warn("Codio speed < 1, setting it to 1")
            _speed = 1
        elif _speed > 10:
            logger.warn("Codio speed > 10, setting it to 10")
            _speed = 10

        return 11 - _speed

    @property
    def width(self):
        _width = 0
        _terminal_width = int(shutil.get_terminal_size()[0] / 4)

        for line in self.obj["lines"]:
            prompt = line.get("prompt", "")
            inp = line.get("in", "")
            out = line.get("out", "")

            if line.get("progress") is not None and line["progress"]:
                _magic_width = _terminal_width
            else:
                _magic_width = 0

            _width = max(
                _width,
                _magic_width,
                len(prompt),
                len(inp) + inp.count(" "),
                len(out) + out.count(" "),
            )

        return _width + 4

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
        _code = []
        _width = self.width

        for line in self.obj["lines"]:
            _c = {}

            # if there is a progress bar, don't display prompt or add style
            if line.get("progress") is not None and line["progress"]:
                progress_char = line.get("progressChar", "█")
                _c["prompt"] = ""
                _c["in"] = progress_char * int(0.6 * _width)
                _c["out"] = ""
            else:
                prompt = line.get("prompt", "")
                inp = line.get("in", "")
                out = line.get("out", "")

                if not (prompt or inp or out):
                    continue

                # if only prompt is present, print it all at once
                if not inp and not out:
                    out = prompt
                    prompt = ""

                _c["prompt"] = prompt
                _c["in"] = inp
                _c["out"] = out

                _c["color"] = line.get("color")
                _c["bold"] = line.get("bold")
                _c["underline"] = line.get("underline")

            _code.append(_c)

        return _code


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
            element_name = child["type"].title().replace("_", "")
            Element = eval(element_name)
            e = Element(obj=child, fg=self.fg, bg=self.bg)
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


class Slide:
    def __init__(self, elements=None):
        self.elements = elements
        self.has_style = False
        self.has_effect = False
        self.has_image = False
        self.has_code = False
        self.has_codio = False
        self.effect = None
        self.fg_color = 0
        self.bg_color = 7

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

        if style.get("fg") is not None:
            try:
                self.fg_color = COLORS[style["fg"]]
            except KeyError:
                raise ValueError(f"Color {style['fg']} is not supported")

        if style.get("bg") is not None:
            try:
                self.bg_color = COLORS[style["bg"]]
            except KeyError:
                raise ValueError(f"Color {style['bg']} is not supported")

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

        if self.has_effect:
            # apply fg and bg color to all elements
            for e in self.elements:
                e.fg = self.fg_color
                e.bg = self.bg_color

        self._elements = elements

    def __repr__(self):
        return (
            f"<Slide elements={self.elements} "
            f"has_style={self.has_style} "
            f"has_code={self.has_code} "
            f"fg_color={self.fg_color} "
            f"bg_color={self.bg_color}>"
        )
