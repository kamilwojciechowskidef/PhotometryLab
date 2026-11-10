"""Single-luminaire diagnostics on native angular knots, without extrapolation."""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from .analysis import sample
from .models import Photometry

DIAGNOSTICS_VERSION = 'diagnostics-v1-native-linear-half-maximum'
PLANES = (0, 90)


@dataclass(frozen=True)
class BeamWidth:
    left_deg: float | None
    right_deg: float | None
    reason: str = ''

    @property
    def width_deg(self) -> float | None:
        if self.left_deg is None or self.right_deg is None:
            return None
        return self.right_deg - self.left_deg


@dataclass(frozen=True)
class Section:
    plane: int
    gamma: np.ndarray
    positive: np.ndarray
    negative: np.ndarray
    beam: BeamWidth


@dataclass(frozen=True)
class Diagnostics:
    filename: str
    unit: str
    sections: tuple[Section, ...]
    peak: float
    peak_c: float
    peak_gamma: float
    axis_cd: float | None
    axis_reason: str
    native_gamma_step_max: float


def half_maximum_width(angles: np.ndarray, values: np.ndarray) -> BeamWidth:
    """Width of a single connected >= half-peak region, with linear crossings.

    Angles are signed: negative angles belong to the opposite C plane.
    Multiple regions or a boundary still above half-peak are not assigned a width.
    """
    angles, values = np.asarray(angles, dtype=float), np.asarray(values, dtype=float)
    if (angles.ndim != 1 or values.shape != angles.shape or len(angles) < 3
            or not np.isfinite(angles).all() or not np.isfinite(values).all()
            or np.any(np.diff(angles) <= 0) or np.any(values < 0)):
        raise ValueError('Invalid angular cross-section.')
    peak = float(values.max())
    if peak <= 0:
        return BeamWidth(None, None, 'No emission in this lower-hemisphere section.')
    half = peak / 2
    inside = np.flatnonzero(values >= half)
    if np.any(np.diff(inside) != 1):
        return BeamWidth(None, None, 'Multiple separate half-maximum lobes; no single FWHM.')
    first, last = int(inside[0]), int(inside[-1])
    if (first == 0 and values[first] > half) or (last == len(values) - 1 and values[last] > half):
        return BeamWidth(None, None, 'Half-maximum crossing lies outside the measured section.')

    def crossing(a, b):
        return float(angles[a] + (half - values[a]) * (angles[b] - angles[a]) / (values[b] - values[a]))

    left = float(angles[first]) if values[first] == half else crossing(first - 1, first)
    right = float(angles[last]) if values[last] == half else crossing(last, last + 1)
    return BeamWidth(left, right)


def _sample(item: Photometry, cs, gs):
    # Rotate the coordinates temporarily to use sample's periodic extension
    # even when an unsymmetrized native C grid begins at a nonzero angle.
    if item.symmetry == 'none':
        origin = float(item.c_angles[0])
        item = replace(item, c_angles=item.c_angles - origin)
        cs = np.asarray(cs) - origin
    return sample(item, np.asarray(cs), np.asarray(gs))


def diagnose(item: Photometry, scale: str = 'absolute') -> Diagnostics:
    """Report native peak and two C cuts; scale is absolute, source or normalized."""
    if scale not in ('absolute', 'source', 'normalized'):
        raise ValueError('Unknown diagnostic scale.')
    if scale == 'absolute' and item.to_cd is None:
        raise ValueError('Absolute cd scale requires a reliable conversion factor.')
    # Guard against clamping at absent symmetry boundaries in stored models.
    bounds = {'plane0': (0, 180), 'plane90': (90, 270), 'quadrants': (0, 90)}
    if item.symmetry in bounds:
        low, high = bounds[item.symmetry]
        if not (np.isclose(item.c_angles[0], low, atol=1e-7, rtol=0)
                and np.isclose(item.c_angles[-1], high, atol=1e-7, rtol=0)):
            raise ValueError('Required C symmetry boundaries are missing.')
    native_peak = float(item.intensity.max())
    factor = item.to_cd if scale == 'absolute' else (1 / native_peak if scale == 'normalized' else 1)
    unit = 'cd' if scale == 'absolute' else ('I / native Imax [-]' if scale == 'normalized' else item.unit)
    peak_index = np.unravel_index(np.argmax(item.intensity), item.intensity.shape)
    gs = item.gamma_angles.copy()
    axis_cd, axis_reason = None, ''
    has_axis = bool(np.isclose(gs[0], 0, atol=1e-7, rtol=0))
    axis_consistent = has_axis and bool(np.allclose(item.intensity[:, 0], item.intensity[0, 0], rtol=1e-3, atol=1e-8))
    if not has_axis:
        axis_reason = 'Gamma = 0 is not measured; axial illuminance is unavailable.'
    elif not axis_consistent:
        axis_reason = 'Gamma = 0 intensities disagree between C planes; axial illuminance is unavailable.'
    elif item.to_cd is None:
        axis_reason = 'Conversion to cd is unknown; axial illuminance is unavailable.'
    else:
        axis_cd = float(item.intensity[0, 0] * item.to_cd)
    sections = []
    for plane in PLANES:
        positive, negative = _sample(item, [plane, plane + 180], gs)
        beam = BeamWidth(None, None, 'FWHM requires measured gamma coverage from 0 to 90 degrees.')
        if item.covers_downward and has_axis:
            if not axis_consistent:
                beam = BeamWidth(None, None, 'Inconsistent gamma = 0 values prevent joining opposite C planes.')
            else:
                lower = np.unique(np.r_[0.0, gs[(gs > 0) & (gs < 90)], 90.0])
                pos, neg = _sample(item, [plane, plane + 180], lower)
                beam = half_maximum_width(np.r_[-lower[:0:-1], lower], np.r_[neg[:0:-1], pos])
        sections.append(Section(plane, gs, positive * factor, negative * factor, beam))
    return Diagnostics(item.filename, unit, tuple(sections), native_peak * factor,
                       float(item.c_angles[peak_index[0]]), float(gs[peak_index[1]]),
                       axis_cd, axis_reason, float(np.diff(gs).max()))


def distance_rows(result: Diagnostics, distances) -> list[dict]:
    """Project half-intensity rays onto planes normal to gamma=0, distance d away.

    Width = d*(tan(right)-tan(left)), not a circular diameter for asymmetric cuts.
    E_axis = I_axis/d² is a point-source, far-field estimate, not a plane average.
    """
    distances = np.asarray(distances, dtype=float)
    if (distances.ndim != 1 or not 1 <= len(distances) <= 100
            or not np.isfinite(distances).all() or np.any(distances <= 0)):
        raise ValueError('Provide 1 to 100 finite positive distances in metres.')
    rows = []
    for distance in distances:
        row = {'Distance [m]': float(distance),
               'Axial illuminance [lx]': None if result.axis_cd is None else result.axis_cd / distance**2}
        for section in result.sections:
            label = f'C{section.plane}-C{section.plane + 180}'
            beam = section.beam
            left = right = None
            if beam.width_deg is not None and -90 < beam.left_deg <= beam.right_deg < 90:
                left, right = distance * np.tan(np.deg2rad([beam.left_deg, beam.right_deg]))
            row[f'{label} left [m]'] = None if left is None else float(left)
            row[f'{label} right [m]'] = None if right is None else float(right)
            row[f'{label} width [m]'] = None if left is None else float(right - left)
        rows.append(row)
    return rows
