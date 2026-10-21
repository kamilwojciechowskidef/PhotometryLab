from contextlib import nullcontext

import pytest

from photolab.demo import make_ies
from photolab.indexing import candidate_file_ids, rank_catalogue
from photolab.parsers import load_photometry


class CandidateCursor:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None
        self.parameters = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, parameters):
        self.statement = statement
        self.parameters = parameters

    def fetchall(self):
        return self.rows


class CandidateConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.cursor_value


def test_candidate_lookup_uses_all_lsh_buckets_as_parameters(monkeypatch):
    cursor = CandidateCursor([(7,), (11,)])
    monkeypatch.setattr("photolab.indexing.psycopg.connect", lambda *args, **kwargs: CandidateConnection(cursor))
    reference = load_photometry("reference.ies", make_ies("Test", "oval"))
    feature, ids = candidate_file_ids("unused", reference, max_candidates=123)
    assert ids == [7, 11]
    assert cursor.parameters[0].startswith("shape-v2-")
    assert cursor.parameters[1:9] == feature.buckets
    assert cursor.parameters[9:17] == feature.buckets
    assert cursor.parameters[-1] == 123
    assert "bucket_0 = %s" in cursor.statement
    assert "ORDER BY" in cursor.statement


def test_candidate_lookup_rejects_unbounded_request():
    reference = load_photometry("reference.ies", make_ies("Test", "oval"))
    with pytest.raises(ValueError, match="20,000"):
        candidate_file_ids("unused", reference, max_candidates=20_001)


def test_exact_ranking_keeps_same_filename_when_records_differ(monkeypatch):
    reference = load_photometry("same.ies", make_ies("Reference", "narrow"))
    candidate = load_photometry("same.ies", make_ies("Candidate", "wide"))
    monkeypatch.setattr("photolab.indexing.candidate_file_ids", lambda *args, **kwargs: (None, [44]))
    monkeypatch.setattr("photolab.indexing.load_stored_photometries", lambda *args: {44: candidate})
    result = rank_catalogue("unused", reference, result_limit=10)
    assert result.candidates_examined == 1
    assert result.results[0][0] == 44
