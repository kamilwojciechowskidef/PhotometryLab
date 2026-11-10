from photolab.catalogue_controls import select_page


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
