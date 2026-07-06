from app.server.transforms import ALWAYS_VISIBLE_TOOLS


def test_render_tools_always_visible():
    for name in ("render_beatgrid", "render_mixdown", "render_diagnose"):
        assert name in ALWAYS_VISIBLE_TOOLS
