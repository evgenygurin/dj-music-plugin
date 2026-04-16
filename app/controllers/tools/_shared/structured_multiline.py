"""Helpers for structured MCP output that contains large multiline text.

Some clients render ``structuredContent`` as JSON literals; string fields then show
``\\n`` instead of line breaks. Pairing ``full_text`` with ``lines: list[str]`` keeps
both copy/paste and tree-style UIs usable.
"""


def split_multiline_for_json_ui(text: str) -> tuple[str, list[str]]:
    """Return the original text and the same content split for line-oriented display."""
    return text, text.splitlines()
