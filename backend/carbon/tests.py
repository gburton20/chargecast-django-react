import os
import unittest
from datetime import datetime, timedelta, timezone as dt_timezone

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, tag
from django.test import TestCase
from django.utils import timezone

from carbon.models import CarbonIntensityRecord

from unittest.mock import Mock, patch

import requests

# Tests to establish whether a national and regional record can be created in the PostgreSQL DB:
class CarbonIntensityRecordCreationTests(TestCase):
	def test_can_create_national_record_with_valid_data(self):
		valid_from = timezone.make_aware(datetime(2026, 1, 1, 0, 0, 0))
		valid_to = valid_from + timedelta(minutes=30)
		generated_at = valid_from - timedelta(minutes=5)

		record = CarbonIntensityRecord.objects.create(
			region_id=None,
			region_shortname=None,
			valid_from=valid_from,
			valid_to=valid_to,
			forecast=200,
			actual=None,
			index=CarbonIntensityRecord.IntensityIndex.MODERATE,
			forecast_generated_at=generated_at,
			is_national=True,
		)

		self.assertEqual(CarbonIntensityRecord.objects.count(), 1)
		self.assertTrue(record.is_national)
		self.assertIsNone(record.region_id)
		self.assertIsNone(record.region_shortname)

	def test_can_create_regional_record_with_valid_data(self):
		valid_from = timezone.make_aware(datetime(2026, 1, 1, 0, 0, 0))
		valid_to = valid_from + timedelta(minutes=30)
		generated_at = valid_from - timedelta(minutes=5)

		record = CarbonIntensityRecord.objects.create(
			region_id="R1",
			region_shortname="South Wales",
			valid_from=valid_from,
			valid_to=valid_to,
			forecast=180,
			actual=175,
			index=CarbonIntensityRecord.IntensityIndex.LOW,
			forecast_generated_at=generated_at,
			is_national=False,
		)

		self.assertEqual(CarbonIntensityRecord.objects.count(), 1)
		self.assertFalse(record.is_national)

# Tests to ensure data quality input to the DB
class CarbonIntensityRecordValidationTests(TestCase):
	def test_required_fields_raise_validation_error(self):
		invalid = CarbonIntensityRecord(
			valid_from=None,
			valid_to=None,
			forecast=None,
			index="",
			forecast_generated_at=None,
			is_national=None,
		)

		with self.assertRaises(ValidationError) as ctx:
			invalid.full_clean()

		self.assertIn("valid_from", ctx.exception.message_dict)
		self.assertIn("valid_to", ctx.exception.message_dict)
		self.assertIn("forecast", ctx.exception.message_dict)
		self.assertIn("index", ctx.exception.message_dict)
		self.assertIn("forecast_generated_at", ctx.exception.message_dict)
		self.assertIn("is_national", ctx.exception.message_dict)

	def test_index_choices_are_enforced_by_full_clean(self):
		valid_from = timezone.make_aware(datetime(2026, 1, 1, 0, 0, 0))
		valid_to = valid_from + timedelta(minutes=30)
		generated_at = valid_from - timedelta(minutes=5)

		invalid = CarbonIntensityRecord(
			region_id=None,
			region_shortname=None,
			valid_from=valid_from,
			valid_to=valid_to,
			forecast=200,
			actual=None,
			index="not-a-valid-choice",
			forecast_generated_at=generated_at,
			is_national=True,
		)

		with self.assertRaises(ValidationError) as ctx:
			invalid.full_clean()

		self.assertIn("index", ctx.exception.message_dict)

