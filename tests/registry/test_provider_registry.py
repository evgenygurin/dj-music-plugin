"""ProviderRegistry + Provider protocol tests."""

import pytest

from app.registry.provider import Provider, ProviderRegistry
from app.shared.errors import NotFoundError


class _FakeProvider:
    """Minimal Provider implementation for tests."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.closed = False

    async def read(self, entity: str, id: str | None, params: dict) -> dict:  # type: ignore[type-arg]
        return {"provider": self.name, "entity": entity, "id": id}

    async def write(self, entity: str, operation: str, params: dict) -> dict:  # type: ignore[type-arg]
        return {"provider": self.name, "op": operation}

    async def search(self, query: str, type: str, limit: int) -> dict:  # type: ignore[type-arg]
        return {"query": query, "type": type, "limit": limit}

    async def download_audio(self, track_id: str):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    async def close(self) -> None:
        self.closed = True


def test_protocol_runtime_check() -> None:
    """Any class matching the shape is a Provider."""
    p = _FakeProvider("yandex")
    assert isinstance(p, Provider)


def test_register_and_get() -> None:
    reg = ProviderRegistry()
    p = _FakeProvider("yandex")
    reg.register(p)
    assert reg.get("yandex") is p


def test_get_unknown_raises() -> None:
    reg = ProviderRegistry()
    with pytest.raises(NotFoundError):
        reg.get("spotify")


def test_default_follows_first_registered_when_flagged() -> None:
    reg = ProviderRegistry()
    p1 = _FakeProvider("yandex")
    p2 = _FakeProvider("spotify")
    reg.register(p1, default=True)
    reg.register(p2)
    assert reg.default() is p1


def test_default_raises_when_none_set() -> None:
    reg = ProviderRegistry()
    with pytest.raises(NotFoundError) as exc_info:
        reg.default()
    assert "default" in str(exc_info.value).lower()


def test_names_sorted() -> None:
    reg = ProviderRegistry()
    reg.register(_FakeProvider("zeta"))
    reg.register(_FakeProvider("alpha"))
    assert reg.names() == ["alpha", "zeta"]


def test_register_duplicate_raises() -> None:
    reg = ProviderRegistry()
    reg.register(_FakeProvider("yandex"))
    with pytest.raises(ValueError):
        reg.register(_FakeProvider("yandex"))


def test_contains_membership() -> None:
    reg = ProviderRegistry()
    reg.register(_FakeProvider("yandex"))
    assert "yandex" in reg
    assert "spotify" not in reg


@pytest.mark.asyncio
async def test_close_all_closes_each() -> None:
    reg = ProviderRegistry()
    p1 = _FakeProvider("yandex")
    p2 = _FakeProvider("spotify")
    reg.register(p1)
    reg.register(p2)
    await reg.close_all()
    assert p1.closed is True
    assert p2.closed is True
    assert reg.names() == []
