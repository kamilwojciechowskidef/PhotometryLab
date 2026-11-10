"""Human-readable labels, separate from source filenames and database IDs."""
from .models import Photometry


def product_label(item: Photometry) -> str:
    """Show source metadata and keep filename to distinguish repeated names."""
    brand = item.manufacturer.strip() if item.manufacturer else ''
    if brand.casefold() in {'not provided', 'niepodany', 'unknown', 'unavailable'}:
        brand = ''
    code = (item.catalogue_number or '').strip()
    description = (item.luminaire or '').strip()
    name = code or (description if description != item.filename else '')
    parts = [value for value in (brand, name) if value]
    return f"{' · '.join(parts)} [{item.filename}]" if parts else item.filename
