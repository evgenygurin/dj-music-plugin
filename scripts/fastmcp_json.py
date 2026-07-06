"""Extract machine payloads from ``fastmcp call --json`` output.

FastMCP CLI shapes differ by target type:

* tool calls return a JSON object, usually with ``structured_content``;
* resource reads return a JSON list of content blocks with JSON in ``text``.

Use this helper in smoke scripts and shell one-liners instead of assuming the
top-level value is always a dict.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any


def _maybe_decode_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def extract_payload(value: Any) -> Any:
    """Return the useful payload from FastMCP CLI JSON output."""

    if isinstance(value, dict):
        if "structured_content" in value:
            return value["structured_content"]
        content = value.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and "text" in first:
                return _maybe_decode_text(first["text"])
        return value

    if isinstance(value, list):
        if not value:
            return []
        if len(value) == 1 and isinstance(value[0], dict) and "text" in value[0]:
            return _maybe_decode_text(value[0]["text"])
        return value

    return value


def _read_input(path: str | None) -> str:
    if path is None or path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract payload from `fastmcp call --json` output."
    )
    parser.add_argument("path", nargs="?", default="-", help="JSON file path, or stdin.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON payload.")
    args = parser.parse_args(argv)

    payload = extract_payload(json.loads(_read_input(args.path)))
    indent = 2 if args.pretty else None
    print(json.dumps(payload, ensure_ascii=False, indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
