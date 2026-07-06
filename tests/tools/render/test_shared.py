from app.tools.render._shared import render_timestamp, render_workspace


def test_workspace_path_by_version(tmp_path, monkeypatch):
    monkeypatch.setenv("DJ_DELIVERY_OUTPUT_DIR", str(tmp_path))
    from app.config import reset_settings_cache

    reset_settings_cache()
    ws = render_workspace(131)
    assert ws.endswith("render/v131")


def test_timestamp_is_sortable_string():
    ts = render_timestamp()
    assert len(ts) == 15 and ts[8] == "-"  # YYYYMMDD-HHMMSS
