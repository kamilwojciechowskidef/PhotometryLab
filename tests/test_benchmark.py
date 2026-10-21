import json

import pytest

from photolab.benchmark import run_benchmark, write_report


def test_synthetic_benchmark_is_reproducible_and_bounded():
    first = run_benchmark(corpus_size=30, query_count=2, top_k=3, seed=7, batch_size=10)
    second = run_benchmark(corpus_size=30, query_count=2, top_k=3, seed=7, batch_size=10)
    assert first.synthetic_only is True
    assert first.raw_vector_bytes == 30 * 684 * 4
    assert first.raw_bucket_bytes == 30 * 8 * 2
    assert [query.candidates for query in first.queries] == [query.candidates for query in second.queries]
    assert [query.recall_at_k for query in first.queries] == [query.recall_at_k for query in second.queries]
    assert all(0 <= query.recall_at_k <= 1 for query in first.queries)


def test_benchmark_writes_json_and_csv_reports(tmp_path):
    report = run_benchmark(corpus_size=12, query_count=1, top_k=2, seed=2, batch_size=6)
    json_path, csv_path = write_report(report, tmp_path / "result")
    assert json.loads(json_path.read_text(encoding="utf-8"))["synthetic_only"] is True
    assert "recall_at_k" in csv_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("arguments", [
    {"corpus_size": 0}, {"corpus_size": 5, "top_k": 6}, {"corpus_size": 5, "query_count": 101},
])
def test_benchmark_validates_bounds(arguments):
    with pytest.raises(ValueError):
        run_benchmark(**arguments)
