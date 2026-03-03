from django.db import models
from django.db.models import Q

# Create your models here.
class CarbonIntensityRecord(models.Model):
    """Stores all interval-based carbon intensity records (regional and national, forecast and actual). 
    
    Carbon intensity is expressed in units of gCO₂/kWh. 
    
    The interval containment pattern is expressed as: 'valid_from <= charged_at < valid_to'. 
    
    National rows must have region_id and region_shortname as NULL, whereas regional rows must have region_id and region_shortname as !NULL."""

    class IntensityIndex(models.TextChoices):
        LOW = "low", "Low"
        MODERATE = "moderate", "Moderate"
        HIGH = "high", "High"
    
    region_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    region_shortname = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    valid_from = models.DateTimeField(db_index=True)
    valid_to = models.DateTimeField()
    forecast = models.IntegerField(help_text="gCO₂/kWh")
    actual = models.IntegerField(null=True, blank=True, help_text="gCO₂/kWh")
    index = models.CharField(max_length=16, choices=IntensityIndex.choices)
    forecast_generated_at = models.DateTimeField()
    is_national = models.BooleanField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta: 
        constraints = [
            models.CheckConstraint(
                condition=Q(valid_from__lt=models.F("valid_to")),
                name="carbon_cir_valid_from_lt_to_chk",
            ),
            models.CheckConstraint(
                condition=(
                    Q(is_national=True, region_id__isnull=True, region_shortname__isnull=True)
                    | Q(is_national=False, region_id__isnull=False, region_shortname__isnull=False)
                ),
                name="carbon_cir_region_nullness_chk",
            ),
        ]

        indexes = [
            models.Index(fields=["region_id", "valid_from"], name="carbon_cir_region_from_idx"),
            models.Index(fields=["is_national", "valid_from"], name="carbon_cir_nat_from_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        scope = "National" if self.is_national else (self.region_shortname or self.region_id or "Regional")
        return f"{scope} {self.valid_from.isoformat()} -> {self.valid_to.isoformat()}"
