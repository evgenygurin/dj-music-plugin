# Spec: Maximal Documentation Update — Claude Code Rules

**Date**: 2026-04-16  
**Status**: Approved  
**Approach**: A (FastMCP docs-first, then code extraction)

## Goal

Fill all gaps in Claude Code memory (`.claude/rules/` + panel `CLAUDE.md` files) so Claude makes zero avoidable mistakes in any part of the codebase. Current coverage: ~70%. Target: ~95%.

## Identified Gaps

| Area | Gap Type | Impact |
|------|----------|--------|
| `app/bootstrap/` | No rules file at all | Claude misorders middleware, breaks transforms |
| `app/transition/` | No rules file | Claude re-implements scoring logic instead of using scorer |
| `app/optimization/` | No rules file | Claude picks wrong algorithm or wrong params |
| `app/providers/` | No rules file | Claude bypasses MusicProvider protocol |
| `app/entities/` | No rules file | Claude creates ad-hoc dicts instead of typed dataclasses |
| `panel/app/CLAUDE.md` | Only claude-mem, no rules | Claude guesses Next.js patterns |
| `panel/components/CLAUDE.md` | Only claude-mem, no rules | Claude invents component patterns |
| `workflows.md` | Missing `description:` in frontmatter | Rule never activates in Claude Code |
| FastMCP: tasks | Not documented | Claude won't use background tasks correctly |
| FastMCP: progress | Not documented | Claude uses ctx.info() instead of ctx.report_progress() |
| FastMCP: server composition | Not documented | Claude re-implements mounting logic |
| FastMCP: lifespan | Partial | Lifespan `|` composition not in rules |

## Sources

### FastMCP Docs (unread pages)
1. `https://gofastmcp.com/servers/lifespan` — startup/shutdown, `|` composition
2. `https://gofastmcp.com/servers/progress` — `ctx.report_progress()`, progress tokens
3. `https://gofastmcp.com/servers/prompts` — full prompts page
4. `https://gofastmcp.com/servers/server-composition` — mounting, proxies, prefixes
5. `https://gofastmcp.com/servers/background-tasks` — `task=True`, `fastmcp[tasks]`
6. `https://gofastmcp.com/python-sdk/client` — Client API, transports, elicitation_handler

### Project Code
- `app/bootstrap/server_builder.py`, `lifespans.py`, `transforms.py`, `visibility.py`, `middleware.py`
- `app/transition/scorer.py`, `app/transition/intent.py`
- `app/optimization/ga.py`, `app/optimization/greedy.py`, `app/optimization/fitness.py`
- `app/providers/__init__.py`, `app/providers/protocol.py` (or similar)
- `app/entities/` (TrackFeatures, AudioFeatures dataclasses)
- `panel/app/layout.tsx`, `panel/app/(dashboard)/page.tsx`
- `panel/components/` (sample components for pattern extraction)

## Deliverables

### New Rule Files (5)

| File | Scope | Style |
|------|-------|-------|
| `.claude/rules/bootstrap.md` | Middleware order, ToolTransform, lifespans `\|` composition, FileSystemProvider, visibility defaults | Detailed (~60 lines) |
| `.claude/rules/transitions.md` | TransitionScorer 6 components, weights, Camelot wheel usage, TransitionIntent | Medium (~40 lines) |
| `.claude/rules/optimization.md` | GA vs greedy choice, fitness params, BuildSetWorkflow, algorithm selection logic | Medium (~30 lines) |
| `.claude/rules/providers.md` | MusicProvider protocol, registry, adapters, multi-platform | Concise (~25 lines) |
| `.claude/rules/entities.md` | TrackFeatures / AudioFeatures dataclasses, pure domain rules, no ORM/HTTP | Concise (~25 lines) |

### Panel Files (2)

| File | Content |
|------|---------|
| `panel/app/CLAUDE.md` | App Router patterns: server components, loading.tsx, error.tsx, layout composition |
| `panel/components/CLAUDE.md` | shadcn usage, cyberpunk theme tokens, component file structure |

### Updated Files (4)

| File | Additions |
|------|-----------|
| `tools.md` | Progress reporting (`ctx.report_progress()`), background tasks pattern |
| `tests.md` | inline-snapshot / dirty-equals, progress token testing |
| `gotchas.md` | Lifespan gotchas, server composition gotchas |
| `workflows.md` | Add `description: Workflow orchestration patterns` to frontmatter |

## Execution Order

1. **Фаза 1**: Fetch 6 FastMCP doc pages, extract patterns
2. **Фаза 2**: Read project code files, extract patterns
3. **Фаза 3**: Write 5 new rule files
4. **Фаза 4**: Fill panel/app/CLAUDE.md + panel/components/CLAUDE.md
5. **Фаза 5**: Update tools.md, tests.md, gotchas.md, workflows.md
6. **Фаза 6**: Commit all changes

## Success Criteria

- Every new rule file has valid YAML frontmatter (`description`, `globs`)
- No placeholder or TBD sections
- Each rule changes Claude's behavior (not "documentation for humans")
- No contradictions with existing rules
- All gotchas are real (verified in code)