# Tests to ensure data quality input to the DB
class CarbonIntensityRecordConstraintTests(TestCase):
	def test_valid_from_must_be_strictly_less_than_valid_to(self):
		valid_from = timezone.make_aware(datetime(2026, 1, 1, 0, 0, 0))
		generated_at = valid_from - timedelta(minutes=5)

		with self.assertRaises(IntegrityError):
			with transaction.atomic():
				CarbonIntensityRecord.objects.create(
					region_id=None,
					region_shortname=None,
					valid_from=valid_from,
					valid_to=valid_from,
					forecast=200,
					actual=None,
					index=CarbonIntensityRecord.IntensityIndex.MODERATE,
					forecast_generated_at=generated_at,
					is_national=True,
				)

	def test_national_rows_require_null_region_fields(self):
		valid_from = timezone.make_aware(datetime(2026, 1, 1, 0, 0, 0))
		valid_to = valid_from + timedelta(minutes=30)
		generated_at = valid_from - timedelta(minutes=5)

		with self.assertRaises(IntegrityError):
			with transaction.atomic():
				CarbonIntensityRecord.objects.create(
					region_id="R1",
					region_shortname="South Wales",
					valid_from=valid_from,
					valid_to=valid_to,
					forecast=200,
					actual=None,
					index=CarbonIntensityRecord.IntensityIndex.MODERATE,
					forecast_generated_at=generated_at,
					is_national=True,
				)

	def test_regional_rows_require_non_null_region_fields(self):
		valid_from = timezone.make_aware(datetime(2026, 1, 1, 0, 0, 0))
		valid_to = valid_from + timedelta(minutes=30)
		generated_at = valid_from - timedelta(minutes=5)

		with self.assertRaises(IntegrityError):
			with transaction.atomic():
				CarbonIntensityRecord.objects.create(
					region_id=None,
					region_shortname=None,
					valid_from=valid_from,
					valid_to=valid_to,
					forecast=200,
					actual=None,
					index=CarbonIntensityRecord.IntensityIndex.MODERATE,
					forecast_generated_at=generated_at,
					is_national=False,
				)

# Checks the expected named indexes (in carbon/models.py > Meta.indexes) are declard on the model:
class CarbonIntensityRecordIndexTests(TestCase):
	def test_expected_meta_indexes_exist(self):
		indexes = {(tuple(idx.fields), idx.name) for idx in CarbonIntensityRecord._meta.indexes}
		self.assertIn((("region_id", "valid_from"), "carbon_cir_region_from_idx"), indexes)
		self.assertIn((("is_national", "valid_from"), "carbon_cir_nat_from_idx"), indexes)

# Tests the scope + valid_from values are included in the __str__() output for human-readable admin/debug messages.
class CarbonIntensityRecordStrTests(TestCase):
	def test_str_contains_scope_and_valid_from(self):
		valid_from = timezone.make_aware(datetime(2026, 1, 1, 0, 0, 0))
		valid_to = valid_from + timedelta(minutes=30)
		generated_at = valid_from - timedelta(minutes=5)

		record = CarbonIntensityRecord.objects.create(
			region_id=None,
			region_shortname=None,
			valid_from=valid_from,
			valid_to=valid_to,
			forecast=200,
			actual=None,
			index=CarbonIntensityRecord.IntensityIndex.MODERATE,
			forecast_generated_at=generated_at,
			is_national=True,
		)

		rendered = str(record)
		self.assertIn("National", rendered)
		self.assertIn(valid_from.isoformat(), rendered)

# Tests for each API method within neso_api_client.py:

# Test for the API method, _iso8601_utc_minute_from_now():
class UTCMinuteFromNowTests(SimpleTestCase):
	def test_iso8601_utc_minute_from_now_formats_as_expected(self):
		# Use a fixed, timezone-aware UTC datetime so the output is deterministic.
		fixed_now = datetime(2026, 3, 5, 12, 34, 56, tzinfo=dt_timezone.utc)

		with patch("carbon.clients.neso_api_client.timezone.now", return_value=fixed_now):
			from carbon.clients.neso_api_client import _iso8601_utc_minute_from_now

			self.assertEqual(_iso8601_utc_minute_from_now(), "2026-03-05T12:34Z")

# Tests for the API method, _get_json():

