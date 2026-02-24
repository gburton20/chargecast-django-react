from __future__ import annotations

from django.db import models


def normalise_postcode(value: str | None) -> str | None:
    if value is None:
        return None
    return "".join(value.split()).upper()


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


class ChargerLocation(models.Model):
    """Represents a charging location with a lat/lng point and a resolved region."""

    name = models.CharField(max_length=128)
    postcode = models.CharField(max_length=16, db_index=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    region_id = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["latitude", "longitude"], name="core_charger_lat_lng_idx"),
            models.Index(fields=["region_id", "postcode"], name="core_charger_reg_pcode_idx"),
        ]

    def save(self, *args, **kwargs):
        self.postcode = normalise_postcode(self.postcode)
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover
        return self.name