"""Sequential ZIP directory import without uploading the directory to Streamlit."""
import argparse
from pathlib import Path

from .artifacts import artifact_root
from .bulk import MAX_TOTAL_BYTES, prepare_zip, import_batch
from .database import database_url


def import_directory(directory, url, root, description, version='zip-cli-v1'):
    directory = Path(directory)
    if not directory.is_dir() or not description.strip():
        raise ValueError('Provide an existing directory and source description.')
    for path in directory.glob('*.zip'):
        if path.is_symlink() or path.stat().st_size > MAX_TOTAL_BYTES:
            raise ValueError(f'Archive exceeds size limit or is a symlink: {path.name}')
        with path.open('rb') as stream:
            content = stream.read(MAX_TOTAL_BYTES + 1)
        files = prepare_zip(content)
        del content
        batch_id, rows = import_batch(url, files, root, f'{description} / {path.name}', version)
        print(f'{path.name}: batch={batch_id} files={len(rows)}', flush=True)
        del files, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    import_directory(args.directory, database_url(), artifact_root(), args.source)


if __name__ == '__main__':
    main()
