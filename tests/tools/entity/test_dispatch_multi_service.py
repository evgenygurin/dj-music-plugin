"""call_handler injects a secondary service to handlers that ask for two."""

from __future__ import annotations

from app.tools.entity._dispatch import call_handler

_SENTINEL = {"registry": "REG", "pipeline": "PIPE", "scorer": "SCORE"}


async def _run(handler: object) -> object:
    return await call_handler(
        handler,  # type: ignore[arg-type]
        ctx=None,
        uow=None,
        data={},
        registry=_SENTINEL["registry"],
        pipeline=_SENTINEL["pipeline"],
        scorer=_SENTINEL["scorer"],
    )


async def test_single_service_handler_unchanged() -> None:
    async def handler(ctx, uow, data, pipeline):
        return pipeline

    assert await _run(handler) == "PIPE"


async def test_handler_gets_pipeline_and_registry() -> None:
    async def handler(ctx, uow, data, pipeline, registry=None):
        return (pipeline, registry)

    assert await _run(handler) == ("PIPE", "REG")


async def test_three_arg_handler_called_without_service() -> None:
    async def handler(ctx, uow, data):
        return "ok"

    assert await _run(handler) == "ok"


async def test_unknown_fourth_param_falls_back_to_registry() -> None:
    async def handler(ctx, uow, data, whatever):
        return whatever

    assert await _run(handler) == "REG"
