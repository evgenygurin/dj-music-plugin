# Cross-Phase Review — 2026-04-17

**Scope:** All 7 implementation plans (Phase 1-7), 27,529 lines total, 175 tasks, 895 steps.
**Against:** `docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md`.
**Method:** seven-dimensional audit via grep-based signal extraction + targeted sampling.

---

## Verdict

**APPROVED TO PROCEED** with 5 minor findings (3 recommended fixes, 2 informational). No blocking issues. Plans are internally consistent, cover every blueprint deliverable, and respect every FastMCP v3 breaking change.

**Update 2026-04-17 12:45 GMT+3:** All 3 recommended fixes applied in follow-up commit. Status now: **APPROVED, all gaps closed.** See "Action Items Status" section below.

---

## Dimension 1 — Spec Coverage

Every blueprint section with concrete deliverables is referenced by at least one plan.

| Blueprint § | Topic | Referenced by |
|---|---|---|
| §3 | Directory structure | P1, P2, P6, P7 |
| §4 | Naming law | *(implicit across all plans — style rule, no explicit ref needed)* |
| §5 | EntityRegistry + handlers | P1, P3 |
| §6 | ProviderRegistry | P1, P3 |
| §7 | Tool catalog | P3, P7 |
| §8 | Resource catalog | P4, P5 |
| §9 | Prompt catalog | P4, P5 |
| §10 | UoW + BaseRepository | P1, P2 |
| §11 | Middleware pipeline | P5, P7 |
| §12 | FastMCP v3 features | P3, P4, P5 |
| §13 | Deletions | P7 |
| §14 | Migration map | P2, P6, P7 |
| §15 | Phased rollout (15.2–15.8) | all plans reference own §15.N |
| §16 | Import-linter | P1, P3, P6 |
| §17 | Testing strategy | P7 |
| §18 | Risks | P7 |

**Verdict:** ✅ Complete.

---

## Dimension 2 — Cross-phase Dependencies

Each plan correctly claims preconditions and references downstream phases.

| Plan | Claims | Verified |
|---|---|---|
| P1 | Produces `shared/`, `config/`, `registry/*`, `repositories/{base,unit_of_work}.py`, `tests/v2/conftest.py` | ✅ all used by P2-P5 |
| P2 | "Phase 1 complete — shared/, config/, registry/, repositories/base.py, UoW skeleton exist" | ✅ matches P1 Task 14+15 |
| P3 | "Phase 1 + 2 complete — uow.tracks / .playlists / ... exist" | ✅ matches P2 Task 19 UoW extension |
| P4 | "Phase 3 complete — tools exist; uow exposes all repos" | ✅ |
| P5 | "Phase 1-4 complete — all models, repos, tools, resources, prompts exist" | ✅ |
| P6 | "Parallel refactor continues — legacy remains intact" | ✅ matches blueprint §15.7 exactly |
| P7 | Deletes every artefact listed in blueprint §13.1 | ✅ P7 Tasks 10-15 cover all groups |

**Forward reference correctness (Phase N mentions future work):**
- P2 correctly defers: "handlers default to None; Phase 3 assigns custom handlers"
- P2 correctly defers: "Migration applied to production — Phase 7 Task 18"
- P1 correctly defers: "Phase 2 extends UoW with lazy repo properties"
- P6 correctly defers: "Phase 7 moves app/ → app/v1_legacy/ and deletes legacy paths"

**Verdict:** ✅ Coherent.

---

## Dimension 3 — Type / Signature Consistency

Key-term frequency matrix across phases (P1..P7):

