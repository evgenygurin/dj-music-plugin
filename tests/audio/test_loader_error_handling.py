"""Decode failures must surface clearly, not get swallowed.

Old loader chained ``except Exception: pass`` over soundfile and
librosa, then fell through to ``wave.open`` (WAV-only). A corrupt MP3
crashed with a cryptic ``wave.Error: file does not start with RIFF id``
instead of the actual codec error — hiding numpy/numba ABI mismatches
and missing libsndfile.

The fix narrows the catch to:
  * ``ImportError`` — soundfile/librosa not installed (legitimate
    fallback case)
  * ``soundfile.LibsndfileError`` /
    ``librosa.util.exceptions.ParameterError`` — known decode errors
    that we wrap into a clear ``RuntimeError("audio decode failed: …")``
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.audio.core.loader import AudioLoader


@pytest.mark.asyncio
async def test_text_file_with_mp3_extension_raises_clear_error(tmp_path: Path) -> None:
    """Garbage-in must yield a clear, named error, not a cryptic
    fall-through to ``wave.Error``.
    """
    fake = tmp_path / "not_audio.mp3"
    fake.write_text("this is plain text, definitely not an MP3")

    loader = AudioLoader(target_sr=22050)

    # We accept either RuntimeError("audio decode failed: …") (preferred)
    # or the actual library-specific exception bubbling up — anything but
    # the silent-swallow path that produced ``wave.Error: file does not
    # start with RIFF id``.
    with pytest.raises((RuntimeError, Exception)) as exc_info:
        await loader.load(str(fake))

    # The error message must reference *audio decoding* — not "wave" or
    # "RIFF" which would indicate the silent-fall-through bug.
    msg = str(exc_info.value).lower()
    assert (
        "audio decode failed" in msg or "decode" in msg or "soundfile" in msg or "libsnd" in msg
    ), f"expected clear decode error, got: {exc_info.value!r}"


@pytest.mark.asyncio
async def test_missing_file_still_raises_filenotfounderror(tmp_path: Path) -> None:
    """Regression — narrowing decode errors must not change the
    pre-existing ``FileNotFoundError`` contract for absent paths.
    """
    loader = AudioLoader(target_sr=22050)
    with pytest.raises(FileNotFoundError, match="not found"):
        await loader.load(str(tmp_path / "missing.wav"))


@pytest.mark.asyncio
async def test_real_wav_still_loads(tmp_path: Path) -> None:
    """Sanity — a valid WAV file must still load via the fallback chain.

    Use stdlib ``wave`` to write a minimal RIFF WAVE file directly so the
    test does not depend on soundfile/librosa being installed.
    """
    import wave

    import numpy as np

    sr = 22050
    samples = (np.sin(2 * np.pi * 440 * np.arange(sr) / sr) * 16384).astype(np.int16)
    fp = tmp_path / "tone.wav"
    with wave.open(str(fp), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())

    loader = AudioLoader(target_sr=sr)
    sig = await loader.load(str(fp))
    assert sig.sample_rate == sr
    assert sig.duration_seconds == pytest.approx(1.0, abs=0.05)
    assert sig.samples.shape[0] > 0
