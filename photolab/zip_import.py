"""Sequential ZIP directory import without uploading the directory to Streamlit."""
import argparse
from pathlib import Path

from .artifacts import artifact_root
from .bulk import MAX_TOTAL_BYTES
from .database import database_url
from .zip_products import import_product_zip


def import_directory(directory, url, root, description, version='zip-cli-v1'):
    directory = Path(directory)
    if not directory.is_dir() or not description.strip():
        raise ValueError('Provide an existing directory and source description.')
    for path in directory.glob('*.zip'):
        if path.is_symlink() or path.stat().st_size > MAX_TOTAL_BYTES:
            raise ValueError(f'Archive exceeds size limit or is a symlink: {path.name}')
        with path.open('rb') as stream:
            content = stream.read(MAX_TOTAL_BYTES + 1)
        batch_id, rows, groups, skipped = import_product_zip(
            url, content, root, f'{description} / {path.name}', version)
        print(f'{path.name}: batch={batch_id} bundles={len(groups)} '
              f'photometry={len(rows) - len(skipped)} skipped={len(skipped)}', flush=True)
        del content, rows, groups, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    import_directory(args.directory, database_url(), artifact_root(), args.source)


if __name__ == '__main__':
    main()
