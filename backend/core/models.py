from __future__ import annotations

from django.db import models
import uuid

# Helper function to standardise the format of postcodes input by the user to a capitalised postcode with no whitespace between letters. This function returns the canonical postcode storage/input for ChargeCast:
def normalise_postcode(value: str | None) -> str | None:
    if value is None:
        return None
    return "".join(value.split()).upper()

# Helper functions to extend the output of normalise_postcode() for:

# i) display formatter for UX, with a single whitespace between the outcode and incode components of any UK postcode:
def display_format_postcode(value: str | None) -> str | None:
    normalised = normalise_postcode(value)
    if not normalised:
        return None
    if len(normalised) <= 3:
        return normalised
    return f"{normalised[:-3]} {normalised[-3:]}"

# ii) outcode extractor for the NESO endpoint (NESO expects outward code only).
def extract_outcode(value: str | None) -> str | None:
    normalised = normalise_postcode(value)
    if not normalised:
        return None
    if len(normalised) <= 3:
        return normalised
    return normalised[:-3]

class Region(models.Model):
    """Stores DNO region definitions from the NESO API."""

    # UUID (or similar identifier) from NESO API.
    region_id = models.CharField(max_length=64, unique=True)
    # Short display name (e.g. "South Wales").
    shortname = models.CharField(max_length=64, db_index=True)
    # Full region name.
    name = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.shortname} ({self.region_id})"


class PostcodeRegionCache(models.Model):
    """Caches postcode->region lookups.

    Cache policy: callers should treat entries as stale based on `resolved_at`.
    """

    # Uppercase, whitespace-stripped postcode.
    postcode = models.CharField(max_length=16, unique=True)
    region_id = models.CharField(max_length=64, db_index=True)
    region_shortname = models.CharField(max_length=64)
    resolved_at = models.DateTimeField(auto_now=True, db_index=True)

    def save(self, *args, **kwargs):
        self.postcode = normalise_postcode(self.postcode)
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.postcode} -> {self.region_shortname}"

# Current replacement for legacy ChargerLocation in this file, TimeStampedModel
class TimeStampedModel(models.Model):
    """Abstract base model with created/updated timestamps"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True