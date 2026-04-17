---
description: General Python gotchas not tied to a specific domain
globs: "**/*.py"
---

# General Python Gotchas

## `from __future__ import annotations`

Makes all annotations strings at runtime. If a function needs the actual type at runtime (e.g., `TrackFeatures()` as a default), import the type normally — don't rely on the string annotation.

## Circular imports

repos→services circular imports: use `TYPE_CHECKING` guard + lazy import inside the method body:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.handlers.track import TrackService

class TrackRepo:
    def method(self) -> None:
        from app.handlers.track import TrackService  # lazy
        ...
```

## Ruff removes unused imports

Ruff auto-removes imports that aren't used yet. When adding an import + its usage, do both in a single edit — don't add the import first and the usage later.
