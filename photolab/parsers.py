"""Strict but useful subset of IES LM-63 (Type C) and EULUMDAT LDT.

Unsupported cases fail with an explanation instead of silently giving wrong plots.
See the project README for supported variants and reference materials.
"""
from __future__ import annotations

from pathlib import Path
import re

import numpy as np

from .models import Photometry


class PhotometryError(ValueError):
    """A user-facing parsing or validation error."""


def _decode(content: bytes) -> str:
    if len(content) > 5_000_000:
        raise PhotometryError("The file exceeds the 5 MB limit for a single file.")
    for encoding in ("utf-8-sig", "cp1250", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise PhotometryError("The file encoding cannot be read.")


def _num(value: str) -> float:
    try:
        return float(value.strip().replace(",", "."))
    except (ValueError, TypeError) as ex:
        raise PhotometryError(f"Invalid numeric value: {value!r}.") from ex


def _integer(value: str, field: str) -> int:
    x = _num(value)
    if not np.isfinite(x) or not x.is_integer():
        raise PhotometryError(f"The {field} field must be an integer.")
    return int(x)


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.replace("\r\n", "\n").split("\n")]


def load_photometry(filename: str, content: bytes) -> Photometry:
    """Read untrusted file bytes. No code execution, disk access, or network access."""
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".ies":
            return _ies(filename, _decode(content)).validate()
        if suffix == ".ldt":
            return _ldt(filename, _decode(content)).validate()
        raise PhotometryError("Supported formats are limited to .ies and .ldt.")
    except PhotometryError:
        raise
    except (ValueError, IndexError, OverflowError, TypeError) as ex:
        raise PhotometryError(f"File {filename}: {ex}") from ex


def _ies(filename: str, text: str) -> Photometry:
    lines = _lines(text)
    tilt_pos = next((i for i, line in enumerate(lines) if line.upper().startswith("TILT=")), None)
    if tilt_pos is None:
        raise PhotometryError("IES: the TILT= section was not found.")
    if lines[tilt_pos].upper() != "TILT=NONE":
        raise PhotometryError("IES: version 0.1 only supports TILT=NONE (not TILT=INCLUDE or an external file).")
    attributes: dict[str, str] = {}
    for line in lines[:tilt_pos]:
        match = re.match(r"\[([^\]]+)\]\s*(.*)", line)
        if match:
            attributes[match.group(1).upper()] = match.group(2).strip()
    nums = [piece for line in lines[tilt_pos+1:] for piece in line.split()]
    if len(nums) < 13:
        raise PhotometryError("IES: required fields are missing after TILT=NONE.")
    values = [_num(x) for x in nums[:13]]
    lamps = _integer(nums[0], "number of lamps")
    multiplier = values[2]
    nv = _integer(nums[3], "number of vertical angles")
    nh = _integer(nums[4], "number of horizontal angles")
    photometric_type = _integer(nums[5], "photometric type")
    if photometric_type != 1:
        raise PhotometryError("IES: only Type C is supported at this stage (photometric type = 1).")
    if not (2 <= nv <= 1000 and 1 <= nh <= 1000 and nv * nh <= 200_000):
        raise PhotometryError("IES: invalid angular-grid dimensions.")
    if multiplier <= 0:
        raise PhotometryError("IES: the candela multiplier must be positive.")
    needed = 13 + nv + nh + nv * nh
    if len(nums) < needed:
        raise PhotometryError(f"IES: too few data values (need {needed}, found {len(nums)}).")
    gamma = np.array([_num(v) for v in nums[13:13+nv]], dtype=float)
    c = np.array([_num(v) for v in nums[13+nv:13+nv+nh]], dtype=float)
    raw = np.array([_num(v) for v in nums[13+nv+nh:needed]], dtype=float)
    intensity = raw.reshape(nh, nv) * multiplier
    if not np.isclose(c[0], 0, atol=0.001):
        raise PhotometryError("IES: the first horizontal angle must be C=0°.")
    endpoint = float(c[-1])
    if nh == 1 and np.isclose(endpoint, 0, atol=0.001):
        symmetry = "radial"
    elif np.isclose(endpoint, 90, atol=0.001):
        symmetry = "quadrants"
    elif np.isclose(endpoint, 180, atol=0.001):
        symmetry = "plane0"
    elif np.isclose(endpoint, 360, atol=0.001):
        symmetry = "none"
    else:
        raise PhotometryError("IES: unknown horizontal angle range (0, 90, 180, or 360°).")
    if symmetry == "none" and np.isclose(c[-1], 360, atol=1e-5):
        if not np.allclose(intensity[0], intensity[-1], rtol=0.01, atol=0.1):
            raise PhotometryError("IES: the C=0° and C=360° data are inconsistent.")
        c, intensity = c[:-1], intensity[:-1]
    if np.any(np.diff(c) <= 0) and len(c) > 1:
        raise PhotometryError("IES: horizontal angles are not strictly increasing.")
    watts = values[12]
    flux = lamps * values[1] if lamps > 0 and values[1] > 0 else None
    return Photometry(
        filename=filename, format="IES LM-63 / typ C",
        manufacturer=attributes.get("MANUFAC", "Niepodany"),
        luminaire=attributes.get("LUMCAT", attributes.get("LUMINAIRE", attributes.get("TEST", Path(filename).stem))),
        c_angles=c, gamma_angles=gamma, intensity=intensity, symmetry=symmetry,
        unit="cd", to_cd=1.0, power_w=watts if watts > 0 else None,
        source_flux_lm=flux,
        warnings=["The flux in an IES header may describe the lamp flux rather than the luminaire flux; it is not a confirmed luminaire flux."] if flux else [],
    )


