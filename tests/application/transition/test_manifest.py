from app.application.transition.manifest import ExecutionManifest


def test_manifest_is_canonical_and_reproducible() -> None:
    manifest = ExecutionManifest(
        "source", "config", "engine", "analysis", "model", "dsp", "renderer", 42
    )
    assert (
        manifest.canonical_json()
        == ExecutionManifest(
            "source", "config", "engine", "analysis", "model", "dsp", "renderer", 42
        ).canonical_json()
    )
