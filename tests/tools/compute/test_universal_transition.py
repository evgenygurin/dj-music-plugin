from app.tools.compute import universal_transition


def test_validate_transition_delegates_to_application_use_case(monkeypatch) -> None:
    calls = []

    class StubValidation:
        def validate(self, source_bpm, target_bpm, duration_s):
            calls.append((source_bpm, target_bpm, duration_s))
            return type(
                "Result",
                (),
                {
                    "accepted": True,
                    "reason": None,
                    "drift_beats": 0.1,
                    "drift_ms": 10.0,
                    "candidate_id": "stable-id",
                },
            )()

    monkeypatch.setattr(universal_transition, "TransitionValidation", StubValidation)

    result = universal_transition.validate_transition_request(128, 128.1, 16)

    assert calls == [(128, 128.1, 16)]
    assert result["candidate_id"] == "stable-id"
    assert result["accepted"] is True
