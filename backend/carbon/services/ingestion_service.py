import logging
from dataclasses import dataclass

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from carbon.clients.neso_api_client import (
    get_national_forecast,
    get_regional_forecast,
    get_national_actual
)
from carbon.models import CarbonIntensityRecord
from core.models import Region

@dataclass
class IngestionResult:
    records_created: int
    records_updated: int
    records_skipped: int
    records_failed: int

def ingest_national_forecast():
    national_forecast = get_national_forecast()
    return 

def ingest_regional_forecast():
    regional_forecast = get_regional_forecast()
    return

def ingest_national_actual():
    national_actual = get_national_actual()
    return

