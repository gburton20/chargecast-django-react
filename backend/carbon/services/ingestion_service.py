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

logger = logging.getLogger(__name__)

@dataclass
class IngestionResult:
    """Structured result from carbon intensity data ingestion."""
    records_created: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    records_failed: int = 0


def ingest_national_forecast() -> IngestionResult:
    """
    Ingest national carbon intensity forecast data from the NESO API.
    
    Fetches the next 48 hours of national forecast data and stores it in the database.
    Uses update_or_create() to ensure idempotency - re-running will update existing records.
    
    Returns:
        IngestionResult: Summary of ingestion operation with counts of created/updated/failed records.
    """
    logger.info("Starting national forecast ingestion...")
    national_forecast = get_national_forecast()
    result = IngestionResult()
    
    if "error" in national_forecast:
        logger.error(f"API error: {national_forecast.get('error')}")
        result.records_failed += 1
        return result
    
    data = national_forecast.get("data", [])
    if not data:
        logger.warning("No forecast data returned from API")
        result.records_skipped += 1
        return result
    
    forecast_generated_at = timezone.now()
    
    for period in data:
        try:
            # Parse timestamps
            valid_from = parse_datetime(period["from"])
            valid_to = parse_datetime(period["to"])
            
            if not valid_from or not valid_to:
                logger.warning(f"Invalid datetime in period: {period}")
                result.records_failed += 1
                continue
            
            # Extract intensity data
            intensity = period.get("intensity", {})
            forecast = intensity.get("forecast")
            index = intensity.get("index")
            
            if forecast is None or index is None:
                logger.warning(f"Missing intensity data in period: {period}")
                result.records_failed += 1
                continue
            
            # Store in database
            _, created = CarbonIntensityRecord.objects.update_or_create(
                region_id=None,
                valid_from=valid_from,
                is_national=True,
                defaults={
                    "region_shortname": None,
                    "valid_to": valid_to,
                    "forecast": forecast,
                    "index": index,
                    "forecast_generated_at": forecast_generated_at,
                },
            )
            
            if created:
                result.records_created += 1
            else:
                result.records_updated += 1
                
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"Failed to process period: {e}")
            result.records_failed += 1
            continue
        except Exception as e:
            logger.error(f"Unexpected error processing period: {e}")
            result.records_failed += 1
            continue
    
    logger.info(
        f"Completed national forecast ingestion: "
        f"{result.records_created} created, "
        f"{result.records_updated} updated, "
        f"{result.records_failed} failed"
    )
    return result


def ingest_regional_forecast() -> IngestionResult:
    """
    Ingest regional carbon intensity forecast data for all DNO regions from the NESO API. 

    Fetches the next 48 hours of regional forecast data nationally and stores it in the database. 

    Uses update_or_create() to ensure idemoptency - re-running will update existing records. 

    Returns:
        IngestionResult: Summary of ingestion operation with counts or created/updated/failed records.
    """
    logger.info("Starting regional forecast ingestion for all DNOs...")
    regional_forecast = get_regional_forecast()
    result = IngestionResult()

    if "error" in regional_forecast:
        logger.error(f"API error: {regional_forecast.get('error')}")
        result.records_failed += 1
        return result
    
    data = regional_forecast.get("data", [])
    if not data:
        logger.warning("No forecast data returned from API")
        result.records_skipped += 1
        return result
    
    forecast_generated_at = timezone.now()

    for period in data:
        try:
            # Parse timestamps
            valid_from = parse_datetime(period["from"])
            valid_to = parse_datetime(period["to"])

            if not valid_from or not valid_to:
                logger.warning(f"Invalid datetime in period: {period}")
                result.records_failed += 1
                continue
            
            regions = period.get("regions", [])
            # Extract intensity data per region in the regions list:
            if not regions:
                logger.error(f"No regions data returned from get_regional_forecast()")
                result.records_failed += 1
            else:
                for region in regions:
                    region_id = region.get("regionid")
                    region_shortname = region.get("shortname")
                    if region_id is None or not region_shortname:
                        logger.error(f"Missing region_id or shortname in region: {region}")
                        result.records_failed += 1
                        continue
                    intensity = region.get("intensity", {})
                    forecast = intensity.get("forecast")
                    index = intensity.get("index")

                    if forecast is None or index is None:
                        logger.warning(f"Missing intensity data in period: {period}, for region: {region_shortname}")
                        result.records_failed += 1
                        continue

                    # Store in database:
                    _, created = CarbonIntensityRecord.objects.update_or_create(
                        region_id=region_id,
                        valid_from=valid_from,
                        is_national=False,
                        defaults={
                            "region_shortname": region_shortname,
                            "valid_to": valid_to,
                            "forecast": forecast,
                            "index": index,
                            "forecast_generated_at": forecast_generated_at,
                        },
                    )

                    if created:
                        result.records_created += 1
                    else:
                        result.records_updated += 1

        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"Failed to process period: {e}")
            result.records_failed += 1
            continue
        except Exception as e:
            logger.error(f"Unexpected error processing period: {e}")
            result.records_failed += 1
            continue
    
    logger.info(
        f"Completed regional forecast ingestion for all DNOs: "
        f"{result.records_created} created, "
        f"{result.records_updated} updated, "
        f"{result.records_failed} failed"
    )
    return result

def ingest_national_actual():
    """
    Ingest national carbon intensity actual data from the NESO API. 

    Fetches 

    """
    national_actual = get_national_actual()
    return