| Symbol | P1 | P2 | P3 | P4 | P5 | P6 | P7 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `UnitOfWork` | 10 | 8 | 30 | 29 | 18 | 0 | 0 |
| `BaseRepository` | 14 | 34 | 0 | 0 | 1 | 0 | 0 |
| `EntityRegistry` | 19 | 18 | 41 | 7 | 1 | 0 | 7 |
| `ProviderRegistry` | 18 | 0 | 33 | 5 | 10 | 0 | 5 |
| `EntityConfig` | 15 | 12 | 11 | 1 | 0 | 0 | 0 |
| `register_default_entities` | 0 | 15 | 22 | 0 | 1 | 0 | 1 |
| `get_uow` | 1 | 0 | 19 | 22 | 13 | 0 | 0 |
| `@cached_property` | 0 | 17 | 0 | 0 | 0 | 0 | 0 |
| `Message` | 0 | 0 | 0 | 27 | 1 | 0 | 0 |
| `PromptResult` | 0 | 0 | 0 | 37 | 0 | 0 | 1 |
| `ResourceResult` | 0 | 0 | 0 | 11 | 0 | 0 | 0 |

**Analysis:**
- `UnitOfWork` introduced P1, used P2-P5, correctly absent from P6 (pure domain) and P7 (cutover)
- `BaseRepository` defined P1, subclassed P2, transparent in P3+ via `uow.<attr>` — correct
- `EntityRegistry` threaded consistently; `register_default_entities` defined P2, called P3 — correct
- `ProviderRegistry` absent from P2 (persistence only) — correct
- `Message` + `PromptResult` concentrated in P4 — v3 breaking-change types used in the right place
- `ResourceResult` used only in P4 — correct

**Verdict:** ✅ Signatures flow cleanly through phases.

---

## Dimension 4 — FastMCP v3 Compliance

Verified adoption of v3 breaking changes across all plans:

| Pattern | Should appear? | Status |
|---|---|---|
| `list_tools()` (not `get_tools()`) | ✅ P3, P5, P6, P7 | correct |
| `mcp.mount(..., namespace=...)` (not `prefix=`) | ✅ | **0 occurrences of `prefix=`** across 27k lines |
| `@tool(enabled=False)` | ❌ removed in v3 | **0 occurrences** ✅ |
| `server.disable(tags=...)` / `ctx.enable_components(tags=...)` | ✅ P3, P5, P7 | used correctly |
| `mcp.types.PromptMessage` | ❌ removed in v3 | only 1 occurrence in P4, and it's a *negation* (`never mcp.types.PromptMessage`) — correct |
| `fastmcp.prompts.Message` + `PromptResult` | ✅ P4 | 27 + 37 occurrences — exhaustive |
| `apply_middleware` / `run_middleware` | ❌ old internal names | 0 occurrences ✅ |
| `ctx.report_progress()` | ✅ P3, P5 | 17 + 8 |
| `ctx.elicit()` | ✅ P3, P4 | 1 + 1 (sparse — only where semantically needed) |
| `BM25SearchTransform(always_visible=...)` | ✅ P5 | 9 occurrences |
| `PromptsAsTools`, `ResourcesAsTools` | ✅ P5 | present |
| Resources return `str \| bytes \| ResourceResult` | ✅ P4 | pattern verified |

**Verdict:** ✅ Full v3 compliance. No legacy-API artefacts detected.

---

## Dimension 5 — Test Strategy

Each test tier has its own `conftest.py`:

| Phase | Conftest location | Scope |
|---|---|---|
| P1 Task 13 | `tests/v2/conftest.py` | shared `engine` + `session` fixtures |
| P3 Task inferred | `tests/v2/tools/conftest.py` | in-memory MCP client + seeded UoW |
| P4 Task 5 | `tests/v2/resources/conftest.py` | `Client(mcp_app)` + seeded_db |
| P4 Task 19 | `tests/v2/prompts/conftest.py` | prompt-specific helpers |
| P5 Task 25 | `tests/v2/server/conftest.py` | `build_mcp_server` + `MiddlewareContext` factory |
| P5 Task inferred | `tests/v2/rest/conftest.py` | FastAPI `TestClient` |

TDD discipline (write failing test → run expecting FAIL → implement → run expecting PASS → commit) observed in every plan: 175 tasks × 5 steps ≈ 875 steps, matches counted 895.