class GetJsonTests(SimpleTestCase):
	# Test for a HTTP 200 (success) API call:
	@patch("carbon.clients.neso_api_client.requests.get")
	def test_get_json_success_returns_parsed_json(self, mock_get):
		mock_response = Mock()
		mock_response.raise_for_status.return_value = None
		mock_response.json.return_value = {"data": [{"ok": True}]}
		mock_get.return_value = mock_response

		from carbon.clients.neso_api_client import _get_json

		result = _get_json("https://example.test/endpoint")
		self.assertEqual(result, {"data": [{"ok": True}]})

		mock_get.assert_called_once()
		called_url = mock_get.call_args.args[0]
		called_kwargs = mock_get.call_args.kwargs
		self.assertEqual(called_url, "https://example.test/endpoint")
		self.assertEqual(called_kwargs.get("headers"), {"Accept": "application/json"})
		self.assertIn("timeout", called_kwargs)

	# Test for a HTTP 500 (internal server error) API call:
	@patch("carbon.clients.neso_api_client.time.sleep")
	@patch("carbon.clients.neso_api_client.random.uniform", return_value=0.0)
	@patch("carbon.clients.neso_api_client.NESO_API_MAX_RETRIES", 1)
	@patch("carbon.clients.neso_api_client.requests.get")
	def test_get_json_retries_on_500_then_succeeds(self, mock_get, _mock_jitter, mock_sleep):
		resp_500 = Mock()
		resp_500.raise_for_status.side_effect = requests.exceptions.HTTPError(response=Mock(status_code=500))

		resp_ok = Mock()
		resp_ok.raise_for_status.return_value = None
		resp_ok.json.return_value = {"ok": True}

		mock_get.side_effect = [resp_500, resp_ok]

		from carbon.clients.neso_api_client import _get_json

		result = _get_json("https://example.test/endpoint")
		self.assertEqual(result, {"ok": True})
		self.assertEqual(mock_get.call_count, 2)
		mock_sleep.assert_called_once()

	# Test for a HTTP 429 (too many requests) API call:
	@patch("carbon.clients.neso_api_client.time.sleep")
	@patch("carbon.clients.neso_api_client.random.uniform", return_value=0.0)
	@patch("carbon.clients.neso_api_client.NESO_API_MAX_RETRIES", 1)
	@patch("carbon.clients.neso_api_client.requests.get")
	def test_get_json_retries_on_429_then_succeeds(self, mock_get, _mock_jitter, mock_sleep):
		resp_429 = Mock()
		resp_429.raise_for_status.side_effect = requests.exceptions.HTTPError(response=Mock(status_code=429))

		resp_ok = Mock()
		resp_ok.raise_for_status.return_value = None
		resp_ok.json.return_value = {"ok": True}

		mock_get.side_effect = [resp_429, resp_ok]

		from carbon.clients.neso_api_client import _get_json

		result = _get_json("https://example.test/endpoint")
		self.assertEqual(result, {"ok": True})
		self.assertEqual(mock_get.call_count, 2)
		mock_sleep.assert_called_once()

	# Test for a HTTP 404 (resource not found) API call:
	@patch("carbon.clients.neso_api_client.time.sleep")
	@patch("carbon.clients.neso_api_client.NESO_API_MAX_RETRIES", 3)
	@patch("carbon.clients.neso_api_client.requests.get")
	def test_get_json_does_not_retry_on_404(self, mock_get, mock_sleep):
		resp_404 = Mock()
		resp_404.raise_for_status.side_effect = requests.exceptions.HTTPError(response=Mock(status_code=404))
		mock_get.return_value = resp_404

		from carbon.clients.neso_api_client import _get_json

		result = _get_json("https://example.test/endpoint")
		self.assertEqual(result, {"error": "NESO API endpoint not found"})
		self.assertEqual(mock_get.call_count, 1)
		mock_sleep.assert_not_called()

	# Test for a HTTP 400 (bad request) API call:
	@patch("carbon.clients.neso_api_client.time.sleep")
	@patch("carbon.clients.neso_api_client.NESO_API_MAX_RETRIES", 3)
	@patch("carbon.clients.neso_api_client.requests.get")
	def test_get_json_does_not_retry_on_400(self, mock_get, mock_sleep):
		resp_400 = Mock()
		resp_400.raise_for_status.side_effect = requests.exceptions.HTTPError(response=Mock(status_code=400))
		mock_get.return_value = resp_400

		from carbon.clients.neso_api_client import _get_json

		result = _get_json("https://example.test/endpoint")
		self.assertEqual(result, {"error": "NESO API HTTP error (400)"})
		self.assertEqual(mock_get.call_count, 1)
		mock_sleep.assert_not_called()

	# Test for a HTTP timeout exception (no response):
	@patch("carbon.clients.neso_api_client.time.sleep")
	@patch("carbon.clients.neso_api_client.random.uniform", return_value=0.0)
	@patch("carbon.clients.neso_api_client.NESO_API_MAX_RETRIES", 1)
	@patch("carbon.clients.neso_api_client.requests.get")
	def test_get_json_retries_on_timeout_then_succeeds(self, mock_get, _mock_jitter, mock_sleep):
		resp_ok = Mock()
		resp_ok.raise_for_status.return_value = None
		resp_ok.json.return_value = {"ok": True}

		mock_get.side_effect = [requests.exceptions.Timeout(), resp_ok]

		from carbon.clients.neso_api_client import _get_json

		result = _get_json("https://example.test/endpoint")
		self.assertEqual(result, {"ok": True})
		self.assertEqual(mock_get.call_count, 2)
		mock_sleep.assert_called_once()

	# Test for a HTTP request exception (e.g. ConnectionError):
	@patch("carbon.clients.neso_api_client.time.sleep")
	@patch("carbon.clients.neso_api_client.random.uniform", return_value=0.0)
	@patch("carbon.clients.neso_api_client.NESO_API_MAX_RETRIES", 1)
	@patch("carbon.clients.neso_api_client.requests.get")
	def test_get_json_retries_on_request_exception_then_succeeds(self, mock_get, _mock_jitter, mock_sleep):
		resp_ok = Mock()
		resp_ok.raise_for_status.return_value = None
		resp_ok.json.return_value = {"ok": True}

		mock_get.side_effect = [requests.exceptions.ConnectionError(), resp_ok]

		from carbon.clients.neso_api_client import _get_json

		result = _get_json("https://example.test/endpoint")
		self.assertEqual(result, {"ok": True})
		self.assertEqual(mock_get.call_count, 2)
		mock_sleep.assert_called_once()

	# Test for _get_json to give up after x number of HTTP retries API call:
	@patch("carbon.clients.neso_api_client.time.sleep")
	@patch("carbon.clients.neso_api_client.random.uniform", return_value=0.0)
	@patch("carbon.clients.neso_api_client.NESO_API_MAX_RETRIES", 1)
	@patch("carbon.clients.neso_api_client.requests.get")
	def test_get_json_gives_up_after_retries(self, mock_get, _mock_jitter, mock_sleep):
		resp_500 = Mock()
		resp_500.raise_for_status.side_effect = requests.exceptions.HTTPError(response=Mock(status_code=500))
		mock_get.side_effect = [resp_500, resp_500]

		from carbon.clients.neso_api_client import _get_json

		result = _get_json("https://example.test/endpoint")
		self.assertIn("error", result)
		self.assertIn("after 1 retries", result["error"])
		self.assertEqual(mock_get.call_count, 2)
		# Sleeps only between attempt 0 -> attempt 1, not after final attempt.
		mock_sleep.assert_called_once()

