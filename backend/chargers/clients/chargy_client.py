import logging
import os
import random
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

PROVIDER_NAME = "chargy"
OCPI_API_BASE_URL = os.getenv("CHARGY_API_BASE_URL", "https://char.gy/open-ocpi")
OCPI_SUCCESS_STATUS_CODE = 1000

CHARGY_TIMEOUT_SECONDS = int(os.getenv("CHARGY_TIMEOUT_SECONDS", "8"))
CHARGY_MAX_RETRIES = int(os.getenv("CHARGY_MAX_RETRIES", "2"))
CHARGY_BACKOFF_BASE_SECONDS = int(os.getenv("CHARGY_BACKOFF_BASE_SECONDS", "1"))
CHARGY_BACKOFF_FACTOR = int(os.getenv("CHARGY_BACKOFF_FACTOR", "2"))
CHARGY_BACKOFF_MAX_SECONDS = int(os.getenv("CHARGY_BACKOFF_MAX_SECONDS", "4"))
_retry_status_codes_raw = os.getenv("CHARGY_RETRY_STATUS_CODES", "429,500,502,503,504")
CHARGY_RETRY_STATUS_CODES = {
    int(code.strip())
    for code in _retry_status_codes_raw.split(",")
    if code.strip()
}

logger = logging.getLogger(__name__)


def build_locations_url() -> str:
    return f"{OCPI_API_BASE_URL.rstrip('/')}/locations"


def build_tariffs_url() -> str:
    return f"{OCPI_API_BASE_URL.rstrip('/')}/tariffs"


def _validate_ocpi_envelope(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("OCPI response payload must be a dictionary")

    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError("Invalid OCPI envelope field: data")

    status_code = payload.get("status_code")
    if status_code is not None:
        if not isinstance(status_code, int):
            raise ValueError("Invalid OCPI envelope field: status_code")
        if status_code != OCPI_SUCCESS_STATUS_CODE:
            raise ValueError(
                f"OCPI non-success status: {status_code} ({payload.get('status_message', 'unknown')})"
            )

    status_message = payload.get("status_message")
    if status_message is not None and not isinstance(status_message, str):
        raise ValueError("Invalid OCPI envelope field: status_message")

    timestamp = payload.get("timestamp")
    if timestamp is not None and not isinstance(timestamp, str):
        raise ValueError("Invalid OCPI envelope field: timestamp")

    return payload


def _compute_backoff_seconds(attempt: int) -> float:
    backoff = CHARGY_BACKOFF_BASE_SECONDS * (CHARGY_BACKOFF_FACTOR ** attempt)
    jitter = random.uniform(0, 0.5)
    return min(CHARGY_BACKOFF_MAX_SECONDS, backoff + jitter)


def get_chargy_locations() -> dict[str, Any]:
    """
    Fetch Char.gy charger locations (locations-only provider).
    """
    url = build_locations_url()
    last_error_message: str | None = None

    for attempt in range(CHARGY_MAX_RETRIES + 1):
        attempt_number = attempt + 1
        request_start = time.monotonic()
        try:
            logger.info(
                "Char.gy locations request started",
                extra={
                    "event": "chargy_locations_request_started",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "locations",
                        "attempt": attempt_number,
                        "max_attempts": CHARGY_MAX_RETRIES + 1,
                    },
                },
            )

            response = requests.get(
                url,
                timeout=CHARGY_TIMEOUT_SECONDS,
            )
            elapsed_ms = int((time.monotonic() - request_start) * 1000)

            logger.info(
                "Char.gy locations response received",
                extra={
                    "event": "chargy_locations_response_received",
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

            normalized_locations: list[dict[str, Any]] = []
            total_evses = 0
            total_connectors = 0
            total_tariff_ids = 0

            for location in payload["data"]:
                if not isinstance(location, dict):
                    continue

                evses = location.get("evses")
                if not isinstance(evses, list):
                    evses = []
                total_evses += len(evses)

                tariff_ids: list[str] = []
                for evse in evses:
                    if not isinstance(evse, dict):
                        continue

                    connectors = evse.get("connectors")
                    if not isinstance(connectors, list):
                        continue
                    total_connectors += len(connectors)

                    for connector in connectors:
                        if not isinstance(connector, dict):
                            continue
                        connector_tariff_ids = connector.get("tariff_ids")
                        if isinstance(connector_tariff_ids, list):
                            tariff_ids.extend(
                                tariff_id
                                for tariff_id in connector_tariff_ids
                                if isinstance(tariff_id, str)
                            )

                total_tariff_ids += len(tariff_ids)
                unique_tariff_ids = sorted(set(tariff_ids))

                normalized_locations.append(
                    {
                        "location_id": location.get("id"),
                        "party_id": location.get("party_id"),
                        "country_code": location.get("country_code"),
                        "evse_count": len(evses),
                        "tariff_ids": unique_tariff_ids,
                    }
                )

            logger.info(
                "Char.gy locations normalized",
                extra={
                    "event": "chargy_locations_normalized",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "locations",
                        "status_code": response.status_code,
                        "elapsed_ms": elapsed_ms,
                        "location_count": len(normalized_locations),
                        "evse_count": total_evses,
                        "connector_count": total_connectors,
                        "tariff_id_count": total_tariff_ids,
                    },
                },
            )

            return {
                "provider": PROVIDER_NAME,
                "ocpi_envelope": payload,
                "locations": normalized_locations,
            }

        except requests.exceptions.Timeout:
            last_error_message = "Char.gy locations request timed out"
            logger.warning(
                "Char.gy locations timeout",
                extra={
                    "event": "chargy_locations_timeout",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "locations",
                        "attempt": attempt_number,
                    },
                },
            )
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response else None
            if status in CHARGY_RETRY_STATUS_CODES:
                last_error_message = f"Retryable Char.gy HTTP error ({status})"
                logger.warning(
                    "Char.gy locations retryable HTTP error",
                    extra={
                        "event": "chargy_locations_http_retry",
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
                    "Char.gy locations non-retryable HTTP error",
                    extra={
                        "event": "chargy_locations_http_error",
                        "context": {
                            "provider": PROVIDER_NAME,
                            "endpoint": "locations",
                            "attempt": attempt_number,
                            "status_code": status,
                        },
                    },
                )
                return {
                    "error": f"Char.gy locations HTTP error ({status})",
                    "provider": PROVIDER_NAME,
                }
        except requests.exceptions.RequestException:
            last_error_message = "Char.gy locations request failed"
            logger.warning(
                "Char.gy locations request exception",
                extra={
                    "event": "chargy_locations_request_exception",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "locations",
                        "attempt": attempt_number,
                    },
                },
            )
        except ValueError:
            logger.error(
                "Char.gy locations response parsing failed",
                extra={
                    "event": "chargy_locations_parse_error",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "locations",
                        "attempt": attempt_number,
                    },
                },
            )
            return {
                "error": "Char.gy locations response parsing error",
                "provider": PROVIDER_NAME,
            }

        if attempt >= CHARGY_MAX_RETRIES:
            logger.error(
                "Char.gy locations request exhausted retries",
                extra={
                    "event": "chargy_locations_request_failed",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "locations",
                        "max_retries": CHARGY_MAX_RETRIES,
                        "error_message": last_error_message,
                    },
                },
            )
            return {
                "error": f"{last_error_message} after {CHARGY_MAX_RETRIES} retries",
                "provider": PROVIDER_NAME,
            }

        sleep_seconds = _compute_backoff_seconds(attempt)
        time.sleep(sleep_seconds)

    return {
        "error": "Char.gy locations request failed",
        "provider": PROVIDER_NAME,
    }


