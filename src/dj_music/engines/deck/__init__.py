"""DeckEngine — single deck runtime state machine.

A deck is a stateful audio source: loaded track + playhead position +
loop region + cue points + pitch + EQ + FX chain. The engine is a
GoF State machine: state transitions are explicit and audio rendering
behaviour depends on current state.

Submodules:
- engine.py    — DeckEngine facade (the public surface tools talk to)
- state.py     — DeckState enum + state machine transitions
- playback.py  — sample buffer reader, position tracking
- pitch.py     — SoundTouch streaming wrapper for ±8% time-stretch
- eq.py        — pedalboard 3-band EQ chain
- effects.py   — filter sweep, echo out, reverb
- cue.py       — cue points, hot cues 1-8, memory cues
- loop.py      — loop in/out, halve/double, reloop
- beatgrid.py  — beat phase tracker for sync
"""
