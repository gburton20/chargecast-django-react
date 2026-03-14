import logging
import os
import random
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

OCPI_API_BASE_URL = "https://uk-public.api.fastned.nl/uk-public/ocpi/cpo/2.2.1"

API_KEY = {
    "fastned": os.environ['FASTNED_API_KEY']
}

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

logger = logging.getLogger(__name__)
token = API_KEY.get("fastned")

fastned_api_headers = {
    "x-api-key": f"{token}",
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
        "data": list
    }

    for key, expected_type in ocpi_envelope_shape.items():
        if key not in payload or not isinstance(payload[key], expected_type):
            raise ValueError(f"Invalid OCPI envelope field: {key}")
        
    return payload