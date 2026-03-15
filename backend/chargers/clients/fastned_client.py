import logging
import os
import random
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

OCPI_API_BASE_URL = "https://uk-public.api.fastned.nl/uk-public/ocpi/cpo/2.2.1"

PROVIDER_NAME = "fastned"
FASTNED_API_KEY = os.environ["FASTNED_API_KEY"]

FASTNED_TIMEOUT_SECONDS= int(os.getenv("FASTNED_TIMEOUT_SECONDS"))
FASTNED_MAX_RETRIES= int(os.getenv("FASTNED_MAX_RETRIES"))
FASTNED_BACKOFF_BASE_SECONDS= int(os.getenv("FASTNED_BACKOFF_BASE_SECONDS"))
FASTNED_BACKOFF_FACTOR= int(os.getenv("FASTNED_BACKOFF_FACTOR"))
FASTNED_BACKOFF_MAX_SECONDS= int(os.getenv("FASTNED_BACKOFF_MAX_SECONDS"))
_retry_status_codes_raw = os.getenv("FASTNED_RETRY_STATUS_CODES", "429,500,502,503,504")
FASTNED_RETRY_STATUS_CODES = {
    int(code.strip())
    for code in _retry_status_codes_raw.split(",")
    if code.strip()
}
OCPI_SUCCESS_STATUS_CODE = 1000
logger = logging.getLogger(__name__)

fastned_api_headers = {
    "x-api-key": FASTNED_API_KEY,
    "Content-Type": "application/json"
}

def build_locations_url() -> str:
    return f"{OCPI_API_BASE_URL}/locations"

def build_tariffs_url() -> str:
    return f"{OCPI_API_BASE_URL}/tariffs"

