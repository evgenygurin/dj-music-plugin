"""16 middleware classes — one per file, single responsibility.

Order in ALL_MIDDLEWARE is outer→inner, matches blueprint §11. First added
wraps all others. DO NOT reorder without changing the spec.
"""

from __future__ import annotations

# Populated in Task 24; imports added after every middleware file exists.
ALL_MIDDLEWARE: list[type] = []  # see register_middleware() in app.py
