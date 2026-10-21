"""Lossless JSON representation of native, unnormalized photometry."""
from dataclasses import asdict, replace
import json

from .models import Photometry


def photometry_to_data(item: Photometry) -> dict:
    """Validate a copy and preserve native units, angles and all model fields."""
    validated = replace(item).validate()
    data = asdict(validated)
    for name in ("c_angles", "gamma_angles", "intensity"):
        data[name] = data[name].tolist()
    # Reject non-finite optional metadata before starting a database transaction.
    json.dumps(data, allow_nan=False)
    return data


def photometry_from_data(data: dict) -> Photometry:
    """Reconstruct and validate stored data without filling missing fields."""
    return Photometry(**data).validate()
