"""app package — thin shim redirecting to dj_music.* for backward compatibility.

Installs a sys.meta_path finder so that *any* import of ``app.X.Y`` resolves to
the already-loaded ``dj_music.X.Y`` module (or loads it on demand), preventing
the same physical file from being executed twice under two different names.
"""

from __future__ import annotations

import contextlib
import importlib
import sys
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec
from types import ModuleType


class _AppToDjMusicFinder(MetaPathFinder):
    """Redirect ``app.<migrated>`` imports to ``dj_music.<migrated>``.

    Only redirects subpackages that have been migrated to src/dj_music/.
    app.schemas, app.db, app.ym, app.api, app.controllers, app.engines,
    app.bootstrap, and app.entities are NOT redirected — they remain in app/.
    """

    _PREFIX = "app."
    _TARGET = "dj_music."

    # Only these top-level subpackages are redirected
    _MIGRATED = frozenset(
        {
            "audio",
            "audit",
            "camelot",
            "core",
            "export",
            "optimization",
            "repositories",
            "services",
            "templates",
            "transition",
        }
    )

    def find_spec(self, fullname: str, path, target=None):  # type: ignore[override]
        if not fullname.startswith(self._PREFIX):
            return None
        # Never redirect app itself
        if fullname == "app":
            return None
        # Only redirect migrated subpackages
        rest = fullname[len(self._PREFIX) :]
        top = rest.split(".")[0]
        if top not in self._MIGRATED:
            return None
        dj_name = self._TARGET + fullname[len(self._PREFIX) :]
        # Load the dj_music module (no-op if already loaded)
        try:
            dj_mod = importlib.import_module(dj_name)
        except ImportError:
            return None
        # Register the alias so subsequent imports hit sys.modules cache
        sys.modules[fullname] = dj_mod
        # Also register as submodule of parent package
        parent, _, child = fullname.rpartition(".")
        if parent in sys.modules:
            with contextlib.suppress(AttributeError, TypeError):
                setattr(sys.modules[parent], child, dj_mod)
        return None  # Let normal machinery return the now-cached module


# Install once
_finder = _AppToDjMusicFinder()
if not any(isinstance(f, _AppToDjMusicFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _finder)
