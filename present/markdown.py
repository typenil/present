# -*- coding: utf-8 -*-

import os

import yaml
import mistune
from loguru import logger

# from pygments import highlight
# from pygments.lexers import get_lexer_by_name
# from pygments.formatters import html

from .slide import Slide, Paragraph, Image, Codio, RenderableFactory


# class HighlightRenderer(mistune.HTMLRenderer):
#     def block_code(self, code, lang=None):
#         if lang:
#             lexer = get_lexer_by_name(lang, stripall=True)
#             formatter = html.HtmlFormatter()
#             return highlight(code, lexer, formatter)
#         return "<pre><code>" + mistune.escape(code) + "</code></pre>"


class Markdown(object):
    """Parse and traverse through the markdown abstract syntax tree."""

    def __init__(self, filename):
        self.filename = filename
        self.dirname = os.path.dirname(os.path.realpath(filename))

    def parse(self):
        with open(self.filename, "r") as f:
            text = f.read()

        slides = []
        ast = mistune.markdown(text, renderer="ast")

        sliden = 0
        bufr = []

        def dump_slide():
            nonlocal bufr, slides, sliden
            if not bufr:
                return

            slides.append(Slide(elements=bufr))
            sliden += 1
            bufr = []

        for i, obj in enumerate(ast):
            if obj["type"] in ["newline"]:
                continue

            if obj["type"] == "thematic_break":
                dump_slide()
                continue

            if obj["type"] == "paragraph":
                images = [c for c in obj["children"] if c["type"] == "image"]
                not_images = [
                    c for c in obj["children"] if c["type"] != "image"
                ]

                for image in images:
                    image["src"] = os.path.join(
                        self.dirname, os.path.expanduser(image["src"])
                    )

                    if image["alt"] == "codio":
                        with open(image["src"], "r") as f:
                            codio = yaml.safe_load(f)
                        bufr.append(Codio(obj=codio))
                    else:
                        bufr.append(Image(obj=image))

                obj["children"] = not_images
                bufr.append(Paragraph(obj=obj))
            else:
                instance = RenderableFactory.create(obj["type"], obj)
                bufr.append(instance)

        dump_slide()

        return slides
