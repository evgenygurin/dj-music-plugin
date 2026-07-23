import asyncio, re
from pathlib import Path
from sqlalchemy import select
from app.db.session import get_session_factory
from app.models.track import Track
from app.models.track_features import TrackAudioFeaturesComputed

STEMS_DIR = Path('/Users/laptop/Desktop/Stems')
PAT = re.compile(r'^(?P<idx>\d+)\s+\[(?P<bpm>\d+)bpm\]\s+\[(?P<genre>\w+)\]\s+(?P<title>.+)-(?:acappella|bass|drums|harmonic|instrumental)\.m4a$')

stem_info = {}
for f in STEMS_DIR.iterdir():
    if f.is_dir() or f.name.startswith('.'): continue
    m = PAT.match(f.name)
    if m: stem_info[m.group('title')] = (int(m.group('bpm')), m.group('genre'))

async def main():
    sf = get_session_factory()
    async with sf() as s:
        r = await s.execute(
            select(Track.id, Track.title,
                   TrackAudioFeaturesComputed.bpm,
                   TrackAudioFeaturesComputed.energy_mean,
                   TrackAudioFeaturesComputed.integrated_lufs,
                   TrackAudioFeaturesComputed.key_code,
                   TrackAudioFeaturesComputed.analysis_level)
            .join(TrackAudioFeaturesComputed)
            .where(Track.title.in_(list(stem_info.keys())))
            .where(TrackAudioFeaturesComputed.bpm.between(126, 140))
            .where(TrackAudioFeaturesComputed.energy_mean >= 0.25)
            .order_by(TrackAudioFeaturesComputed.bpm)
        )
        rows = r.all()

    s1, bridge, s2 = [], [], []
    for row in rows:
        orig_bpm, genre = stem_info.get(row.title, (0, '?'))
        entry = (row.id, row.title, row.bpm, row.energy_mean, row.integrated_lufs, row.key_code, row.analysis_level, genre)
        if row.bpm and row.bpm <= 130.5:
            s1.append(entry)
        elif row.bpm and row.bpm <= 132.5:
            bridge.append(entry)
        else:
            s2.append(entry)

    def show(label, entries, n=20):
        print(f'\n{label} ({len(entries)} tracks):')
        for e in entries[:n]:
            print(f'  #{e[0]:<5} [{e[2]:>5.1f}BPM] [{e[7]:<14}] E={e[3]:.3f} LUFS={e[4]:.1f} key={e[5]} lvl={e[6]} | {e[1][:50]}')

    show('STORY 1 (126-130 BPM, hypnotic/deep)', s1, 30)
    show('BRIDGE (131-132 BPM)', bridge, 10)
    show('STORY 2 (133-140 BPM, hard/peak)', s2, 30)

    # Recommend picks
    print('\n=== RECOMMENDED SELECTION ===')
    # Story 1: pick diverse genres, lower energy
    seen_g = set()
    s1_picks = []
    for e in sorted(s1, key=lambda x: x[3], reverse=True):
        if e[7] not in seen_g and len(s1_picks) < 8:
            s1_picks.append(e); seen_g.add(e[7])
    print(f'Story 1: {len(s1_picks)} — {[e[0] for e in s1_picks]}')

    # Bridge: 1-2 tracks
    bridge_picks = sorted(bridge, key=lambda x: -x[3])[:2]
    print(f'Bridge: {[e[0] for e in bridge_picks]}')

    # Story 2: high energy, diverse keys
    seen_k = set()
    s2_picks = []
    for e in sorted(s2, key=lambda x: -x[3]):
        if e[5] not in seen_k and len(s2_picks) < 8:
            s2_picks.append(e); seen_k.add(e[5])
    print(f'Story 2: {len(s2_picks)} — {[e[0] for e in s2_picks]}')

    all_picks = [e[0] for e in s1_picks] + [e[0] for e in bridge_picks] + [e[0] for e in s2_picks]
    print(f'\nTOTAL: {len(all_picks)} tracks')
    print(f'IDs: {all_picks}')

asyncio.run(main())
