from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from .models import FleetChargingEvent, FleetUploadBatch


class FleetModelsTests(TestCase):
	def test_can_create_batch_and_event(self):
		batch = FleetUploadBatch.objects.create(
			filename="fleet_upload.csv",
			rows_received=2,
			rows_processed=2,
			rows_failed=0,
			fallback_rows=0,
			total_kwh=Decimal("12.500"),
			total_emissions_kg=Decimal("2.345678"),
		)

		event = FleetChargingEvent.objects.create(
			batch=batch,
			vehicle_id="veh_123",
			postcode="SW1A1AA",
			charged_at=timezone.now(),
			region_id="R1",
			region_shortname="South Wales",
			kwh_consumed=Decimal("12.500"),
			carbon_intensity_used=200,
			intensity_type_used=FleetChargingEvent.IntensityTypeUsed.REGIONAL_FORECAST,
			calculated_emissions_kg=Decimal("2.500000"),
		)

		self.assertEqual(event.batch_id, batch.id)
		self.assertEqual(batch.charging_events.count(), 1)

	def test_event_is_immutable(self):
		batch = FleetUploadBatch.objects.create(filename="fleet_upload.csv")
		event = FleetChargingEvent.objects.create(
			batch=batch,
			vehicle_id="veh_123",
			postcode="SW1A1AA",
			charged_at=timezone.now(),
			region_id="R1",
			region_shortname="South Wales",
			kwh_consumed=Decimal("1.000"),
			carbon_intensity_used=200,
			intensity_type_used=FleetChargingEvent.IntensityTypeUsed.NATIONAL_FORECAST,
			calculated_emissions_kg=Decimal("0.200000"),
		)

		event.postcode = "EC1A1BB"
		with self.assertRaises(ValueError):
			event.save()
