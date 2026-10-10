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
            raise ValueError("Tablice kątów muszą być jednowymiarowe.")
        if self.intensity.shape != (len(self.c_angles), len(self.gamma_angles)):
            raise ValueError("Nieprawidłowa liczba wartości światłości względem siatki kątowej.")
        if not len(self.c_angles) or len(self.gamma_angles) < 2:
            raise ValueError("Za mało punktów kątowych.")
        for array in (self.c_angles, self.gamma_angles, self.intensity):
            if not np.isfinite(array).all():
                raise ValueError("Plik zawiera NaN lub nieskończoność.")
        if np.any(self.intensity < 0):
            raise ValueError("Plik zawiera ujemne światłości.")
        if np.max(self.intensity) <= 0:
            raise ValueError("Wszystkie wartości światłości są zerowe.")
        if np.any(np.diff(self.gamma_angles) <= 0):
            raise ValueError("Kąty gamma nie są ściśle rosnące.")
        if self.gamma_angles[0] < -1e-5 or self.gamma_angles[-1] > 180 + 1e-5:
            raise ValueError("Gamma poza zakresem 0–180° (typ C).")
        if np.any(self.c_angles < -1e-5) or np.any(self.c_angles > 360 + 1e-5):
            raise ValueError("Kąty C poza zakresem 0–360°.")
        if np.any(np.diff(self.c_angles) <= 0):
            raise ValueError("Kąty C nie są ściśle rosnące.")
        if self.symmetry not in {"none", "radial", "quadrants", "plane0", "plane90"}:
            raise ValueError("Nieznana symetria.")
        if self.to_cd is not None and (not np.isfinite(self.to_cd) or self.to_cd <= 0):
            raise ValueError("Nieprawidłowy współczynnik przeliczenia na cd.")
        return self
