import datetime

from django.db import models
from django.utils import timezone

# Create your models here.

# Region model:
class Region(models.Model):
    # UUID from NESO API:
    region_id = models.TextField
    # (e.g. 'South Wales')
    shortname = models.TextField
    # Full region name:
    name = models.TextField
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

# PostcodeRegionCache model:
class PostcodeRegionCache(models.Model):
    # Uppercase, stripped:
    postcode = models.TextField
    region_id = models.TextField
    region_shortname = models.TextField
    resolved_at = models.DateTimeField(auto_now=True)

# ChargerLocation model:
class ChargerLocation(models.Model):
    name = models.TextField
    postcode = models.TextField
    latitude = models.DecimalField
    longitude = models.DecimalField
    region_id = models.TextField
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)