# Test for the API method, get_national_forecast():

class GetNationalForecastTests(SimpleTestCase):
	@patch("carbon.clients.neso_api_client._get_json", return_value={"ok": True})
	@patch(
		"carbon.clients.neso_api_client._iso8601_utc_minute_from_now",
		return_value="2026-03-05T12:34Z",
	)
	def test_get_national_forecast_builds_expected_url_and_delegates(self, mock_now_str, mock_get_json):
		from carbon.clients.neso_api_client import API_BASE_URL, get_national_forecast

		result = get_national_forecast()
		self.assertEqual(result, {"ok": True})

		mock_now_str.assert_called_once_with()
		mock_get_json.assert_called_once_with(
			f"{API_BASE_URL}/intensity/2026-03-05T12:34Z/fw48h"
		)

# Test for the API method, get_regional_forecast():

class GetRegionalForecastTests(SimpleTestCase):
	@patch("carbon.clients.neso_api_client._get_json", return_value={"ok": True})
	@patch(
		"carbon.clients.neso_api_client._iso8601_utc_minute_from_now",
		return_value="2026-03-05T12:34Z",
	)
	def test_get_regional_forecast_builds_expected_url_and_delegates(self, mock_now_str, mock_get_json):
		from carbon.clients.neso_api_client import API_BASE_URL, get_regional_forecast

		result = get_regional_forecast()
		self.assertEqual(result, {"ok": True})

		mock_now_str.assert_called_once_with()
		mock_get_json.assert_called_once_with(
			f"{API_BASE_URL}/regional/intensity/2026-03-05T12:34Z/fw48h"
		)

