# lifecycle-02: Set Reasoning

**Phase**: Lifecycle
**Status**: completed
**MCP Tools**: `suggest_next_track`, `explain_transition`, `find_replacement`, `compare_set_versions`, `quick_set_review`
**Services**: `ReasoningService`
**Dependencies**: workflow-01

## BR-RSN-001: AI-Assisted Set Refinement

**Description**: Five reasoning tools that help a DJ understand and improve their set — suggestions, explanations, replacements, comparisons, and quality reviews.

**Rationale**: After automated set building, human-AI collaboration refines the result. These tools give the AI contextual intelligence to advise.

### User Stories

#### US-RSN-001: As a DJ, I want track suggestions for a set position

**Acceptance Criteria:**
- [x] AC-RSN-001: Given a set and position, when `suggest_next_track(set_id=6, after_position=5, count=5)` is called, then return candidates scored against both neighbors
- [x] AC-RSN-002: Given `prefer_mood="acid"`, then boost acid tracks in ranking
- [x] AC-RSN-003: Given `energy_direction="up"`, then prefer tracks with higher energy than current position

#### US-RSN-002: As a DJ, I want to understand why a transition works or fails

**Acceptance Criteria:**
- [x] AC-RSN-004: Given two tracks, when `explain_transition(from=42, to=55)` is called, then return 6-component breakdown with human-readable reasoning

#### US-RSN-003: As a DJ, I want replacement options for a weak spot

**Acceptance Criteria:**
- [x] AC-RSN-005: Given a set position, when `find_replacement(set_id=6, position=7)` is called, then return alternatives scored against prev+next tracks

#### US-RSN-004: As a DJ, I want to compare set versions

**Acceptance Criteria:**
- [x] AC-RSN-006: When `compare_set_versions(set_id=6)` is called, then show tracks added/removed, score deltas between latest two versions

#### US-RSN-005: As a DJ, I want a quick quality check

**Acceptance Criteria:**
- [x] AC-RSN-007: When `quick_set_review(set_id=6)` is called, then return pass/fail verdict with weak transitions flagged
