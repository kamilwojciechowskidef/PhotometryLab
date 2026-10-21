"""Incremental feature generation and approximate-candidate retrieval."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import psycopg

from .analysis import Similarity, compare
from .database import DatabaseError, load_stored_photometries, store_feature
from .features import FEATURE_VERSION, FeatureSet, build_feature
from .models import Photometry
from .storage import photometry_from_data


@dataclass(frozen=True)
class IndexingResult:
    examined: int
    indexed: int
    invalid: int


@dataclass(frozen=True)
class CatalogueSearch:
    candidates_examined: int
    results: list[tuple[int, Similarity]]


def build_pending_features(
    url: str,
    *,
    batch_size: int = 200,
    max_records: int | None = None,
    progress: Callable[[IndexingResult], None] | None = None,
) -> IndexingResult:
    """Index unindexed records in bounded transactions.

    Invalid stored records are recorded once in ``feature_generation_errors`` and
    excluded from later retries until an explicit data-repair workflow exists.
    """
    if not 1 <= batch_size <= 1_000:
        raise ValueError("Batch size must be between 1 and 1,000.")
    if max_records is not None and max_records < 1:
        raise ValueError("Maximum records must be positive.")
    result = IndexingResult(examined=0, indexed=0, invalid=0)
    try:
        with psycopg.connect(url, connect_timeout=10) as connection:
            while max_records is None or result.examined < max_records:
                request_size = min(batch_size, max_records - result.examined) if max_records else batch_size
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT p.file_id, p.data
                        FROM photolab.photometries p
                        LEFT JOIN photolab.feature_sets f
                          ON f.file_id = p.file_id AND f.algorithm_version = %s
                        LEFT JOIN photolab.feature_generation_errors e
                          ON e.file_id = p.file_id AND e.algorithm_version = %s
                        WHERE f.file_id IS NULL AND e.file_id IS NULL
                        ORDER BY p.file_id
                        LIMIT %s
                        """,
                        (FEATURE_VERSION, FEATURE_VERSION, request_size),
                    )
                    rows = cursor.fetchall()
                    if not rows:
                        break
                    indexed = invalid = 0
                    for file_id, data in rows:
                        try:
                            store_feature(cursor, file_id, build_feature(photometry_from_data(data)))
                            indexed += 1
                        except (TypeError, ValueError, KeyError, IndexError) as error:
                            cursor.execute(
                                """
                                INSERT INTO photolab.feature_generation_errors
                                    (file_id, algorithm_version, message)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (file_id, algorithm_version)
                                DO UPDATE SET message = EXCLUDED.message,
                                              recorded_at = CURRENT_TIMESTAMP
                                """,
                                (file_id, FEATURE_VERSION, str(error)),
                            )
                            invalid += 1
                connection.commit()
                result = IndexingResult(result.examined + len(rows), result.indexed + indexed,
                                        result.invalid + invalid)
                if progress:
                    progress(result)
    except psycopg.Error as error:
        raise DatabaseError("PostgreSQL feature indexing failed.") from error
    return result


def candidate_file_ids(
    url: str,
    reference: Photometry,
    *,
    max_candidates: int = 10_000,
) -> tuple[FeatureSet, list[int]]:
    """Return an LSH candidate pool, never a claim of exhaustive nearest neighbours."""
    if not 1 <= max_candidates <= 20_000:
        raise ValueError("Candidate limit must be between 1 and 20,000.")
    feature = build_feature(reference)
    bucket_conditions = " OR ".join(f"bucket_{index} = %s" for index in range(8))
    score = " + ".join(f"(bucket_{index} = %s)::int" for index in range(8))
    try:
        with psycopg.connect(url, connect_timeout=10) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT file_id
                    FROM photolab.feature_sets
                    WHERE algorithm_version = %s AND ({bucket_conditions})
                    ORDER BY ({score}) DESC, file_id
                    LIMIT %s
                    """,
                    (FEATURE_VERSION, *feature.buckets, *feature.buckets, max_candidates),
                )
                return feature, [row[0] for row in cursor.fetchall()]
    except psycopg.Error as error:
        raise DatabaseError("PostgreSQL candidate lookup failed.") from error


def rank_catalogue(
    url: str,
    reference: Photometry,
    *,
    max_candidates: int = 10_000,
    result_limit: int = 50,
    allow_rotation: bool = True,
) -> CatalogueSearch:
    """Rank only retrieved candidates with the existing exact comparison code."""
    if not 1 <= result_limit <= 500:
        raise ValueError("Result limit must be between 1 and 500.")
    _, candidate_ids = candidate_file_ids(url, reference, max_candidates=max_candidates)
    candidates = load_stored_photometries(url, candidate_ids)
    ranked = [
        (file_id, compare(reference, item, allow_rotation))
        for file_id, item in candidates.items()
    ]
    ranked.sort(key=lambda value: (value[1].rmse, -value[1].cosine, value[0]))
    return CatalogueSearch(candidates_examined=len(candidates), results=ranked[:result_limit])


def _main() -> None:
    """Run bounded backfill outside Streamlit, suitable for a scheduled worker."""
    import argparse
    from .database import database_url

    parser = argparse.ArgumentParser(description="Build PhotometryLab feature index batches.")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--max-records", type=int, default=10_000,
                        help="Records per invocation; use a scheduler for the full catalogue.")
    arguments = parser.parse_args()
    result = build_pending_features(
        database_url(), batch_size=arguments.batch_size, max_records=arguments.max_records,
        progress=lambda state: print(
            f"examined={state.examined} indexed={state.indexed} invalid={state.invalid}",
            flush=True,
        ),
    )
    print(f"completed: examined={result.examined} indexed={result.indexed} invalid={result.invalid}")


if __name__ == "__main__":
    _main()
