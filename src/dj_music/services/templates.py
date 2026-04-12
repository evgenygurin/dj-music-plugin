# Re-export shim: app.services.templates -> dj_music.templates
import importlib as _importlib
import sys as _sys

_real = _importlib.import_module("dj_music.templates")
_sys.modules[__name__] = _real
