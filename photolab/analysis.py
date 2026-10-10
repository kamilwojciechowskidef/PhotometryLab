"""Reproducible comparison algorithms on an aligned C-gamma grid."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .models import Photometry

# Coverage shared by typical 0..90 deg and 0..180 deg reports.
C_GRID = np.arange(0.0, 360.0, 10.0)  # 36 planes
GAMMA_GRID = np.arange(0.0, 90.01, 5.0)  # 19 values


def sample(item: Photometry, c_angles: np.ndarray, gamma_angles: np.ndarray,
           absolute: bool = False) -> np.ndarray:
    """Interpolate native data without extrapolating missing gamma measurements.

    Returns [C, gamma], using the real symmetry defined in the input format.
    """
    c_angles = np.asarray(c_angles, dtype=float).reshape(-1)
    gamma_angles = np.asarray(gamma_angles, dtype=float).reshape(-1)
    if (gamma_angles.min() < item.gamma_angles[0] - 1e-6 or
            gamma_angles.max() > item.gamma_angles[-1] + 1e-6):
        raise ValueError("Dane nie pokrywają wymaganego zakresu gamma. Nie ekstrapolujemy pomiarów.")
    if absolute and item.to_cd is None:
        raise ValueError("Brak danych do wiarygodnego przeliczenia na cd.")
    # Interpolation along gamma at native C planes.
    interpolated = np.stack([np.interp(gamma_angles, item.gamma_angles, row)
                             for row in item.intensity])
    azimuth = np.mod(c_angles, 360.0)
    if item.symmetry == "radial":
        result = np.tile(interpolated[0], (len(azimuth), 1))
    else:
        if item.symmetry == "quadrants":
            mod = np.mod(azimuth, 180.0)
            folded = np.minimum(mod, 180.0 - mod)
        elif item.symmetry == "plane0":
            folded = np.minimum(azimuth, 360.0 - azimuth)
        elif item.symmetry == "plane90":
            folded = np.where(azimuth < 90, 180-azimuth, np.where(azimuth > 270, 540-azimuth, azimuth))
        elif item.symmetry == "none":
            folded = azimuth
        else:
            raise ValueError(f"Nieznana symetria: {item.symmetry}")
        if item.symmetry == "none":
            x = np.r_[item.c_angles, item.c_angles[0] + 360.0]
            y = np.vstack([interpolated, interpolated[:1]])
        else:
            x, y = item.c_angles, interpolated
        result = np.stack([np.interp(folded, x, y[:, k]) for k in range(len(gamma_angles))], axis=1)
    return result * (item.to_cd if absolute else 1.0)


def shape_matrix(item: Photometry) -> np.ndarray:
    """Each file is scaled to its own maximum, ignoring lamp flux differences."""
    a = sample(item, C_GRID, GAMMA_GRID)
    maximum = a.max()
    if maximum <= 0:
        raise ValueError("Brak emisji w dolnej półprzestrzeni (0–90°).")
    return a / maximum


def _angular_weights() -> np.ndarray:
    # Solid-angle weight sin(gamma), normalized over the sampled domain.
    w = np.broadcast_to(np.sin(np.deg2rad(GAMMA_GRID))[None, :], (len(C_GRID), len(GAMMA_GRID)))
    return w / w.sum()


@dataclass
class Similarity:
    filename: str
    cosine: float           # [-1, 1], typically [0, 1] for nonnegative intensities
    rmse: float             # lower is better, max-normalized intensities
    rotation_deg: int       # candidate azimuth shift yielding best alignment


def compare(reference: Photometry, candidate: Photometry, allow_rotation: bool = True) -> Similarity:
    """Weighted cosine and normalized RMSE. Searches C rotations in steps of 10°."""
    x, y = shape_matrix(reference), shape_matrix(candidate)
    w = _angular_weights()
    nx = np.sqrt(np.sum(w * x*x))
    best: Similarity | None = None
    for shift in (range(len(C_GRID)) if allow_rotation else [0]):
        z = np.roll(y, shift, axis=0)
        nz = np.sqrt(np.sum(w * z*z))
        cos = float(np.sum(w * x * z) / (nx * nz))
        rms = float(np.sqrt(np.sum(w * (x-z)**2)))
        # Choose minimum error, then cosine; stable 0 degree on exact ties.
        result = Similarity(candidate.filename, cos, rms, int(C_GRID[shift]))
        if best is None or (result.rmse < best.rmse - 1e-12) or (
            abs(result.rmse-best.rmse) <= 1e-12 and result.cosine > best.cosine + 1e-12
        ):
            best = result
    assert best is not None
    return best


def find_similar(reference: Photometry, candidates: Sequence[Photometry],
                 allow_rotation: bool = True) -> list[Similarity]:
    results = [compare(reference, c, allow_rotation) for c in candidates if c.filename != reference.filename]
    return sorted(results, key=lambda x: (x.rmse, -x.cosine, x.filename))


def estimated_downward_lumens(item: Photometry) -> float | None:
    """Numerical lower-hemisphere flux from Type-C luminous intensity; not a certified value."""
    if not item.covers_downward or item.to_cd is None:
        return None
    cs = np.arange(0, 361, 5.0)
    gs = np.arange(0, 91, 2.5)
    intensity_cd = sample(item, cs, gs, absolute=True)
    theta = np.deg2rad(gs)
    az = np.deg2rad(cs)
    integrand = intensity_cd * np.sin(theta)[None, :]
    integrate = getattr(np, "trapezoid", np.trapz)
    return float(integrate(integrate(integrand, theta, axis=1), az, axis=0))


def embedding(items: Sequence[Photometry], clusters: int = 3) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, np.ndarray]:
    """PCA + KMeans on photometry shapes. Optional IsolationForest at n>=8.

    Return XY, cluster labels, anomaly flags or None, explained variance ratio.
    Machine learning is exploratory; no performance claims on synthetic sample data.
    """
    if len(items) < 3:
        raise ValueError("Analiza ML wymaga przynajmniej 3 opraw.")
    from sklearn.decomposition import PCA
    from sklearn.cluster import KMeans
    from sklearn.ensemble import IsolationForest
    x = np.array([shape_matrix(item).flatten() for item in items])
    # Weight the angular features by actual solid-angle contribution.
    x *= np.sqrt(_angular_weights().flatten())[None, :]
    pca = PCA(n_components=2, random_state=42)
    xy = pca.fit_transform(x)
    k = min(max(2, clusters), len(items)-1)
    labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(x)
    anomalies = None
    if len(items) >= 8:
        anomalies = IsolationForest(n_estimators=100, contamination=0.15,
                                    random_state=42).fit_predict(x) == -1
    return xy, labels, anomalies, pca.explained_variance_ratio_
