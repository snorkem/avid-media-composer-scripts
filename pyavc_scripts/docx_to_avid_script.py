#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
#
# docx_to_avid_script.py - batch-convert DOCX transcripts to Avid script files.
# Copyright (C) 2026 snorkem (https://github.com/snorkem/avid-media-composer-scripts)
#
# The .avc files are written by pyavc, by Lawson Tanner:
#     https://github.com/lawson-tanner/pyavc
#     Licensed under the GNU General Public License v3.0.
# pyavc is used as an unmodified library and is not bundled with this script.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details. You should have received a copy of the GNU General Public License
# along with this program (see LICENSE in this folder). If not, see
# <https://www.gnu.org/licenses/>.
"""Convert a folder of DOCX transcripts into Avid Media Composer script files (.avc).

Text is read from each DOCX (paragraphs and tables, in document order),
optionally cleaned to plain ASCII punctuation, and handed to pyavc, which
writes the .avc file. Output goes to a subfolder of the input folder unless
--output is given.

Script file generation is provided by pyavc (c) Lawson Tanner,
https://github.com/lawson-tanner/pyavc, GPL-3.0.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import logging
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    from avc.file import AVCFile
    from docx import Document
    from docx.opc.exceptions import PackageNotFoundError
    from docx.table import Table
except ImportError as exc:  # pragma: no cover - environment problem
    requirements = Path(__file__).with_name("requirements.txt")
    sys.exit(f"Missing package '{exc.name}'. Install the requirements with:\n"
             f"    pip install -r \"{requirements}\"")

__version__ = "1.0.0"

PYAVC_CREDIT = ("Avid script files are generated with pyavc by Lawson Tanner "
                "(https://github.com/lawson-tanner/pyavc), licensed under GPL-3.0.")

DEFAULT_SUBFOLDER = "avid_scripts"
# pyavc cuts output file names to 56 characters (before the extension).
AVC_NAME_LIMIT = 56

# Typographic characters that Word inserts automatically, mapped to plain
# ASCII so the script reads the same in every Avid version and font.
ASCII_REPLACEMENTS = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
    "–": "-", "−": "-", "—": "--", "―": "--",
    "…": "...",
    " ": " ", " ": " ", " ": " ", " ": " ",
    "​": "", "‌": "", "‍": "", "­": "", "﻿": "",
    " ": "\n", " ": "\n",
})

logger = logging.getLogger("docx_to_avid_script")


@dataclass
class ScriptFormat:
    """Display settings for the .avc file. Names match pyavc's AVCFile arguments."""
    text_width: int = 80
    font_size: int = 12
    font_name: str = "Open Sans"
    white_bg: bool = False
    show_row_colors: bool = True
    left_margin: int = 40
    text_width_px: int = 512
    show_frames: bool = True
    interpolate_position: bool = False
    show_all_takes: bool = True
    show_line_numbers: bool = True
    word_wrap: bool = True
    hold_slates_onscreen: bool = False
    take_color: int = 1


class EmptyTranscriptError(Exception):
    """Raised when a DOCX file contains no text."""


# ---------------------------------------------------------------------------
# DOCX reading
# ---------------------------------------------------------------------------

def table_lines(table: Table) -> list[str]:
    """Return one line per table row, with the cell texts separated by spaces."""
    lines = []
    for row in table.rows:
        texts = []
        previous_tc = None
        for cell in row.cells:
            # A horizontally merged cell is returned once per grid column.
            if cell._tc is previous_tc:
                continue
            previous_tc = cell._tc
            text = " ".join(cell.text.split())
            if text:
                texts.append(text)
        lines.append(" ".join(texts))
    return lines


def extract_lines(docx_path: Path, include_tables: bool = True) -> list[str]:
    """Read the body text of a DOCX file, keeping paragraph and table order."""
    try:
        document = Document(str(docx_path))
    except PackageNotFoundError:
        raise ValueError("not a valid .docx file (it may be damaged, or an older "
                         ".doc file renamed to .docx)") from None
    lines: list[str] = []
    for block in document.iter_inner_content():
        if isinstance(block, Table):
            if include_tables:
                lines.extend(table_lines(block))
        else:
            # Soft line breaks inside a paragraph come back as "\n".
            lines.extend(block.text.split("\n"))
    return lines


