"""Read-only PostgreSQL measurements for the PhotometryLab feature index."""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from time import perf_counter

import psycopg

from .database import DatabaseError, database_url
from .features import FEATURE_VERSION


@dataclass(frozen=True)
class RelationMetrics:
    name: str
    total_bytes: int
    table_bytes: int
    index_bytes: int


@dataclass(frozen=True)
class CandidateMeasurement:
    file_id: int
    candidates: int
    seconds: float


@dataclass(frozen=True)
class DatabaseBenchmarkReport:
    feature_version: str
    stored_files: int
    stored_photometries: int
    current_features: int
    relations: list[RelationMetrics]
    candidate_queries: list[CandidateMeasurement]

    @property
    def mean_candidate_seconds(self) -> float | None:
        if not self.candidate_queries:
            return None
        return mean(item.seconds for item in self.candidate_queries)


_CANDIDATE_SQL = """
    SELECT file_id
    FROM photolab.feature_sets
    WHERE algorithm_version = %s AND (
        bucket_0 = %s OR bucket_1 = %s OR bucket_2 = %s OR bucket_3 = %s
        OR bucket_4 = %s OR bucket_5 = %s OR bucket_6 = %s OR bucket_7 = %s
    )
    ORDER BY (
        (bucket_0 = %s)::int + (bucket_1 = %s)::int + (bucket_2 = %s)::int + (bucket_3 = %s)::int
        + (bucket_4 = %s)::int + (bucket_5 = %s)::int + (bucket_6 = %s)::int + (bucket_7 = %s)::int
    ) DESC, file_id
    LIMIT %s
"""


def run_database_benchmark(
    url: str, *, sample_size: int = 10, max_candidates: int = 10_000,
) -> DatabaseBenchmarkReport:
    """Measure existing catalogue relations and candidate queries without writes.

    The connection asks PostgreSQL to make every transaction read-only. This is
    a diagnostic for an existing catalogue, not a loader or a schema migration.
    """
    if not 1 <= sample_size <= 100:
        raise ValueError("Sample size must be between 1 and 100.")
    if not 1 <= max_candidates <= 20_000:
        raise ValueError("Candidate limit must be between 1 and 20,000.")
    try:
        with psycopg.connect(
            url, connect_timeout=10, autocommit=True,
            options="-c default_transaction_read_only=on",
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT
                           (SELECT count(*) FROM photolab.photometry_files),
                           (SELECT count(*) FROM photolab.photometries),
                           (SELECT count(*) FROM photolab.feature_sets WHERE algorithm_version = %s)
                    """,
                    (FEATURE_VERSION,),
                )
                stored_files, stored_photometries, current_features = cursor.fetchone()
                cursor.execute(
                    """SELECT c.relname, pg_total_relation_size(c.oid),
                                      pg_relation_size(c.oid), pg_indexes_size(c.oid)
                       FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                       WHERE n.nspname = 'photolab'
                         AND c.relname IN ('photometry_files', 'photometries', 'feature_sets')
                       ORDER BY c.relname"""
                )
                relations = [RelationMetrics(*row) for row in cursor.fetchall()]
                cursor.execute(
                    """SELECT file_id, bucket_0, bucket_1, bucket_2, bucket_3,
                                      bucket_4, bucket_5, bucket_6, bucket_7
                       FROM photolab.feature_sets WHERE algorithm_version = %s
                       ORDER BY file_id LIMIT %s""",
                    (FEATURE_VERSION, sample_size),
                )
                samples = cursor.fetchall()
                measurements: list[CandidateMeasurement] = []
                for file_id, *buckets in samples:
                    started = perf_counter()
                    cursor.execute(_CANDIDATE_SQL, (FEATURE_VERSION, *buckets, *buckets, max_candidates))
                    candidates = len(cursor.fetchall())
                    measurements.append(CandidateMeasurement(file_id, candidates, perf_counter() - started))
    except psycopg.Error as error:
        raise DatabaseError("Read-only PostgreSQL benchmark failed.") from error
    return DatabaseBenchmarkReport(
        feature_version=FEATURE_VERSION, stored_files=stored_files,
        stored_photometries=stored_photometries, current_features=current_features,
        relations=relations, candidate_queries=measurements,
    )


def write_database_report(report: DatabaseBenchmarkReport, output: Path) -> tuple[Path, Path]:
    """Write JSON summary and CSV records without writing to PostgreSQL."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    json_path, csv_path = output.with_suffix(".json"), output.with_suffix(".csv")
    payload = asdict(report) | {"mean_candidate_seconds": report.mean_candidate_seconds}
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("file_id", "candidates", "seconds"))
        writer.writeheader()
        writer.writerows(asdict(item) for item in report.candidate_queries)
    return json_path, csv_path


def _main() -> None:
    parser = argparse.ArgumentParser(description="Measure an existing PhotometryLab PostgreSQL catalogue read-only.")
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--max-candidates", type=int, default=10_000)
    parser.add_argument("--output", type=Path, default=Path("benchmark/database"))
    arguments = parser.parse_args()
    report = run_database_benchmark(database_url(), sample_size=arguments.samples,
                                    max_candidates=arguments.max_candidates)
    json_path, csv_path = write_database_report(report, arguments.output)
    average = "n/a" if report.mean_candidate_seconds is None else f"{report.mean_candidate_seconds:.6f}s"
    print(f"current features: {report.current_features}; mean candidate query: {average}")
    print(f"reports: {json_path} and {csv_path}")


if __name__ == "__main__":
    _main()
