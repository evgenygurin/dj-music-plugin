import asyncio, re, os
from pathlib import Path
from sqlalchemy import select
from app.db.session import get_session_factory
from app.models.track import Track
from app.models.track_features import TrackAudioFeaturesComputed
from app.models.audio_file import DjLibraryItem

STEMS_DIR = Path('/Users/laptop/Desktop/Stems')
PAT = re.compile(r'^(?P<idx>\d+)\s+\[(?P<bpm>\d+)bpm\]\s+\[(?P<genre>\w+)\]\s+(?P<title>.+)-(?:acappella|bass|drums|harmonic|instrumental)\.m4a$')
stem_titles = set()
for f in STEMS_DIR.iterdir():
    if f.is_dir() or f.name.startswith('.'): continue
    m = PAT.match(f.name)
    if m: stem_titles.add(m.group('title'))

async def main():
    sf = get_session_factory()
    async with sf() as s:
        r = await s.execute(
            select(Track.id, Track.title,
                   TrackAudioFeaturesComputed.bpm, TrackAudioFeaturesComputed.energy_mean,
                   TrackAudioFeaturesComputed.key_code, TrackAudioFeaturesComputed.integrated_lufs)
            .join(TrackAudioFeaturesComputed).join(DjLibraryItem)
            .where(Track.title.in_(list(stem_titles)))
            .where(TrackAudioFeaturesComputed.analysis_level >= 5)
            .where(TrackAudioFeaturesComputed.bpm.between(124, 140))
            .where(TrackAudioFeaturesComputed.integrated_lufs >= -14)
            .where(DjLibraryItem.file_path.startswith('/Users/laptop/Desktop/Stems'))
            .order_by(TrackAudioFeaturesComputed.energy_mean)
        )
        rows = r.all()
    
    # Manual curation: pick tracks with smooth BPM progression + rising energy + Camelot flow
    # Strategy: start dark/hypnotic, build through driving, peak with industrial/hard
    
    # WARMUP: low energy, deep/dub/dark, BPM 126-128
    warm_picks = [193, 28370, 176, 157, 445]
    # BUILD: medium energy, driving/hypnotic, BPM 128-131  
    build_picks = [577, 451, 9522, 22642, 184]
    # PEAK: high energy, hard/industrial, BPM 132-138
    peak_picks = [29369, 18628, 27168, 3154, 5076]
    
    all_picks = warm_picks + build_picks + peak_picks
    
    # Verify features
    async with sf() as s:
        r = await s.execute(
            select(Track.id, Track.title, TrackAudioFeaturesComputed.bpm,
                   TrackAudioFeaturesComputed.energy_mean, TrackAudioFeaturesComputed.key_code)
            .join(TrackAudioFeaturesComputed).where(Track.id.in_(all_picks))
        )
        rows = {r.id: r for r in r}
    
    for i, tid in enumerate(all_picks):
        r = rows.get(tid)
        if r:
            zone = 'WARM' if i < 5 else ('BUILD' if i < 10 else 'PEAK')
            print(f'{i+1:>2}. [{zone}] #{tid:<5} [{r.bpm:>5.1f}BPM] E={r.energy_mean:.3f} K{r.key_code} | {r.title[:45]}')
    
    print(f'\nIDs: {all_picks}')

asyncio.run(main())
