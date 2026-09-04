from app.domain.mixing.execution import ExecutionIdentity


def test_execution_identity_changes_when_any_version_invalidator_changes() -> None:
    base = ExecutionIdentity(
        "source", "config", "engine", "analysis", "model", "dsp", "renderer", 7
    )
    changed = ExecutionIdentity(
        "source", "config", "engine", "analysis-v2", "model", "dsp", "renderer", 7
    )
    assert base.hash != changed.hash
    assert (
        base.hash
        == ExecutionIdentity(
            "source", "config", "engine", "analysis", "model", "dsp", "renderer", 7
        ).hash
    )
