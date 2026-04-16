"""Tests for :mod:`app.core.logging_config`."""

from __future__ import annotations

import logging

import pytest

from app.config import Settings


def test_configure_logging_writes_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """With ``DJ_LOG_FILE`` set, log lines are duplicated to that file."""
    log_file = tmp_path / "out.log"
    monkeypatch.setenv("DJ_LOG_FILE", str(log_file))
    monkeypatch.setenv("DJ_LOG_FORMAT", "text")

    import app.core.logging_config as logging_config

    monkeypatch.setattr(logging_config, "settings", Settings())
    logging_config.configure_logging(force=True)

    logging.getLogger("test.file").info("hello file sink")

    text = log_file.read_text(encoding="utf-8")
    assert "hello file sink" in text
    assert "test.file" in text
