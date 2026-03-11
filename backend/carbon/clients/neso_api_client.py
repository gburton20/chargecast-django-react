from __future__ import annotations

from datetime import timezone as dt_timezone
import logging
import random
import time
from typing import Any

import requests
from django.conf import settings
from django.utils import timezone
from core.models import extract_outcode

API_BASE_URL = "https://api.carbonintensity.org.uk"
NESO_API_TIMEOUT_SECONDS = getattr(settings, "NESO_API_TIMEOUT_SECONDS", 10)
NESO_API_MAX_RETRIES = getattr(settings, "NESO_API_MAX_RETRIES", 3)
NESO_API_BACKOFF_FACTOR = getattr(settings, "NESO_API_BACKOFF_FACTOR", 1.5)
_DEFAULT_HEADERS = {"Accept": "application/json"}
logger = logging.getLogger(__name__)


def _iso8601_utc_minute_from_now() -> str:
    """Return the current time as an ISO 8601 UTC minute timestamp.

    Format: YYYY-MM-DDTHH:MMZ (e.g. 2026-03-05T12:34Z). Used to populate the `{from}` path parameter required by the NESO Carbon Intensity API."""
    now = timezone.now()
    if timezone.is_naive(now):
        now = timezone.make_aware(now, dt_timezone.utc)
    else:
        now = now.astimezone(dt_timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%MZ")


def _get_json(url: str) -> dict[str, Any]:
    """GET a NESO API URL and return parsed JSON.

    Uses `requests.get` with `_DEFAULT_HEADERS` and `NESO_API_TIMEOUT_SECONDS`. Retries transient failures up to `NESO_API_MAX_RETRIES` with exponential backoff based on `NESO_API_BACKOFF_FACTOR` (plus small jitter).

    Returns:
      - Parsed JSON on success
      - `{"error": "<message>"}` on failure

    Error handling:
      - 404: returns a not-found error (no retry)
      - 429 and 5xx: retry
      - Most other 4xx: return an error without retry"""
    last_error_message: str | None = None

    for attempt in range(NESO_API_MAX_RETRIES + 1):
        attempt_number = attempt + 1
        request_start = time.monotonic()
        try:
            logger.info(
                "NESO API request started",
                extra={
                    "event": "neso_api_request_started",
                    "context": {
                        "endpoint": url,
                        "attempt": attempt_number,
                        "max_attempts": NESO_API_MAX_RETRIES + 1,
                    },
                },
            )
            response = requests.get(url, headers=_DEFAULT_HEADERS, timeout=NESO_API_TIMEOUT_SECONDS)
            elapsed_ms = int((time.monotonic() - request_start) * 1000)
            logger.info(
                "NESO API response received",
                extra={
                    "event": "neso_api_response_received",
                    "context": {
                        "endpoint": url,
                        "attempt": attempt_number,
                        "status_code": response.status_code,
                        "elapsed_ms": elapsed_ms,
                    },
                },
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            last_error_message = "Request to NESO API timed out"
            logger.warning(
                "NESO API timeout",
                extra={
                    "event": "neso_api_request_timeout",
                    "context": {
                        "endpoint": url,
                        "attempt": attempt_number,
                    },
                },
            )
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response else None
            response_body = (exc.response.text[:1000] if exc.response and exc.response.text else None)
            if status == 404:
                logger.error(
                    "NESO API endpoint not found",
                    extra={
                        "event": "neso_api_http_error",
                        "context": {
                            "endpoint": url,
                            "status_code": status,
                            "response_body": response_body,
                        },
                    },
                )
                return {"error": "NESO API endpoint not found"}
            if status == 429:
                last_error_message = "NESO API rate limited (429)"
            elif status and status >= 500:
                last_error_message = "NESO API server error"
            else:
                logger.error(
                    "NESO API non-retryable HTTP error",
                    extra={
                        "event": "neso_api_http_error",
                        "context": {
                            "endpoint": url,
                            "status_code": status,
                            "response_body": response_body,
                        },
                    },
                )
                return {"error": f"NESO API HTTP error ({status})"}
            logger.warning(
                "NESO API retryable HTTP error",
                extra={
                    "event": "neso_api_http_retry",
                    "context": {
                        "endpoint": url,
                        "status_code": status,
                        "response_body": response_body,
                        "attempt": attempt_number,
                    },
                },
            )
        except requests.exceptions.RequestException:
            last_error_message = "NESO API request failed"
            logger.warning(
                "NESO API request failed",
                extra={
                    "event": "neso_api_request_exception",
                    "context": {
                        "endpoint": url,
                        "attempt": attempt_number,
                    },
                },
            )
        except ValueError:
            logger.error(
                "NESO API response parsing failed",
                extra={
                    "event": "neso_api_response_parse_error",
                    "context": {
                        "endpoint": url,
                        "attempt": attempt_number,
                    },
                },
            )
            return {"error": "NESO API response parsing error"}

        if attempt >= NESO_API_MAX_RETRIES:
            logger.error(
                "NESO API request exhausted retries",
                extra={
                    "event": "neso_api_request_failed",
                    "context": {
                        "endpoint": url,
                        "max_retries": NESO_API_MAX_RETRIES,
                        "error_message": last_error_message,
                    },
                },
            )
            return {"error": f"{last_error_message} after {NESO_API_MAX_RETRIES} retries"}

        sleep_seconds = (NESO_API_BACKOFF_FACTOR * (2**attempt)) + random.uniform(0, 0.5)
        time.sleep(sleep_seconds)

    return {"error": "NESO API request failed"}

# Get the national carbon intensity forecast for the next 48 hours:
def get_national_forecast() -> dict[str, Any]:
    """Fetch the national carbon intensity forecast for the next 48 hours.

    Calls `/intensity/{from}/fw48h` where `{from}` is the current UTC minute."""
    now_str = _iso8601_utc_minute_from_now()
    url = f"{API_BASE_URL}/intensity/{now_str}/fw48h"
    return _get_json(url)


# Get the regional carbon intensity forecast for all DNO regions for the next 48 hours:
def get_regional_forecast() -> dict[str, Any]:
    """Fetch the regional carbon intensity forecast for all DNO regions (48 hours).

    Calls `/regional/intensity/{from}/fw48h` where `{from}` is the current UTC minute."""
    now_str = _iso8601_utc_minute_from_now()
    url = f"{API_BASE_URL}/regional/intensity/{now_str}/fw48h"
    return _get_json(url)


# Actual carbon intensity for the past 24 hours:
def get_national_actual() -> dict[str, Any]:
    """Fetch national carbon intensity actuals for the past 24 hours.

    Calls `/intensity/{from}/pt24h` where `{from}` is the current UTC minute.'"""
    now_str = _iso8601_utc_minute_from_now()
    url = f"{API_BASE_URL}/intensity/{now_str}/pt24h"
    return _get_json(url)


# Postcode to region method:
def resolve_postcode_to_region(postcode: str | None) -> dict[str, Any]:
    """Resolve a UK postcode to a NESO region.

    Extracts the outcode via `extract_outcode(postcode)` and calls
    `/regional/postcode/{outcode}`.

    Returns `{"error": "Postcode is required"}` if the postcode is missing/invalid.
    """
    outcode = extract_outcode(postcode)
    if not outcode:
        return {"error": "Postcode is required"}
    url = f"{API_BASE_URL}/regional/postcode/{outcode}"
    return _get_json(url)