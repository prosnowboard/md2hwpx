"""High-level Markdown-to-HWPX conversion orchestrator.

Ties together the parser, style manager, and renderer into a single
public API for converting Markdown text or files to HWPX output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from md2hwpx.parser import MarkdownParser
from md2hwpx.renderer import HwpxRenderer
from md2hwpx.style_manager import StyleManager


class Converter:
    """Convert Markdown content to HWPX format.

    Usage::

        converter = Converter(style_preset="default")
        converter.convert_file("input.md", "output.hwpx")

        # or from string
        hwpx_bytes = converter.convert_text("# Hello")
    """

    STYLE_PRESETS = StyleManager.PRESETS

    def __init__(self, style_preset: str = "default") -> None:
        self.style_manager = StyleManager(style_preset)
        self.parser = MarkdownParser()
        self.renderer = HwpxRenderer(self.style_manager)

    def convert_text(self, markdown_text: str) -> bytes:
        """Convert Markdown text to HWPX bytes.

        Args:
            markdown_text: Markdown source string.

        Returns:
            HWPX file content as bytes.
        """
        doc = self.parser.parse(markdown_text)
        return self.renderer.render(doc)

    def convert_file(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        encoding: str = "utf-8",
    ) -> None:
        """Read a Markdown file and write the HWPX output.

        Args:
            input_path: Path to the input ``.md`` file.
            output_path: Path for the output ``.hwpx`` file.
            encoding: Text encoding of the source file.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        md_text = input_path.read_text(encoding=encoding)
        hwpx_bytes = self.convert_text(md_text)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(hwpx_bytes)
