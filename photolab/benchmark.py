"""Reproducible synthetic benchmark for the feature-index algorithm."""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

import numpy as np

from .analysis import weighted_shape_vector
from .demo import make_ies
from .features import FEATURE_DIMENSIONS, FEATURE_VERSION, LSH_BANDS, feature_bucket_matrix
from .parsers import load_photometry


@dataclass(frozen=True)
class BenchmarkQuery:
    query_number: int
    candidates: int
    recall_at_k: float
    exact_ranking_seconds: float
    candidate_filter_seconds: float


@dataclass(frozen=True)
class BenchmarkReport:
    feature_version: str
    synthetic_only: bool
    corpus_size: int
    query_count: int
    top_k: int
    seed: int
    feature_generation_seconds: float
    feature_generation_per_second: float
    raw_vector_bytes: int
    raw_bucket_bytes: int
    queries: list[BenchmarkQuery]


def _prototypes() -> np.ndarray:
    """Use project demo distributions only as labelled mathematical seeds."""
    kinds = ("narrow", "narrow_similar", "wide", "batwing", "oval", "asymmetric")
    return np.asarray([
        weighted_shape_vector(load_photometry(f"benchmark-{kind}.ies", make_ies(kind, kind))).reshape(-1)
        for kind in kinds
    ], dtype=np.float32)


def _batches(corpus_size: int, seed: int, batch_size: int):
    """Yield deterministic vectors without retaining a corpus in RAM."""
    prototypes = _prototypes()
    generator = np.random.Generator(np.random.PCG64(seed))
    for start in range(0, corpus_size, batch_size):
        count = min(batch_size, corpus_size - start)
        labels = generator.integers(0, len(prototypes), size=count)
        noise = generator.normal(0.0, 0.035, size=(count, FEATURE_DIMENSIONS)).astype(np.float32)
        vectors = np.maximum(prototypes[labels] * (1.0 + noise), 0.0)
        yield start, vectors


def _bucket_matrix(vectors: np.ndarray) -> np.ndarray:
    return feature_bucket_matrix(vectors)


def _query_vectors(query_count: int, seed: int) -> np.ndarray:
    prototypes = _prototypes()
    generator = np.random.Generator(np.random.PCG64(seed + 1))
    labels = np.arange(query_count) % len(prototypes)
    noise = generator.normal(0.0, 0.02, size=(query_count, FEATURE_DIMENSIONS)).astype(np.float32)
    return np.maximum(prototypes[labels] * (1.0 + noise), 0.0)


def _top_k(scores: np.ndarray, identifiers: np.ndarray, matches: np.ndarray, top_k: int):
    positions = np.argpartition(scores, -top_k)[-top_k:]
    positions = positions[np.argsort(scores[positions])[::-1]]
    return scores[positions], identifiers[positions], matches[positions]


def run_benchmark(*, corpus_size: int = 10_000, query_count: int = 10, top_k: int = 20,
                  seed: int = 20261021, batch_size: int = 2_000) -> BenchmarkReport:
    """Measure LSH-candidate recall against exact cosine ranking on synthetic data."""
    if corpus_size < 1:
        raise ValueError("Corpus size must be positive.")
    if not 1 <= query_count <= 100:
        raise ValueError("Query count must be between 1 and 100.")
    if not 1 <= top_k <= corpus_size:
        raise ValueError("top_k must be between 1 and corpus size.")
    if batch_size < 1:
        raise ValueError("Batch size must be positive.")

    started = perf_counter()
    for _, vectors in _batches(corpus_size, seed, batch_size):
        _bucket_matrix(vectors)
    feature_seconds = perf_counter() - started
    reports: list[BenchmarkQuery] = []
    for number, query in enumerate(_query_vectors(query_count, seed), start=1):
        query_buckets = _bucket_matrix(query.reshape(1, -1))[0]
        query_norm = float(np.linalg.norm(query))
        best_scores = np.full(top_k, -np.inf, dtype=np.float64)
        best_ids = np.full(top_k, -1, dtype=np.int64)
        best_matches = np.zeros(top_k, dtype=bool)
        candidates = 0
        exact_started = perf_counter()
        filter_seconds = 0.0
        for start, vectors in _batches(corpus_size, seed, batch_size):
            norms = np.linalg.norm(vectors, axis=1)
            scores = (vectors @ query) / (norms * query_norm)
            filter_started = perf_counter()
            matches = np.any(_bucket_matrix(vectors) == query_buckets, axis=1)
            filter_seconds += perf_counter() - filter_started
            candidates += int(matches.sum())
            identifiers = np.arange(start, start + len(vectors), dtype=np.int64)
            best_scores, best_ids, best_matches = _top_k(
                np.concatenate((best_scores, scores)), np.concatenate((best_ids, identifiers)),
                np.concatenate((best_matches, matches)), top_k,
            )
        reports.append(BenchmarkQuery(number, candidates, float(best_matches.mean()),
                                      perf_counter() - exact_started, filter_seconds))
    return BenchmarkReport(
        feature_version=FEATURE_VERSION, synthetic_only=True, corpus_size=corpus_size,
        query_count=query_count, top_k=top_k, seed=seed,
        feature_generation_seconds=feature_seconds,
        feature_generation_per_second=corpus_size / feature_seconds if feature_seconds else float("inf"),
        raw_vector_bytes=corpus_size * FEATURE_DIMENSIONS * np.dtype("<f4").itemsize,
        raw_bucket_bytes=corpus_size * LSH_BANDS * np.dtype(np.uint16).itemsize,
        queries=reports,
    )


def write_report(report: BenchmarkReport, output: Path) -> tuple[Path, Path]:
    """Write a JSON summary and a per-query CSV beside it."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    json_path, csv_path = output.with_suffix(".json"), output.with_suffix(".csv")
    json_path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(asdict(report.queries[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(query) for query in report.queries)
    return json_path, csv_path


def _main() -> None:
    parser = argparse.ArgumentParser(description="Run a synthetic PhotometryLab feature-index benchmark.")
    parser.add_argument("--corpus-size", type=int, default=10_000)
    parser.add_argument("--queries", type=int, default=10)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=20261021)
    parser.add_argument("--output", type=Path, default=Path("benchmark/feature-index"))
    arguments = parser.parse_args()
    report = run_benchmark(corpus_size=arguments.corpus_size, query_count=arguments.queries,
                           top_k=arguments.top_k, batch_size=arguments.batch_size, seed=arguments.seed)
    json_path, csv_path = write_report(report, arguments.output)
    mean_recall = float(np.mean([query.recall_at_k for query in report.queries]))
    print(f"synthetic benchmark completed: mean recall@{report.top_k}={mean_recall:.3f}")
    print(f"reports: {json_path} and {csv_path}")


if __name__ == "__main__":
    _main()
