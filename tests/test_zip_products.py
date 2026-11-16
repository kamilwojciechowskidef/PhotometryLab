import json
from io import BytesIO
from zipfile import ZipFile

import pytest
from PIL import Image

from photolab import zip_products
from photolab.artifacts import ArtifactError, save_source
from photolab.demo import make_ies, make_ldt
from photolab.identifiers import identify_file


def archive(entries):
    buffer = BytesIO()
    with ZipFile(buffer, 'w') as zipped:
        for name, content in entries:
            zipped.writestr(name, content)
    return buffer.getvalue()


def test_groups_all_assets_by_relative_stem_with_optional_ldt():
    content = archive([
        ('one/item.ies', make_ies('CAT-1', 'narrow')),
        ('one/item.ldt', make_ldt('CAT-1', 'wide')),
        ('one/item.json', json.dumps({'hash': 'item', 'lumcat': 'CAT-1'}).encode()),
        ('one/item.jpg', b'\xff\xd8\xffsynthetic'),
        ('two/item.ies', make_ies('CAT-2', 'wide')),
        ('two/item.png', b'\x89PNG\r\n\x1a\nsynthetic'),
        ('readme.txt', b'not part of the bundle'),
    ])
    bundles, skipped = zip_products.prepare_product_zip(content)
    by_stem = {bundle.stem: bundle for bundle in bundles}
    assert set(by_stem) == {'one/item', 'two/item'}
    assert len(by_stem['one/item'].files) == 4
    assert by_stem['one/item'].metadata['lumcat'] == 'CAT-1'
    assert len(by_stem['two/item'].files) == 2
    assert by_stem['two/item'].metadata is None
    assert skipped[0].name == 'readme.txt'


@pytest.mark.parametrize('name,content', [
    ('x.json', b'{bad'), ('x.json', b'[]'), ('x.json', b'{"hash":"different"}'),
    ('x.json', b'{"n": NaN}'), ('x.png', b'not a png'), ('x.jpg', b'not a jpeg'),
])
def test_invalid_sidecar_rejected_before_import(name, content):
    data = archive([('x.ies', make_ies('x', 'narrow')), (name, content)])
    with pytest.raises(ValueError):
        zip_products.prepare_product_zip(data)


def test_no_photometry_or_duplicate_asset_type_is_rejected():
    with pytest.raises(ValueError, match='photometric'):
        zip_products.prepare_product_zip(archive([('x.json', b'{}')]))
    with pytest.raises(ValueError, match='Ambiguous'):
        zip_products.prepare_product_zip(archive([('x.ies', b'a'), ('x.IES', b'b')]))


class Cursor:
    def __init__(self, missing=False):
        self.calls = []
        self.missing = missing

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        if 'to_regclass' in self.calls[-1][0]:
            return (None, None) if self.missing else ('table1', 'table2')
        return (42,)


class Connection:
    def __init__(self, cursor):
        self.cursor_value = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.cursor_value


def test_missing_migration_prevents_photometry_import(monkeypatch, tmp_path):
    monkeypatch.setattr(zip_products.psycopg, 'connect', lambda *a, **k: Connection(Cursor(missing=True)))
    monkeypatch.setattr(zip_products, 'import_batch', lambda *a, **k: pytest.fail('must not import'))
    with pytest.raises(zip_products.DatabaseError, match='migration 006'):
        zip_products.import_product_zip('unused', archive([('x.ies', make_ies('x', 'narrow'))]),
                                         tmp_path, 'source', 'test')


def test_import_links_photometry_and_preserves_exact_sidecar_bytes(monkeypatch, tmp_path):
    cursor = Cursor()
    monkeypatch.setattr(zip_products.psycopg, 'connect', lambda *a, **k: Connection(cursor))
    monkeypatch.setattr(zip_products, 'import_batch',
                        lambda url, files, root, description, version, progress: (
                            8, [{'filename': files[0].name, 'file_id': 12, 'outcome': 'new'}]))
    states = []
    monkeypatch.setattr(zip_products, 'update_batch', lambda url, batch, report, finished:
                        states.append((batch, finished)))
    stored = []
    monkeypatch.setattr(zip_products, 'save_source', lambda root, content: stored.append(content) or 'path')
    ies = make_ies('CAT', 'narrow')
    raw_json = b'{"hash":"x", "lumcat":"CAT"}'
    image = b'\xff\xd8\xffsynthetic'
    batch, report, groups, skipped = zip_products.import_product_zip(
        'unused', archive([('x.ies', ies), ('x.json', raw_json), ('x.jpg', image)]),
        tmp_path, 'source', 'test')
    assert batch == 8 and not skipped
    assert states == [(8, False)]
    assert stored == [ies, raw_json, image]
    asset_calls = [params for sql, params in cursor.calls if 'INSERT INTO photolab.zip_bundle_assets' in sql]
    assert len(asset_calls) == 3
    assert asset_calls[0][-1] == 12
    assert asset_calls[1][-1] is None and asset_calls[2][-1] is None
    assert groups[0].metadata['lumcat'] == 'CAT'
    assert any('UPDATE photolab.import_batches' in sql and params == ('completed', 8)
               for sql, params in cursor.calls)


def test_image_preview_verifies_hash_and_decodes_only_supported_image(tmp_path):
    buffer = BytesIO()
    Image.new('RGB', (32, 16), color='red').save(buffer, format='JPEG')
    content = buffer.getvalue()
    identifier = identify_file(content)
    save_source(tmp_path, content)
    asset = {'kind': 'jpg', 'sha256': identifier.sha256, 'size': len(content)}
    assert zip_products.preview_image(tmp_path, asset).size == (32, 16)
    with pytest.raises(ArtifactError, match='integrity'):
        zip_products.preview_image(tmp_path, {**asset, 'size': len(content) + 1})
    with pytest.raises(ArtifactError, match='format or dimensions'):
        zip_products.preview_image(tmp_path, {**asset, 'kind': 'png'})
