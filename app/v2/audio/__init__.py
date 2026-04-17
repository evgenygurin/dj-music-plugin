"""Audio analysis pipeline (v2).

Librosa + essentia machinery. Not pure — may touch filesystem, numeric deps.
Import-linter contract `v2-audio-internal` forbids MCP/REST/repository imports.

Submodules:
- core           — STFT/framing/loader plumbing
- analyzers      — 18 concrete analyzer implementations
- classification — rule-based mood classifier (15 subgenres)
"""
