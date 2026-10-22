import json

import pytest

from photolab.database_benchmark import run_database_benchmark, write_database_report
from photolab.features import FEATURE_VERSION


class Cursor:
    def __init__(self):
        self.calls = []
        self.stage = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, parameters=None):
        self.calls.append((statement, parameters))
        self.stage += 1

    def fetchone(self):
        return (12, 10, 8)

    def fetchall(self):
        if self.stage == 2:
            return [("feature_sets", 1000, 800, 200)]
        if self.stage == 3:
            return [(5, 1, 2, 3, 4, 5, 6, 7, 8)]
        return [(1,), (2,)]


class Connection:
    def __init__(self, cursor):
        self.cursor_value = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.cursor_value


def test_database_benchmark_is_read_only_and_parameterized(monkeypatch):
    cursor = Cursor()
    received = {}

    def connect(*args, **kwargs):
        received.update(kwargs)
        return Connection(cursor)

    monkeypatch.setattr("photolab.database_benchmark.psycopg.connect", connect)
    report = run_database_benchmark("unused", sample_size=1, max_candidates=50)
    assert received["autocommit"] is True
    assert received["options"] == "-c default_transaction_read_only=on"
    assert (report.stored_files, report.stored_photometries, report.current_features) == (12, 10, 8)
    assert report.relations[0].index_bytes == 200
    assert report.candidate_queries[0].candidates == 2
    statement, params = cursor.calls[-1]
    assert "bucket_0 = %s" in statement
    assert params == (FEATURE_VERSION, 1, 2, 3, 4, 5, 6, 7, 8, 1, 2, 3, 4, 5, 6, 7, 8, 50)


def test_database_benchmark_writes_reports(tmp_path):
    from photolab.database_benchmark import DatabaseBenchmarkReport
    value = DatabaseBenchmarkReport(FEATURE_VERSION, 1, 1, 1, [], [])
    json_path, csv_path = write_database_report(value, tmp_path / "database")
    assert json.loads(json_path.read_text(encoding="utf-8"))["current_features"] == 1
    assert csv_path.read_text(encoding="utf-8").startswith("file_id,candidates,seconds")


@pytest.mark.parametrize("arguments", [
    {"sample_size": 0}, {"sample_size": 101}, {"max_candidates": 20_001},
])
def test_database_benchmark_validates_bounds(arguments):
    with pytest.raises(ValueError):
        run_database_benchmark("unused", **arguments)
