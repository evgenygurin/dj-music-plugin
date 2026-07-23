from __future__ import annotations

import pytest

from app.tools.render.echo_builder import echo_builder
from app.tools.render.filter_sweep_builder import filter_sweep_builder
from app.tools.render.reverb_builder import reverb_builder


@pytest.mark.asyncio
async def test_echo_builder_preserves_zero_custom_values() -> None:
    result = await echo_builder(
        delay_ms=250.0,
        decay=0.0,
        taps=1,
        wet_dry=0.0,
        stereo_spread=0.0,
    )

    assert result.decay == 0.0
    assert result.wet_dry_ratio == 0.0
    assert result.stereo_spread == 0.0


@pytest.mark.asyncio
async def test_reverb_builder_preserves_zero_custom_values() -> None:
    result = await reverb_builder(decay_s=0.1, pre_delay_ms=0.0, mix_ratio=0.0)

    assert result.pre_delay_ms == 0.0
    assert result.mix_ratio == 0.0


@pytest.mark.asyncio
async def test_filter_sweep_open_direction_returns_highpass_expr() -> None:
    result = await filter_sweep_builder(
        start_freq_hz=200.0,
        end_freq_hz=12000.0,
        direction="open",
    )

    assert result.outgoing is not None
    assert result.outgoing.direction == "open"
    assert result.outgoing.ffmpeg_expr.startswith("highpass=")


@pytest.mark.asyncio
async def test_filter_sweep_preset_incoming_open_uses_highpass_expr() -> None:
    result = await filter_sweep_builder(preset="classic_lowpass")

    assert result.incoming is not None
    assert result.incoming.direction == "open"
    assert result.incoming.ffmpeg_expr.startswith("highpass=")
