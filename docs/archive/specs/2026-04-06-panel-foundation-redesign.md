# Panel Foundation Redesign — Design Spec

> Подпроект 1 из 9. Цель: превратить убогую панель-прототип в production-quality UI с полным покрытием 43 MCP tools.

## Проблема

Панель на 5.5/10: cyberpunk-тема без характера, нет error boundaries, toast не подключены, loading states не совпадают с реальными компонентами, пустые состояния — голый текст, motion library установлена но не используется, cmdk установлен но не подключен, 43 MCP tools — покрыты только 6.

## Решение

### 1. Тема: Linear Minimalism

Заменить cyberpunk neon на нейтральный минимализм:

| Element | Current | New |
|---------|---------|-----|
| Primary | magenta #ff00ff | neutral gray (--primary: oklch(0.0 0.0 0)) |
| Accent | cyan, green, amber | single blue (--accent: oklch(0.55 0.18 250)) |
| Background | dark gradients | #0a0a0a (dark), #fafafa (light) |
| Cards | shadow-xs + neon borders | borderless, bg-card, subtle border-border only |
| Charts | neon gradients | monochrome grays + one accent highlight |
| Fonts | Geist Sans/Mono (keep) | same |
| Radius | 0.625rem | 0.5rem |

Применяется через CSS variables в `globals.css` — все shadcn компоненты подхватят автоматически.

### 2. Schema-Driven Tool UI

Ядро архитектуры — один универсальный генератор форм из JSON Schema.

**Data flow:**
```text
GET /api/tools → список tools с tags, annotations, inputSchema
GET /api/tools/{name}/schema → JSON Schema
                               ↓
                        zod schema (json-schema-to-zod)
                               ↓
                        shadcn Form + Field (auto-generated)
                               ↓
POST /api/tools/{name}/call → execute
                               ↓
                        structuredContent → render result
```

**Компоненты:**

`ToolForm` — принимает tool name, подтягивает schema, рендерит форму:
- `string` → Input
- `integer` / `number` → Input type=number
- `boolean` → Switch
- `string` с enum → Select
- `array` → multi-select или textarea (JSON)
- Nested object → collapsible fieldset
- Все параметры опциональные → не показываются по умолчанию, раскрываются через "Advanced"

`ToolResult` — рендерит ответ tool call:
- `structured_content` с массивом → DataTable (автоматически)
- `structured_content` с объектом → key-value пары в Card
- `is_error=true` → Alert variant=destructive
- Длинные операции → Spinner → Toast при завершении

### 3. Навигация

**Sidebar** (Linear-style):
```text
DJ Music                    [⌘K]

MAIN
  Dashboard                 /
  Library                   /library
  Playlists                 /playlists
  Sets                      /sets

TOOLS
  Discover                  /discover
  Curation                  /curation
  Audio                     /audio
  Delivery                  /delivery

SYSTEM
  Tools                     /tools (generic tool runner)
  Admin                     /admin

                            v0.5.0
```

Активный route — bg-accent, без лишних украшений. Collapsible на мобилке через Sheet.

**Header:**
- Breadcrumb слева
- Global search справа: Command+K (cmdk уже установлен)

**Command Palette (⌘K):**
- Поиск по tracks, playlists, sets (через MCP `search` tool)
- Быстрый доступ к tools по имени
- Навигация по страницам

### 4. Новые shadcn компоненты

Установить из shadcn v4:
- `empty` — пустые состояния (иконка + title + description + CTA)
- `spinner` — индикатор загрузки для actions
- `field` — обёртка для form inputs (label + input + error)
- `form` — формы с zod validation
- `alert-dialog` — подтверждение деструктивных действий
- `dialog` — модалки для create/edit
- `command` — уже есть (cmdk), подключить
- `progress` — progress bar для long-running operations

### 5. Infrastructure

**Error Boundaries:**
- `app/error.tsx` — глобальный fallback с retry
- Per-route `error.tsx` для library, sets, playlists

**Loading States:**
- Каждый route → `loading.tsx` с Skeleton, совпадающим с реальным layout
- Server actions → Spinner + toast при завершении

**Toast Notifications:**
- Sonner уже установлен → подключить к layout.tsx
- Все server actions → toast.success/toast.error

**Motion Animations:**
- Page transitions: fade-in (motion library уже установлена)
- List animations: stagger при загрузке таблиц
- Micro-interactions: hover scale на карточках, button press

### 6. CRUD паттерн

Все domain pages используют одинаковый паттерн:

