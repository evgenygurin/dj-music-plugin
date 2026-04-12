# Re-export shim for backward compatibility
import importlib as _importlib
import sys as _sys

_real = _importlib.import_module("dj_music.services.set.builder")
_sys.modules[__name__] = _real
