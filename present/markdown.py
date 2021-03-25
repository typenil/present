# -*- coding: utf-8 -*-

import os

import yaml
import mistune

from .slide import (
    Slide,
    Paragraph,
    Image,
    Codio,
    RenderableFactory,
    SourceFile,
)


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

        bufr = []

        def dump_slide():
            nonlocal bufr, slides
            if not bufr:
                return

            slides.append(Slide(elements=bufr))
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

                        instance = (
                            SourceFile(obj=codio, dirname=self.dirname)
                            if codio.get("type") == "sourceFile"
                            else Codio(obj=codio)
                        )
                        bufr.append(instance)
                    else:
                        bufr.append(Image(obj=image))

                obj["children"] = not_images
                bufr.append(Paragraph(obj=obj))
            else:
                instance = RenderableFactory.create(obj["type"], obj)
                bufr.append(instance)

        dump_slide()

        return slides
