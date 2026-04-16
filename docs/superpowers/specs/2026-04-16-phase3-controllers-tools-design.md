# Phase 3 Design: Controllers and Tool Surface Refactoring

## Context

Provider-agnostic refactoring of the DJ Music Plugin. This is Phase 3 of 4 — high risk. It renames the public MCP tool surface, moves provider-specific controllers out of the `yandex/` package, replaces the `ym` visibility vocabulary with `platform`, and updates all prompt and panel callers in one breaking-change slice.

Branch: `refactor/provider-agnostic-naming`

Parent prompt: `docs/superpowers/specs/2026-04-16-provider-agnostic-refactoring-prompt.md`
Phase 1 design: `docs/superpowers/specs/2026-04-16-phase1-schemas-repos-filters-design.md`
Phase 2 design: `docs/superpowers/specs/2026-04-16-phase2-service-layer-design.md`

---

## Scope

~18 files across five sub-tasks:

1. Move provider-facing tools from `app/controllers/tools/yandex/` to `app/controllers/tools/platform/`
2. Rename all public tool names from YM-specific to provider-agnostic names
3. Replace `kind: int`-style controller inputs with opaque `playlist_id: str`
4. Rename visibility vocabulary from `ym` to `platform`
5. Update workflow prompts, panel callers, and acceptance expectations to the new surface

This phase is a deliberate breaking API change. No deprecated aliases are kept.

---

## Core Design Decision: Big Bang Public API Rename

Phase 3 uses a true `big bang` rename. Old `ym_*` tool names, the `ym` visibility tag, and `kind`-based controller inputs disappear in the same phase.

Rejected alternative: keep deprecated aliases for one release. That would reduce short-term churn, but it would preserve the old vocabulary in prompts, tests, and clients, weakening the point of the refactor and forcing a second breaking cleanup later.

Rejected alternative: rename only tool functions but keep the `yandex/` package and `ym` tags. That would leave a misleading boundary where the public API claims to be provider-agnostic, but the controller structure still encodes the vendor.

The goal of this phase is not backward compatibility. The goal is a clean public boundary:

- tool names do not encode the active vendor
- controller parameters do not encode YM-specific identifiers
- prompts and panel code speak the same vocabulary as the registered tools
- vendor-specific knowledge remains in `app/clients/ym/` and the provider adapter

---

## Section A: Controller Package Move

### A.1 Directory rename

Move:

- `app/controllers/tools/yandex/` -> `app/controllers/tools/platform/`

Files moved without changing responsibility:

- `search.py`
- `tracks.py`
- `albums.py`
- `playlists.py`
- `likes.py`
- `__init__.py`
- `_constants.py`

The package name changes because these controllers are no longer modeling "Yandex tools". They model "remote platform tools" backed by the active `MusicProvider`.

### A.2 Icons and display labels

This phase does not require renaming every YM-branded display affordance. Specifically:

- `ICON_YM` may remain temporarily if it is only a presentation detail
- tool `title=` strings should be updated where they are user-visible and misleading

Priority is on API contract and vocabulary. Low-level visual polish can follow in Phase 4 if needed.

---

## Section B: Public Tool Renames

### B.1 Target mapping

| Old tool | New tool | Reason |
|----------|----------|--------|
| `ym_search` | `search_platform` | Short umbrella name for multi-entity platform search (`tracks`, `albums`, `artists`, `playlists`) |
| `ym_get_tracks` | `get_platform_tracks` | Explicit remote-track fetch |
| `ym_artist_tracks` | `get_platform_artist_tracks` | Read-style naming that keeps the platform context explicit |
| `ym_get_album` | `get_platform_album` | Read-style naming that keeps the platform context explicit |
| `ym_playlists` | `platform_playlists` | Dispatch tool centered on playlist operations |
| `ym_likes` | `platform_liked_tracks` | Dispatch tool centered on liked-track operations |
| `push_set_to_ym` | `push_set_to_platform` | Mutation name keeps the remote destination explicit |
| `expand_playlist_ym` | `expand_platform_playlist` | Expansion target remains explicit in the public name |

### B.2 Function names, decorators, and prompt references

Each rename must be applied consistently in three places:

1. Python function name
2. FastMCP registration surface
3. All prompt and panel text that calls the tool by name

This phase is complete only when all three layers agree.

### B.3 No alias layer

There are no wrapper tools, aliases, or shadow registrations such as:

```python
async def ym_search(...):
    return await search_platform(...)
```

That pattern is explicitly excluded from this design.

---

## Section C: Parameter Boundary for Playlists

### C.1 `kind: int` becomes `playlist_id: str`

Controller-level playlist inputs become opaque string identifiers:

| Old parameter | New parameter |
|---------------|---------------|
| `kind: int` | `playlist_id: str` |
| `ym_playlist_kind` | `playlist_id` |

This applies to:

- `platform_playlists`
- `expand_platform_playlist`
- any prompt text or panel action that still teaches users to pass YM `kind`

