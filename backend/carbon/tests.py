from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from carbon.models import CarbonIntensityRecord

# Tests to establish whether a national and regional record can be created in the PostgreSQL DB via data sourced from the NESO carbon intensity API.
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

# Tests to ensure expected named indexes are declard on the model (in core/models.py > Meta.indexes) to the DB are created successfully:
class CarbonIntensityRecordIndexTests(TestCase):
	def test_expected_meta_indexes_exist(self):
		indexes = {(tuple(idx.fields), idx.name) for idx in CarbonIntensityRecord._meta.indexes}
		self.assertIn((("region_id", "valid_from"), "carbon_cir_region_from_idx"), indexes)
		self.assertIn((("is_national", "valid_from"), "carbon_cir_nat_from_idx"), indexes)

# Tests whether the scope and valid from values input by the user are converted to strings successfully for human-readable admin and debugging messages
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