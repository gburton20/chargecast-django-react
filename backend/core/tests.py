from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal
from core.models import Region, PostcodeRegionCache, ChargerLocation

# Create your tests here per model:

# Region model's tests:

# Region's field validation tests:
class RegionValidationTests(TestCase):
    def test_blank_required_fields_raise_validation_error(self):
        invalid_instance = Region(region_id="", shortname="", name="")

        with self.assertRaises(ValidationError) as ctx:
            invalid_instance.full_clean()

        self.assertIn("region_id", ctx.exception.message_dict)
        self.assertIn("shortname", ctx.exception.message_dict)
        self.assertIn("name", ctx.exception.message_dict)

    def test_max_length_fields_raise_validation_error(self):
        invalid_instance = Region(
            region_id="R" * 65,
            shortname="S" * 65,
            name="N" * 129,
        )

        with self.assertRaises(ValidationError) as ctx:
            invalid_instance.full_clean()

        self.assertIn("region_id", ctx.exception.message_dict)
        self.assertIn("shortname", ctx.exception.message_dict)
        self.assertIn("name", ctx.exception.message_dict)

    def test_unique_region_id_raises_validation_error(self):
        Region.objects.create(region_id="REG-1", shortname="South", name="South Region")
        invalid_instance = Region(region_id="REG-1", shortname="Other", name="Other Region")

        with self.assertRaises(ValidationError) as ctx:
            invalid_instance.full_clean()

        self.assertIn("region_id", ctx.exception.message_dict)

    def test_valid_region_saves_correctly(self):
        valid_instance = Region(region_id="REG-2", shortname="North", name="North Region")
        valid_instance.full_clean()
        valid_instance.save()

        self.assertEqual(Region.objects.count(), 1)

# Region's index presence tests:
class RegionIndexTests(TestCase):
    def test_region_id_is_unique(self):
        region_id_field = Region._meta.get_field("region_id")
        self.assertTrue(region_id_field.unique)

    def test_shortname_is_indexed(self):
        shortname_field = Region._meta.get_field("shortname")
        self.assertTrue(shortname_field.db_index)


# PostcodeRegionCache models' tests:

# PostcodeRegionCache's field validation tests:
class PostcodeRegionCacheValidationTests(TestCase):
    def test_blank_required_fields_raise_validation_error(self):
        invalid_instance = PostcodeRegionCache(postcode="", region_id="", region_shortname="")

        with self.assertRaises(ValidationError) as ctx:
            invalid_instance.full_clean()

        self.assertIn("postcode", ctx.exception.message_dict)
        self.assertIn("region_id", ctx.exception.message_dict)
        self.assertIn("region_shortname", ctx.exception.message_dict)

    def test_max_length_fields_raise_validation_error(self):
        invalid_instance = PostcodeRegionCache(
            postcode="P" * 17,
            region_id="R" * 65,
            region_shortname="S" * 65,
        )

        with self.assertRaises(ValidationError) as ctx:
            invalid_instance.full_clean()

        self.assertIn("postcode", ctx.exception.message_dict)
        self.assertIn("region_id", ctx.exception.message_dict)
        self.assertIn("region_shortname", ctx.exception.message_dict)

    def test_unique_postcode_raises_validation_error(self):
        PostcodeRegionCache.objects.create(
            postcode="SW1A1AA",
            region_id="REG-1",
            region_shortname="South",
        )
        invalid_instance = PostcodeRegionCache(
            postcode="SW1A1AA",
            region_id="REG-2",
            region_shortname="North",
        )

        with self.assertRaises(ValidationError) as ctx:
            invalid_instance.full_clean()

        self.assertIn("postcode", ctx.exception.message_dict)

    def test_valid_instance_saves_correctly(self):
        valid_instance = PostcodeRegionCache(
            postcode="SW1A1AA",
            region_id="REG-1",
            region_shortname="South",
        )
        valid_instance.full_clean()
        valid_instance.save()

        self.assertEqual(PostcodeRegionCache.objects.count(), 1)

# PostcodeRegionCache's index presence tests:
class PostcodeRegionCacheIndexTests(TestCase):
    def test_postcode_is_unique(self):
        postcode_field = PostcodeRegionCache._meta.get_field("postcode")
        self.assertTrue(postcode_field.unique)

    def test_region_id_is_indexed(self):
        region_id_field = PostcodeRegionCache._meta.get_field("region_id")
        self.assertTrue(region_id_field.db_index)

    def test_resolved_at_is_indexed(self):
        resolved_at_field = PostcodeRegionCache._meta.get_field("resolved_at")
        self.assertTrue(resolved_at_field.db_index)


# ChargerLocation model's tests:

# ChargerLocation's field validation tests:
class ChargerLocationValidationTests(TestCase):
    def test_blank_required_fields_raise_validation_error(self):
        invalid_instance = ChargerLocation(
            name="",
            postcode="",
            latitude=None,
            longitude=None,
            region_id="",
        )

        with self.assertRaises(ValidationError) as ctx:
            invalid_instance.full_clean()

        self.assertIn("name", ctx.exception.message_dict)
        self.assertIn("postcode", ctx.exception.message_dict)
        self.assertIn("latitude", ctx.exception.message_dict)
        self.assertIn("longitude", ctx.exception.message_dict)
        self.assertIn("region_id", ctx.exception.message_dict)

    def test_max_length_fields_raise_validation_error(self):
        invalid_instance = ChargerLocation(
            name="N" * 129,
            postcode="P" * 17,
            latitude=Decimal("51.501000"),
            longitude=Decimal("-0.141000"),
            region_id="R" * 65,
        )

        with self.assertRaises(ValidationError) as ctx:
            invalid_instance.full_clean()

        self.assertIn("name", ctx.exception.message_dict)
        self.assertIn("postcode", ctx.exception.message_dict)
        self.assertIn("region_id", ctx.exception.message_dict)

    def test_latitude_longitude_decimal_constraints_raise_validation_error(self):
        invalid_instance = ChargerLocation(
            name="Test Charger",
            postcode="SW1A1AA",
            latitude=Decimal("1234.123456"),
            longitude=Decimal("-0.141000"),
            region_id="REG-1",
        )

        with self.assertRaises(ValidationError) as ctx:
            invalid_instance.full_clean()

        self.assertIn("latitude", ctx.exception.message_dict)

    def test_valid_instance_saves_correctly(self):
        valid_instance = ChargerLocation(
            name="Test Charger",
            postcode="SW1A1AA",
            latitude=Decimal("51.501000"),
            longitude=Decimal("-0.141000"),
            region_id="REG-1",
        )
        valid_instance.full_clean()
        valid_instance.save()

        self.assertEqual(ChargerLocation.objects.count(), 1)

# ChargerLocation's index presence tests:
class ChargerLocationIndexTests(TestCase):
    def test_postcode_and_region_id_fields_are_indexed(self):
        postcode_field = ChargerLocation._meta.get_field("postcode")
        region_id_field = ChargerLocation._meta.get_field("region_id")
        self.assertTrue(postcode_field.db_index)
        self.assertTrue(region_id_field.db_index)

    def test_meta_indexes_include_expected_indexes(self):
        indexes = {(tuple(idx.fields), idx.name) for idx in ChargerLocation._meta.indexes}
        self.assertIn((("latitude", "longitude"), "core_charger_lat_lng_idx"), indexes)
        self.assertIn((("region_id", "postcode"), "core_charger_reg_pcode_idx"), indexes)
