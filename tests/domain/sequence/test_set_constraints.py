from app.domain.sequence.constraints import SetConstraints


def test_set_constraints_reject_excluded_and_repeated_tracks() -> None:
    constraints = SetConstraints(excluded_tracks=frozenset({"x"}), max_tracks=3)
    assert constraints.accepts("a", ("a",)) is False
    assert constraints.accepts("x", ("a",)) is False
    assert constraints.accepts("b", ("a",)) is True
