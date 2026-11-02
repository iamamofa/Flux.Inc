"""Validation for project-defined, plain-text sample metadata."""
import json

from django.core.exceptions import ValidationError


def _metadata_pairs(pairs):
    result = {}
    seen = set()
    for key, value in pairs:
        normalized = key.strip().casefold()
        if normalized in seen:
            raise ValidationError('Metadata field names must be unique, ignoring case and surrounding spaces.')
        seen.add(normalized)
        result[key] = value
    return result


def normalize_sample_metadata(raw):
    """Return a bounded string mapping without interpreting or removing markup."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw, object_pairs_hook=_metadata_pairs)
        except (json.JSONDecodeError, TypeError, RecursionError):
            raise ValidationError('Metadata must be a JSON object of field names and text values.')
    if not isinstance(raw, dict):
        raise ValidationError('Metadata must be an object of field names and text values.')
    if len(raw) > 50:
        raise ValidationError('A sample can have at most 50 metadata fields.')
    result = {}
    seen = set()
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValidationError('Metadata field names and values must be text.')
        key = key.strip()
        if not key or len(key) > 80:
            raise ValidationError('Metadata field names must contain between 1 and 80 characters.')
        if key.casefold() in seen:
            raise ValidationError('Metadata field names must be unique, ignoring case and surrounding spaces.')
        if len(value) > 2000:
            raise ValidationError('Each metadata value must contain at most 2,000 characters.')
        seen.add(key.casefold())
        result[key] = value
    return result


def validate_sample_metadata(value):
    normalize_sample_metadata(value)
