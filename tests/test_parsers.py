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