def _ldt(filename: str, text: str) -> Photometry:
    lines = _lines(text)
    if len(lines) < 26:
        raise PhotometryError("LDT: header is too short (26 lines are required).")
    mc = _integer(lines[3], "Mc")
    ng = _integer(lines[5], "Ng")
    sym = _integer(lines[2], "Isym")
    nsets = _integer(lines[25], "number of lamp sets")
    if sym not in range(5):
        raise PhotometryError("LDT: unknown Isym symmetry code.")
    if not (4 <= mc <= 1000 and 2 <= ng <= 1000 and mc*ng <= 200_000):
        raise PhotometryError("LDT: invalid grid dimensions.")
    if not (1 <= nsets <= 20):
        raise PhotometryError("LDT: the number of lamp sets must be between 1 and 20.")
    base = 26 + 6 * nsets
    if len(lines) < base:
        raise PhotometryError("LDT: lamp-set data are missing.")
    try:
        lamp_counts = [_integer(lines[26+6*i], "lamp count") for i in range(nsets)]
        fluxes = [_num(lines[26+6*i+2]) for i in range(nsets)]
        powers = [_num(lines[26+6*i+5]) for i in range(nsets)]
    except IndexError as ex:
        raise PhotometryError("LDT: lamp-set rows are missing.") from ex
    conv = _num(lines[23])
    if conv <= 0:
        raise PhotometryError("LDT: the conversion factor must be positive.")
    # From the variable-length tail, spaces and line breaks are interchangeable.
    tokens = " ".join(lines[base:]).split()
    fixed_count = 10 + mc + ng
    if len(tokens) < fixed_count:
        raise PhotometryError("LDT: direct ratios or angle tables are missing.")
    nums = [_num(item) for item in tokens]
    c = np.array(nums[10:10+mc], dtype=float)
    gamma = np.array(nums[10+mc:10+mc+ng], dtype=float)
    if not np.isclose(c[0], 0, atol=0.001):
        raise PhotometryError("LDT: the first C-plane must be 0°.")
    if not np.all(np.diff(c) > 0):
        raise PhotometryError("LDT: C angles must be increasing.")
    if not c[-1] < 360:
        raise PhotometryError("LDT: the C grid must not contain a duplicate 360° point.")
    if sym == 0:
        indices = np.arange(mc)
        mode = "none"
    elif sym == 1:
        indices = np.array([0])
        mode = "radial"
    elif sym == 2:
        indices = np.flatnonzero(c <= 180 + 1e-4)
        mode = "plane0"
    elif sym == 3:
        indices = np.flatnonzero((c >= 90 - 1e-4) & (c <= 270 + 1e-4))[::-1]
        mode = "plane90"
    else:
        indices = np.flatnonzero(c <= 90 + 1e-4)
        mode = "quadrants"
    # Folding C angles is valid only if the measured domain includes both
    # symmetry boundaries. Otherwise np.interp would invent a constant tail.
    bounds = {2: (0.0, 180.0), 3: (90.0, 270.0), 4: (0.0, 90.0)}
    if sym in bounds:
        lower, upper = bounds[sym]
        selected = c[indices]
        if (len(selected) < 2 or
                not np.isclose(selected.min(), lower, rtol=0, atol=1e-4) or
                not np.isclose(selected.max(), upper, rtol=0, atol=1e-4)):
            raise PhotometryError(
                f"LDT: incomplete C-angle range for Isym={sym}; "
                f"C={lower:g}° and C={upper:g}° planes are required. "
                "Missing measurements are not extrapolated."
            )
    count = len(indices) * ng
    if count == 0 or len(nums) < fixed_count + count:
        raise PhotometryError(f"LDT: intensity values are missing for symmetry code {sym} (need {count} values).")
    required_c_ranges = {
        "plane0": (0.0, 180.0),
        "plane90": (90.0, 270.0),
        "quadrants": (0.0, 90.0),
    }
    if mode in required_c_ranges:
        start, end = required_c_ranges[mode]
        available = c[indices]
        if (not np.isclose(available.min(), start, atol=1e-3) or
                not np.isclose(available.max(), end, atol=1e-3)):
            raise PhotometryError(
                f"LDT: Isym={sym} requires C data from {start:g}° to {end:g}°; "
                "missing boundary planes are not interpolated."
            )
    matrix = np.array(nums[fixed_count:fixed_count+count], dtype=float).reshape(len(indices), ng)
    selected_c = c[indices]
    order = np.argsort(selected_c)
    matrix = matrix[order]
    selected_c = selected_c[order]
    flux = sum((abs(n) if n != 0 else 0)*f for n, f in zip(lamp_counts, fluxes) if f > 0)
    warnings = []
    if flux <= 0:
        scale = None
        warnings.append("No reliable flux is available to convert cd/klm to cd. Shape comparison remains possible.")
    else:
        scale = flux / 1000.0 * conv
        warnings.append("The cd/klm→cd conversion assumes correctly populated lamp-count and flux fields; verify the manufacturer data.")
    if nsets > 1:
        warnings.append("Multiple lamp sets: the sum of their reference fluxes was used.")
    power = sum(x for x in powers if x > 0)
    return Photometry(
        filename=filename, format="EULUMDAT LDT", manufacturer=lines[0] or "Not provided",
        luminaire=lines[9] or lines[8] or Path(filename).stem,
        c_angles=selected_c, gamma_angles=gamma, intensity=matrix, symmetry=mode,
        unit="cd/klm", to_cd=scale, power_w=power if power > 0 else None,
        source_flux_lm=flux if flux > 0 else None, warnings=warnings,
    )
