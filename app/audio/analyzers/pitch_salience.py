# Re-export shim for backward compatibility
import importlib as _importlib
import sys as _sys

_real = _importlib.import_module("dj_music.audio.analyzers.pitch_salience")
_sys.modules[__name__] = _real
