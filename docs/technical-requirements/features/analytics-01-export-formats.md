# analytics-01: Export Formats

**Phase**: Analytics
**Status**: completed
**Modules**: `app/export/`
**Dependencies**: workflow-03

## BR-EXP-001: Four Export Formats

**Description**: DJ sets exportable as M3U8, Rekordbox XML, JSON guide, and text cheat sheet.

| Format | Writer | Output |
|--------|--------|--------|
| M3U8 | `M3U8Writer` | Extended M3U with `#EXTDJ-*` tags (BPM, key, energy, cue, loop, section, EQ, transition, note) |
| Rekordbox XML | `RekordboxWriter` | Pioneer DJ compatible XML |
| JSON Guide | `JSONWriter` | Structured JSON with per-track and per-transition details + analytics |
| Cheat Sheet | `CheatsheetWriter` | Human-readable text (BPM flow, key changes, energy curve, transition types) |

### User Stories

#### US-EXP-001: As a DJ, I want my set in multiple formats

**Acceptance Criteria:**
- [x] AC-EXP-001: M3U8 includes standard + custom `#EXTDJ-*` extension tags
- [x] AC-EXP-002: Rekordbox XML is importable by Pioneer rekordbox
- [x] AC-EXP-003: JSON guide includes set-level analytics (avg score, BPM range, energy profile)
- [x] AC-EXP-004: Cheat sheet is printable/readable on a phone at the booth
