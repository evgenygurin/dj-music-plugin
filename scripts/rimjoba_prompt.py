#!/usr/bin/env python3
"""Print RimJoba Suno Custom Mode prompt blocks.

Usage:
  uv run python scripts/rimjoba_prompt.py street_trap
  uv run python scripts/rimjoba_prompt.py phonk --extra-negative "bright EDM festival drop"
  uv run python scripts/rimjoba_prompt.py --list
"""

from __future__ import annotations

import argparse
import sys

from app.domain.suno_voice.rimjoba import (
    REFERENCE_URL,
    UnknownRimJobaModeError,
    assemble_rimjoba_style,
    list_modes,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assemble RimJoba Suno voice prompt")
    parser.add_argument(
        "mode",
        nargs="?",
        help="Genre mode (street_trap, techno_rap, boom_bap, phonk, club, late_night)",
    )
    parser.add_argument("--list", action="store_true", help="List modes and exit")
    parser.add_argument(
        "--extra-negative",
        default="",
        help="Optional genre-neg append",
    )
    parser.add_argument(
        "--title",
        default="",
        help="Track name without prefix; prints full title RimJoba — <name>",
    )
    args = parser.parse_args(argv)

    if args.list:
        for mode in list_modes():
            print(mode)
        return 0

    if not args.mode:
        parser.error("mode required (or pass --list)")

    try:
        prompt = assemble_rimjoba_style(args.mode, extra_negative=args.extra_negative)
    except UnknownRimJobaModeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    title = (
        f"{prompt.title_prefix} — {args.title}"
        if args.title.strip()
        else f"{prompt.title_prefix} — <name>"
    )
    print(f"REFERENCE: {REFERENCE_URL}")
    print(f"MODE: {prompt.mode}")
    print(f"TITLE: {title}")
    print("STYLE:")
    print(prompt.style)
    print("NEGATIVE:")
    print(prompt.negative_tags)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
