# workflow-02: Audio Analysis Pipeline

**Phase**: Workflow
**Status**: completed
**MCP Tools**: `analyze_track`, `analyze_batch`, `separate_stems` (hidden)
**Atomic Tools**: `analyze_one_track`, `classify_one_track`, `gate_one_track` (hidden)
**Services**: `AudioService`, `AnalyzeTrackWorkflow`, `TieredPipeline`
**Dependencies**: core-01

## BR-AUD-001: Tiered Analysis (L1-L4)

**Description**: Audio analysis is tiered by need — L1+L2 (triage/classification), L3 (transition scoring), L4 (delivery with permanent files). Each level adds analyzers incrementally.

**Rationale**: Full analysis is 23s/track. Tiered approach reduces 500 tracks from 3.2 hours to 6 minutes by only analyzing what's needed at each stage.

### User Stories

#### US-AUD-001: As the system, I want to auto-analyze tracks to the required level

**Acceptance Criteria:**
- [x] AC-AUD-001: Given `classify_mood` is called on unanalyzed tracks, then auto-trigger L1+L2 (BPM, loudness, energy, spectral, key, MFCC)
- [x] AC-AUD-002: Given `build_set` needs transition scores, then auto-trigger L3 (+ beat analysis) for candidate tracks
- [x] AC-AUD-003: Given `deliver_set` is called, then auto-download permanent MP3 files (L4)
- [x] AC-AUD-004: Given track already at required level, then skip re-analysis (idempotent)

## BR-AUD-002: 20 Audio Analyzers

**Description**: Plugin-based architecture with 20 analyzers producing 47+ features. Core analyzers (numpy only) + librosa analyzers (optional) + essentia analyzers (optional).

**Rationale**: Analyzers are independent units that can fail independently — partial failures don't block the pipeline.

### User Stories

#### US-AUD-002: As a DJ, I want to analyze a specific track

**Acceptance Criteria:**
- [x] AC-AUD-005: Given an MP3 file, when `analyze_track(track_id=42)` is called, then run all available analyzers and persist features
- [x] AC-AUD-006: Given `force=true`, then re-analyze even if features already exist
- [x] AC-AUD-007: Given a librosa analyzer fails (package not installed), then continue with remaining analyzers and report partial results

## BR-AUD-003: Stitched Multi-Window Strategy

**Description**: Heavy librosa analyzers operate on a 60s clip stitched from 3 windows of 20s at positions ~1/6, 3/6, 5/6 with hann-fade blending.

**Rationale**: 5x speedup vs full-track analysis with negligible accuracy loss. Multi-window captures variation between sections.

## BR-AUD-004: Mood Classification

**Description**: Rule-based classifier assigns tracks to 15 techno subgenres using weighted scoring on 6-8 audio features per subgenre.

**Rationale**: No ML model needed — subgenre profiles are domain-expert defined. Catch-all subgenres (driving, hypnotic) penalized to prevent domination.

### User Stories

#### US-AUD-003: As a DJ, I want tracks classified by techno subgenre

**Acceptance Criteria:**
- [x] AC-AUD-008: Given analyzed tracks, when `classify_mood(playlist_id=5)` is called, then assign one of 15 subgenres with confidence score
- [x] AC-AUD-009: Given `reclassify=true`, then override existing classifications
- [x] AC-AUD-010: Classification persists `mood` and `mood_confidence` to `track_audio_features_computed`