def get_chargy_tariffs() -> dict[str, Any]:
    """
    Fetch Char.gy tariffs. Char.gy returns time-of-use GBP tariffs (and EUR/USD
    equivalents) via a public OCPI endpoint — no authentication required.
    """
    url = build_tariffs_url()
    last_error_message: str | None = None

    for attempt in range(CHARGY_MAX_RETRIES + 1):
        attempt_number = attempt + 1
        request_start = time.monotonic()
        try:
            logger.info(
                "Char.gy tariffs request started",
                extra={
                    "event": "chargy_tariffs_request_started",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "tariffs",
                        "attempt": attempt_number,
                        "max_attempts": CHARGY_MAX_RETRIES + 1,
                    },
                },
            )

            response = requests.get(
                url,
                timeout=CHARGY_TIMEOUT_SECONDS,
            )
            elapsed_ms = int((time.monotonic() - request_start) * 1000)

            logger.info(
                "Char.gy tariffs response received",
                extra={
                    "event": "chargy_tariffs_response_received",
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
                "Char.gy tariffs normalized",
                extra={
                    "event": "chargy_tariffs_normalized",
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
            last_error_message = "Char.gy tariffs request timed out"
            logger.warning(
                "Char.gy tariffs timeout",
                extra={
                    "event": "chargy_tariffs_timeout",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "tariffs",
                        "attempt": attempt_number,
                    },
                },
            )
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response else None
            if status in CHARGY_RETRY_STATUS_CODES:
                last_error_message = f"Retryable Char.gy HTTP error ({status})"
                logger.warning(
                    "Char.gy tariffs retryable HTTP error",
                    extra={
                        "event": "chargy_tariffs_http_retry",
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
                    "Char.gy tariffs non-retryable HTTP error",
                    extra={
                        "event": "chargy_tariffs_http_error",
                        "context": {
                            "provider": PROVIDER_NAME,
                            "endpoint": "tariffs",
                            "attempt": attempt_number,
                            "status_code": status,
                        },
                    },
                )
                return {
                    "error": f"Char.gy tariffs HTTP error ({status})",
                    "provider": PROVIDER_NAME,
                }
        except requests.exceptions.RequestException:
            last_error_message = "Char.gy tariffs request failed"
            logger.warning(
                "Char.gy tariffs request exception",
                extra={
                    "event": "chargy_tariffs_request_exception",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "tariffs",
                        "attempt": attempt_number,
                    },
                },
            )
        except ValueError:
            logger.error(
                "Char.gy tariffs response parsing failed",
                extra={
                    "event": "chargy_tariffs_parse_error",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "tariffs",
                        "attempt": attempt_number,
                    },
                },
            )
            return {
                "error": "Char.gy tariffs response parsing error",
                "provider": PROVIDER_NAME,
            }

        if attempt >= CHARGY_MAX_RETRIES:
            logger.error(
                "Char.gy tariffs request exhausted retries",
                extra={
                    "event": "chargy_tariffs_request_failed",
                    "context": {
                        "provider": PROVIDER_NAME,
                        "endpoint": "tariffs",
                        "max_retries": CHARGY_MAX_RETRIES,
                        "error_message": last_error_message,
                    },
                },
            )
            return {
                "error": f"{last_error_message} after {CHARGY_MAX_RETRIES} retries",
                "provider": PROVIDER_NAME,
            }

        sleep_seconds = _compute_backoff_seconds(attempt)
        time.sleep(sleep_seconds)

    return {
        "error": "Char.gy tariffs request failed",
        "provider": PROVIDER_NAME,
    }