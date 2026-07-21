"""检索：过阈过滤 + 混合检索入口。"""

from unittest.mock import MagicMock, patch

from src.services.retrieval import clear_query_embed_cache, retrieve


def test_retrieve_filters_below_threshold():
    clear_query_embed_cache()
    hits = [
        {"id": "a", "score": 0.9, "text": "a", "metadata": {}},
        {"id": "b", "score": 0.1, "text": "b", "metadata": {}},
    ]
    vs = MagicMock()
    vs.search.return_value = hits
    vs.get_by_course_id.return_value = []
    with patch(
        "src.services.retrieval._cached_query_vec", return_value=(0.1, 0.2)
    ):
        out = retrieve(
            "三重积分",
            vs,
            "course-default",
            top_k=5,
            score_threshold=0.25,
        )
    assert len(out) == 1
    assert out[0]["text"] == "a"
    vs.search.assert_called_once()


def test_retrieve_empty_query():
    vs = MagicMock()
    assert retrieve("   ", vs, "course-default") == []
    vs.search.assert_not_called()
