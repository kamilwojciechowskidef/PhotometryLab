"""Explicit, non-destructive diagnostics for imported photometric files."""
from __future__ import annotations

from dataclasses import dataclass

from .analysis import shape_matrix
from .models import Photometry


@dataclass(frozen=True)
class QualityReport:
    """Readiness of one parsed file for the operations supported by this prototype."""

    filename: str
    status: str
    comparison_ready: bool
    downward_flux_ready: bool
    issues: tuple[str, ...]


def classify_parse_error(message: str) -> str:
    """Classify a rejected file without claiming that damaged data is supported."""
    lowered = message.lower()
    unsupported = (
        "supported formats",
        "only supports",
        "unknown symmetry code",
        "unknown horizontal angle range",
    )
    incomplete = ("too few", "missing ")
    if any(fragment in lowered for fragment in unsupported):
        return "unsupported"
    if any(fragment in lowered for fragment in incomplete):
        return "incomplete"
    return "damaged"


def rejected_file_report(filename: str, message: str) -> QualityReport:
    """Create a report for a file rejected before a ``Photometry`` object exists."""
    return QualityReport(
        filename=filename,
        status=classify_parse_error(message),
        comparison_ready=False,
        downward_flux_ready=False,
        issues=(message,),
    )


def assess_quality(item: Photometry) -> QualityReport:
    """Report limitations; never modify, fill in, or extrapolate input data."""
    issues = list(item.warnings)
    try:
        shape_matrix(item)
        comparison_ready = True
    except ValueError as error:
        comparison_ready = False
        issues.append(str(error))

    downward_flux_ready = item.covers_downward and item.to_cd is not None
    if item.to_cd is None:
        issues.append("No reliable conversion of intensity to cd; the downward flux cannot be calculated.")
    elif not item.covers_downward:
        issues.append("The data do not cover the full γ=0–90° range; the downward flux cannot be calculated.")

    return QualityReport(
        filename=item.filename,
        status=("incomplete" if not comparison_ready else
                "valid with limitations" if issues else "valid"),
        comparison_ready=comparison_ready,
        downward_flux_ready=downward_flux_ready,
        issues=tuple(dict.fromkeys(issues)),
    )
