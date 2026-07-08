from __future__ import annotations

import numpy as np
import numpy.typing as npt


def cosine_similarity(a: npt.NDArray[np.float64], b: npt.NDArray[np.float64]) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-10 or nb < 1e-10:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def cosine_similarity_bulk(
    matrix: npt.NDArray[np.float64], ia: npt.NDArray[np.int64], ib: npt.NDArray[np.int64]
) -> npt.NDArray[np.float64]:
    a = matrix[ia]
    b = matrix[ib]
    dot = np.sum(a * b, axis=1)
    norm_a = np.sqrt(np.sum(a * a, axis=1))
    norm_b = np.sqrt(np.sum(b * b, axis=1))
    denom = norm_a * norm_b
    safe_denom = np.where(denom == 0, 1.0, denom)
    cos = np.where(denom == 0, -1.0, dot / safe_denom)
    mapped = np.clip((cos + 1.0) / 2.0, 0.0, 1.0)
    return mapped
