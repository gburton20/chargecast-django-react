from decimal import Decimal

from django.db import models

# Create your models here.
class FleetUploadBatch(models.Model):
    """Tracks the user-uploaded .csv batches containing fleet charging data"""

    class ProcessingStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        COMPLETED_WITH_ERRORS = "completed_with_errors", "Completed with errors"
        FAILED = "failed", "Failed"

    filename = models.CharField(max_length=64, null=False, blank=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    rows_received = models.IntegerField(default=0)
    rows_processed = models.IntegerField(default=0)
    rows_failed = models.IntegerField(default=0)
    fallback_rows = models.IntegerField(default=0)
    total_kwh = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal("0"),
        help_text="kWh",
    )
    total_emissions_kg = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=Decimal("0"),
        help_text="kgCO₂",
    )
    processing_status = models.CharField(
        max_length=32,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
    )
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class FleetChargingEvent(models.Model):
    """Append-only charging event ledger.

    Immutability intent: this table is designed as an immutable ledger.
    Enforcement strategy:
    - No update endpoints should be exposed at the API layer.
    - This model also prevents updates after creation by raising in `save()`.
    """

    class IntensityTypeUsed(models.TextChoices):
        REGIONAL_FORECAST = "regional_forecast", "Regional forecast"
        NATIONAL_ACTUAL = "national_actual", "National actual"
        NATIONAL_FORECAST = "national_forecast", "National forecast"

    batch = models.ForeignKey(
        FleetUploadBatch,
        on_delete=models.PROTECT,
        related_name="charging_events",
    )
    vehicle_id = models.CharField(max_length=64)
    postcode = models.CharField(max_length=16)
    charged_at = models.DateTimeField(help_text="UTC, timezone-aware datetime")
    region_id = models.CharField(max_length=64)
    region_shortname = models.CharField(max_length=64, db_index=True)
    kwh_consumed = models.DecimalField(max_digits=10, decimal_places=3, help_text="kWh")
    carbon_intensity_used = models.IntegerField(help_text="gCO₂/kWh")
    intensity_type_used = models.CharField(choices=IntensityTypeUsed.choices, max_length=64)
    calculated_emissions_kg = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        help_text="kgCO₂",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("FleetChargingEvent is immutable and cannot be updated.")
        return super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=["vehicle_id", "charged_at"], name="charged_at_from_vehicle_idx"),
            models.Index(fields=["region_id", "charged_at"], name="charged_at_from_region_idx"),
            models.Index(fields=["postcode"], name="postcode_idx")
        ]

