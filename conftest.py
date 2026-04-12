"""Root conftest — ensure app→dj_music import redirect is installed early.

Must be loaded before any test module so that the meta path finder is in place
before any ``app.audio.*`` / ``app.core.*`` etc. imports happen in workers.
"""


def pytest_configure(config) -> None:  # type: ignore[no-untyped-def]
    """Alias migrated app.* subpackages to dj_music.* before collection.

    Runs in both the main process and every xdist worker process (pytest
    calls pytest_configure in workers too before any test modules are imported).
    """
    import importlib
    import sys

    _MIGRATED = [
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
    ]

    def _alias(app_name: str, dj_name: str) -> None:
        if app_name in sys.modules:
            return
        try:
            mod = importlib.import_module(dj_name)
        except ImportError:
            return
        sys.modules[app_name] = mod

    # Pre-register top-level packages first
    for sub in _MIGRATED:
        _alias(f"app.{sub}", f"dj_music.{sub}")

    # Eagerly register all already-loaded dj_music submodules as app.* aliases
    for key in list(sys.modules):
        if key.startswith("dj_music."):
            app_key = "app." + key[len("dj_music.") :]
            rest = key[len("dj_music.") :]
            top = rest.split(".")[0] if rest else ""
            if top in _MIGRATED:
                sys.modules.setdefault(app_key, sys.modules[key])
