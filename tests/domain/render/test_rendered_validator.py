from app.domain.render.rendered_validator import AudioMetrics, RenderedAudioValidator


def test_rendered_validator_rejects_clipping_and_nonfinite_metrics() -> None:
    result = RenderedAudioValidator().validate(
        AudioMetrics(
            duration_s=10,
            channels=2,
            sample_rate=44100,
            peak_db=1.0,
            loudness_lufs=-10,
            finite=False,
        )
    )
    assert not result.accepted
    assert "finite" in result.reasons


def test_rendered_validator_accepts_safe_metrics() -> None:
    metrics = AudioMetrics(10, 2, 44100, -1.0, -14.0, True)
    assert RenderedAudioValidator().validate(metrics).accepted
