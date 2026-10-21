import json

import numpy as np
import pytest

from photolab.demo import make_ies, make_ldt
from photolab.parsers import load_photometry
from photolab.storage import photometry_to_data, photometry_from_data
from photolab.analysis import compare, estimated_downward_lumens


@pytest.mark.parametrize('name,content', [
    ('test.ies', make_ies('Test', 'oval')),
    ('test.ldt', make_ldt('Test', 'wide', 3500)),
])
def test_native_photometry_json_roundtrip(name, content):
    original = load_photometry(name, content)
    restored = photometry_from_data(json.loads(json.dumps(photometry_to_data(original))))
    for field in ('c_angles', 'gamma_angles', 'intensity'):
        np.testing.assert_array_equal(getattr(original, field), getattr(restored, field))
    assert photometry_to_data(original) == photometry_to_data(restored)
    assert compare(original, restored).rmse == pytest.approx(0, abs=1e-15)
    assert estimated_downward_lumens(original) == estimated_downward_lumens(restored)


def test_unknown_conversion_and_metadata_remain_unknown():
    item = load_photometry('test.ldt', make_ldt('Test', 'wide', 3500))
    item.to_cd = item.power_w = item.source_flux_lm = None
    restored = photometry_from_data(photometry_to_data(item))
    assert restored.to_cd is restored.power_w is restored.source_flux_lm is None


def test_invalid_stored_matrix_is_rejected():
    data = photometry_to_data(load_photometry('test.ies', make_ies('Test', 'oval')))
    data['intensity'] = [[1]]
    with pytest.raises(ValueError, match='shape'):
        photometry_from_data(data)