# Test for the API method, get_national_actual():

class GetNationalActualTests(SimpleTestCase):
	@patch("carbon.clients.neso_api_client._get_json", return_value={"ok": True})
	@patch(
		"carbon.clients.neso_api_client._iso8601_utc_minute_from_now",
		return_value="2026-03-05T12:34Z",
	)
	def test_get_national_actual_builds_expected_url_and_delegates(self, mock_now_str, mock_get_json):
		from carbon.clients.neso_api_client import API_BASE_URL, get_national_actual

		result = get_national_actual()
		self.assertEqual(result, {"ok": True})

		mock_now_str.assert_called_once_with()
		mock_get_json.assert_called_once_with(
			f"{API_BASE_URL}/intensity/2026-03-05T12:34Z/pt24h"
		)

# Test for the API method, resolve_postcode_to_region():

class ResolvePostcodeToRegionTests(SimpleTestCase):
	@patch("carbon.clients.neso_api_client._get_json")
	def test_resolve_postcode_to_region_requires_postcode(self, mock_get_json):
		from carbon.clients.neso_api_client import resolve_postcode_to_region

		result = resolve_postcode_to_region(None)
		self.assertEqual(result, {"error": "Postcode is required"})
		mock_get_json.assert_not_called()

	@patch("carbon.clients.neso_api_client._get_json", return_value={"ok": True})
	@patch("carbon.clients.neso_api_client.extract_outcode", return_value="SW1A")
	def test_resolve_postcode_to_region_builds_expected_url_and_delegates(
		self, mock_extract_outcode, mock_get_json
	):
		from carbon.clients.neso_api_client import API_BASE_URL, resolve_postcode_to_region

		result = resolve_postcode_to_region("sw1a 1aa")
		self.assertEqual(result, {"ok": True})

		mock_extract_outcode.assert_called_once_with("sw1a 1aa")
		mock_get_json.assert_called_once_with(f"{API_BASE_URL}/regional/postcode/SW1A")

# Integration tests:
@tag("integration")
@unittest.skipUnless(os.getenv("RUN_INTEGRATION_TESTS") == "1", "Set RUN_INTEGRATION_TESTS=1")
class NESOIntegrationTests(SimpleTestCase):
	def test_national_forecast_returns_data(self):
		from carbon.clients.neso_api_client import get_national_forecast

		result = get_national_forecast()
		self.assertNotIn("error", result, msg=result.get("error"))
		self.assertIn("data", result)
		self.assertIsInstance(result["data"], list)
		self.assertGreater(len(result["data"]), 0)

	def test_regional_forecast_returns_data(self):
		from carbon.clients.neso_api_client import get_regional_forecast

		result = get_regional_forecast()
		self.assertNotIn("error", result, msg=result.get("error"))
		self.assertIn("data", result)
		self.assertIsInstance(result["data"], list)
		self.assertGreater(len(result["data"]), 0)

	def test_national_actual_returns_data(self):
		from carbon.clients.neso_api_client import get_national_actual

		result = get_national_actual()
		self.assertNotIn("error", result, msg=result.get("error"))
		self.assertIn("data", result)
		self.assertIsInstance(result["data"], list)
		self.assertGreater(len(result["data"]), 0)

	def test_resolve_postcode_to_region_returns_data(self):
		from carbon.clients.neso_api_client import resolve_postcode_to_region

		result = resolve_postcode_to_region("SW1A 1AA")
		self.assertNotIn("error", result, msg=result.get("error"))
		self.assertIn("data", result)
		self.assertIsInstance(result["data"], list)
		self.assertGreater(len(result["data"]), 0)
		self.assertIsInstance(result["data"][0], dict)

