import numpy as np
import pytest

from photolab.parsers import load_photometry, PhotometryError
from photolab.demo import make_ies, make_ldt
from photolab.analysis import (C_GRID, GAMMA_GRID, compare, embedding,
                               estimated_downward_lumens, sample, shape_matrix)
from photolab.models import Photometry


def read_ies(kind="narrow"):
    return load_photometry(f"{kind}.ies", make_ies(kind, kind))


def test_read_ies_and_symmetry():
    item = read_ies("oval")
    assert item.format.startswith("IES")
    assert item.unit == "cd"
    assert len(item.c_angles) == 36  # 360º duplicate removed
    a = sample(item, np.array([0, 90, 180]), np.array([0, 45, 90]))
    assert a.shape == (3, 3)
    assert np.isclose(a[0, 0], a[1, 0], atol=1e-4)


def test_ldt_radial_and_units():
    item = load_photometry("demo.ldt", make_ldt("Downlight", "wide", 3500))
    assert item.unit == "cd/klm"
    assert item.to_cd == pytest.approx(3.5)
    cs = np.array([0., 110., 270.])
    a = sample(item, cs, np.array([0., 30., 90.]), absolute=True)
    assert np.allclose(a[0], a[1])
    assert a[0, 0] == pytest.approx(620, rel=0.01)


def test_same_shape_in_ies_and_ldt():
    ies = read_ies("narrow")
    ldt = load_photometry("lamp.ldt", make_ldt("Spot", "narrow", 3500))
    r = compare(ies, ldt)
    assert r.cosine > 0.99999
    assert r.rmse < 0.0001


def test_similar_beats_different():
    a = read_ies("narrow")
    b = read_ies("narrow_similar")
    c = read_ies("wide")
    assert compare(a, b).rmse < compare(a, c).rmse
    assert compare(a, b).cosine > compare(a, c).cosine


def test_ies_invalid_tilt_and_type():
    data = make_ies("Test", "narrow")
    with pytest.raises(PhotometryError, match="TILT=NONE"):
        load_photometry("x.ies", data.replace(b"TILT=NONE", b"TILT=INCLUDE"))
    with pytest.raises(PhotometryError, match="typ C"):
        load_photometry("x.ies", data.replace(b"19 37 1 2", b"19 37 2 2"))


def test_broken_data_rejected():
    with pytest.raises(PhotometryError):
        load_photometry("bad.ies", b"IESNA:LM-63-2002\nTILT=NONE\n1 2 3\n")
    with pytest.raises(PhotometryError):
        load_photometry("bad.ldt", b"broken\n")
    with pytest.raises(PhotometryError):
        load_photometry("bad.exe", b"123")


def test_no_extrapolation():
    item = read_ies("narrow")
    with pytest.raises(ValueError, match="ekstrapolujemy"):
        sample(item, C_GRID, np.array([-5, 0, 90]))


def test_isym_quadrant_and_plane90():
    base = read_ies("oval")
    # Manually specified distributions test mirror rules independently of file IO.
    quadrant = Photometry("q", "test", "m", "n", np.array([0, 90]),
                          np.array([0, 90]), np.array([[10, 2], [6, 2]]), "quadrants", "cd", 1).validate()
    arr = sample(quadrant, np.array([30, 150, 210, 330]), np.array([0, 90]))
    assert np.allclose(arr[0], arr[1])
    assert np.allclose(arr[1], arr[2])
    assert np.allclose(arr[2], arr[3])
    plane90 = Photometry("p", "test", "m", "n", np.array([90, 180, 270]),
                         np.array([0, 90]), np.array([[5, 2], [8, 2], [4, 2]]), "plane90", "cd", 1).validate()
    arr = sample(plane90, np.array([60, 120, 240, 300]), np.array([0, 90]))
    assert np.allclose(arr[0], arr[1])
    assert np.allclose(arr[2], arr[3])


def test_uniform_downward_hemisphere_flux():
    item = Photometry("uniform", "test", "a", "b", np.array([0.]),
                     np.array([0., 90., 180.]), np.array([[100., 100., 100.]]),
                     "radial", "cd", 1).validate()
    assert estimated_downward_lumens(item) == pytest.approx(2*np.pi*100, rel=0.001)


def test_ml_shapes():
    from photolab.demo import samples
    items = [load_photometry(name, val) for name, val in samples().items()]
    xy, labels, anomalies, var = embedding(items, clusters=3)
    assert xy.shape == (8, 2)
    assert len(set(labels)) == 3
    assert anomalies.shape == (8,)
    assert (var > 0).all()


def test_rotation_invariant_comparison():
    cs = np.arange(0, 360, 10)
    g = np.array([0., 45., 90.])
    # Shape changes with both C angle and gamma: meaningful azimuth shift.
    def values(angles):
        a = np.deg2rad(angles)
        return 5 + 20 * (1 + np.cos(a[:,None])) * np.array([1, 0.7, 0.2])[None, :]
    source = Photometry('a.ies', 'test', 'a', 'b', cs, g, values(cs), 'none', 'cd', 1).validate()
    turned = Photometry('b.ies', 'test', 'a', 'b', cs, g, values((cs-90)%360), 'none', 'cd', 1).validate()
    fixed = compare(source, turned, allow_rotation=False)
    free = compare(source, turned, allow_rotation=True)
    assert fixed.rmse > 0.05
    assert free.rmse < 1e-12
    assert free.rotation_deg == 270


def test_no_data_in_downward_hemisphere_excluded():
    up = Photometry('up', 'test', 'a', 'b', np.array([0.]),
                    np.array([90., 180.]), np.array([[10., 50.]]),
                    'radial', 'cd', 1).validate()
    with pytest.raises(ValueError, match='ekstrapolujemy'):
        shape_matrix(up)
