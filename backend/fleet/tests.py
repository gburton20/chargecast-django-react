from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from .models import FleetChargingEvent, FleetUploadBatch

# Validates that a FleetUploadBatch row can be created with valid data, and that the default processing_status = PENDING:
class FleetUploadBatchCreationTests(TestCase):
	def test_can_create_batch(self):
		batch = FleetUploadBatch.objects.create(
			filename="fleet_upload.csv",
			rows_received=2,
			rows_processed=2,
			rows_failed=0,
			fallback_rows=0,
			total_kwh=Decimal("12.500"),
			total_emissions_kg=Decimal("2.345678"),
		)

		self.assertEqual(FleetUploadBatch.objects.count(), 1)
		self.assertEqual(batch.processing_status, FleetUploadBatch.ProcessingStatus.PENDING)

# Validates via the Django model validation method, full_clean() model-level schema rules including filename cannot be blank and that a processing status must be one of the declared choices: 
class FleetUploadBatchValidationTests(TestCase):
	def test_blank_filename_raises_validation_error(self):
		invalid = FleetUploadBatch(filename="")

		with self.assertRaises(ValidationError) as ctx:
			invalid.full_clean()

		self.assertIn("filename", ctx.exception.message_dict)

	def test_processing_status_choices_are_enforced_by_full_clean(self):
		invalid = FleetUploadBatch(filename="fleet_upload.csv", processing_status="not-a-choice")

		with self.assertRaises(ValidationError) as ctx:
			invalid.full_clean()

		self.assertIn("processing_status", ctx.exception.message_dict)

# Validates the __str__() method called in fleet's models.py file for FleetUploadBatch converts the FleetUploadBatch object into a human-readable admin/debug string
class FleetUploadBatchStrTests(TestCase):
	def test_batch_str_includes_filename(self):
		batch = FleetUploadBatch.objects.create(filename="fleet_upload.csv")
		self.assertIn("fleet_upload.csv", str(batch))

# Validates whether a FleetChargingEvent can be created for a batch, and that the foreign key (FK) relationship between FleetChargingEvent.batch and FleetUploadBatch works 
class FleetChargingEventCreationTests(TestCase):
	def test_can_create_event_for_batch(self):
		batch = FleetUploadBatch.objects.create(filename="fleet_upload.csv")
		charged_at = timezone.make_aware(datetime(2026, 1, 1, 12, 0, 0))

		event = FleetChargingEvent.objects.create(
			batch=batch,
			vehicle_id="veh_123",
			postcode="SW1A1AA",
			charged_at=charged_at,
			region_id="R1",
			region_shortname="South Wales",
			kwh_consumed=Decimal("12.500"),
			carbon_intensity_used=200,
			intensity_type_used=FleetChargingEvent.IntensityTypeUsed.REGIONAL_FORECAST,
			calculated_emissions_kg=Decimal("2.500000"),
		)

		self.assertEqual(event.batch_id, batch.id)
		self.assertEqual(batch.charging_events.count(), 1)

# Validates 'intensity_type_used' choice enforcement via the Django model validation method, full_clean(). An invalid choice raises a ValidationError.
class FleetChargingEventValidationTests(TestCase):
	def test_intensity_type_used_choices_are_enforced_by_full_clean(self):
		batch = FleetUploadBatch.objects.create(filename="fleet_upload.csv")
		charged_at = timezone.make_aware(datetime(2026, 1, 1, 12, 0, 0))

		invalid = FleetChargingEvent(
			batch=batch,
			vehicle_id="veh_123",
			postcode="SW1A1AA",
			charged_at=charged_at,
			region_id="R1",
			region_shortname="South Wales",
			kwh_consumed=Decimal("1.000"),
			carbon_intensity_used=200,
			intensity_type_used="not-a-choice",
			calculated_emissions_kg=Decimal("0.200000"),
		)

		with self.assertRaises(ValidationError) as ctx:
			invalid.full_clean()

		self.assertIn("intensity_type_used", ctx.exception.message_dict)


# As the FleetChargingEvent model correlates to an append-only ledger in the DB, this prevents the deletion of uploaded batches from the DB if related FleetChargingEvents are found (see on_delete=PROTECT):
class FleetChargingEventFKTests(TestCase):
	def test_batch_delete_is_protected_if_events_exist(self):
		batch = FleetUploadBatch.objects.create(filename="fleet_upload.csv")
		charged_at = timezone.make_aware(datetime(2026, 1, 1, 12, 0, 0))

		FleetChargingEvent.objects.create(
			batch=batch,
			vehicle_id="veh_123",
			postcode="SW1A1AA",
			charged_at=charged_at,
			region_id="R1",
			region_shortname="South Wales",
			kwh_consumed=Decimal("1.000"),
			carbon_intensity_used=200,
			intensity_type_used=FleetChargingEvent.IntensityTypeUsed.NATIONAL_FORECAST,
			calculated_emissions_kg=Decimal("0.200000"),
		)

		with self.assertRaises(ProtectedError):
			batch.delete()

# As the FleetChargingEvent model correlates to an append-only ledger in the DB, this test validates the model's save() immutability guard:
class FleetChargingEventImmutabilityTests(TestCase):
	def test_event_is_immutable(self):
		batch = FleetUploadBatch.objects.create(filename="fleet_upload.csv")
		charged_at = timezone.make_aware(datetime(2026, 1, 1, 12, 0, 0))

		event = FleetChargingEvent.objects.create(
			batch=batch,
			vehicle_id="veh_123",
			postcode="SW1A1AA",
			charged_at=charged_at,
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

# Tests whether vehicle_ids are included in the output of the __str__() Django methods run per FleetChargingEvent:
class FleetChargingEventStrTests(TestCase):
	def test_event_str_includes_vehicle_id(self):
		batch = FleetUploadBatch.objects.create(filename="fleet_upload.csv")
		charged_at = timezone.make_aware(datetime(2026, 1, 1, 12, 0, 0))

		event = FleetChargingEvent.objects.create(
			batch=batch,
			vehicle_id="veh_123",
			postcode="SW1A1AA",
			charged_at=charged_at,
			region_id="R1",
			region_shortname="South Wales",
			kwh_consumed=Decimal("1.000"),
			carbon_intensity_used=200,
			intensity_type_used=FleetChargingEvent.IntensityTypeUsed.NATIONAL_FORECAST,
			calculated_emissions_kg=Decimal("0.200000"),
		)

		self.assertIn("veh_123", str(event))
