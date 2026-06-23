#!/usr/bin/env python3
"""POC: classify a track's Discogs style via essentia genre_discogs400.

Audio -> Discogs-EffNet embeddings -> genre_discogs400 head -> 400 styles.
The head is trained on 2M+ Discogs-annotated tracks (human ground truth),
so the top electronic style is a reliable subgenre label from audio alone.

Run on the VM (genre venv with essentia-tensorflow):
    /root/genre/venv/bin/python scripts/discogs_genre_test.py <audio.mp3>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from essentia.standard import (  # type: ignore
    MonoLoader,
    TensorflowPredict2D,
    TensorflowPredictEffnetDiscogs,
)

MODELS = Path("/root/genre/models")
EFFNET = str(MODELS / "discogs-effnet-bs64-1.pb")
HEAD = str(MODELS / "genre_discogs400-discogs-effnet-1.pb")
LABELS = json.loads((MODELS / "genre_discogs400-discogs-effnet-1.json").read_text())["classes"]


def classify(path: str, top_k: int = 8) -> list[tuple[str, float]]:
    # genre_discogs400 expects 16 kHz mono.
    audio = MonoLoader(filename=path, sampleRate=16000, resampleQuality=4)()
    embeddings = TensorflowPredictEffnetDiscogs(graphFilename=EFFNET, output="PartitionedCall:1")(
        audio
    )
    preds = TensorflowPredict2D(
        graphFilename=HEAD,
        input="serving_default_model_Placeholder",
        output="PartitionedCall:0",
    )(embeddings)
    mean = np.asarray(preds).mean(axis=0)  # [400]
    order = np.argsort(mean)[::-1][:top_k]
    return [(LABELS[i], float(mean[i])) for i in order]


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: discogs_genre_test.py <audio.mp3>")
        sys.exit(1)
    path = sys.argv[1]
    print(f"classifying: {path}")
    results = classify(path)
    print("=== top styles ===")
    for label, prob in results:
        print(f"  {prob:6.3f}  {label}")
    # electronic-only view (the techno subgenre we care about)
    elec = [(l, p) for l, p in results if l.startswith("Electronic")]
    if elec:
        print(f"=== top electronic style: {elec[0][0]} ({elec[0][1]:.3f}) ===")


if __name__ == "__main__":
    main()
