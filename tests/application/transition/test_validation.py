from app.application.transition.validation import TransitionValidation


def test_validation_use_case_returns_stable_technical_result() -> None:
    result = TransitionValidation().validate(128, 128.01, 30)

    assert result.accepted
    assert result.candidate_id
    assert result.drift_beats >= 0


def test_validation_use_case_rejects_excessive_tempo_ratio() -> None:
    result = TransitionValidation().validate(100, 130, 30)

    assert not result.accepted
    assert result.reason == "tempo_ratio"