**List Page:**
- Header: title + [Create] button
- Filters через `nuqs` (URL params) — deep-linkable, shareable
- DataTable с сортировкой, поиском, пагинацией
- Bulk actions через selected rows
- Row click → detail page
- [Create] → Dialog с Form + zod

**Detail Page:**
- Header: ← back + title + [Actions ▾] dropdown
- Tabs: Overview | Features | Sections | Actions
- Actions tab: кнопки для MCP tools с автоформами из schema
- Каждое действие → Spinner → toast → revalidatePath

### 7. Страницы

| Route | Тип | Данные | MCP Tools |
|-------|-----|--------|-----------|
| `/` | Dashboard | Supabase direct | get_library_stats |
| `/library` | Domain CRUD | Supabase + MCP | list_tracks, manage_tracks, filter_tracks, search |
| `/library/[id]` | Detail | Supabase + MCP | get_track, get_track_features, analyze_track, classify_mood |
| `/playlists` | Domain CRUD | Supabase + MCP | list_playlists, manage_playlist |
| `/playlists/[id]` | Detail | Supabase + MCP | get_playlist, audit_playlist |
| `/sets` | Domain CRUD | Supabase + MCP | list_sets, manage_set, build_set |
| `/sets/[id]` | Detail | Supabase + MCP | get_set, rebuild_set, score_transitions, deliver_set, explain_transition, suggest_next_track, quick_set_review, compare_set_versions, get_set_cheat_sheet |
| `/discover` | Tool-driven | MCP | ym_search, ym_get_tracks, ym_get_album, ym_artist_tracks, find_similar_tracks, import_tracks, download_tracks |
| `/curation` | Tool-driven | MCP | classify_mood, distribute_to_subgenres, audit_playlist, review_set_quality, sync_playlist, push_set_to_ym |
| `/audio` | Tool-driven | MCP | analyze_track, analyze_batch |
| `/delivery` | Tool-driven | MCP | deliver_set, export_set |
| `/tools` | Generic | MCP | grid всех 43 tools по tags |
| `/tools/[name]` | Generic | MCP | ToolForm + ToolResult (любой tool) |
| `/admin` | Admin | MCP | unlock_tools, list_platforms |

### 8. Dashboard (Linear-style)

Минималистичный, информативный:
- 4 metric cards (tracks, analyzed, sets, avg quality) — numbers с NumberFlow animation
- BPM distribution — bar chart (monochrome + accent)
- Key distribution — реальный Camelot Wheel (circular SVG, не radar)
- Mood distribution — horizontal bars (sorted by count)
- Energy (LUFS) distribution — area chart
- Analysis coverage — progress bars per level

### 9. Технические решения

- `nuqs` для URL state management (фильтры, пагинация, tab selection)
- `@tanstack/react-virtual` для виртуализации длинных таблиц (>100 rows)
- `motion` для page transitions и micro-interactions
- `date-fns` для форматирования timestamps
- `@number-flow/react` для анимированных чисел в dashboard metrics
- `zod` для form validation (конвертация из JSON Schema через утилиту)
- Sonner для toast notifications
- cmdk для Command Palette

### 10. Порядок реализации (подпроекты 2-9)

1. **Foundation** (этот spec) — тема, layout, sidebar, infra компоненты
2. **Library** — tracks CRUD + detail + features + actions
3. **Playlists** — CRUD + track management + audit
4. **Sets** — CRUD + build + transitions + reasoning
5. **Dashboard** — stats + charts (Linear-style)
6. **Discover** — YM search + import + download
7. **Curation** — classify + distribute + sync
8. **Audio & Delivery** — analyze + deliver + export
9. **Admin + Generic Tools** — /tools/[name] schema-driven runner

Каждый подпроект — отдельный plan → implement цикл.

### 11. Scope Foundation (этот подпроект)

Что входит:
- globals.css — новая тема Linear
- Установка shadcn компонентов (empty, spinner, field, form, alert-dialog, dialog, progress)
- app-sidebar.tsx — редизайн навигации
- site-header.tsx — Command+K
- layout.tsx — Sonner, motion provider
- error.tsx — error boundaries (global + per-route)
- loading.tsx — корректные skeletons
- lib/mcp-client.ts — расширить: fetchToolSchema, callToolGeneric
- components/tool-form.tsx — schema-driven form generator
- components/tool-result.tsx — structured content renderer
- app/tools/page.tsx — grid всех tools
- app/tools/[name]/page.tsx — generic tool runner

Что НЕ входит (следующие подпроекты):
- Domain pages (library, playlists, sets) — перенос на новый паттерн
- Dashboard charts redesign
- Discover, Curation, Audio, Delivery pages
