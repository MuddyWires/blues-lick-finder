from lick_finder.embeddings import best_chunk_per_video, rrf
from lick_finder.search import filter_level


def chunk(video_id, start=0, level="intermediate"):
    return {"video_id": video_id, "start": start, "level": level}


def test_filter_level_keeps_matching_and_unclear():
    results = [chunk("a", level="beginner"), chunk("b", level="advanced"),
               chunk("c", level="unclear"), chunk("d", level="intermediate")]
    assert [r["video_id"] for r in filter_level(results, "beginner")] == ["a", "c"]


def test_filter_level_without_a_level_passes_everything():
    results = [chunk("a", level="beginner"), chunk("b", level="advanced")]
    assert filter_level(results, None) == results


def test_best_chunk_per_video_keeps_the_first_chunk_of_each_video():
    results = [chunk("a", 0), chunk("a", 1500), chunk("b", 0), chunk("a", 3000)]
    assert [(r["video_id"], r["start"]) for r in best_chunk_per_video(results)] == [
        ("a", 0), ("b", 0)
    ]


def test_best_chunk_per_video_limits_the_number_of_videos():
    results = [chunk(v) for v in "abcdefg"]
    assert len(best_chunk_per_video(results)) == 5


def test_rrf_ranks_chunks_found_by_both_lists_above_chunks_found_by_one():
    # c: ranks 3 and 1, b: ranks 2 and 3, a: rank 1 only, d: rank 2 only.
    list_one = [chunk("a"), chunk("b"), chunk("c")]
    list_two = [chunk("c"), chunk("d"), chunk("b")]
    assert [r["video_id"] for r in rrf([list_one, list_two])] == ["c", "b", "a", "d"]


def test_rrf_weight_lets_one_list_win_a_disagreement():
    keyword = [chunk("a"), chunk("b")]
    vector = [chunk("b"), chunk("a")]
    assert rrf([keyword, vector], weights=[0.25, 1.0])[0]["video_id"] == "b"
    assert rrf([keyword, vector], weights=[1.0, 0.25])[0]["video_id"] == "a"
