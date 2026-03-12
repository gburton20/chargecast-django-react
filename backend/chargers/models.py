# chargers/models.py
from django.db import models
import uuid


class EVSEStatus(models.TextChoices):
    """Canonical EVSE statuses used by the map and ingestion pipeline."""

    AVAILABLE = "AVAILABLE", "Available"
    BLOCKED = "BLOCKED", "Blocked"
    CHARGING = "CHARGING", "Charging"
    INOPERATIVE = "INOPERATIVE", "Inoperative"
    OUTOFORDER = "OUTOFORDER", "Out of order"
    PLANNED = "PLANNED", "Planned"
    REMOVED = "REMOVED", "Removed"
    RESERVED = "RESERVED", "Reserved"
    UNKNOWN = "UNKNOWN", "Unknown"


class ConnectorStandard(models.TextChoices):
    CHADEMO = "CHADEMO", "CHAdeMO"
    DOMESTIC_A = "DOMESTIC_A", "Domestic A"
    DOMESTIC_B = "DOMESTIC_B", "Domestic B"
    DOMESTIC_C = "DOMESTIC_C", "Domestic C"
    DOMESTIC_D = "DOMESTIC_D", "Domestic D"
    DOMESTIC_E = "DOMESTIC_E", "Domestic E"
    DOMESTIC_F = "DOMESTIC_F", "Domestic F"
    DOMESTIC_G = "DOMESTIC_G", "Domestic G"
    DOMESTIC_H = "DOMESTIC_H", "Domestic H"
    DOMESTIC_I = "DOMESTIC_I", "Domestic I"
    DOMESTIC_J = "DOMESTIC_J", "Domestic J"
    DOMESTIC_K = "DOMESTIC_K", "Domestic K"
    DOMESTIC_L = "DOMESTIC_L", "Domestic L"
    IEC_60309_2_SINGLE_16 = "IEC_60309_2_SINGLE_16", "IEC 60309-2 Single 16A"
    IEC_60309_2_THREE_16 = "IEC_60309_2_THREE_16", "IEC 60309-2 Three 16A"
    IEC_60309_2_THREE_32 = "IEC_60309_2_THREE_32", "IEC 60309-2 Three 32A"
    IEC_60309_2_THREE_64 = "IEC_60309_2_THREE_64", "IEC 60309-2 Three 64A"
    IEC_62196_T1 = "IEC_62196_T1", "IEC 62196 Type 1"
    IEC_62196_T1_COMBO = "IEC_62196_T1_COMBO", "IEC 62196 Type 1 Combo"
    IEC_62196_T2 = "IEC_62196_T2", "IEC 62196 Type 2"
    IEC_62196_T2_COMBO = "IEC_62196_T2_COMBO", "IEC 62196 Type 2 Combo"
    IEC_62196_T3A = "IEC_62196_T3A", "IEC 62196 Type 3A"
    IEC_62196_T3C = "IEC_62196_T3C", "IEC 62196 Type 3C"
    NEMA_5_20 = "NEMA_5_20", "NEMA 5-20"
    NEMA_6_30 = "NEMA_6_30", "NEMA 6-30"
    NEMA_6_50 = "NEMA_6_50", "NEMA 6-50"
    NEMA_10_30 = "NEMA_10_30", "NEMA 10-30"
    NEMA_10_50 = "NEMA_10_50", "NEMA 10-50"
    NEMA_14_30 = "NEMA_14_30", "NEMA 14-30"
    NEMA_14_50 = "NEMA_14_50", "NEMA 14-50"
    PANTOGRAPH_BOTTOM_UP = "PANTOGRAPH_BOTTOM_UP", "Pantograph bottom up"
    PANTOGRAPH_TOP_DOWN = "PANTOGRAPH_TOP_DOWN", "Pantograph top down"
    TESLA_R = "TESLA_R", "Tesla Roadster"
    TESLA_S = "TESLA_S", "Tesla Supercharger"
    UNKNOWN = "UNKNOWN", "Unknown"


class ConnectorFormat(models.TextChoices):
    SOCKET = "SOCKET", "Socket"
    CABLE = "CABLE", "Cable"
    UNKNOWN = "UNKNOWN", "Unknown"


class PowerType(models.TextChoices):
    AC_1_PHASE = "AC_1_PHASE", "AC 1 phase"
    AC_3_PHASE = "AC_3_PHASE", "AC 3 phase"
    DC = "DC", "DC"
    UNKNOWN = "UNKNOWN", "Unknown"


