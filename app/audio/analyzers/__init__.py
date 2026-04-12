# Re-export shim for backward compatibility
import importlib as _importlib
import sys as _sys

_real = _importlib.import_module("dj_music.audio.analyzers")
_sys.modules[__name__] = _real
# Ensure submodule aliases are registered so re-imports hit the same object
_sys.modules[__name__ + ".base"] = _importlib.import_module("dj_music.audio.analyzers.base")
