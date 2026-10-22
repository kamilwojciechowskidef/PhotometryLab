import numpy as np
import pytest

from photolab.demo import make_ies
from photolab.features import FEATURE_DIMENSIONS, FEATURE_VERSION, build_feature
from photolab.models import Photometry
from photolab.parsers import load_photometry


def test_feature_has_documented_dimension_and_stable_digest():
    item = load_photometry("shape.ies", make_ies("Test", "oval"))
    first = build_feature(item)
    second = build_feature(item)
    assert FEATURE_VERSION.startswith("shape-v2-")
    assert first.vector.shape == (FEATURE_DIMENSIONS,)
    assert first.vector.dtype == np.dtype("<f4")
    assert first.digest == second.digest
    assert first.buckets == second.buckets
    assert len(first.buckets) == 8
    assert all(0 <= value <= 4095 for value in first.buckets)


def test_feature_is_invariant_to_c_grid_rotation():
    c_angles = np.arange(0, 360, 10, dtype=float)
    gamma_angles = np.array([0.0, 45.0, 90.0])
    angles = np.deg2rad(c_angles)
    matrix = 3 + (1 + np.cos(angles[:, None])) * np.array([15.0, 8.0, 2.0])
    source = Photometry("source.ies", "test", "a", "b", c_angles, gamma_angles,
                        matrix, "none", "cd", 1).validate()
    rotated = Photometry("rotated.ies", "test", "a", "b", c_angles, gamma_angles,
                         np.roll(matrix, 9, axis=0), "none", "cd", 1).validate()
    left, right = build_feature(source), build_feature(rotated)
    np.testing.assert_array_equal(left.vector, right.vector)
    assert left.digest == right.digest
    assert left.buckets == right.buckets


def test_feature_refuses_distribution_without_downward_emission():
    item = Photometry("empty.ies", "test", "a", "b", np.array([0.0]),
                      np.array([0.0, 90.0]), np.zeros((1, 2)), "radial", "cd", 1)
    with pytest.raises(ValueError, match="zero"):
        item.validate()


def test_lsh_demo_bands_do_not_have_a_universal_bucket():
    kinds = ("narrow", "narrow_similar", "wide", "batwing", "oval", "asymmetric")
    buckets = [build_feature(load_photometry(f"{kind}.ies", make_ies(kind, kind))).buckets for kind in kinds]
    assert all(len({item[band] for item in buckets}) > 1 for band in range(8))