def clean_lines(lines: list[str], ascii_punctuation: bool = True) -> list[str]:
    """Optionally straighten punctuation, then trim blank lines at both ends."""
    if ascii_punctuation:
        lines = "\n".join(lines).translate(ASCII_REPLACEMENTS).split("\n")
    lines = [line.rstrip() for line in lines]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def output_base_name(docx_path: Path) -> str:
    """The output file name without extension, as pyavc would shorten it."""
    return docx_path.stem.rstrip()[:AVC_NAME_LIMIT]


def numbered_path(directory: Path, base_name: str) -> Path:
    """Return the first free '<name>(n).avc' path, using pyavc's naming style."""
    count = 1
    while True:
        suffix = f"({count})"
        candidate = directory / f"{base_name[:AVC_NAME_LIMIT - len(suffix)]}{suffix}.avc"
        if not candidate.exists():
            return candidate
        count += 1


def convert_transcript(docx_path: Path, target_dir: Path, script_format: ScriptFormat,
                       if_exists: str = "skip", ascii_punctuation: bool = True,
                       include_tables: bool = True) -> Path | None:
    """Convert one DOCX file to an .avc file in target_dir.

    Returns the path written, or None if the file was skipped because the
    output already exists.
    """
    base_name = output_base_name(docx_path)
    target = target_dir / f"{base_name}.avc"
    if target.exists():
        if if_exists == "skip":
            return None
        if if_exists == "rename":
            target = numbered_path(target_dir, base_name)

    lines = clean_lines(extract_lines(docx_path, include_tables), ascii_punctuation)
    if not any(line.strip() for line in lines):
        raise EmptyTranscriptError("no text found")

    target_dir.mkdir(parents=True, exist_ok=True)
    # Build in a temporary folder next to the target, then move into place, so a
    # failed conversion never leaves a partial file or destroys an existing one.
    with tempfile.TemporaryDirectory(dir=target_dir, prefix=".avc_tmp_") as tmp:
        tmp_dir = Path(tmp)
        source_txt = tmp_dir / "transcript.txt"
        source_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
        avc_file = AVCFile(str(source_txt), str(tmp_dir), base_name, **asdict(script_format))
        with contextlib.redirect_stdout(io.StringIO()):  # pyavc prints on success
            created = Path(avc_file.create())
        created.replace(target)
    return target


def find_transcripts(input_dir: Path, output_dir: Path, recursive: bool) -> list[Path]:
    """List the DOCX files to convert, ignoring Word lock files and the output folder."""
    candidates = input_dir.rglob("*") if recursive else input_dir.iterdir()
    transcripts = []
    for path in candidates:
        if not path.is_file() or path.suffix.lower() != ".docx":
            continue
        if path.name.startswith(("~$", "._")):
            continue
        if path.is_relative_to(output_dir):
            continue
        transcripts.append(path)
    return sorted(transcripts)


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def int_range(minimum: int, maximum: int):
    """argparse type: a whole number between minimum and maximum."""
    def parse(value: str) -> int:
        try:
            number = int(value)
        except ValueError:
            raise argparse.ArgumentTypeError(f"'{value}' is not a whole number") from None
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(f"must be between {minimum} and {maximum}")
        return number
    return parse


def ascii_text(value: str) -> str:
    """argparse type: a non-empty ASCII string (pyavc stores the font name as ASCII)."""
    value = value.strip()
    if not value or not value.isascii():
        raise argparse.ArgumentTypeError("font name must be non-empty plain ASCII text")
    return value