def _validate_ocpi_envelope(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("OCPI response payload must be a dictionary")
    
    ocpi_envelope_shape = {
        "data": list,
        "status_code": int,
        "status_message": str,
        "timestamp": str, 
    }

    for key, expected_type in ocpi_envelope_shape.items():
        if key not in payload or not isinstance(payload[key], expected_type):
            raise ValueError(f"Invalid OCPI envelope field: {key}")
        
    if payload["status_code"] != OCPI_SUCCESS_STATUS_CODE:
        raise ValueError(
            f"OCPI non-success status: {payload['status_code']} ({payload['status_message']})"
        )
        
    return payload

def _compute_backoff_seconds(attempt: int) -> float:
    backoff = FASTNED_BACKOFF_BASE_SECONDS * (FASTNED_BACKOFF_FACTOR ** attempt)
    jitter = random.uniform(0, 0.5)
    return min(FASTNED_BACKOFF_MAX_SECONDS, backoff + jitter)

def get_fastned_locations() -> dict[str, Any]:
    """
    Fetch Fastned charger locations
    """
    url = build_locations_url()
    headers = fastned_api_headers
    last_error_message: str | None = None

    for attempt in range(FASTNED_MAX_RETRIES + 1):
        attempt_number = attempt + 1
        request_start = time.monotonic()
        try:
            logger.info(
                "Fastned locations request started",
                extra={
                    "event": "fastned_locations_request_started",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "locations",
                        "attempt": attempt_number,
                        "max_attempts": FASTNED_MAX_RETRIES + 1,
                    },
                },
            )

            response = requests.get(
                url, 
                headers=headers,
                timeout=FASTNED_TIMEOUT_SECONDS,
            )
            elapsed_ms = int((time.monotonic() - request_start) * 1000)

            logger.info(
                "Fastned locations response received",
                extra = {
                    "event": "fastned_locations_response_received",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "locations",
                        "attempt": attempt_number,
                        "status_code": response.status_code,
                        "elapsed_ms": elapsed_ms,
                    },
                },
            )

            response.raise_for_status()
            payload = _validate_ocpi_envelope(response.json())

            normalised_locations: list[dict[str, Any]] = []
            total_evses = 0
            total_connectors = 0
            total_tariff_ids = 0

            for location in payload["data"]:
                if not isinstance(location, dict):
                    continue

                evses = location.get("evses") or []
                if not isinstance(evses, list):
                    evses = []
                total_evses += len(evses)

                tariff_ids: list[str] = []
                for evse in evses: 
                    if not isinstance(evse, dict):
                        continue
                    connectors = evse.get("connectors") or []
                    if not isinstance(connectors, list):
                        continue
                    total_connectors += len(connectors)
                    for connector in connectors:
                        if not isinstance(connector, dict):
                            continue
                        connector_tariff_ids = connector.get("tariff_ids") or []
                        if isinstance(connector_tariff_ids, list):
                            tariff_ids.extend(
                                tariff_id
                                for tariff_id in connector_tariff_ids
                                if isinstance(tariff_id, str)
                            )
                total_tariff_ids += len(tariff_ids)

                unique_tariff_ids = sorted(set(tariff_ids))

                normalised_locations.append(
                    {
                        "location_id": location.get("id"),
                        "party_id": location.get("party_id"),
                        "country_code": location.get("country_code"),
                        "evse_count": len(evses),
                        "tariff_ids": unique_tariff_ids,
                    }
                )

            logger.info(
                "Fastned locations normalised",
                extra={
                    "event": "fastned_locations_normalised",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "locations",
                        "status_code": response.status_code,
                        "elapsed_ms": elapsed_ms,
                        "location_count": len(normalised_locations),
                        "evse_count": total_evses,
                        "connector_count": total_connectors,
                        "tariff_id_count": total_tariff_ids,
                    },
                },
            )

            return {
                "provider": PROVIDER_NAME,
                "ocpi_envelope": payload,
                "locations": normalised_locations,
            }
        
        except requests.exceptions.Timeout:
            last_error_message = "Fastned locations request timed out"
            logger.warning(
                "Fastned locations timeout",
                extra={
                    "event": "fastned_locations_timeout",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "locations",
                        "attempt": attempt_number,
                    },
                },
            )
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response else None
            if status == 401:
                logger.error(
                    "Fastned locations authentication failed",
                    extra={
                        "event": "fastned_locations_auth_failed",
                        "context": {
                            "provider": PROVIDER_NAME,
                            "endpoint": "locations",
                            "attempt": attempt_number,
                            "status_code": status,
                        },
                    },
                )
                return {
                    "error": "Fastned locations authentication failed (401)",
                    "provider": PROVIDER_NAME,
                }
            if status in FASTNED_RETRY_STATUS_CODES:
                last_error_message = f"Retryable Fastned HTTP error ({status})"
                logger.warning(
                    "Fastned locations retryable HTTP error",
                    extra={
                        "event": "fastned_locations_http_retry",
                        "context": {
                            "provider": PROVIDER_NAME,
                            "endpoint": "locations",
                            "attempt": attempt_number,
                            "status_code": status,
                        },
                    },
                )
            else:
                logger.error(
                    "Fastned locations non-retryable HTTP error",
                    extra={
                        "event": "fastned_locations_http_error",
                        "context": {
                            "provider": PROVIDER_NAME,
                            "endpoint": "locations",
                            "attempt": attempt_number,
                            "status_code": status,
                        },
                    },
                )
                return {
                    "error": f"Fastned locations HTTP error ({status})",
                    "provider": PROVIDER_NAME,
                }
        except requests.exceptions.RequestException:
            last_error_message = "Fastned locations request failed"
            logger.warning(
                "Fastned locations request exception",
                extra={
                    "event": "fastned_locations_request_exception",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "locations",
                        "attempt": attempt_number,
                    },
                },
            )
        except ValueError:
            logger.error(
                "Fastned locations response parsing failed",
                extra={
                    "event": "fastned_locations_parse_error",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "locations",
                        "attempt": attempt_number,
                    },
                },
            )
            return {
                "error": "Fastned locations response parsing error",
                "provider": PROVIDER_NAME,
            }

        if attempt >= FASTNED_MAX_RETRIES:
            logger.error(
                "Fastned locations request exhausted retries",
                extra={
                    "event": "fastned_locations_request_failed",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "locations",
                        "max_retries": FASTNED_MAX_RETRIES,
                        "error_message": last_error_message,
                    },
                },
            )
            return {
                "error": f"{last_error_message} after {FASTNED_MAX_RETRIES} retries",
                "provider": PROVIDER_NAME,
            }

        sleep_seconds = _compute_backoff_seconds(attempt)
        time.sleep(sleep_seconds)

    return {
        "error": "Fastned locations request failed",
        "provider": PROVIDER_NAME,
    }