# Ingestion tests:
class NESOIngestionTests(TestCase):
	@patch("carbon.services.ingestion_service.get_national_forecast")
	def test_ingest_national_forecast_creates_and_idempotently_updates_records_(self, mock_get_national_forecast):
		from carbon.services.ingestion_service import ingest_national_forecast

		for run in range(2):
			if run == 0:
				mock_get_national_forecast.return_value = {
					"data": [
						{
							"from": "2026-03-09T12:00Z",
							"to": "2026-03-09T12:30Z",
							"intensity":{
								"forecast": 250, 
								"actual":None, 
								"index": "moderate"
							},
						}
					]
				}

			else:
				mock_get_national_forecast.return_value = {
					"data": [
						{
							"from": "2026-03-09T12:00Z",
							"to": "2026-03-09T12:30Z",
							"intensity":{
								"forecast": 125, 
								"actual":None, 
								"index": "low"
							},
						}
					]
				}

			result = ingest_national_forecast()

			if run == 0:
				self.assertEqual(result.records_created, 1)
				self.assertEqual(result.records_updated, 0)
			else:
				self.assertEqual(result.records_created, 0)
				self.assertEqual(result.records_updated, 1)
				self.assertEqual(CarbonIntensityRecord.objects.filter(is_national=True).count(), 1)

			record = CarbonIntensityRecord.objects.get(is_national=True)
			expected_forecast = 250 if run == 0 else 125
			self.assertEqual(record.forecast, expected_forecast)

	
	@patch("carbon.services.ingestion_service.get_regional_forecast")
	def test_ingest_regional_forecast_creates_and_idempotently_updates_records(self, mock_get_regional_forecast):
		from carbon.services.ingestion_service import ingest_regional_forecast

		for run in range(2):
			if run == 0:
				mock_get_regional_forecast.return_value = {
					"data": [
						{
							"from": "2026-03-09T13:00Z",
							"to": "2026-03-09T13:30Z",
							"regions": [
								{
									"regionid": 1,
									"shortname": "North Scotland",
									"intensity":{
										"forecast": 0, 
										"index": "very low"
									}
								}
							]
						}
					]
				}

			else:
				mock_get_regional_forecast.return_value = {
					"data": [
						{
							"from": "2026-03-09T13:00Z",
							"to": "2026-03-09T13:30Z",
							"regions": [
								{
									"regionid": 1,
									"shortname": "North Scotland",
									"intensity":{
										"forecast": 60, 
										"index": "low"
									}
								}
							]
						}
					]
				}

			result = ingest_regional_forecast()

			if run == 0:
				self.assertEqual(result.records_created, 1)
				self.assertEqual(result.records_updated, 0)
			else:
				self.assertEqual(result.records_created, 0)
				self.assertEqual(result.records_updated, 1)
				self.assertEqual(CarbonIntensityRecord.objects.filter(is_national=False, region_id=1).count(), 1)

			record = CarbonIntensityRecord.objects.get(is_national=False, region_id=1)
			expected_forecast = 0 if run == 0 else 60
			self.assertEqual(record.forecast, expected_forecast)

	@patch("carbon.clients.neso_api_client.get_national_actual")
	def test_ingest_national_actual_updates_records_(self, mock_get_national_actual):
		from carbon.services.ingestion_service import ingest_national_actual

		# Create pre-existing forecast record to be updated
		valid_from = timezone.make_aware(datetime(2026, 3, 9, 12, 0, 0))
		valid_to = timezone.make_aware(datetime(2026, 3, 9, 12, 30, 0))
		CarbonIntensityRecord.objects.create(
			region_id=None,
			region_shortname=None,
			valid_from=valid_from,
			valid_to=valid_to,
			forecast=350,
			actual=None,
			index=CarbonIntensityRecord.IntensityIndex.HIGH,
			forecast_generated_at=timezone.now(),
			is_national=True,
		)

		base_response = {
			"data": [
				{
					"from": "2026-03-09T12:00Z",
					"to": "2026-03-09T12:30Z",
					"intensity":{
						"forecast": 350, 
						"actual": None, 
						"index": "high"
					},
				}
			]
		}

		for run in range(2):
			base_response["data"][0]["intensity"]["actual"] = 300 if run == 0 else 400
			mock_get_national_actual.return_value = base_response

			result = ingest_national_actual()

			if run == 0:
				self.assertEqual(result.records_updated, 1)
			else:
				self.assertEqual(result.records_updated, 1)
				self.assertEqual(CarbonIntensityRecord.objects.filter(is_national=True).count(), 1)

			record = CarbonIntensityRecord.objects.get(is_national=True)
			expected_actual = 300 if run == 0 else 400
			self.assertEqual(record.actual, expected_actual)