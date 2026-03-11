import logging
import time
import uuid
from dataclasses import dataclass

from django.db import DatabaseError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from carbon.clients.neso_api_client import (
    get_national_actual,
    get_national_forecast,
    get_regional_forecast,
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


def _log(level: int, message: str, event: str, **context) -> None:
    logger.log(level, message, extra={"event": event, "context": context})


def ingest_national_forecast() -> IngestionResult:
    """
    Ingest national carbon intensity forecast data from the NESO API.
    
    Fetches the next 48 hours of national forecast data and stores it in the database.
    Uses update_or_create() to ensure idempotency - re-running will update existing records.
    
    Returns:
        IngestionResult: Summary of ingestion operation with the counts of created/updated/failed records.
    """
    run_id = uuid.uuid4().hex
    started_at = time.monotonic()
    _log(
        logging.INFO,
        "Starting national forecast ingestion",
        "ingestion_started",
        run_id=run_id,
        scope="national_forecast",
    )

    national_forecast = get_national_forecast()
    result = IngestionResult()

    if "error" in national_forecast:
        _log(
            logging.ERROR,
            "NESO API error returned for national forecast",
            "ingestion_api_error",
            run_id=run_id,
            scope="national_forecast",
            error_message=national_forecast.get("error"),
        )
        result.records_failed += 1
        return result

    data = national_forecast.get("data", [])
    if not data:
        _log(
            logging.WARNING,
            "No national forecast data returned from API",
            "ingestion_no_data",
            run_id=run_id,
            scope="national_forecast",
        )
        result.records_skipped += 1
        return result

    forecast_generated_at = timezone.now()

    for period in data:
        try:
            valid_from = parse_datetime(period["from"])
            valid_to = parse_datetime(period["to"])

            if not valid_from or not valid_to:
                _log(
                    logging.WARNING,
                    "Invalid datetime in national forecast period",
                    "ingestion_parse_error",
                    run_id=run_id,
                    scope="national_forecast",
                    period=period,
                )
                result.records_failed += 1
                continue

            intensity = period.get("intensity", {})
            forecast = intensity.get("forecast")
            index = intensity.get("index")

            if forecast is None or index is None:
                _log(
                    logging.WARNING,
                    "Missing national forecast intensity data",
                    "ingestion_parse_error",
                    run_id=run_id,
                    scope="national_forecast",
                    period=period,
                )
                result.records_failed += 1
                continue

            try:
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
            except DatabaseError as exc:
                _log(
                    logging.ERROR,
                    "Database error while writing national forecast record",
                    "ingestion_database_error",
                    run_id=run_id,
                    scope="national_forecast",
                    model="CarbonIntensityRecord",
                    operation="update_or_create",
                    error_message=str(exc),
                    valid_from=valid_from.isoformat(),
                )
                result.records_failed += 1
                continue

            if created:
                result.records_created += 1
            else:
                result.records_updated += 1

        except (ValueError, KeyError, TypeError) as exc:
            _log(
                logging.WARNING,
                "Failed to parse national forecast period",
                "ingestion_parse_error",
                run_id=run_id,
                scope="national_forecast",
                error_message=str(exc),
            )
            result.records_failed += 1
            continue
        except Exception as exc:  # pragma: no cover
            logger.exception(
                "Unexpected national forecast ingestion failure",
                extra={
                    "event": "ingestion_unexpected_error",
                    "context": {
                        "run_id": run_id,
                        "scope": "national_forecast",
                        "error_message": str(exc),
                    },
                },
            )
            result.records_failed += 1
            continue

    _log(
        logging.INFO,
        "Completed national forecast ingestion",
        "ingestion_completed",
        run_id=run_id,
        scope="national_forecast",
        records_created=result.records_created,
        records_updated=result.records_updated,
        records_skipped=result.records_skipped,
        records_failed=result.records_failed,
        duration_ms=int((time.monotonic() - started_at) * 1000),
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
    run_id = uuid.uuid4().hex
    started_at = time.monotonic()
    _log(
        logging.INFO,
        "Starting regional forecast ingestion",
        "ingestion_started",
        run_id=run_id,
        scope="regional_forecast",
    )

    regional_forecast = get_regional_forecast()
    result = IngestionResult()

    if "error" in regional_forecast:
        _log(
            logging.ERROR,
            "NESO API error returned for regional forecast",
            "ingestion_api_error",
            run_id=run_id,
            scope="regional_forecast",
            error_message=regional_forecast.get("error"),
        )
        result.records_failed += 1
        return result

    data = regional_forecast.get("data", [])
    if not data:
        _log(
            logging.WARNING,
            "No regional forecast data returned from API",
            "ingestion_no_data",
            run_id=run_id,
            scope="regional_forecast",
        )
        result.records_skipped += 1
        return result

    forecast_generated_at = timezone.now()

    for period in data:
        try:
            valid_from = parse_datetime(period["from"])
            valid_to = parse_datetime(period["to"])

            if not valid_from or not valid_to:
                _log(
                    logging.WARNING,
                    "Invalid datetime in regional forecast period",
                    "ingestion_parse_error",
                    run_id=run_id,
                    scope="regional_forecast",
                    period=period,
                )
                result.records_failed += 1
                continue

            regions = period.get("regions", [])
            if not regions:
                _log(
                    logging.ERROR,
                    "No regional list present in forecast period",
                    "ingestion_parse_error",
                    run_id=run_id,
                    scope="regional_forecast",
                    period=period,
                )
                result.records_failed += 1
                continue

            for region in regions:
                region_id = region.get("regionid")
                region_shortname = region.get("shortname")
                if region_id is None or not region_shortname:
                    _log(
                        logging.ERROR,
                        "Missing regional identifiers",
                        "ingestion_parse_error",
                        run_id=run_id,
                        scope="regional_forecast",
                        region=region,
                    )
                    result.records_failed += 1
                    continue

                intensity = region.get("intensity", {})
                forecast = intensity.get("forecast")
                index = intensity.get("index")

                if forecast is None or index is None:
                    _log(
                        logging.WARNING,
                        "Missing regional forecast intensity data",
                        "ingestion_parse_error",
                        run_id=run_id,
                        scope="regional_forecast",
                        region_shortname=region_shortname,
                        period=period,
                    )
                    result.records_failed += 1
                    continue

                try:
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
                except DatabaseError as exc:
                    _log(
                        logging.ERROR,
                        "Database error while writing regional forecast record",
                        "ingestion_database_error",
                        run_id=run_id,
                        scope="regional_forecast",
                        model="CarbonIntensityRecord",
                        operation="update_or_create",
                        error_message=str(exc),
                        region_id=region_id,
                        valid_from=valid_from.isoformat(),
                    )
                    result.records_failed += 1
                    continue

                if created:
                    result.records_created += 1
                else:
                    result.records_updated += 1

        except (ValueError, KeyError, TypeError) as exc:
            _log(
                logging.WARNING,
                "Failed to parse regional forecast period",
                "ingestion_parse_error",
                run_id=run_id,
                scope="regional_forecast",
                error_message=str(exc),
            )
            result.records_failed += 1
            continue
        except Exception as exc:  # pragma: no cover
            logger.exception(
                "Unexpected regional forecast ingestion failure",
                extra={
                    "event": "ingestion_unexpected_error",
                    "context": {
                        "run_id": run_id,
                        "scope": "regional_forecast",
                        "error_message": str(exc),
                    },
                },
            )
            result.records_failed += 1
            continue

    _log(
        logging.INFO,
        "Completed regional forecast ingestion",
        "ingestion_completed",
        run_id=run_id,
        scope="regional_forecast",
        records_created=result.records_created,
        records_updated=result.records_updated,
        records_skipped=result.records_skipped,
        records_failed=result.records_failed,
        duration_ms=int((time.monotonic() - started_at) * 1000),
    )
    return result


def ingest_national_actual() -> IngestionResult:
    """
    Ingest national carbon intensity actual data from the NESO API. 

    Fetches the previous 24 hours of national actual data and stores it in the database. 

    Updates existing national forecast rows with actual values to ensure idempotency. 

    Returns:
        IngestionResult: A summary of the ingestion operation with the counts of created/updated/failed records.

    """
    run_id = uuid.uuid4().hex
    started_at = time.monotonic()
    _log(
        logging.INFO,
        "Starting national actual ingestion",
        "ingestion_started",
        run_id=run_id,
        scope="national_actual",
    )

    national_actual = get_national_actual()
    result = IngestionResult()

    if "error" in national_actual:
        _log(
            logging.ERROR,
            "NESO API error returned for national actual",
            "ingestion_api_error",
            run_id=run_id,
            scope="national_actual",
            error_message=national_actual.get("error"),
        )
        result.records_failed += 1
        return result

    data = national_actual.get("data", [])
    if not data:
        _log(
            logging.WARNING,
            "No national actual data returned from API",
            "ingestion_no_data",
            run_id=run_id,
            scope="national_actual",
        )
        result.records_skipped += 1
        return result

    national_actual_generated_at = timezone.now()

    for period in data:
        try:
            valid_from = parse_datetime(period["from"])
            valid_to = parse_datetime(period["to"])

            if not valid_from or not valid_to:
                _log(
                    logging.WARNING,
                    "Invalid datetime in national actual period",
                    "ingestion_parse_error",
                    run_id=run_id,
                    scope="national_actual",
                    period=period,
                )
                result.records_failed += 1
                continue

            intensity = period.get("intensity", {})
            actual = intensity.get("actual")
            index = intensity.get("index")

            if index is None:
                _log(
                    logging.WARNING,
                    "Missing national actual intensity index",
                    "ingestion_parse_error",
                    run_id=run_id,
                    scope="national_actual",
                    period=period,
                )
                result.records_failed += 1
                continue

            if actual is None:
                _log(
                    logging.INFO,
                    "National actual value not yet available; skipping period",
                    "ingestion_skipped",
                    run_id=run_id,
                    scope="national_actual",
                    valid_from=period.get("from"),
                )
                result.records_skipped += 1
                continue

            try:
                updated_count = CarbonIntensityRecord.objects.filter(
                    region_id=None,
                    valid_from=valid_from,
                    is_national=True,
                ).update(
                    valid_to=valid_to,
                    actual=actual,
                    index=index,
                    forecast_generated_at=national_actual_generated_at,
                )
            except DatabaseError as exc:
                _log(
                    logging.ERROR,
                    "Database error while updating national actual record",
                    "ingestion_database_error",
                    run_id=run_id,
                    scope="national_actual",
                    model="CarbonIntensityRecord",
                    operation="filter.update",
                    error_message=str(exc),
                    valid_from=valid_from.isoformat(),
                )
                result.records_failed += 1
                continue

            if updated_count == 0:
                _log(
                    logging.WARNING,
                    "No matching national forecast row found for actual update",
                    "ingestion_skipped",
                    run_id=run_id,
                    scope="national_actual",
                    valid_from=valid_from.isoformat(),
                )
                result.records_skipped += 1
            else:
                result.records_updated += updated_count

        except (ValueError, KeyError, TypeError) as exc:
            _log(
                logging.WARNING,
                "Failed to parse national actual period",
                "ingestion_parse_error",
                run_id=run_id,
                scope="national_actual",
                error_message=str(exc),
            )
            result.records_failed += 1
            continue
        except Exception as exc:  # pragma: no cover
            logger.exception(
                "Unexpected national actual ingestion failure",
                extra={
                    "event": "ingestion_unexpected_error",
                    "context": {
                        "run_id": run_id,
                        "scope": "national_actual",
                        "error_message": str(exc),
                    },
                },
            )
            result.records_failed += 1
            continue

    _log(
        logging.INFO,
        "Completed national actual ingestion",
        "ingestion_completed",
        run_id=run_id,
        scope="national_actual",
        records_created=result.records_created,
        records_updated=result.records_updated,
        records_skipped=result.records_skipped,
        records_failed=result.records_failed,
        duration_ms=int((time.monotonic() - started_at) * 1000),
    )
    return result
