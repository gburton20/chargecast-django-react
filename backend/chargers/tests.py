import importlib
import os
from unittest.mock import MagicMock, patch

from django.test import TestCase


class EcoMovementClientTests(TestCase):
	def _load_client_module(self):
		env = {
			"ECO_MOVEMENT_BLINK_API_KEY": "blink-token",
			"ECO_MOVEMENT_BP_API_KEY": "bp-token",
			"ECO_MOVEMENT_IONITY_API_KEY": "ionity-token",
			"ECO_MOVEMENT_SHELL_API_KEY": "shell-token",
			"ECO_MOVEMENT_TIMEOUT_SECONDS": "8",
			"ECO_MOVEMENT_MAX_RETRIES": "2",
			"ECO_MOVEMENT_BACKOFF_BASE_SECONDS": "1",
			"ECO_MOVEMENT_BACKOFF_FACTOR": "2",
			"ECO_MOVEMENT_BACKOFF_MAX_SECONDS": "4",
			"ECO_MOVEMENT_RETRY_STATUS_CODES": "429,500,502,503,504",
		}

		with patch.dict(os.environ, env, clear=False):
			from chargers.clients import eco_movement_client

			return importlib.reload(eco_movement_client)

	def test_get_locations_extracts_tariff_ids(self):
		client = self._load_client_module()

		payload = {
			"timestamp": "2026-03-13T13:12:04Z",
			"status_code": 1000,
			"status_message": "Success",
			"data": [
				{
					"id": "location-1",
					"party_id": "BLK",
					"country_code": "GB",
					"evses": [
						{
							"connectors": [
								{"tariff_ids": ["tariff-1", "tariff-2"]},
								{"tariff_ids": ["tariff-2"]},
							]
						}
					],
				}
			],
		}

		response = MagicMock()
		response.status_code = 200
		response.raise_for_status.return_value = None
		response.json.return_value = payload

		with patch.object(client.requests, "get", return_value=response):
			result = client.get_eco_movement_locations("blink")

		self.assertEqual(result["provider"], "blink")
		self.assertEqual(len(result["locations"]), 1)
		self.assertEqual(result["locations"][0]["location_id"], "location-1")
		self.assertEqual(result["locations"][0]["tariff_ids"], ["tariff-1", "tariff-2"])

	def test_get_locations_retries_retryable_http_error(self):
		client = self._load_client_module()

		retry_response = MagicMock()
		retry_response.status_code = 503
		retry_response.raise_for_status.side_effect = client.requests.exceptions.HTTPError(response=retry_response)

		success_payload = {
			"timestamp": "2026-03-13T13:12:04Z",
			"status_code": 1000,
			"status_message": "Success",
			"data": [],
		}
		success_response = MagicMock()
		success_response.status_code = 200
		success_response.raise_for_status.return_value = None
		success_response.json.return_value = success_payload

		with patch.object(client.requests, "get", side_effect=[retry_response, success_response]) as mocked_get:
			with patch.object(client.time, "sleep", return_value=None):
				result = client.get_eco_movement_locations("blink")

		self.assertEqual(mocked_get.call_count, 2)
		self.assertEqual(result["provider"], "blink")
		self.assertEqual(result["locations"], [])

	def test_get_tariffs_returns_tariff_rows(self):
		client = self._load_client_module()

		payload = {
			"timestamp": "2026-03-13T13:12:04Z",
			"status_code": 1000,
			"status_message": "Success",
			"data": [
				{"id": "tariff-a", "currency": "GBP"},
				{"id": "tariff-b", "currency": "GBP"},
			],
		}

		response = MagicMock()
		response.status_code = 200
		response.raise_for_status.return_value = None
		response.json.return_value = payload

		with patch.object(client.requests, "get", return_value=response):
			result = client.get_eco_movement_tariffs("bp")

		self.assertEqual(result["provider"], "bp")
		self.assertEqual(len(result["tariffs"]), 2)
