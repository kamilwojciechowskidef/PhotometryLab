"""Source metadata remains distinct from filenames and older stored models."""
from dataclasses import replace

from photolab.demo import make_ies, make_ldt
from photolab.parsers import load_photometry
from photolab.product_labels import product_label
from photolab.storage import photometry_from_data, photometry_to_data


def test_ies_catalogue_number_is_read_separately_from_filename():
    content = make_ies('CAT-123', 'narrow')
    item = load_photometry('a1b2.ies', content)
    assert item.filename == 'a1b2.ies'
    assert item.catalogue_number == 'CAT-123'
    assert 'CAT-123' in product_label(item)
    assert 'a1b2.ies' in product_label(item)
    assert photometry_from_data(photometry_to_data(item)).catalogue_number == 'CAT-123'


def test_missing_catalogue_number_is_not_fabricated_from_ies_description():
    content = make_ies('Test', 'narrow').replace(b'[LUMCAT] Test', b'[LUMINAIRE] Descriptive name')
    item = load_photometry('hash.ies', content)
    assert item.catalogue_number is None
    assert item.luminaire == 'Descriptive name'
    assert 'Descriptive name' in product_label(item)


def test_ldt_luminaire_number_is_extracted():
    content = make_ldt('Product ABC', 'wide')
    item = load_photometry('hash.ldt', content)
    assert item.catalogue_number == 'Product ABC-01'
    assert 'Product ABC-01' in product_label(item)


def test_legacy_stored_record_remains_readable_without_inventing_catalogue_number():
    item = load_photometry('old.ies', make_ies('Old description', 'narrow'))
    data = photometry_to_data(item)
    del data['catalogue_number']
    restored = photometry_from_data(data)
    assert restored.catalogue_number is None
    assert restored.luminaire == 'Old description'
    assert 'Old description' in product_label(restored)


def test_labels_keep_distinct_filenames_for_identical_product_metadata():
    item = load_photometry('first.ies', make_ies('CAT-123', 'narrow'))
    other = replace(item, filename='second.ies')
    assert product_label(item) != product_label(other)


def test_streamlit_diagnostic_label_contains_brand_catalogue_and_filename():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
import streamlit as st
from photolab.demo import make_ies
from photolab.parsers import load_photometry
from photolab.diagnostics_ui import render_diagnostics
render_diagnostics(st, [load_photometry('hash.ies', make_ies('CAT-123', 'narrow'))])
''').run(timeout=20)
    assert not app.exception
    option = app.selectbox[0].options[0]
    assert 'SYNTHETIC SAMPLES' in option
    assert 'CAT-123' in option
    assert 'hash.ies' in option
