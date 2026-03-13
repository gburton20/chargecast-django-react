import logging
import os
import random
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

OCPI_API_BASE_URL = "https://open-chargepoints.com/api/ocpi/cpo/2.2.1"

API_KEYS = {
    "blink": os.environ['ECO_MOVEMENT_BLINK_API_KEY'], 
    "bp": os.environ['ECO_MOVEMENT_BP_API_KEY'],
    "ionity": os.environ['ECO_MOVEMENT_IONITY_API_KEY'],
    "shell": os.environ['ECO_MOVEMENT_SHELL_API_KEY']
}

ECO_MOVEMENT_TIMEOUT_SECONDS=int(os.getenv("ECO_MOVEMENT_TIMEOUT_SECONDS"))
ECO_MOVEMENT_MAX_RETRIES=int(os.getenv("ECO_MOVEMENT_MAX_RETRIES"))
ECO_MOVEMENT_BACKOFF_BASE_SECONDS= int(os.getenv("ECO_MOVEMENT_BACKOFF_BASE_SECONDS"))
ECO_MOVEMENT_BACKOFF_FACTOR= int(os.getenv("ECO_MOVEMENT_BACKOFF_FACTOR"))
ECO_MOVEMENT_BACKOFF_MAX_SECONDS= int(os.getenv("ECO_MOVEMENT_BACKOFF_MAX_SECONDS"))
_retry_status_codes_raw = os.getenv("ECO_MOVEMENT_RETRY_STATUS_CODES", "429,500,502,503,504")
ECO_MOVEMENT_RETRY_STATUS_CODES = {
    int(code.strip())
    for code in _retry_status_codes_raw.split(",")
    if code.strip()
}
OCPI_SUCCESS_STATUS_CODE = 1000
logger = logging.getLogger(__name__)


def build_headers(provider: str) -> dict:
    """
    Build request headers dynamically for an OCPI provider
    """
    token = API_KEYS.get(provider)

    if not token:
        raise ValueError(f"No API token configured for provider: {provider}")
    
    return {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json",
    }


def build_locations_url() -> str:
    return f"{OCPI_API_BASE_URL}/locations"


def build_tariffs_url() -> str:
    return f"{OCPI_API_BASE_URL}/tariffs"


