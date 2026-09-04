from app.application.transition.cache import InMemoryTransitionCache
from app.application.transition.manifest import ExecutionManifest
from app.domain.mixing.execution import ExecutionIdentity


def test_execution_identity_changes_with_config() -> None:
    base = dict(
        source_hash="s",
        engine_version="e",
        analysis_version="a",
        model_version="m",
        dsp_version="d",
        renderer_version="r",
        seed=1,
    )
    assert (
        ExecutionIdentity(config_hash="one", **base).hash
        != ExecutionIdentity(config_hash="two", **base).hash
    )


def test_cache_is_bounded() -> None:
    assert InMemoryTransitionCache(1)._max_entries == 1


def test_manifest_is_canonical() -> None:
    manifest = ExecutionManifest("s", "c", "e", "a", "m", "d", "r", 1)
    assert manifest.canonical_json().startswith('{"analysis_version"')
