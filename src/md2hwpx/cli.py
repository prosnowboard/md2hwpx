"""Command-line interface for md2hwpx.

Usage::

    md2hwpx input.md                     # writes input.hwpx
    md2hwpx input.md -o output.hwpx      # explicit output path
    md2hwpx input.md --style academic     # use academic preset
    md2hwpx --list-styles                 # list available presets
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from md2hwpx import __version__
from md2hwpx.converter import Converter
from md2hwpx.style_manager import StyleManager


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md2hwpx",
        description="Convert Markdown files to HWPX (한글) format.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Path to the Markdown file to convert.",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output HWPX file path. Defaults to <input>.hwpx.",
    )
    parser.add_argument(
        "-s", "--style",
        default="default",
        choices=StyleManager.PRESETS,
        help="Style preset (default: %(default)s).",
    )
    parser.add_argument(
        "-e", "--encoding",
        default="utf-8",
        help="Input file encoding (default: %(default)s).",
    )
    parser.add_argument(
        "--list-styles",
        action="store_true",
        help="List available style presets and exit.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print progress information.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.list_styles:
        print("Available style presets:")
        for preset in StyleManager.PRESETS:
            print(f"  - {preset}")
        return 0

    if not args.input:
        parser.error("the following argument is required: input")

    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        return 1

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix(".hwpx")

    if args.verbose:
        print(f"Input:  {input_path}")
        print(f"Output: {output_path}")
        print(f"Style:  {args.style}")

    try:
        converter = Converter(style_preset=args.style)
        converter.convert_file(input_path, output_path, encoding=args.encoding)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.verbose:
        print(f"Done. {output_path.stat().st_size} bytes written.")
    else:
        print(f"Converted: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
