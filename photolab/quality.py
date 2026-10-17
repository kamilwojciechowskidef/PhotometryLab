"""Explicit, non-destructive diagnostics for imported photometric files."""
from __future__ import annotations

from dataclasses import dataclass

from .analysis import shape_matrix
from .models import Photometry


@dataclass(frozen=True)
class QualityReport:
    """Readiness of one parsed file for the operations supported by this prototype."""

    filename: str
    comparison_ready: bool
    downward_flux_ready: bool
    issues: tuple[str, ...]

    @property
    def status(self) -> str:
        if not self.comparison_ready:
            return "niegotowy do porównania"
        if self.issues:
            return "gotowy z ograniczeniami"
        return "gotowy"


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
        issues.append("Brak wiarygodnego przeliczenia światłości na cd; nie obliczymy strumienia dolnego.")
    elif not item.covers_downward:
        issues.append("Dane nie pokrywają pełnego zakresu γ=0–90°; nie obliczymy strumienia dolnego.")

    return QualityReport(
        filename=item.filename,
        comparison_ready=comparison_ready,
        downward_flux_ready=downward_flux_ready,
        issues=tuple(dict.fromkeys(issues)),
    )
