from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal
from core.models import Region, PostcodeRegionCache

# Region model's tests:

# Region's field validation tests:

# Validates the Region schema so only data that fits the model contract can be saved:
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

# Checks field-level constraints on the Region model; i) region_id is unique, ii) shortname is indexed
class RegionIndexTests(TestCase):
    def test_region_id_is_unique(self):
        region_id_field = Region._meta.get_field("region_id")
        self.assertTrue(region_id_field.unique)

    def test_shortname_is_indexed(self):
        shortname_field = Region._meta.get_field("shortname")
        self.assertTrue(shortname_field.db_index)

# Confirms the .__str__() method returns the expected human-readable string:
class RegionStrTests(TestCase):
    def test_region_str_includes_shortname_and_region_id(self):
        region = Region.objects.create(region_id="REG-1", shortname="South", name="South Region")
        self.assertEqual(str(region), "South (REG-1)")


# PostcodeRegionCache models' tests:

# PostcodeRegionCache's field validation tests:

# Validates the schema rules for cache rows (required/non-blank, max length, uniqueness on postcode)
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
# Checks field-level indexing/constraints:
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

# Verifies the model's save(), normalises the postcode (stripping of whitespace and uppercase) so stored cache keys are consistent
class PostcodeRegionCacheSaveNormalisationTests(TestCase):
    def test_postcode_is_normalised_on_save(self):
        cache = PostcodeRegionCache.objects.create(
            postcode=" sw1a  1aa ",
            region_id="REG-1",
            region_shortname="South",
        )
        cache.refresh_from_db()
        self.assertEqual(cache.postcode, "SW1A1AA")

# Verifies the cache rows' __str__() format is readable
class PostcodeRegionCacheStrTests(TestCase):
    def test_cache_str_is_readable_mapping(self):
        cache = PostcodeRegionCache.objects.create(
            postcode="SW1A1AA",
            region_id="REG-1",
            region_shortname="South",
        )
        self.assertEqual(str(cache), "SW1A1AA -> South")
