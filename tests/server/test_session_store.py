"""InMemorySessionStore tests."""

from __future__ import annotations

from app.server.session_store import InMemorySessionStore


def test_get_empty_draft() -> None:
    store = InMemorySessionStore()
    draft = store.get_draft("s1")
    assert draft["tracks"] == []
    assert draft["template_name"] is None


def test_update_draft_then_get() -> None:
    store = InMemorySessionStore()
    store.update_draft("s1", tracks=[1, 2, 3], template_name="classic_60")
    draft = store.get_draft("s1")
    assert draft["tracks"] == [1, 2, 3]
    assert draft["template_name"] == "classic_60"


def test_sessions_are_isolated() -> None:
    store = InMemorySessionStore()
    store.update_draft("s1", tracks=[1])
    store.update_draft("s2", tracks=[9])
    assert store.get_draft("s1")["tracks"] == [1]
    assert store.get_draft("s2")["tracks"] == [9]


def test_tool_history_append_and_read() -> None:
    store = InMemorySessionStore()
    store.append_tool("s1", tool="entity_list", ok=True)
    store.append_tool("s1", tool="entity_get", ok=False)
    entries = store.get_tool_history("s1")
    assert len(entries) == 2
    assert entries[0]["tool"] == "entity_list"


def test_energy_sample_fifo() -> None:
    store = InMemorySessionStore(energy_capacity=3)
    for v in (-10.0, -9.5, -9.0, -8.5):
        store.append_energy("s1", v)
    samples = store.get_energy_samples("s1", last_n=5)
    assert samples == [-9.5, -9.0, -8.5]


def test_energy_last_n_slice() -> None:
    store = InMemorySessionStore(energy_capacity=100)
    for v in (-10.0, -9.0, -8.0, -7.0):
        store.append_energy("s1", v)
    assert store.get_energy_samples("s1", last_n=2) == [-8.0, -7.0]
