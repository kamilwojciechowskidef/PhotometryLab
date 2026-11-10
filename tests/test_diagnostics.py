from dataclasses import replace

import numpy as np
import pytest

from photolab.diagnostics import diagnose, distance_rows, half_maximum_width
from photolab.diagnostics_ui import polar_figure, beam_figure, beam_schematic_figure
from photolab.models import Photometry


def radial(gamma=(0, 20, 40, 90), values=(1000, 500, 0, 0), unit='cd', to_cd=1):
    return Photometry('synthetic.ies', 'test', 'SYNTHETIC', 'test', np.array([0.]),
                      np.array(gamma), np.array([values]), 'radial', unit, to_cd).validate()


def test_known_symmetric_beam_width_and_inverse_square_lux():
    result = diagnose(radial())
    assert result.axis_cd == 1000
    assert result.sections[0].beam.width_deg == pytest.approx(40)
    assert result.sections[1].beam.left_deg == pytest.approx(-20)
    rows = distance_rows(result, [2, 4])
    assert [row['Axial illuminance [lx]'] for row in rows] == [250, 62.5]
    assert rows[0]['C0-C180 width [m]'] == pytest.approx(4 * np.tan(np.deg2rad(20)))
    assert rows[1]['C0-C180 width [m]'] == pytest.approx(2 * rows[0]['C0-C180 width [m]'])


def test_schematic_uses_calculated_diameter_and_lux():
    rows = distance_rows(diagnose(radial()), [2, 4])
    figure = beam_schematic_figure(rows, 0, radial=True)
    assert figure.layout.shapes[0].type == 'circle'
    assert figure.layout.shapes[0].y1 - figure.layout.shapes[0].y0 == pytest.approx(4 * np.tan(np.deg2rad(20)))
    assert figure.data[-1].customdata[0][0] == 250
    assert '250.00 lx' in figure.layout.annotations[-2].text


def test_schematic_keeps_asymmetric_boundaries_and_missing_values():
    result = diagnose(radial(unit='cd/klm', to_cd=None), 'source')
    rows = distance_rows(result, [2])
    rows[0]['C0-C180 left [m]'] = -2.0
    rows[0]['C0-C180 right [m]'] = 1.0
    rows[0]['C0-C180 width [m]'] = 3.0
    figure = beam_schematic_figure(rows, 0, radial=False)
    assert figure.layout.shapes[0].type == 'line'
    assert (figure.layout.shapes[0].y0, figure.layout.shapes[0].y1) == (-2, 1)
    assert figure.data[-1].customdata[0][0] is None
    assert 'unavailable' in figure.layout.annotations[-1].text
    axis_only = beam_schematic_figure(distance_rows(diagnose(radial((0, 90), (100, 100))), [2]), None)
    assert not axis_only.layout.shapes
    assert axis_only.data[-1].customdata[0][0] == 25


def test_crossings_interpolated_on_nonuniform_native_grid():
    result = diagnose(radial((0, 10, 30, 90), (100, 80, 20, 0)))
    assert result.sections[0].beam.width_deg == pytest.approx(40)


def test_narrow_beam_uses_native_knots_not_five_degree_comparison_grid():
    result = diagnose(radial((0, 0.7, 1.4, 90), (100, 50, 0, 0)))
    assert result.sections[0].beam.width_deg == pytest.approx(1.4)


def test_asymmetry_preserves_opposite_planes_and_projected_offsets():
    item = Photometry('asym', 'test', 'SYNTHETIC', 'test', np.array([0, 90, 180, 270]),
                      np.array([0, 10, 30, 90]),
                      np.array([[100, 50, 0, 0], [100, 80, 20, 0],
                                [100, 80, 50, 0], [100, 80, 20, 0]]), 'none', 'cd', 1).validate()
    result = diagnose(item)
    beam = result.sections[0].beam
    assert (beam.left_deg, beam.right_deg, beam.width_deg) == (-30, 10, 40)
    row = distance_rows(result, [2])[0]
    assert row['C0-C180 left [m]'] == pytest.approx(-2 * np.tan(np.deg2rad(30)))
    assert row['C0-C180 right [m]'] == pytest.approx(2 * np.tan(np.deg2rad(10)))
    assert row['C0-C180 width [m]'] != pytest.approx(4 * np.tan(np.deg2rad(20)))
    figure = polar_figure(result)
    np.testing.assert_array_equal(figure.data[1].r, [100, 80, 50, 0])
    np.testing.assert_array_equal(figure.data[1].theta, [0, -10, -30, -90])
    assert figure.layout.polar.angularaxis.rotation % 360 == 270
    assert figure.layout.polar.angularaxis.direction == 'counterclockwise'


def test_shifted_single_lobe_keeps_both_crossings_on_same_side():
    beam = half_maximum_width(np.array([-90, 0, 10, 20, 30, 40, 90]),
                             np.array([0, 0, 50, 100, 50, 0, 0]))
    assert (beam.left_deg, beam.right_deg, beam.width_deg) == (10, 30, 20)


@pytest.mark.parametrize('gamma,values,reason', [
    ((0, 30, 60, 90), (10, 100, 0, 0), 'Multiple'),
    ((0, 90), (100, 100), 'outside'),
    ((0, 90, 180), (0, 0, 100), 'No emission'),
])
def test_ambiguous_or_unbounded_widths_are_not_invented(gamma, values, reason):
    result = diagnose(radial(gamma, values))
    assert result.sections[0].beam.width_deg is None
    assert reason in result.sections[0].beam.reason
    assert distance_rows(result, [2])[0]['C0-C180 width [m]'] is None


