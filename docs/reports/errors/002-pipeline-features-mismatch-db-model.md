# BUG-002: Pipeline returns features not in DB model → TypeError

## Problem

`AnalysisPipeline.analyze()` returns feature dicts with keys that don't exist as
columns in `TrackAudioFeaturesComputed`. When passed via `**result.features`,
SQLAlchemy raises `TypeError: 'X' is an invalid keyword argument`.

## Affected Keys

| Pipeline key | Source analyzer | DB column | Status |
|-------------|----------------|-----------|--------|
| `energy_band_sub` | EnergyAnalyzer | `energy_sub` | Fixed: renamed |
| `energy_band_low` | EnergyAnalyzer | `energy_low` | Fixed: renamed |
| `energy_band_low_mid` | EnergyAnalyzer | `energy_lowmid` | Fixed: renamed |
| `energy_band_mid` | EnergyAnalyzer | `energy_mid` | Fixed: renamed |
| `energy_band_high_mid` | EnergyAnalyzer | `energy_highmid` | Fixed: renamed |
| `energy_band_high` | EnergyAnalyzer | `energy_high` | Fixed: renamed |
| `energy_band_brilliance` | EnergyAnalyzer | (none) | Fixed: removed band |
| `mfcc_mean` | MFCCExtractor | (none) | Fixed: filter_features() |
| `chroma_vector` | KeyDetector | (none) | Fixed: filter_features() |

## Fix Applied

1. **EnergyAnalyzer** (`app/audio/analyzers/energy.py`):
   - Renamed bands: `energy_band_{name}` → `energy_{name}` to match DB columns
   - Removed `brilliance` band (no DB column)
   - Added ratio computation (`energy_{name}_ratio`)

2. **MoodClassifier** (`app/audio/mood.py`):
   - Updated all `energy_band_*` references to `energy_*`

3. **Feature filter** (`app/models/audio.py`):
   - Added `TrackAudioFeaturesComputed.filter_features(dict)` classmethod
   - Filters pipeline output to only valid DB columns
   - Prevents any future mismatches from crashing

4. **Applied filter** in both save locations:
   - `app/services/audio_service.py:131`
   - `app/mcp/tools/audio_atomic.py:100`

## Date

2026-03-25
