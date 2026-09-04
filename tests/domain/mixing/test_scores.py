from app.domain.mixing.scores import DimensionScore, MusicalScore, rank_scores


def test_correlated_groups_are_normalized_before_weighted_total() -> None:
    score = MusicalScore(
        dimensions=(
            DimensionScore("spectrum", 1.0, group="spectral"),
            DimensionScore("low_end", 1.0, group="spectral"),
            DimensionScore("groove", 0.0, group="groove"),
        )
    )
    assert score.grouped_value("spectral") == 1.0
    assert score.total() == 1.0


def test_hard_rejected_candidates_are_not_ranked() -> None:
    accepted = MusicalScore((DimensionScore("harmony", 0.5),))
    rejected = MusicalScore((DimensionScore("harmony", 1.0),), hard_rejected=True)
    assert rank_scores((("accepted", accepted), ("rejected", rejected))) == ("accepted",)
