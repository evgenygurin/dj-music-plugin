# Elicitation Implementation Guide

## Overview

This project implements FastMCP v3 elicitation for user decision points across the DJ Music Plugin MCP server. Elicitation allows tools to pause execution and request user input when automated decisions aren't appropriate.

## Architecture

### Core Utilities (`app/core/elicitation.py`)

Three reusable helper functions with graceful fallback:

#### `safe_elicit(ctx, message, response_type, default_action, default_data)`
- **Purpose**: Core elicitation wrapper with fallback
- **Returns**: `(action, data)` tuple where action is "accept"/"decline"/"cancel"
- **Fallback**: Uses `default_action` and `default_data` when client doesn't support elicitation
- **Use case**: Custom Pydantic schemas

#### `safe_confirm(ctx, message, default)`
- **Purpose**: Simple yes/no confirmation
- **Returns**: `True`/`False`/`None` (None = cancelled)
- **Fallback**: Uses `default` boolean value
- **Use case**: Destructive operations, overwrite confirmations

#### `safe_choice(ctx, message, choices, default)`
- **Purpose**: Single-choice selection from list
- **Returns**: Selected choice string or `None` (cancelled)
- **Fallback**: Uses `default` choice
- **Use case**: Multiple options (e.g., "continue", "skip", "abort")

### EntityResolver with Elicitation (`app/core/entity_resolver.py`)

Enhanced entity resolution supporting:
- Exact ID lookup
- YM ID lookup
- Text search with ambiguous result handling
- **Elicitation on ambiguous matches** (top-5 choices presented to user)

**Key classes**:
- `EntityMatch[T]`: Single match with score
- `ResolvedEntity[T]`: Resolution result with confidence and alternatives
- `EntityResolver[T]`: Generic resolver with elicitation support

## Implementation Points

### 1. `deliver_set` Tool (2 elicitation points)

**Elicitation Point 1: Hard Conflicts**
- **Trigger**: Transition scores with 0.0 (BPM>10, Camelot≥5, or Energy>6 LUFS)
- **Choices**: `["continue", "skip_conflicts", "abort"]`
- **Default**: `"continue"`
- **Location**: `app/mcp/tools/delivery.py:186-213`

```python
conflict_action = await safe_choice(
    ctx,
    message=f"Found {conflict_count} hard conflict(s). How should we proceed?",
    choices=["continue", "skip_conflicts", "abort"],
    default="continue",
)
```

**Elicitation Point 2: YM Playlist Exists (future)**
- **Trigger**: YM playlist with same name already exists
- **Choices**: `["overwrite", "append", "create_new", "cancel"]`
- **Default**: `"append"`
- **Location**: `app/mcp/tools/delivery.py:265-286` (commented, needs YM client)

### 2. `sync_playlist` Tool

**Elicitation Point: Track Deletion Conflicts**
- **Trigger**: Track exists locally but deleted on YM (or vice versa)
- **Type**: Per-conflict confirmation
- **Returns**: Boolean (keep/delete) or None (cancel entire sync)
- **Location**: `app/mcp/tools/sync.py:59-101`

```python
keep_local = await safe_confirm(
    ctx,
    message=f"Track '{conflict['title']}' was deleted on YM. Keep it locally?",
    default=True,
)
if keep_local is None:
    return {"cancelled": True, ...}
```

### 3. `distribute_to_subgenres` Tool

**Elicitation Point: Clean Rebuild Confirmation**
- **Trigger**: `mode="clean_rebuild"` (destructive operation)
- **Type**: Boolean confirmation
- **Default**: `False` (safe default for destructive operation)
- **Location**: `app/mcp/tools/curation.py:462-477`

```python
confirmed = await safe_confirm(
    ctx,
    message=(
        f"⚠️ Mode 'clean_rebuild' will DELETE all existing tracks from "
        f"subgenre playlists before redistributing {len(track_ids)} tracks. Continue?"
    ),
    default=False,
)
```

### 4. `EntityResolver` (ambiguous query resolution)

**Elicitation Point: Multiple Text Matches**
- **Trigger**: Text search returns >1 result with similar scores
- **Choices**: Top-5 entity display names
- **Default**: Best match (highest score)
- **Location**: `app/core/entity_resolver.py:165-188`

```python
selected = await safe_choice(
    ctx,
    message=f"Found {len(matches)} matches for '{query}'. Which one?",
    choices=[get_display_name(m.entity) for m in top_matches],
    default=choices[0],
)
```

## Fallback Behavior

All elicitation functions gracefully handle:

1. **No Context** (`ctx=None`): Uses default action/value
2. **Elicitation Not Supported**: Catches exception, logs warning via `ctx.info()`, uses default
3. **Client Error**: Same as #2

**Example fallback message**:
```
⚠️ User input required but client doesn't support elicitation. Using default: continue
```

## Testing

### Unit Tests (`tests/test_core/test_elicitation.py`)

Tests for all three helper functions:
- Accept/decline/cancel actions
- Fallback on missing context
- Fallback on elicitation error
- Default value handling

### Integration Tests (`tests/test_core/test_entity_resolver.py`)

Tests for EntityResolver:
- Exact ID resolution
- YM ID resolution
- Single text match (no elicitation)
- Multiple matches with elicitation
- Elicitation cancelled
- Fallback when no context
- Max alternatives limit

### Mocking Pattern

```python
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.elicit = AsyncMock()
    return ctx

class MockElicitResult:
    def __init__(self, action: str, data=None):
        self.action = action
        self.data = data

# In test:
mock_ctx.elicit.return_value = MockElicitResult(
    action="accept",
    data=YourSchema(field="value")
)
```

## Best Practices

1. **Always use helpers**: Don't call `ctx.elicit()` directly — use `safe_elicit()`, `safe_confirm()`, or `safe_choice()`
2. **Safe defaults**: For destructive operations, default to `False` or safest option
3. **Clear messages**: Include context in elicitation messages (what will happen if accepted)
4. **Handle cancellation**: Always check for `None` return and abort operation gracefully
5. **Log warnings**: Use `ctx.warning()` before elicitation to explain why user input is needed
6. **Limit choices**: Keep choice lists ≤5 options for better UX

## Design Spec Reference

From `docs/superpowers/specs/2026-03-24-dj-music-plugin-design.md` §7:

| Elicitation Point | Tool | Trigger | Schema | Default |
|------------------|------|---------|--------|---------|
| Hard conflicts | deliver_set | score=0.0 | Literal["continue", "skip_conflicts", "abort"] | "continue" |
| YM playlist exists | deliver_set | Playlist name collision | Literal["overwrite", "append", "create_new", "cancel"] | "append" |
| Track deleted | sync_playlist | Deletion conflict | bool | True |
| Clean rebuild | distribute_to_subgenres | mode="clean_rebuild" | bool | False |
| Ambiguous query | EntityResolver | Multiple matches | Literal[top-5 titles] | Best match |

## Future Enhancements

1. **YM Playlist Sync**: Uncomment and implement elicitation point 2 in `deliver_set` once YM client is integrated
2. **Metadata Conflicts**: Extend `sync_playlist` to handle title/artist mismatches
3. **Batch Elicitation**: Allow resolving multiple conflicts in one elicitation call
4. **Elicitation Preferences**: Remember user choices for repeated scenarios (e.g., "always skip conflicts")
