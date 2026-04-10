# workflow-03: Set Delivery & Export

**Phase**: Workflow
**Status**: completed
**MCP Tools**: `deliver_set`, `export_set` (hidden)
**Services**: `DeliveryService`, `DeliverSetWorkflow`
**Dependencies**: workflow-01, workflow-02, analytics-01

## BR-DLV-001: Multi-Format Set Export

**Description**: Deliver a completed DJ set as numbered MP3 copies, M3U8 playlist, JSON guide, Rekordbox XML, and text cheat sheet.

**Rationale**: DJs need set files in formats compatible with their software (Rekordbox, Traktor, djay) plus human-readable guides.

### User Stories

#### US-DLV-001: As a DJ, I want to export my set for performance

**Acceptance Criteria:**
- [x] AC-DLV-001: Given a scored set, when `deliver_set(set_id=6, copy_files=true)` is called, then create `generated-sets/{name}/` with all artifacts
- [x] AC-DLV-002: Given `sync_to_ym=true`, then push the set as a YM playlist
- [x] AC-DLV-003: Given hard conflicts exist (score=0.0), then trigger elicitation asking user to continue or abort
- [x] AC-DLV-004: Given iCloud stubs (blocks < 90% of size), then skip copying but reference original path in M3U

## BR-DLV-002: Transition Conflict Gating

**Description**: Delivery pipeline gates on hard conflicts — if any transition has score=0.0, user must explicitly approve continuation.

**Rationale**: Prevents accidentally delivering unplayable sets. DJ can override if they plan manual transitions.
