import pytest

from photolab.catalogue_controls import add_to_comparison, select_page


class Stub:
    def __init__(self, range_choice=1):
        self.range_choice = range_choice
        self.calls = []

    def selectbox(self, label, options, **kwargs):
        options = list(options)
        self.calls.append((label, options))
        return self.range_choice if label == 'Page range' else options[-1]


def test_page_dropdown_never_lists_nonexistent_pages():
    stub = Stub()
    assert select_page(stub, 101, key='test') == 3
    assert stub.calls == [('Catalogue page', [1, 2, 3])]


def test_three_million_records_have_bounded_page_options():
    stub = Stub(range_choice=60)
    assert select_page(stub, 3_000_000, key='test') == 60_000
    assert len(stub.calls[0][1]) == 60
    assert stub.calls[1][1][0] == 59_001
    assert len(stub.calls[1][1]) == 1000


def test_empty_catalogue_has_single_page():
    stub = Stub()
    assert select_page(stub, 0, key='test') == 1


def test_adding_catalogue_items_preserves_ids_and_avoids_duplicates():
    selection = {}
    choices = {1: {'filename': 'a.ies', 'sha256': 'a' * 64, 'manufacturer': 'Brand',
                   'model': 'Description', 'catalogue_number': 'CAT'}}
    assert add_to_comparison(selection, [1, 1], choices) == 1
    assert add_to_comparison(selection, [1], choices) == 0
    assert selection[1]['filename'] == 'a.ies'
    assert 'CAT' in selection[1]['label']


def test_limit_and_stale_page_never_partially_modify_selection():
    selection = {n: {'filename': str(n)} for n in range(19)}
    choices = {n: {'filename': str(n), 'sha256': 'a' * 64, 'manufacturer': 'B', 'model': 'M'}
               for n in (20, 21)}
    with pytest.raises(ValueError, match='at most 20'):
        add_to_comparison(selection, [20, 21], choices)
    assert len(selection) == 19
    with pytest.raises(ValueError, match='page changed'):
        add_to_comparison(selection, [20, 22], choices)
    assert len(selection) == 19
