# Re-export shim for backward compatibility
import importlib as _importlib
import sys as _sys

_real = _importlib.import_module("dj_music.audio.analyzers.key")
_sys.modules[__name__] = _real
