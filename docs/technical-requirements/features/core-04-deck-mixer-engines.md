# core-04: Deck & Mixer Engines

**Phase**: Core
**Status**: completed (state management; audio rendering planned)
**MCP Tools**: `deck_load`, `mixer_crossfader`, `mixer_channel_gain`, `watch_decks`
**Services**: `DeckEngine`, `MixerEngine`

## BR-DCK-001: Virtual DJ Deck State Machine

**Description**: 4-deck mixer with state machine per deck (EMPTY → LOADING → LOADED → PLAYING/PAUSED/CUEING). Real-time state streaming via `watch_decks`.

**Rationale**: Foundation for live mix preview and automated transition execution (Phase 15+).

### User Stories

#### US-DCK-001: As an AI assistant, I want to load and control decks

**Acceptance Criteria:**
- [x] AC-DCK-001: Given a track, when `deck_load(deck_id=1, track_id=42)` is called, then transition deck state to LOADED
- [x] AC-DCK-002: When `mixer_crossfader(target=0.5)` is called, then set crossfader to center blend
- [x] AC-DCK-003: When `mixer_channel_gain(deck_id=1, value=1.2)` is called, then set deck volume to 120%

#### US-DCK-002: As an AI assistant, I want to monitor mixer state in real-time

**Acceptance Criteria:**
- [x] AC-DCK-004: When `watch_decks(hz=15, duration_s=60)` is called, then stream snapshots via `report_progress` at specified rate
- [x] AC-DCK-005: Cancellable via MCP `notifications/cancelled`
