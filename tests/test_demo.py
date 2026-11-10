"""Numerical regressions for explicitly synthetic demonstration photometry."""
import numpy as np
import pytest
from pathlib import Path

from photolab.demo import _pattern, make_ies, samples
from photolab.diagnostics import diagnose, distance_rows
from photolab.parsers import load_photometry


def test_asymmetric_demo_is_single_valued_at_both_poles():
    cs = np.arange(0., 361., 10.)
    values = _pattern('asymmetric', np.array([0., 180.]), cs)
    expected = 780 * np.exp(-0.5 * (np.array([30., 150.]) / 25)**2)
    np.testing.assert_allclose(values, np.broadcast_to(expected, values.shape), rtol=1e-12)


def test_asymmetric_demo_peak_and_equal_angular_offsets():
    # Rotated axis is C=0, gamma=30; 20 and 40 degrees are equally far from it.
    values = _pattern('asymmetric', np.array([20., 30., 40.]), np.array([0., 360.]))
    expected = 780 * np.exp(-0.5 * (np.array([10., 0., 10.]) / 25)**2)
    np.testing.assert_allclose(values, np.broadcast_to(expected, values.shape), rtol=1e-12)
    opposite = _pattern('asymmetric', np.array([30.]), np.array([180.]))[0, 0]
    assert opposite == pytest.approx(780 * np.exp(-0.5 * (60/25)**2))


def test_exported_asymmetric_demo_has_axial_lux_and_finite_beam_widths():
    item = load_photometry('synthetic.ies', make_ies('Synthetic tilted beam', 'asymmetric'))
    result = diagnose(item)
    assert (result.peak, result.peak_c, result.peak_gamma) == pytest.approx((780, 0, 30))
    assert result.axis_cd == pytest.approx(780 * np.exp(-0.5 * (30/25)**2), abs=1e-5)
    assert not result.axis_reason
    analytic_fwhm = 2 * np.sqrt(2 * np.log(2)) * 25
    # The file's 10-degree grid introduces interpolation error; not exact angular measurement.
    assert result.sections[0].beam.width_deg == pytest.approx(analytic_fwhm, abs=1.0)
    assert all(section.beam.width_deg is not None for section in result.sections)
    row = distance_rows(result, [2])[0]
    assert row['Axial illuminance [lx]'] == pytest.approx(result.axis_cd / 4)
    assert row['C0-C180 width [m]'] > 0
    assert row['C90-C270 width [m]'] > 0


def test_bundled_asymmetric_example_matches_current_generator():
    path = Path(__file__).resolve().parents[1] / 'examples' / 'DEMO_06_Asymetria_IES.ies'
    # Ignore platform line endings, but keep all photometric values identical.
    assert path.read_text(encoding='utf-8') == samples()['DEMO_06_Asymmetry_IES.ies'].decode('utf-8')
