from app.domain.render.manifest import RenderManifest


def test_render_manifest_is_deterministic() -> None:
    manifest = RenderManifest("plan", "config", "source", "renderer", "dsp", "model")
    assert manifest.canonical_json() == manifest.canonical_json()
