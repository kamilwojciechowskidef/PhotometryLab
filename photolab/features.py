"""Versioned, rotation-invariant coarse features for scalable candidate retrieval."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from functools import lru_cache

import numpy as np

from .analysis import C_GRID, GAMMA_GRID, weighted_shape_vector
from .models import Photometry


FEATURE_VERSION = "shape-v2-c36-g19-maxnorm-weighted-canonical-centered-lsh96"
FEATURE_DIMENSIONS = len(C_GRID) * len(GAMMA_GRID)
LSH_BANDS = 8
LSH_BITS_PER_BAND = 12
LSH_SEED = 20261021


@dataclass(frozen=True)
class FeatureSet:
    """A reproducible candidate-retrieval feature, not a final similarity score."""

    vector: np.ndarray
    l2_norm: float
    canonical_rotation: int
    digest: str
    buckets: tuple[int, ...]


@lru_cache(maxsize=1)
def _projections() -> np.ndarray:
    """Fixed ±1 hyperplanes; changing them requires a new FEATURE_VERSION."""
    generator = np.random.Generator(np.random.PCG64(LSH_SEED))
    return generator.choice(
        np.array([-1.0, 1.0], dtype=np.float32),
        size=(LSH_BANDS * LSH_BITS_PER_BAND, FEATURE_DIMENSIONS),
    )


def _canonical_vector(item: Photometry) -> tuple[np.ndarray, int]:
    matrix = weighted_shape_vector(item).astype("<f4", copy=False)
    choices = [(np.roll(matrix, shift, axis=0).tobytes(), shift) for shift in range(len(C_GRID))]
    _, shift = min(choices)
    return np.ascontiguousarray(np.roll(matrix, shift, axis=0).reshape(-1), dtype="<f4"), int(C_GRID[shift])


def feature_bucket_matrix(vectors: np.ndarray) -> np.ndarray:
    """Return LSH codes after centering each vector for more selective signs."""
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim == 1:
        vectors = vectors.reshape(1, -1)
    if vectors.ndim != 2 or vectors.shape[1] != FEATURE_DIMENSIONS:
        raise ValueError(f"Feature vector must contain {FEATURE_DIMENSIONS} values.")
    centered = vectors - vectors.mean(axis=1, keepdims=True)
    bits = (centered @ _projections().T >= 0).reshape(-1, LSH_BANDS, LSH_BITS_PER_BAND)
    weights = (1 << np.arange(LSH_BITS_PER_BAND, dtype=np.uint16))[None, None, :]
    return np.sum(bits.astype(np.uint16) * weights, axis=2, dtype=np.uint16)


def feature_buckets(vector: np.ndarray) -> tuple[int, ...]:
    """Return reproducible LSH bucket codes for one flattened feature vector."""
    return tuple(int(value) for value in feature_bucket_matrix(vector)[0])


def build_feature(item: Photometry) -> FeatureSet:
    """Build deterministic features from the same normalized shape as comparison."""
    vector, rotation = _canonical_vector(item)
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm <= 0:
        raise ValueError("Cannot create a feature for an empty distribution.")
    digest = sha256(FEATURE_VERSION.encode("ascii") + vector.tobytes()).hexdigest()
    return FeatureSet(vector=vector, l2_norm=norm, canonical_rotation=rotation,
                      digest=digest, buckets=feature_buckets(vector))
