# BUG-008: classify_mood missing reclassify parameter in service

**Status:** FIXED (2026-03-27)

## Symptom

`classify_mood` tool call fails with:
```text
CurationService.classify_mood() got an unexpected keyword argument 'reclassify'
```

## Root Cause

Tool `classify_mood` in `app/mcp/tools/curation.py` accepts `reclassify: bool = False` and passes it to `svc.classify_mood(reclassify=reclassify)`, but `CurationService.classify_mood()` did not accept this parameter.

## Fix

1. Added `reclassify: bool = False` parameter to `CurationService.classify_mood()` in `app/services/curation_service.py`
2. Added skip logic: when `reclassify=False`, tracks with existing mood classification are skipped
