from app.tools.compute.universal_transition import validate_transition_request


def test_universal_transition_tool_exposes_hard_validation() -> None:
    result = validate_transition_request(128, 128.2, 400)
    assert result["accepted"] is False
    assert result["reason"] == "tempo_drift"