def _validate_ocpi_envelope(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("OCPI response payload must be a dictionary")

    ocpi_envelope_shape = {
        "timestamp": str,
        "status_code": int,
        "status_message": str,
        "data": list,
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
    backoff = ECO_MOVEMENT_BACKOFF_BASE_SECONDS * (ECO_MOVEMENT_BACKOFF_FACTOR ** attempt)
    jitter = random.uniform(0, 0.5)
    return min(ECO_MOVEMENT_BACKOFF_MAX_SECONDS, backoff + jitter)


def get_eco_movement_locations(provider: str) -> dict[str, Any]:
    """
    Fetch charger locations data for a single Eco-Movement provider.
    """
    # If the provider string name is not in API_KEYS:
    if provider not in API_KEYS:
        raise ValueError(f"Unsupported provider: {provider}")

    # If this code is running, it means provider is in API_KEYS.
    url = build_locations_url()
    headers = build_headers(provider)
    last_error_message: str | None = None

    for attempt in range(ECO_MOVEMENT_MAX_RETRIES + 1):
        attempt_number = attempt + 1
        request_start = time.monotonic()
        try:
            logger.info(
                "Eco-Movement locations request started",
                extra={
                    "event": "eco_movement_locations_request_started",
                    "context": {
                        "provider": provider,
                        "endpoint": "locations",
                        "attempt": attempt_number,
                        "max_attempts": ECO_MOVEMENT_MAX_RETRIES + 1,
                    },
                },
            )

            response = requests.get(
                url,
                headers=headers,
                timeout=ECO_MOVEMENT_TIMEOUT_SECONDS,
            )
            elapsed_ms = int((time.monotonic() - request_start) * 1000)

            logger.info(
                "Eco-Movement locations response received",
                extra={
                    "event": "eco_movement_locations_response_received",
                    "context": {
                        "provider": provider,
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
                "Eco-Movement locations normalized",
                extra={
                    "event": "eco_movement_locations_normalized",
                    "context": {
                        "provider": provider,
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
                "provider": provider,
                "ocpi_envelope": payload,
                "locations": normalized_locations,
            }

        except requests.exceptions.Timeout:
            last_error_message = "Eco-Movement locations request timed out"
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response else None
            if status in ECO_MOVEMENT_RETRY_STATUS_CODES:
                last_error_message = f"Retryable Eco-Movement HTTP error ({status})"
            else:
                return {
                    "error": f"Eco-Movement locations HTTP error ({status})",
                    "provider": provider,
                }
        except requests.exceptions.RequestException:
            last_error_message = "Eco-Movement locations request failed"
        except ValueError:
            return {
                "error": "Eco-Movement locations response parsing error",
                "provider": provider,
            }

        if attempt >= ECO_MOVEMENT_MAX_RETRIES:
            return {
                "error": f"{last_error_message} after {ECO_MOVEMENT_MAX_RETRIES} retries",
                "provider": provider,
            }

        sleep_seconds = _compute_backoff_seconds(attempt)
        time.sleep(sleep_seconds)

    return {
        "error": "Eco-Movement locations request failed",
        "provider": provider,
    }


def get_eco_movement_tariffs(provider: str) -> dict[str, Any]:
    """
    Fetch tariff(s) data for a single Eco-Movement provider.
    """
    if provider not in API_KEYS:
        raise ValueError(f"Unsupported provider: {provider}")

    url = build_tariffs_url()
    headers = build_headers(provider)
    last_error_message: str | None = None

    for attempt in range(ECO_MOVEMENT_MAX_RETRIES + 1):
        attempt_number = attempt + 1
        request_start = time.monotonic()
        try:
            logger.info(
                "Eco-Movement tariffs request started",
                extra={
                    "event": "eco_movement_tariffs_request_started",
                    "context": {
                        "provider": provider,
                        "endpoint": "tariffs",
                        "attempt": attempt_number,
                        "max_attempts": ECO_MOVEMENT_MAX_RETRIES + 1,
                    },
                },
            )

            response = requests.get(
                url,
                headers=headers,
                timeout=ECO_MOVEMENT_TIMEOUT_SECONDS,
            )
            elapsed_ms = int((time.monotonic() - request_start) * 1000)

            logger.info(
                "Eco-Movement tariffs response received",
                extra={
                    "event": "eco_movement_tariffs_response_received",
                    "context": {
                        "provider": provider,
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
                "Eco-Movement tariffs normalized",
                extra={
                    "event": "eco_movement_tariffs_normalized",
                    "context": {
                        "provider": provider,
                        "endpoint": "tariffs",
                        "status_code": response.status_code,
                        "elapsed_ms": elapsed_ms,
                        "tariff_count": len(tariff_rows),
                    },
                },
            )

            return {
                "provider": provider,
                "ocpi_envelope": payload,
                "tariffs": tariff_rows,
            }

        except requests.exceptions.Timeout:
            last_error_message = "Eco-Movement tariffs request timed out"
            logger.warning(
                "Eco-Movement tariffs timeout",
                extra={
                    "event": "eco_movement_tariffs_timeout",
                    "context": {
                        "provider": provider,
                        "endpoint": "tariffs",
                        "attempt": attempt_number,
                    },
                },
            )
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response else None
            if status in ECO_MOVEMENT_RETRY_STATUS_CODES:
                last_error_message = f"Retryable Eco-Movement HTTP error ({status})"
                logger.warning(
                    "Eco-Movement tariffs retryable HTTP error",
                    extra={
                        "event": "eco_movement_tariffs_http_retry",
                        "context": {
                            "provider": provider,
                            "endpoint": "tariffs",
                            "attempt": attempt_number,
                            "status_code": status,
                        },
                    },
                )
            else:
                logger.error(
                    "Eco-Movement tariffs non-retryable HTTP error",
                    extra={
                        "event": "eco_movement_tariffs_http_error",
                        "context": {
                            "provider": provider,
                            "endpoint": "tariffs",
                            "attempt": attempt_number,
                            "status_code": status,
                        },
                    },
                )
                return {
                    "error": f"Eco-Movement tariffs HTTP error ({status})",
                    "provider": provider,
                }
        except requests.exceptions.RequestException:
            last_error_message = "Eco-Movement tariffs request failed"
            logger.warning(
                "Eco-Movement tariffs request exception",
                extra={
                    "event": "eco_movement_tariffs_request_exception",
                    "context": {
                        "provider": provider,
                        "endpoint": "tariffs",
                        "attempt": attempt_number,
                    },
                },
            )
        except ValueError:
            logger.error(
                "Eco-Movement tariffs response parsing failed",
                extra={
                    "event": "eco_movement_tariffs_parse_error",
                    "context": {
                        "provider": provider,
                        "endpoint": "tariffs",
                        "attempt": attempt_number,
                    },
                },
            )
            return {
                "error": "Eco-Movement tariffs response parsing error",
                "provider": provider,
            }
        if attempt >= ECO_MOVEMENT_MAX_RETRIES:
            logger.error(
                "Eco-Movement tariffs request exhausted retries",
                extra={
                    "event": "eco_movement_tariffs_request_failed",
                    "context": {
                        "provider": provider,
                        "endpoint": "tariffs",
                        "max_retries": ECO_MOVEMENT_MAX_RETRIES,
                        "error_message": last_error_message,
                    },
                },
            )
            return {
                "error": f"{last_error_message} after {ECO_MOVEMENT_MAX_RETRIES} retries",
                "provider": provider,
            }
        sleep_seconds = _compute_backoff_seconds(attempt)
        time.sleep(sleep_seconds)
    return {
        "error": "Eco-Movement tariffs request failed",
        "provider": provider,
    }