class ChargerLocation(models.Model):
    """
    OCPI Location with ingestion provenance and soft-delete safety fields.

    `ingested_at` is explicitly written by each ingestion cycle so downstream code
    can reason about freshness independently from row creation time.

    `is_active` implements soft-delete behaviour so locations missing from a feed
    can be hidden without destroying historical relationships.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=16, blank=True, null=True)
    country_code = models.CharField(max_length=3, blank=True, null=True, default="GBR")
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    party_id = models.CharField(max_length=10)
    location_id = models.CharField(max_length=255)
    source_provider = models.CharField(max_length=50)
    publish = models.BooleanField(blank=True, null=True)
    opening_times = models.JSONField(blank=True, null=True)
    charging_when_closed = models.BooleanField(blank=True, null=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Soft-delete flag used when an upstream provider stops returning a location.",
    )
    last_updated = models.DateTimeField(blank=True, null=True)
    ingested_at = models.DateTimeField(
        help_text="Timestamp of the ingestion run that last processed this record.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "charger_locations"
        unique_together = [["party_id", "location_id"]]
        indexes = [
            models.Index(fields=["postal_code"]),
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["source_provider"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["ingested_at"]),
        ]

    def __str__(self):
        label = self.name or self.location_id
        return f"{label} ({self.source_provider})"


class EVSE(models.Model):
    """
    OCPI EVSE stored with a canonical status for consistent downstream display.

    `status` defaults to `UNKNOWN` so missing or unmappable upstream statuses are
    still representable without breaking the ingestion pipeline.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(
        ChargerLocation, 
        on_delete=models.CASCADE, 
        related_name="evses"
    )
    uid = models.CharField(max_length=255)
    evse_id = models.CharField(max_length=255, blank=True, null=True)
    capabilities = models.JSONField(blank=True, null=True)
    physical_reference = models.CharField(max_length=255, blank=True, null=True)
    floor_level = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=EVSEStatus.choices,
        default=EVSEStatus.UNKNOWN,
        help_text="Canonical EVSE status. Unknown preserves unmappable upstream values safely.",
    )
    last_updated = models.DateTimeField(blank=True, null=True)
    ingested_at = models.DateTimeField(
        help_text="Timestamp of the ingestion run that last processed this record.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "evses"
        unique_together = [["location", "uid"]]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["ingested_at"]),
        ]

    def __str__(self):
        return f"EVSE {self.uid} at {self.location.name}"


class Connector(models.Model):
    """Charging connector on an EVSE"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evse = models.ForeignKey(EVSE, on_delete=models.CASCADE, related_name="connectors")
    connector_id = models.CharField(max_length=255)
    standard = models.CharField(max_length=50, choices=ConnectorStandard.choices, default=ConnectorStandard.UNKNOWN)
    format = models.CharField(max_length=10, choices=ConnectorFormat.choices, default=ConnectorFormat.UNKNOWN)
    power_type = models.CharField(max_length=20, choices=PowerType.choices, default=PowerType.UNKNOWN)
    max_voltage = models.IntegerField(null=True, blank=True)
    max_amperage = models.IntegerField(null=True, blank=True)
    max_electric_power = models.IntegerField(null=True, blank=True)
    last_updated = models.DateTimeField(blank=True, null=True)
    ingested_at = models.DateTimeField(
        help_text="Timestamp of the ingestion run that last processed this record.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "connectors"
        unique_together = [["evse", "connector_id"]]
        indexes = [
            models.Index(fields=["standard"]),
            models.Index(fields=["ingested_at"]),
        ]

    def __str__(self):
        return f"Connector {self.connector_id} ({self.standard})"


class Tariff(models.Model):
    """Charging tariff with freshness fields for operational ingestion safety."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    party_id = models.CharField(max_length=10)
    tariff_id = models.CharField(max_length=255)
    source_provider = models.CharField(max_length=50)
    currency = models.CharField(max_length=3, default="GBP")
    tariff_alt_text = models.JSONField(default=list, blank=True)
    elements = models.JSONField(default=list)
    last_updated = models.DateTimeField(blank=True, null=True)
    last_seen_at = models.DateTimeField()
    is_stale = models.BooleanField(default=False)
    ingested_at = models.DateTimeField(
        help_text="Timestamp of the ingestion run that last processed this record.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tariffs"
        unique_together = [["party_id", "tariff_id"]]
        indexes = [
            models.Index(fields=["party_id", "tariff_id"]),
            models.Index(fields=["is_stale"]),
            models.Index(fields=["source_provider"]),
            models.Index(fields=["last_seen_at"]),
            models.Index(fields=["ingested_at"]),
        ]

    def __str__(self):
        return f"Tariff {self.tariff_id} ({self.source_provider})"


class ConnectorTariff(models.Model):
    """Many-to-many relationship between connectors and tariffs"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connector = models.ForeignKey(
        Connector, 
        on_delete=models.CASCADE, 
        related_name="connector_tariffs"
    )
    tariff = models.ForeignKey(
        Tariff, 
        on_delete=models.CASCADE, 
        related_name="connector_tariffs"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "connector_tariffs"
        unique_together = [["connector", "tariff"]]
    
    def __str__(self):
        return f"{self.connector} → {self.tariff}"