### C.2 Controller no longer formats YM playlist IDs

The helper below disappears from controller code:

```python
def _playlist_id(kind: int) -> str:
    return f"{settings.ym_user_id}:{kind}"
```

Controllers stop constructing `owner_id:kind`. They pass `playlist_id` through as-is. The active provider or adapter remains responsible for interpreting it.

This keeps the controller boundary honest:

- controllers accept an opaque platform identifier
- adapters know platform-specific encoding rules
- service and prompt layers do not hardcode YM formatting rules

### C.3 Validation semantics

Validation stays shallow at the controller level:

- missing required `playlist_id` -> `ToolError`
- malformed YM-specific format -> provider/adapter concern, not controller parsing

Phase 3 renames the boundary. It does not add new provider protocol methods or new parsing abstractions.

---

## Section D: Visibility Vocabulary

### D.1 Rename the category

Replace:

- `ToolCategory.YM = "ym"`

With:

- `ToolCategory.PLATFORM = "platform"`

This is a semantic change, not a cosmetic one. The category now describes a capability family, not a vendor.

### D.2 Update all tag-based callers

All places that rely on the old visibility vocabulary must move in the same slice:

- tool decorators with `tags={ToolCategory.YM.value}`
- admin/category listings
- `enable_components(tags={"ym"})`
- prompt instructions that teach the model to unlock or call YM tools

After this phase, the public visibility vocabulary is `platform` only.

---

## Section E: Prompt and Panel Synchronization

### E.1 Workflow prompts

Files under `app/controllers/prompts/workflows/` are part of the public MCP surface because they teach the model how to call tools. They must be updated in the same phase as the tool rename.

Most visible case:

- `app/controllers/prompts/workflows/dj_expert_session.py`

Examples of required prompt vocabulary changes:

- `ym_likes(action="get_liked")` -> `platform_liked_tracks(action="get_liked")`
- references to `expand_playlist_ym` -> `expand_platform_playlist`
- any mention of `ym_*` tool names or tag `ym` -> new platform names

### E.2 Panel boundary

Panel actions and queries must use the same vocabulary as MCP registration. The panel may still know that the active provider is Yandex Music as a business fact, but it must not encode that in tool names or payload field names.

Panel rules after Phase 3:

- no `ym_*` tool calls
- no `kind` input for remote playlist actions
- no mixed old/new vocabulary in helper names, action payloads, or route glue

### E.3 Acceptance tests

Acceptance smoke tests must verify the new public tool surface rather than preserving the old names.

That includes:

- tool presence assertions
- prompt content assertions if any exist
- category and visibility expectations

---

## Section F: Error Handling and Non-Goals

### F.1 Error semantics unchanged

Phase 3 does not redesign runtime behavior:

- existing `ToolError` guards stay in place
- dispatch behavior stays in place
- provider exceptions still surface through the existing middleware stack

The only intentional behavior change is the public naming and input shape.

### F.2 Explicit non-goals

This phase does not:

- add deprecated aliases
- introduce new provider protocol methods
- rename environment variables such as `settings.ym_*`
- rename `app/clients/ym/`
- redesign adapter internals
- change database schema

Those remain outside the boundary of Phase 3.

---

## Section G: Verification Strategy

### G.1 Primary invariants

Phase 3 is successful when all of these are true:

1. Public tool registration exposes only the new names
2. No prompt teaches the model to call removed `ym_*` tools
3. No panel integration still calls removed `ym_*` tools
4. No controller builds YM-specific playlist IDs from `settings.ym_user_id`
5. Visibility uses `platform`, not `ym`

### G.2 Exit checks

```bash
make check
rg -i "ym_search|ym_playlists|ym_get|ym_likes|ym_artist|push_set_to_ym|expand_playlist_ym" app/ panel/ tests/
rg 'ToolCategory\.YM|tags=\{"ym"\}|enable_components\(tags=\{"ym"\}\)' app/
```

Expected result:

- `make check` is green
- the grep commands return no matches outside deliberately preserved YM low-level code

---

## Risks

| Risk | Why it matters | Mitigation |
|------|----------------|------------|
| Prompt/tool drift | Prompt still teaches removed names | Update prompts in the same commit slice as tool renames |
| Panel/tool drift | Panel calls unregistered tools | Update panel callers before phase completion |
| Hidden YM formatting in controllers | Boundary remains falsely generic | Remove `_playlist_id(kind)` and any `settings.ym_user_id` usage from controller package |
| Partial rename in tests | Green code, stale contract tests | Update acceptance smoke assertions to the new surface |

---

## Result

After Phase 3:

1. The public MCP surface is provider-agnostic in names, tags, and playlist input shape
2. The controller package no longer advertises Yandex Music as the public abstraction
3. Prompts, panel, and tests all speak the same tool vocabulary
4. YM-specific knowledge remains below the controller boundary, where it belongs