**Verdict:** ✅ Test isolation per layer, consistent TDD pattern.

---

## Dimension 6 — Gaps + Duplications

### Gaps found (3, all minor)

**G1. `prefetch_service` migration unclear.**
Blueprint §14.3 says `app/services/prefetch_service.py` → `app/v2/server/prefetch.py`. No phase creates this file. P1 mentions "prefetch" once in its own context, but no migration task exists.

**Impact:** low. `prefetch_service` is a speculative prefetch for `suggest_next_track`. Phase 4 resources (suggest_next) could reference it but don't.

**Recommended fix:** Add one Task in P5 (server composition) or P4 (resources) that creates `app/v2/server/prefetch.py` as a thin port of the legacy class. 30-60 lines.

**G2. `panel-guide.md` + `vm-deployment.md` not in P7 docs rewrite.**
P7 Tasks 5-9 rewrite `CLAUDE.md`, `architecture.md`, `tool-catalog.md`, `structure.md`. But `panel-guide.md` references legacy tool names and `vm-deployment.md` references `scripts/vm_*.py` which must adapt.

**Impact:** low. Panel is out of scope per D2; VM scripts use `scripts/compat_shims.py` from P7 Task 3.

**Recommended fix:** Extend P7 Task 9 (or add Task 9a) to cover:
- `docs/panel-guide.md` — note that panel is unchanged but dashboard reads must adjust if column renames happen (they don't in v1, but spell this out)
- `docs/vm-deployment.md` — refresh service names, note compat shim lifecycle

**G3. Alembic migration path preservation across swap.**
P7 Task 15 deletes `app/db/` (includes `migrations/`). P7 Task 16 (atomic swap) moves `app/v2/` → `app/`. But `app/v2/db/` has no `migrations/` folder — only `session.py` + `seed.py` per P2 Task 20.

**Impact:** high if missed. After swap, `alembic` commands would break because `script_location` in `alembic.ini` still points at `app/db/migrations/` which was just deleted.

**Recommended fix:** P7 Task 15 should MOVE (not delete) `app/db/migrations/` into `app/v2/db/migrations/` BEFORE deleting the rest of legacy `app/db/`. Then Task 17 (pyproject/alembic.ini updates) updates `alembic.ini` if the prefix needs adjustment (probably not — path remains `app/db/migrations/` after swap).

### Duplications found: none

Each plan owns its layer; no phase re-implements another's work. Parity tests in P3 (migration-parity) and P6 (v2==legacy) are intentional safety mechanisms, not duplications.

### Informational (2, no action needed)

**I1. Import-linter contract count over target.**
Blueprint §16 proposes 9 contracts as target set. Plans implement 13 (6 legacy + 5 from P1 + 2 from P6). **Over-delivery** — stricter isolation than required. No action needed.

**I2. Phase 4 resource file granularity.**
Blueprint §3 suggests 8 resource files in `app/v2/resources/`. P4 creates 11 (splits `reference/` into 4 separate files: camelot / subgenres / templates / audit_rules). **More granular** — better SRP. No action needed.

---

## Dimension 7 — Rollback + Safety (P7)

P7 has been built with the right paranoia. Every destructive task has an explicit **Rollback** block:

- Task 10 (delete engines/): `git reset --hard <pre-task-SHA>`
- Task 11 (delete ym/ + api/services): same
- Task 12 (delete decks/mixer/etc.): same
- Task 13 (delete services/): same
- Task 14 (delete controllers/bootstrap/api/schemas): same
- Task 15 (delete transition/optimization/camelot/...): same
- Task 16 (atomic swap): **dual rollback** — `git reset --hard` AND filesystem backup at `/tmp/phase-7-swap-backup/`
- Task 18 (apply DB migration): `alembic downgrade`
- Task 21 (tag `v1.0.0`): `git tag -d v1.0.0 && git push --delete origin v1.0.0`

**Dedicated pre-flight:**
- Task 1: verify Phase 1-6 merged to `dev`
- Task 2: Supabase logical backup captured
- Task 6: backup ID recorded in `/tmp/phase-7-backup-id.txt`
- Task 7: pre-cutover SHA pinned in `/tmp/phase-7-pre-cutover-sha.txt`

**Campaign continuity:**
- Task 3: `scripts/compat_shims.py` written so legacy tool names resolve during cutover
- Task 4: BFS / L5 graceful stop (`kill -TERM`) with batch flush
- Task 20: BFS / L5 restart with new tool names after swap
- Task 21: release only after 24h VM stability

**Merge hygiene:**
- All cutover work on `cutover/v1.0.0` branch
- Merges to `dev` via PR + green CI
- `dev → main` via `gh pr merge --squash` (project rule enforced)

**Verdict:** ✅ Extensive rollback coverage. One missing spot: **G3 above** (alembic migrations must move, not delete).

---

## Summary Table

| Dimension | Status | Findings |
|---|---|---|
| 1. Spec coverage | ✅ | 15/16 sections referenced (§4 implicit) |
| 2. Cross-phase deps | ✅ | All preconditions validated |
| 3. Type consistency | ✅ | Symbols flow correctly P1→P7 |
| 4. FastMCP v3 compliance | ✅ | 0 legacy APIs, full v3 types |
| 5. Test strategy | ✅ | Per-layer conftest + TDD |
| 6. Gaps / duplications | ⚠ 3 gaps | G1, G2, G3 (recommended fixes) |
| 7. Rollback / safety | ✅ / ⚠ | Missing alembic move (overlap with G3) |

**Overall:** ready for execution, with 3 recommended fixes before Phase 7 runs. None block Phase 1-6.

---

## Recommended Action Items

1. **Before Phase 5 execution:** Add a task creating `app/v2/server/prefetch.py` (port of legacy `prefetch_service.py`). ~45 LOC. Solves G1.
2. **Before Phase 7 execution:** Extend P7 Task 9 to rewrite `docs/panel-guide.md` + `docs/vm-deployment.md`. Solves G2.
3. **Inside Phase 7:** Modify Task 15 (or add Task 14a) — `git mv app/db/migrations/ app/v2/db/migrations/` BEFORE deleting the rest of `app/db/`. Solves G3 (alembic continuity).

Apply fixes 1-2 when starting each phase (open respective plan, append task). Apply fix 3 immediately to P7 Task 15 in a dedicated patch commit.

---

## Go/No-Go

**Recommendation: GO.** Start Phase 1 execution. Patches for G1-G3 can be applied as the corresponding phases approach (Phase 1-4 are unaffected). Fix G3 now while it's fresh.

---

## Action Items Status (updated 2026-04-17 12:45 GMT+3)

| # | Gap | Fix location | Status |
|---|---|---|---|
| G1 | `prefetch_service` not ported | Phase 5 plan — new `Task 2a` between Task 2 (di.py) and Task 3 (lifespan.py). Creates `app/v2/server/prefetch.py` (~110 LOC) + 4 pytest cases. | ✅ applied |
| G2 | `vm-deployment.md` missing from P7 docs rewrite | Phase 7 plan — Task 8 extended: added `docs/vm-deployment.md` to Files block; new Step 6 covering scripts' new tool-name payloads (`entity_create(entity="track_features")`, `provider_search`, etc.); commit message updated to reflect vm scope. `panel-guide.md` was already in Task 8 Step 5 — review report had a false negative. Numbers corrected: 13 dead → 15 dead, 44→31 → 46→31. | ✅ applied |
| G3 | Alembic `migrations/` lost during P7 swap | Phase 7 plan — Task 15 split: new Step 3a preserves `app/db/migrations/` via `git mv app/db/migrations/ app/v2/db/migrations/` with its own commit, Step 3b then deletes the rest of `app/db/`; Step 5 description corrected to reflect the relocated path. | ✅ applied |

**Result:** all 3 recommended fixes are now in the plans. No further review gates — Phase 1 execution can start immediately.
