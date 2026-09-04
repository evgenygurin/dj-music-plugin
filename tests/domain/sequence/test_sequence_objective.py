from app.domain.sequence.objective import SequenceObjective


def test_sequence_objective_rewards_continuity_and_penalizes_repetition() -> None:
    objective = SequenceObjective()
    assert objective.edge_value(0.9, repeated=False) > objective.edge_value(0.9, repeated=True)
