"""Bounded page controls and short-lived in-process catalogue statistics."""
from functools import lru_cache
from time import monotonic

from .database import count_catalogue, list_catalogue_manufacturers

PAGE_SIZE = 50
PAGES_PER_RANGE = 1000
BRAND_LIMIT = 500
MAX_COMPARISON_FILES = 20


def add_to_comparison(selection, selected_ids, choices):
    """Add page entries atomically to a session selection; retain DB IDs and hashes."""
    if not selected_ids:
        raise ValueError('Choose at least one saved luminaire first.')
    if any(file_id not in choices for file_id in selected_ids):
        raise ValueError('The catalogue page changed. Select the files again.')
    new_ids = list(dict.fromkeys(file_id for file_id in selected_ids if file_id not in selection))
    if len(selection) + len(new_ids) > MAX_COMPARISON_FILES:
        raise ValueError(f'Select at most {MAX_COMPARISON_FILES} saved photometry files for the local comparison.')
    records = {}
    for file_id in new_ids:
        row = choices[file_id]
        records[file_id] = {
            'sha256': row['sha256'], 'filename': row['filename'],
            'label': f"#{file_id} · {row['manufacturer']} · {row.get('catalogue_number') or row['model'] or 'Unavailable'}",
        }
    selection.update(records)
    return len(new_ids)


@lru_cache(maxsize=128)
def _count(url, manufacturer, model, tick):
    return count_catalogue(url, manufacturer=manufacturer, model=model,
                           manufacturer_exact=bool(manufacturer))


@lru_cache(maxsize=64)
def _brands(url, search, tick):
    return tuple(list_catalogue_manufacturers(url, search=search, limit=BRAND_LIMIT))


def invalidate_catalogue_cache():
    _count.cache_clear()
    _brands.cache_clear()


def get_count(url, manufacturer='', model=''):
    return _count(url, manufacturer, model, int(monotonic() // 60))


def get_brands(url, search=''):
    return _brands(url, search, int(monotonic() // 60))


def select_page(st, total, *, key):
    """Select a real page; at most 1000 page options are sent to the browser."""
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    blocks = (pages + PAGES_PER_RANGE - 1) // PAGES_PER_RANGE
    block = 1
    if blocks > 1:
        block = st.selectbox('Page range', range(1, blocks + 1), key=f'{key}_range',
            format_func=lambda b: f'{(b-1)*PAGES_PER_RANGE+1}–{min(b*PAGES_PER_RANGE, pages)}')
    first = (block - 1) * PAGES_PER_RANGE + 1
    last = min(block * PAGES_PER_RANGE, pages)
    return st.selectbox('Catalogue page', range(first, last + 1), key=f'{key}_{block}')
