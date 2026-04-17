"""FastMCP resources for v2.

FileSystemProvider auto-discovers `@resource` decorators in submodules.
This package keeps the following guarantees:

1. All resource functions return ``str | bytes | ResourceResult`` (never dict/list).
2. JSON payloads are serialized with ``json.dumps`` and ``mime_type="application/json"``.
3. Every resource carries ``tags={...}`` + read-only annotations.
4. Tests in ``tests/v2/resources/`` verify URI template matching and payload shape.
"""
