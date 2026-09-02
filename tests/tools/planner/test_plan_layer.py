import pytest

from app.tools.planner.plan_layer import plan_layer


def test_plan_layer_one_low_invariant() -> None:
    for n in [2, 4, 6, 12]:
        res = plan_layer(n_decks=n, roles=None)
        assert len(res.decks) == n
        assert sum(1 for d in res.decks if d.owns_low) == 1
        assert res.invariant == "one LOW"

    # N=2 -> [FOUNDATION, INCOMING]
    assert [d.role for d in plan_layer(n_decks=2, roles=None).decks] == ["FOUNDATION", "INCOMING"]


def test_plan_layer_custom_roles() -> None:
    from app.schemas.planner import Role

    custom_roles = [Role.FOUNDATION, Role.INCOMING, Role.PERCUSSION]
    res = plan_layer(n_decks=3, roles=custom_roles)
    assert len(res.decks) == 3
    assert [d.role for d in res.decks] == ["FOUNDATION", "INCOMING", "PERCUSSION"]


def test_plan_layer_invalid_n_decks() -> None:
    with pytest.raises(ValueError):
        plan_layer(n_decks=1, roles=None)
    with pytest.raises(ValueError):
        plan_layer(n_decks=13, roles=None)


def test_plan_layer_invalid_role() -> None:
    from app.schemas.planner import Role

    # No LOW role
    with pytest.raises(ValueError):
        plan_layer(n_decks=2, roles=[Role.TEXTURE, Role.VOICE])
    # Too few roles
    with pytest.raises(ValueError):
        plan_layer(n_decks=3, roles=[Role.FOUNDATION, Role.INCOMING])
    # Too many roles
    with pytest.raises(ValueError):
        plan_layer(n_decks=2, roles=[Role.FOUNDATION, Role.INCOMING, Role.PERCUSSION])


def test_plan_layer_invariant_check() -> None:
    for n in [2, 4, 6, 12]:
        res = plan_layer(n_decks=n, roles=None)
        assert res.invariant == "one LOW"
        assert sum(1 for d in res.decks if d.owns_low) == 1
