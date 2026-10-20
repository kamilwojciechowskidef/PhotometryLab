"""Transparent data model; no implicit photometric unit conversion."""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class Photometry:
    filename: str
    format: str
    manufacturer: str
    luminaire: str
    c_angles: np.ndarray
    gamma_angles: np.ndarray
    intensity: np.ndarray  # rows are C planes, columns are gamma angles
    symmetry: str           # none, radial, quadrants, plane0, plane90
    unit: str               # cd or cd/klm
    to_cd: Optional[float]  # multiplier for intensity matrix; None if unknown
    power_w: Optional[float] = None
    source_flux_lm: Optional[float] = None
    warnings: list[str] = field(default_factory=list)

    @property
    def covers_downward(self) -> bool:
        return bool(self.gamma_angles[0] <= 1e-7 and self.gamma_angles[-1] >= 90 - 1e-7)

    def validate(self) -> "Photometry":
        self.c_angles = np.asarray(self.c_angles, dtype=float)
        self.gamma_angles = np.asarray(self.gamma_angles, dtype=float)
        self.intensity = np.asarray(self.intensity, dtype=float)
        if self.c_angles.ndim != 1 or self.gamma_angles.ndim != 1:
            raise ValueError("Angle arrays must be one-dimensional.")
        if self.intensity.shape != (len(self.c_angles), len(self.gamma_angles)):
            raise ValueError("The intensity matrix shape does not match the angle grid.")
        if not len(self.c_angles) or len(self.gamma_angles) < 2:
            raise ValueError("Too few angular points.")
        for array in (self.c_angles, self.gamma_angles, self.intensity):
            if not np.isfinite(array).all():
                raise ValueError("The file contains NaN or infinity.")
        if np.any(self.intensity < 0):
            raise ValueError("The file contains negative intensities.")
        if np.max(self.intensity) <= 0:
            raise ValueError("All intensity values are zero.")
        if np.any(np.diff(self.gamma_angles) <= 0):
            raise ValueError("Gamma angles are not strictly increasing.")
        if self.gamma_angles[0] < -1e-5 or self.gamma_angles[-1] > 180 + 1e-5:
            raise ValueError("Gamma angles are outside the 0–180° range (Type C).")
        if np.any(self.c_angles < -1e-5) or np.any(self.c_angles > 360 + 1e-5):
            raise ValueError("C angles are outside the 0–360° range.")
        if np.any(np.diff(self.c_angles) <= 0):
            raise ValueError("C angles are not strictly increasing.")
        if self.symmetry not in {"none", "radial", "quadrants", "plane0", "plane90"}:
            raise ValueError("Unknown symmetry.")
        if self.to_cd is not None and (not np.isfinite(self.to_cd) or self.to_cd <= 0):
            raise ValueError("Invalid conversion factor to cd.")
        return self