def test_half_maximum_at_horizon_has_angle_but_no_finite_projection():
    result = diagnose(radial((0, 90), (100, 50)))
    assert result.sections[0].beam.width_deg == 180
    rows = distance_rows(result, [2])
    assert rows[0]['C0-C180 width [m]'] is None
    assert len(beam_figure(result, rows).data) == 0


def test_missing_lower_range_remains_visible_without_filling_missing_angles():
    result = diagnose(radial((20, 90, 180), (50, 100, 25)))
    assert result.axis_cd is None
    assert result.sections[0].beam.width_deg is None
    figure = polar_figure(result)
    np.testing.assert_array_equal(figure.data[0].theta, [20, 90, 180])
    np.testing.assert_array_equal(figure.data[1].theta, [-20, -90, -180])
    assert result.peak_gamma == 90
    assert result.peak == 100


def test_absolute_conversion_and_shared_native_normalization():
    item = radial(unit='cd/klm', to_cd=3.5)
    absolute, source, normalized = (diagnose(item, scale) for scale in ('absolute', 'source', 'normalized'))
    assert absolute.peak == 3500
    assert source.peak == 1000
    assert normalized.peak == 1
    assert source.unit == 'cd/klm'
    np.testing.assert_allclose(absolute.sections[0].positive, source.sections[0].positive * 3.5)
    for result in (absolute, source, normalized):
        assert result.sections[0].beam.width_deg == 40
        assert distance_rows(result, [2])[0]['Axial illuminance [lx]'] == 875


def test_unknown_absolute_scale_allows_shape_but_not_lux():
    item = radial(unit='cd/klm', to_cd=None)
    with pytest.raises(ValueError, match='conversion'):
        diagnose(item)
    result = diagnose(item, 'source')
    assert result.sections[0].beam.width_deg == 40
    assert distance_rows(result, [2])[0]['Axial illuminance [lx]'] is None


def test_inconsistent_pole_is_not_averaged_into_fabricated_axial_intensity():
    item = replace(radial(), symmetry='none', c_angles=np.array([0., 180.]),
                   intensity=np.array([[1000, 500, 0, 0], [2000, 500, 0, 0]]))
    result = diagnose(item)
    assert result.axis_cd is None
    assert 'disagree' in result.axis_reason
    assert all(section.beam.width_deg is None for section in result.sections)


def test_periodic_c_interpolation_across_zero_with_nonzero_native_origin():
    item = Photometry('periodic', 'test', 'SYNTHETIC', 'test', np.array([90, 180, 270]),
                      np.array([0, 90]), np.array([[100, 20], [100, 40], [100, 60]]),
                      'none', 'cd', 1).validate()
    result = diagnose(item)
    assert result.sections[0].positive[-1] == 40  # halfway between C270 and C450 (=C90)
    assert result.sections[1].positive[-1] == 20
    assert result.sections[1].negative[-1] == 60


@pytest.mark.parametrize('symmetry,cs,expected', [
    ('quadrants', [0, 90], [[100, 10], [100, 20], [100, 10], [100, 20]]),
    ('plane0', [0, 90, 180], [[100, 10], [100, 20], [100, 30], [100, 20]]),
    ('plane90', [90, 180, 270], [[100, 20], [100, 10], [100, 20], [100, 30]]),
])
def test_symmetry_reconstruction_has_expected_cuts(symmetry, cs, expected):
    item = Photometry('symmetry', 'test', 'SYNTHETIC', 'test', np.array(cs), np.array([0, 90]),
                      np.array([[100, 10*(i+1)] for i in range(len(cs))]), symmetry, 'cd', 1).validate()
    result = diagnose(item)
    actual = [result.sections[0].positive, result.sections[1].positive,
              result.sections[0].negative, result.sections[1].negative]
    np.testing.assert_allclose(actual, expected)


def test_missing_symmetry_boundary_refuses_clamped_cut():
    item = replace(radial(), c_angles=np.array([0, 80]), intensity=np.array([[1000, 500, 0, 0]]*2),
                   symmetry='quadrants')
    with pytest.raises(ValueError, match='boundaries'):
        diagnose(item)


@pytest.mark.parametrize('distances', [[0], [-2], [np.nan], [np.inf], [], [[2]], [1]*101])
def test_invalid_distances_rejected(distances):
    with pytest.raises(ValueError, match='distances'):
        distance_rows(diagnose(radial()), distances)


def test_real_streamlit_diagnostics_single_luminaire_and_scale_switch():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
import streamlit as st
from photolab.demo import make_ies
from photolab.parsers import load_photometry
from photolab.diagnostics_ui import render_diagnostics
render_diagnostics(st, [load_photometry('synthetic.ies', make_ies('Test', 'narrow'))])
''').run(timeout=20)
    assert not app.exception
    assert len(app.get('plotly_chart')) == 3
    assert len(app.get('download_button')) == 3
    assert app.dataframe[0].value['FWHM [°]'].notna().all()
    app.selectbox[1].select('Normalized to native maximum').run(timeout=20)
    assert not app.exception
    assert app.metric[0].value == '1'