def build_parser() -> argparse.ArgumentParser:
    defaults = ScriptFormat()
    parser = argparse.ArgumentParser(
        description="Convert a folder of DOCX transcripts to Avid Media Composer "
                    "script files (.avc).",
        epilog=PYAVC_CREDIT,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input_dir", type=Path, help="Folder containing .docx transcripts")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Output folder (default: a subfolder named "
                             f"'{DEFAULT_SUBFOLDER}' inside the input folder)")
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="Also convert transcripts in subfolders, keeping the folder structure")
    parser.add_argument("--if-exists", choices=("skip", "overwrite", "rename"), default="skip",
                        help="What to do when an .avc file with the same name exists. "
                             "'rename' adds a number, e.g. 'Interview(1).avc'")
    parser.add_argument("--keep-unicode", action="store_true",
                        help="Keep curly quotes, dashes, ellipses and special spaces "
                             "instead of converting them to plain ASCII")
    parser.add_argument("--no-tables", action="store_true",
                        help="Ignore text inside Word tables")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed logging")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    fmt = parser.add_argument_group(
        "script formatting",
        "These match the options in Media Composer's Script settings and can be "
        "changed later in Avid.")
    bool_flag = argparse.BooleanOptionalAction
    fmt.add_argument("-t", "--text-width", type=int_range(10, 1000), default=defaults.text_width,
                     help="Maximum characters per line before a line break is inserted")
    fmt.add_argument("-f", "--font-size", type=int_range(1, 255), default=defaults.font_size,
                     help="Font size in pixels")
    fmt.add_argument("--font", dest="font_name", type=ascii_text, default=defaults.font_name,
                     help="Font name. Avid uses its default font if this one isn't installed")
    fmt.add_argument("--white-bg", action=bool_flag, default=defaults.white_bg,
                     help="White script background (turns off row colors). Otherwise "
                          "Avid's interface setting is used")
    fmt.add_argument("--row-colors", dest="show_row_colors", action=bool_flag,
                     default=defaults.show_row_colors, help="Alternate row colors")
    fmt.add_argument("--left-margin", type=int_range(0, 5000), default=defaults.left_margin,
                     help="Left margin in pixels")
    fmt.add_argument("--text-width-px", type=int_range(128, 5120),
                     default=defaults.text_width_px,
                     help="Width of the text area in pixels (display only)")
    fmt.add_argument("--frames", dest="show_frames", action=bool_flag,
                     default=defaults.show_frames, help="Show a frame thumbnail on each slate")
    fmt.add_argument("--interpolate-position", action=bool_flag,
                     default=defaults.interpolate_position,
                     help="Allow manual sync marks (Interpolate Position)")
    fmt.add_argument("--all-takes", dest="show_all_takes", action=bool_flag,
                     default=defaults.show_all_takes,
                     help="Show all takes; --no-all-takes shows only the primary take")
    fmt.add_argument("--line-numbers", dest="show_line_numbers", action=bool_flag,
                     default=defaults.show_line_numbers, help="Show line numbers")
    fmt.add_argument("--word-wrap", action=bool_flag, default=defaults.word_wrap,
                     help="Wrap long lines on screen")
    fmt.add_argument("--hold-slates", dest="hold_slates_onscreen", action=bool_flag,
                     default=defaults.hold_slates_onscreen,
                     help="Keep slate information in the record monitor until the next slate")
    fmt.add_argument("--take-color", type=int_range(1, 22), default=defaults.take_color,
                     help="Take highlight color, 1-22 (see the pyavc README for the palette)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s: %(message)s")

    input_dir = args.input_dir.expanduser().resolve()
    if not input_dir.is_dir():
        parser.error(f"input folder not found: {input_dir}")
    output_dir = (args.output.expanduser() if args.output else input_dir / DEFAULT_SUBFOLDER).resolve()
    if output_dir.exists() and not output_dir.is_dir():
        parser.error(f"output path is not a folder: {output_dir}")

    script_format = ScriptFormat(**{name: getattr(args, name) for name in asdict(ScriptFormat())})

    transcripts = find_transcripts(input_dir, output_dir, args.recursive)
    if not transcripts:
        logger.error("No .docx files found in %s%s", input_dir,
                     "" if args.recursive else " (use -r to search subfolders)")
        return 1

    logger.info("Converting %d transcript(s) to %s", len(transcripts), output_dir)
    logger.debug(PYAVC_CREDIT)
    converted = skipped = failed = 0
    for docx_path in transcripts:
        relative = docx_path.relative_to(input_dir)
        target_dir = output_dir / relative.parent
        try:
            result = convert_transcript(
                docx_path, target_dir, script_format,
                if_exists=args.if_exists,
                ascii_punctuation=not args.keep_unicode,
                include_tables=not args.no_tables,
            )
        except EmptyTranscriptError:
            skipped += 1
            logger.warning("Skipped %s (no text found)", relative)
            continue
        except Exception as exc:  # report and continue with the next file
            failed += 1
            logger.error("%s: %s", relative, exc)
            logger.debug("Traceback:", exc_info=True)
            continue
        if result is None:
            skipped += 1
            logger.info("Skipped %s (output exists; use --if-exists overwrite or rename)", relative)
        else:
            converted += 1
            logger.info("Converted %s -> %s", relative, result.relative_to(output_dir))

    logger.info("Done: %d converted, %d skipped, %d failed", converted, skipped, failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
