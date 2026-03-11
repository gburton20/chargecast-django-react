import json
import logging
from io import StringIO
from unittest.mock import Mock, patch

import requests
from django.core.management import call_command
from django.test import SimpleTestCase
from django.db import DatabaseError

from carbon.services.ingestion_service import IngestionResult
from config.logging import StructuredJsonFormatter


class StructuredLoggingFormatterTests(SimpleTestCase):
    def test_structured_json_formatter_includes_event_and_context(self):
        formatter = StructuredJsonFormatter()
        record = logging.makeLogRecord(
            {
                "name": "carbon.test",
                "levelname": "INFO",
                "levelno": logging.INFO,
                "msg": "test message",
                "args": (),
                "event": "test_event",
                "context": {"run_id": "abc123", "records_created": 2},
            }
        )

        payload = json.loads(formatter.format(record))

        self.assertEqual(payload["logger"], "carbon.test")
        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(payload["message"], "test message")
        self.assertEqual(payload["event"], "test_event")
        self.assertEqual(payload["run_id"], "abc123")
        self.assertEqual(payload["records_created"], 2)


class ApiClientLoggingTests(SimpleTestCase):
    @patch("carbon.clients.neso_api_client.logger.error")
    @patch("carbon.clients.neso_api_client.requests.get")
    def test_get_json_logs_http_error_context(self, mock_get, mock_error):
        response = Mock()
        response.text = "bad request body"
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=Mock(status_code=400, text="bad request body"))
        mock_get.return_value = response

        from carbon.clients.neso_api_client import _get_json

        result = _get_json("https://example.test/endpoint")

        self.assertEqual(result, {"error": "NESO API HTTP error (400)"})
        self.assertTrue(mock_error.called)

        logged_extra = mock_error.call_args.kwargs["extra"]["context"]
        self.assertEqual(logged_extra["endpoint"], "https://example.test/endpoint")
        self.assertEqual(logged_extra["status_code"], 400)
        self.assertEqual(logged_extra["response_body"], "bad request body")


class IngestionServiceLoggingTests(SimpleTestCase):
    @patch("carbon.services.ingestion_service.logger.log")
    @patch("carbon.services.ingestion_service.CarbonIntensityRecord.objects.update_or_create")
    @patch("carbon.services.ingestion_service.get_national_forecast")
    def test_ingest_national_forecast_logs_database_error_context(
        self,
        mock_get_national_forecast,
        mock_update_or_create,
        mock_logger_log,
    ):
        from carbon.services.ingestion_service import ingest_national_forecast

        mock_get_national_forecast.return_value = {
            "data": [
                {
                    "from": "2026-03-09T12:00Z",
                    "to": "2026-03-09T12:30Z",
                    "intensity": {"forecast": 250, "index": "moderate"},
                }
            ]
        }
        mock_update_or_create.side_effect = DatabaseError("db unavailable")

        result = ingest_national_forecast()

        self.assertEqual(result.records_failed, 1)

        database_error_logs = [
            kwargs["extra"]["context"]
            for _, _, kwargs in mock_logger_log.mock_calls
            if kwargs.get("extra", {}).get("event") == "ingestion_database_error"
        ]
        self.assertEqual(len(database_error_logs), 1)
        self.assertEqual(database_error_logs[0]["model"], "CarbonIntensityRecord")
        self.assertEqual(database_error_logs[0]["operation"], "update_or_create")


class IngestionCommandLoggingTests(SimpleTestCase):
    @patch("carbon.management.commands.ingest_carbon_data.logger.log")
    @patch("carbon.management.commands.ingest_carbon_data.ingest_national_actual")
    @patch("carbon.management.commands.ingest_carbon_data.ingest_regional_forecast")
    @patch("carbon.management.commands.ingest_carbon_data.ingest_national_forecast")
    def test_command_logs_summary_metrics(
        self,
        mock_national,
        mock_regional,
        mock_actual,
        mock_logger_log,
    ):
        mock_national.return_value = IngestionResult(records_created=1, records_updated=0, records_skipped=0, records_failed=0)
        mock_regional.return_value = IngestionResult(records_created=2, records_updated=1, records_skipped=0, records_failed=0)
        mock_actual.return_value = IngestionResult(records_created=0, records_updated=1, records_skipped=1, records_failed=0)

        out = StringIO()
        call_command("ingest_carbon_data", stdout=out)

        completion_logs = [
            kwargs["extra"]["context"]
            for _, _, kwargs in mock_logger_log.mock_calls
            if kwargs.get("extra", {}).get("event") == "ingestion_command_completed"
        ]
        self.assertEqual(len(completion_logs), 1)
        self.assertEqual(completion_logs[0]["records_created"], 3)
        self.assertEqual(completion_logs[0]["records_updated"], 2)
        self.assertEqual(completion_logs[0]["records_skipped"], 1)
        self.assertEqual(completion_logs[0]["records_failed"], 0)
