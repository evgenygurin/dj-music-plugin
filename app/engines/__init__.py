"""Long-lived runtime engines (Band 2B).

These are singletons constructed once per server process inside an
@lifespan and exposed via AppState. Unlike services (Band 2A) which
are per-request, engines hold state across tool calls — playback
position, mixer EQ, transition progress, audio output stream.

Subpackages:
- deck/        — DeckEngine state machine + cue/loop/pitch/EQ
- mixer/       — MixerEngine facade over decks + crossfader
- transition/  — TransitionEngine strategies + beatmatch
- output/      — AudioOutputBus (sounddevice driver, ring buffer)
- state/       — Snapshot, recorder, persisted session state

The lifespan that wires it all up lives in `app/engines/lifespan.py`
and is composed into `app/core/lifespan.py:app_lifespan`.

Audio stack (locked decisions, see .claude/rules/fastmcp.md):
- sounddevice 0.5.x  — PortAudio callback (numpy float32)
- pedalboard 0.9+    — EQ / filters / reverb / delay (releases GIL)
- soundtouch         — realtime ±8% pitch/tempo time-stretch
- soundfile + miniaudio — file decoding to numpy
- numpy 2.x          — mix kernel
"""
