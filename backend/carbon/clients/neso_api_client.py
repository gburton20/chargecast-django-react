from __future__ import annotations

from datetime import timezone as dt_timezone
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


def _iso8601_utc_minute_from_now() -> str:
    now = timezone.now()
    if timezone.is_naive(now):
        now = timezone.make_aware(now, dt_timezone.utc)
    else:
        now = now.astimezone(dt_timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%MZ")


def _get_json(url: str) -> dict[str, Any]:
    last_error_message: str | None = None

    for attempt in range(NESO_API_MAX_RETRIES + 1):
        try:
            response = requests.get(url, headers=_DEFAULT_HEADERS, timeout=NESO_API_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            last_error_message = "Request to NESO API timed out"
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response else None
            if status == 404:
                return {"error": "NESO API endpoint not found"}
            if status == 429:
                last_error_message = "NESO API rate limited (429)"
            elif status and status >= 500:
                last_error_message = "NESO API server error"
            else:
                return {"error": f"NESO API HTTP error ({status})"}
        except requests.exceptions.RequestException:
            last_error_message = "NESO API request failed"

        if attempt >= NESO_API_MAX_RETRIES:
            return {"error": f"{last_error_message} after {NESO_API_MAX_RETRIES} retries"}

        sleep_seconds = (NESO_API_BACKOFF_FACTOR * (2**attempt)) + random.uniform(0, 0.5)
        time.sleep(sleep_seconds)

    return {"error": "NESO API request failed"}

# Get the national carbon intensity forecast for the next 48 hours:
def get_national_forecast() -> dict[str, Any]:
    now_str = _iso8601_utc_minute_from_now()
    url = f"{API_BASE_URL}/intensity/{now_str}/fw48h"
    return _get_json(url)


# Get the regional carbon intensity forecast for all DNO regions for the next 48 hours:
def get_regional_forecast() -> dict[str, Any]:
    now_str = _iso8601_utc_minute_from_now()
    url = f"{API_BASE_URL}/regional/intensity/{now_str}/fw48h"
    return _get_json(url)


# Actual carbon intensity for the past 24 hours:
def get_national_actual() -> dict[str, Any]:
    now_str = _iso8601_utc_minute_from_now()
    url = f"{API_BASE_URL}/intensity/{now_str}/pt24h"
    return _get_json(url)


# Postcode to region method:
def resolve_postcode_to_region(postcode: str | None) -> dict[str, Any]:
    outcode = extract_outcode(postcode)
    if not outcode:
        return {"error": "Postcode is required"}
    url = f"{API_BASE_URL}/regional/postcode/{outcode}"
    return _get_json(url)