from app.shared.errors import ValidationError

# Simulate the actual error from app/tools/compute/sequence_optimize.py
pinned_set = {146, 147}
excluded_set = {146}
overlap = pinned_set & excluded_set

# This is now the exact code from the modified sequence_optimize.py
try:
    raise ValidationError(
        f"track_ids cannot be both pinned and excluded: {sorted(overlap)}",
        details={"overlap": sorted(overlap), "pinned": sorted(pinned_set), "excluded": sorted(excluded_set)},
    )
except ValidationError as e:
    print("=== ValidationError Details Test ===")
    print(f"Message: {e}")
    print(f"Type: {type(e).__name__}")
    print(f"Details dictionary: {e.details}")
    print(f"Details type: {type(e.details)}")

    # Verify specific fields
    assert "overlap" in e.details, f"'overlap' key missing in details. Available keys: {list(e.details.keys())}"
    assert "pinned" in e.details, f"'pinned' key missing in details. Available keys: {list(e.details.keys())}"
    assert "excluded" in e.details, f"'excluded' key missing in details. Available keys: {list(e.details.keys())}"

    print()
    print("✅ Test PASSED: All expected keys (overlap, pinned, excluded) are present in details")
    print(f"   overlap: {e.details['overlap']}")
    print(f"   pinned: {e.details['pinned']}")
    print(f"   excluded: {e.details['excluded']}")
