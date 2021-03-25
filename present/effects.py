from random import randint, choice
from typing import Callable, List, Dict
from pygments import highlight, lex
from pygments.lexers import get_lexer_by_name

from asciimatics.effects import Print
from asciimatics.screen import Screen
from asciimatics.effects import Stars, Matrix
from asciimatics.particles import Explosion, StarFirework
from asciimatics.renderers import (
    Renderer,
    Plasma,
    SpeechBubble,
    StaticRenderer,
    ColourImageFile,
    DynamicRenderer,
)

from .utils import normalize_name


ATTRS = {
    "bold": Screen.A_BOLD,
    "normal": Screen.A_NORMAL,
    "reverse": Screen.A_REVERSE,
    "underline": Screen.A_UNDERLINE,
}
COLORS = {
    "black": Screen.COLOUR_BLACK,
    "red": Screen.COLOUR_RED,
    "green": Screen.COLOUR_GREEN,
    "yellow": Screen.COLOUR_YELLOW,
    "blue": Screen.COLOUR_BLUE,
    "magenta": Screen.COLOUR_MAGENTA,
    "cyan": Screen.COLOUR_CYAN,
    "white": Screen.COLOUR_WHITE,
}
EFFECTS = ["fireworks", "explosions", "stars", "matrix", "plasma"]


class Text(StaticRenderer):
    def __init__(self, text):
        super(Text, self).__init__()
        self._images = [text]


class SourceFile(DynamicRenderer):
    def __init__(self, source=None, height=100, width=100):
        super().__init__(height, width)
        self._source = source
        self._height = height
        self._width = width
        self._state = None

    def _render_now(self):
        x = y = 1

        for i, c in enumerate(self._source):
            kwargs = {}

            self._write(c, x, y, **kwargs)
            y += 1

        return self._plain_image, self._colour_map


class Codio(DynamicRenderer):
    def __init__(self, code=None, height=100, width=100):
        super(Codio, self).__init__(height, width)
        self._code = code
        self._height = height
        self._width = width
        self._state = None
        self._reset()

    def _reset(self):
        self._state = {
            i: {"len": 0, "start": False, "end": False}
            for i in range(len(self._code))
        }

    def _get_code(self, i):
        if self._state.get(i - 1) is None:
            self._state[i]["start"] = True

        if self._code[i]["in"]:
            if self._state[i]["len"] == len(self._code[i]["in"]):
                self._state[i]["end"] = True
                return self._code[i]["in"], self._code[i]["out"]

            if (
                self._state.get(i - 1) is not None
                and not self._state[i - 1]["end"]
            ):
                return None, None
            c = self._code[i]["in"][: self._state[i]["len"]]
            self._state[i]["len"] += 1
            return c, None

        if not self._code[i]["in"] and self._code[i]["out"]:
            if (
                self._state.get(i - 1) is not None
                and not self._state[i - 1]["end"]
            ):
                return None, None
            self._state[i]["end"] = True
            return None, self._code[i]["out"]

    def _render_now(self):
        x = y = 1

        for i, c in enumerate(self._code):
            kwargs = {}

            if self._code[i].get("color") is not None:
                kwargs.update({"colour": COLORS[self._code[i]["color"]]})

            if self._code[i].get("bold") is not None and self._code[i]["bold"]:
                kwargs.update({"attr": ATTRS["bold"]})

            if (
                self._code[i].get("underline") is not None
                and self._code[i]["underline"]
            ):
                kwargs.update({"attr": ATTRS["underline"]})

            inp, out = self._get_code(i)
            if inp is not None:
                prompt = self._code[i]["prompt"]
                if prompt:
                    self._write(f"{prompt} {inp}", x, y, **kwargs)
                else:
                    self._write(f"{inp}", x, y, **kwargs)
                y += 1
            if out is not None and out:
                self._write(out, x, y, **kwargs)
                y += 1

        return self._plain_image, self._colour_map


def reset(screen: Screen) -> List[Print]:
    reset = Print(
        screen,
        SpeechBubble("Press 'r' to restart."),
        int(screen.height / 2) - 2,
        attr=ATTRS["bold"],
    )
    return [reset]


def fireworks(screen: Screen) -> List[StarFirework]:
    effects: List[Effect] = []
    x_regions = [
        (0, screen.width),
        (0, screen.width // 3),
        (screen.width // 3 * 2, screen.width),
    ]
    y_regions = [
        (0, screen.height),
        (screen.height // 2, screen.height),
    ]

    for _ in range(20):
        x = randint(*choice(x_regions))
        y = randint(*choice(y_regions))
        effects.insert(
            1,
            StarFirework(
                screen,
                x,
                y,
                randint(25, 30),
                start_frame=randint(0, 250),
            ),
        )
    return effects


def explosions(screen: Screen) -> List[Explosion]:
    effects = []
    x_regions = [
        (0, screen.width),
        (0, screen.width // 3),
        (screen.width // 3 * 2, screen.width),
    ]
    y_regions = [
        (0, screen.height),
        (screen.height // 2, screen.height),
    ]

    for _ in range(20):
        x = randint(*choice(x_regions))
        y = randint(*choice(y_regions))
        effects.append(
            Explosion(
                screen,
                x,
                y,
                randint(20, 30),
                start_frame=randint(0, 250),
            )
        )
    return effects


def stars(screen: Screen) -> List[Stars]:
    return [Stars(screen, (screen.width + screen.height) // 2, stop_frame=100)]


def matrix(screen: Screen) -> List[Matrix]:
    return [Matrix(screen, stop_frame=200)]


def plasma(screen: Screen) -> List[Print]:
    return [
        Print(
            screen,
            Plasma(screen.height, screen.width, screen.colours),
            0,
            speed=1,
            transparent=False,
        )
    ]


def countdown(screen: Screen) -> List[Print]:
    pass


Effect = Callable[[Screen], List[Renderer]]


class EffectFactory:
    EFFECTS: Dict[str, Effect] = {
        normalize_name(klass.__name__): klass
        for klass in [
            fireworks,
            explosions,
            stars,
            matrix,
            plasma,
            countdown,
        ]
    }

    @classmethod
    def create(cls, name: str, effect: Effect) -> List[Renderer]:
        return cls.EFFECTS[normalize_name(name)](effect)
