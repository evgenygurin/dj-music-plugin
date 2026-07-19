"""mix_cluster_workflow — find the most-mixable clusters/chains in a pool."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(playlist_id: int, limit: int) -> str:
    return f"""Find the most-mixable clusters inside playlist {playlist_id} and
seed a set from the strongest chain — a bottom-up alternative to building from
a template down.

Where build_set_workflow imposes an arc, this discovers which tracks already
mix beautifully and lets a set emerge from those affinities. Good for "what in
my crate goes together?" and for seeding a set core you then extend.

1. Resolve + ready the pool (track has no playlist_id column):
   local://playlists/{playlist_id}?include_tracks=true -> pool_ids = [...]
   dj_entity_list(entity="track_features", filters={{"track_id__in": pool_ids}},
              fields="scoring")
   — ensure level >= 3; analyze_library_workflow first for stragglers. Cap the
     pool at ~{limit} tracks (pairwise scoring is O(n^2)); if larger, pre-filter
     by BPM/mood band first to a coherent sub-pool.
   Use staged narrowing for big crates: hard filters (BPM corridor, analysis
   level, audio_file / physical MP3 when delivery is required) -> style/feature
   filters -> diversity cap -> pair scoring. If any filter is uncertain, read
   schema://entities/track_features before calling entity_list.
   Treat mood is a hint, not ground truth; confirm clusters with BPM, LUFS,
   energy_mean, spectral balance and Beatport genre metadata.

2. Score every pair in the pool:
   dj_transition_score_pool(track_ids=[...up to {limit}...])
   — returns the pairwise compatibility matrix (overall + per-component). Pairs
     at overall 0.0 are hard_rejects (BPM/key/energy clash) — un-mixable.
   dj_ui_score_pool_matrix(track_ids=[...]) — visual N x N heatmap (Prefab
     clients); the bright diagonal-adjacent cells are your clusters.

3. Read the clusters off the matrix:
   - A CLUSTER = a group of tracks mutually scoring high (e.g. > 0.7). These
     share BPM band + compatible Camelot keys + similar energy.
   - A CHAIN  = an ordered path through high-scoring pairs with no hard_reject
     step. The longest clean chain is your set spine.
   - Isolated tracks (high score to nobody) are mix-orphans — park them.
   - For raw/hypnotic or atonal chains, use groove-first interpretation:
     stable BPM, low-end discipline, percussion density and LUFS continuity may
     matter more than a neat Camelot path.
   - If Beatport genre and classifier mood conflict, keep both labels in the
     review notes instead of forcing the cluster into one genre.

4. Cross-check against history + taste (optional but recommended):
   local://transition_history/best_pairs?limit=20 — pairs that mixed well
   before; if any sit in your cluster, anchor on them.
   dj_entity_list(entity="track_affinity", filters={{"avg_score__gte": 0.7}})
   — learned good pairings to prefer.

5. Order the best chain and persist it as a set core:
   dj_sequence_optimize(track_ids=[<chain ids>], algorithm="greedy")
   — greedy is fine here: the pool is already mutually compatible, so a nearest
     -neighbour walk preserves the clusters. Use "ga" if you want an arc on top.
   dj_entity_create(entity="set_version", data={{"set_id": <id>,
                "track_order": [...], "label": "cluster_core"}})

6. Grow from the core if needed: run extend_set_workflow to lengthen the chain,
   or crate_digging_workflow to source new tracks that bridge two clusters.

Return: {{"playlist_id": {playlist_id}, "clusters": [[...ids...], ...],
         "best_chain": [...], "orphans": [...], "set_id": ...,
         "version_id": ...}}.
"""


@prompt(
    name="mix_cluster_workflow",
    description="Find mutually-mixable clusters/chains in a pool; seed a set from the best chain.",
    tags={"namespace:workflow", "set_building", "analysis"},
    meta=PROMPT_META,
)
def mix_cluster_workflow(playlist_id: int, limit: int = 30) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(playlist_id, limit))],
        description=f"Mix-cluster discovery on playlist {playlist_id} (<= {limit} tracks).",
    )
