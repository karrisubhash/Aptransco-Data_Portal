from django.core.management import call_command
from django.test import TestCase

from .models import Category, SubCategory


class SeedMasterdataTests(TestCase):
    def test_seed_creates_taxonomy(self):
        call_command("seed_masterdata")
        self.assertEqual(Category.objects.count(), 2)
        self.assertEqual(SubCategory.objects.count(), 11)
        self.assertTrue(Category.objects.filter(name="Component").exists())
        self.assertTrue(Category.objects.filter(name="Defect").exists())

    def test_seed_is_idempotent(self):
        call_command("seed_masterdata")
        call_command("seed_masterdata")  # re-run must not duplicate
        self.assertEqual(Category.objects.count(), 2)
        self.assertEqual(SubCategory.objects.count(), 11)


class SubCategoryConstraintTests(TestCase):
    def test_unique_together(self):
        from django.db import IntegrityError, transaction

        cat = Category.objects.create(name="Component")
        SubCategory.objects.create(category=cat, name="Peak")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SubCategory.objects.create(category=cat, name="Peak")