def get_fastned_tariffs() -> dict[str, Any]:
    """
    Fetch Fastned tariffs.
    """
    url = build_tariffs_url()
    headers = fastned_api_headers
    last_error_message: str | None = None

    for attempt in range(FASTNED_MAX_RETRIES + 1):
        attempt_number = attempt + 1
        request_start = time.monotonic()
        try:
            logger.info(
                "Fastned tariffs request started",
                extra={
                    "event": "fastned_tariffs_request_started",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "tariffs",
                        "attempt": attempt_number,
                        "max_attempts": FASTNED_MAX_RETRIES + 1,
                    },
                },
            )

            response = requests.get(
                url,
                headers=headers,
                timeout=FASTNED_TIMEOUT_SECONDS,
            )
            elapsed_ms = int((time.monotonic() - request_start) * 1000)

            logger.info(
                "Fastned tariffs response received",
                extra={
                    "event": "fastned_tariffs_response_received",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "tariffs",
                        "attempt": attempt_number,
                        "status_code": response.status_code,
                        "elapsed_ms": elapsed_ms,
                    },
                },
            )

            response.raise_for_status()
            payload = _validate_ocpi_envelope(response.json())

            tariff_rows: list[dict[str, Any]] = [
                row for row in payload["data"] if isinstance(row, dict)
            ]

            logger.info(
                "Fastned tariffs normalized",
                extra={
                    "event": "fastned_tariffs_normalized",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "tariffs",
                        "status_code": response.status_code,
                        "elapsed_ms": elapsed_ms,
                        "tariff_count": len(tariff_rows),
                    },
                },
            )

            return {
                "provider": PROVIDER_NAME,
                "ocpi_envelope": payload,
                "tariffs": tariff_rows,
            }

        except requests.exceptions.Timeout:
            last_error_message = "Fastned tariffs request timed out"
            logger.warning(
                "Fastned tariffs timeout",
                extra={
                    "event": "fastned_tariffs_timeout",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "tariffs",
                        "attempt": attempt_number,
                    },
                },
            )
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response else None
            if status == 401:
                logger.error(
                    "Fastned tariffs authentication failed",
                    extra={
                        "event": "fastned_tariffs_auth_failed",
                        "context": {
                            "provider": PROVIDER_NAME,
                            "endpoint": "tariffs",
                            "attempt": attempt_number,
                            "status_code": status,
                        },
                    },
                )
                return {
                    "error": "Fastned tariffs authentication failed (401)",
                    "provider": PROVIDER_NAME,
                }
            if status in FASTNED_RETRY_STATUS_CODES:
                last_error_message = f"Retryable Fastned HTTP error ({status})"
                logger.warning(
                    "Fastned tariffs retryable HTTP error",
                    extra={
                        "event": "fastned_tariffs_http_retry",
                        "context": {
                            "provider": PROVIDER_NAME,
                            "endpoint": "tariffs",
                            "attempt": attempt_number,
                            "status_code": status,
                        },
                    },
                )
            else:
                logger.error(
                    "Fastned tariffs non-retryable HTTP error",
                    extra={
                        "event": "fastned_tariffs_http_error",
                        "context": {
                            "provider": PROVIDER_NAME,
                            "endpoint": "tariffs",
                            "attempt": attempt_number,
                            "status_code": status,
                        },
                    },
                )
                return {
                    "error": f"Fastned tariffs HTTP error ({status})",
                    "provider": PROVIDER_NAME,
                }
        except requests.exceptions.RequestException:
            last_error_message = "Fastned tariffs request failed"
            logger.warning(
                "Fastned tariffs request exception",
                extra={
                    "event": "fastned_tariffs_request_exception",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "tariffs",
                        "attempt": attempt_number,
                    },
                },
            )
        except ValueError:
            logger.error(
                "Fastned tariffs response parsing failed",
                extra={
                    "event": "fastned_tariffs_parse_error",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "tariffs",
                        "attempt": attempt_number,
                    },
                },
            )
            return {
                "error": "Fastned tariffs response parsing error",
                "provider": PROVIDER_NAME,
            }

        if attempt >= FASTNED_MAX_RETRIES:
            logger.error(
                "Fastned tariffs request exhausted retries",
                extra={
                    "event": "fastned_tariffs_request_failed",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "tariffs",
                        "max_retries": FASTNED_MAX_RETRIES,
                        "error_message": last_error_message,
                    },
                },
            )
            return {
                "error": f"{last_error_message} after {FASTNED_MAX_RETRIES} retries",
                "provider": PROVIDER_NAME,
            }

        sleep_seconds = _compute_backoff_seconds(attempt)
        time.sleep(sleep_seconds)

    return {
        "error": "Fastned tariffs request failed",
        "provider": PROVIDER_NAME,
    }