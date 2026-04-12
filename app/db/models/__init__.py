# Compatibility shim: redirect all app.db.models.X imports to dj_music.models.X
import sys as _sys
import importlib as _importlib
from importlib.abc import MetaPathFinder as _Finder, Loader as _Loader
from importlib.machinery import ModuleSpec as _Spec


class _AliasLoader(_Loader):
    def __init__(self, canonical: str) -> None:
        self._canonical = canonical

    def create_module(self, spec):  # type: ignore[override]
        real = _importlib.import_module(self._canonical)
        _sys.modules[spec.name] = real
        return real

    def exec_module(self, module):  # type: ignore[override]
        pass  # already loaded


class _AliasFinder(_Finder):
    _PREFIX = "app.db.models."

    def find_spec(self, fullname, path, target=None):  # type: ignore[override]
        if not fullname.startswith(self._PREFIX):
            return None
        canonical = "dj_music.models." + fullname[len(self._PREFIX):]
        return _Spec(fullname, _AliasLoader(canonical), origin="alias")


if not any(isinstance(f, _AliasFinder) for f in _sys.meta_path):
    _sys.meta_path.insert(0, _AliasFinder())

# Also alias the package itself
_canonical_name = "dj_music.models"
if _canonical_name not in _sys.modules:
    _importlib.import_module(_canonical_name)
_sys.modules[__name__] = _sys.modules[_canonical_name]
