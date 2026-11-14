from app.retrieval.fusion import reciprocal_rank_fusion


def test_overlap_ranks_above_a_single_list_hit() -> None:
    fused = reciprocal_rank_fusion(
        [
            ["a", "b", "c"],
            ["b", "a", "d"],
        ],
        k=60,
    )
    scores = dict(fused)
    assert scores["b"] > scores["d"]
    assert scores["a"] == scores["b"]
    assert fused[0][0] in {"a", "b"}


def test_empty_leg_keeps_the_other_ranking() -> None:
    fused = reciprocal_rank_fusion([["a", "b"], []], k=60)
    assert fused == [("a", 1 / 61), ("b", 1 / 62)]


def test_both_empty() -> None:
    assert reciprocal_rank_fusion([[], []], k=60) == []


def test_duplicate_keeps_the_first_rank() -> None:
    fused = reciprocal_rank_fusion([["a", "a", "b"]], k=60)
    scores = dict(fused)
    assert scores["a"] == 1 / 61
    assert scores["b"] == 1 / 63


def test_phrase_weight_lifts_a_precise_hit_over_a_keyword_only_hit() -> None:
    fused = reciprocal_rank_fusion(
        [["kw-only"], ["precise"]],
        k=60,
        weights=[1.0, 2.0],
    )
    assert fused[0][0] == "precise"
    assert fused[0][1] == 2.0 / 61
    assert fused[1][0] == "kw-only"
