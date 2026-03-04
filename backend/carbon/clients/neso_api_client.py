import requests
from django.conf import settings

API_BASE_URL = "https://api.carbonintensity.org.uk"

NESO_API_TIMEOUT_SECONDS = getattr(settings, "NESO_API_TIMEOUT_SECONDS", 10)

# Get the national carbon intensity forecast for the next 48 hours:
def get_national_forecast():
    url = f"{API_BASE_URL}/intensity/fw48h"
    headers = {"Accept": "application/json"}
    response = requests.get(url, headers=headers, timeout=NESO_API_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()

# Get the regional carbon intensity forecast for all DNO regions for the next 48 hours:
def get_regional_forecast():
    url = f"{API_BASE_URL}/regional/intensity/fw48h"
    headers = {"Accept": "application/json"}
    response = requests.get(url, headers=headers, timeout=NESO_API_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()

# Actual carbon intensity for the past 24 hours:
def get_national_actual():
    url = f"{API_BASE_URL}/intensity/pt24h"
    headers = {"Accept": "application/json"}
    response = requests.get(url, headers=headers, timeout=NESO_API_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()

# Postcode to region method:
def resolve_postcode_to_region(postcode):
    url = f"{API_BASE_URL}/regional/postcode/{postcode}"
    headers = {"Accept": "application/json"}
    response = requests.get(url, headers=headers, timeout=NESO_API_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()