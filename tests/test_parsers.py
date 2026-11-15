"""Synthetic parser fixtures; not evidence of manufacturer format compliance."""
import numpy as np
import pytest

from photolab.analysis import sample
from photolab.demo import make_ldt
from photolab.parsers import PhotometryError, load_photometry


def ldt_with_planes(symmetry, planes):
    # Reuse only the fixed header; explicitly specify angular and intensity data.
    header = make_ldt("Synthetic coverage test", "wide").decode().splitlines()[:32]
    header[2] = str(symmetry)
    header[3] = str(len(planes))
    header[4] = "0"  # Nonuniform angular spacing.
    header[5] = "2"
    header[6] = "90"
    if symmetry == 2:
        measured = [c for c in planes if c <= 180]
    elif symmetry == 3:
        measured = [c for c in planes if 90 <= c <= 270][::-1]
    else:
        measured = [c for c in planes if c <= 90]
    tail = [0] * 10 + planes + [0, 90]
    for c in measured:
        tail.extend([100 + c, 10 + c])
    return ("\n".join(header + [str(x) for x in tail]) + "\n").encode()


@pytest.mark.parametrize("symmetry,planes", [
    (2, [0, 90, 170, 270]),
    (3, [0, 80, 180, 270]),
    (3, [0, 90, 180, 280]),
    (4, [0, 80, 180, 270]),
])
def test_ldt_rejects_incomplete_symmetry_domain(symmetry, planes):
    with pytest.raises(PhotometryError, match="incomplete C-angle range"):
        load_photometry("incomplete.ldt", ldt_with_planes(symmetry, planes))


@pytest.mark.parametrize("symmetry,planes,queries,expected", [
    (2, [0, 70, 180, 270], [0, 180, 360], [100, 280, 100]),
    (3, [0, 90, 160, 270], [90, 270, 60, 300], [190, 370, 220, 340]),
    (4, [0, 40, 90, 180, 270], [0, 90, 180, 270, 360], [100, 190, 100, 190, 100]),
])
def test_ldt_complete_nonuniform_symmetry_domain(symmetry, planes, queries, expected):
    item = load_photometry("complete.ldt", ldt_with_planes(symmetry, planes))
    actual = sample(item, np.array(queries), np.array([0.]))
    np.testing.assert_allclose(actual[:, 0], expected)


def test_ldt_radial_single_plane_is_sampled_at_every_azimuth():
    item = load_photometry('radial.ldt', ldt_with_planes(1, [0]))
    assert item.symmetry == 'radial'
    np.testing.assert_allclose(item.intensity, [[100, 10]])
    np.testing.assert_allclose(sample(item, np.array([0, 90, 270]), np.array([0, 90])),
                               [[100, 10], [100, 10], [100, 10]])


def test_ldt_single_plane_requires_radial_symmetry():
    with pytest.raises(PhotometryError, match='invalid grid dimensions'):
        load_photometry('invalid.ldt', ldt_with_planes(0, [0]))


def ies_with_planes(planes):
    values = [[100, 10 + i * 10] for i in range(len(planes))]
    rows = ['IESNA91', 'TILT=NONE', f'1 -1 1 2 {len(planes)} 1 2 0 0 0',
            '1 1 20', '0 90', ' '.join(map(str, planes))]
    rows.extend(' '.join(map(str, row)) for row in values)
    return ('\n'.join(rows) + '\n').encode()


def test_ies_periodic_grid_interpolates_across_zero():
    planes = list(range(0, 360, 15))
    item = load_photometry('periodic.ies', ies_with_planes(planes))
    assert item.symmetry == 'none'
    assert item.c_angles[-1] == 345
    np.testing.assert_allclose(sample(item, np.array([345, 352.5, 0, 360]), np.array([90]))[:, 0],
                               [240, 125, 10, 10])


@pytest.mark.parametrize('planes', [[0, 30, 90, 180, 270], [0, 90, 180, 270, 350], [0, 90, 180, 300]])
def test_ies_rejects_incomplete_or_nonuniform_periodic_grid(planes):
    with pytest.raises(PhotometryError, match='horizontal angle range'):
        load_photometry('incomplete.ies', ies_with_planes(planes))
