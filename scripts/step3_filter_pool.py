"""Step 3: Query features for existing candidates, filter pool to ~20 tracks.

Run: uv run python scripts/step3_filter_pool.py
"""
import asyncio
import sys

from fastmcp import Client
from app.server.app import build_mcp_server

# Candidate track IDs
CANDIDATE_IDS = [161,164,172,173,180,184,214,263,291,313,451,551,554,562,592,686]

async def main():
    mcp = build_mcp_server()
    async with Client(mcp) as client:
        r = await client.call_tool("entity_list", {
            "entity": "track_features",
            "filters": {"track_id__in": CANDIDATE_IDS},
            "limit": 20,
            "fields": "summary",
        })
        data = r.structured_content
        items = data.get("items", [])
        print(f"Found features for {len(items)}/{len(CANDIDATE_IDS)} existing tracks:\n")

        for item in items:
            tid = item.get("track_id")
            bpm = item.get("bpm", "?")
            energy = item.get("energy_mean", "?")
            lufs = item.get("integrated_lufs", "?")
            key = item.get("key_code", "?")
            level = item.get("analysis_level", "?")
            centroid = item.get("spectral_centroid_hz", "?")
            print(f"  track={tid:>5}  BPM={bpm}  energy={energy}  LUFS={lufs}  key={key}  level={level}  centroid={centroid}")

        if not items:
            print("No features found for any candidates!")
            print("Need to run analysis first.")


if __name__ == "__main__":
    asyncio.run(main())
