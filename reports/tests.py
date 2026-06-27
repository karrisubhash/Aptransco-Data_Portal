import shutil
import tempfile
import zipfile
from io import BytesIO

from PIL import Image as PILImage

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from masterdata.models import Category, SubCategory
from transmission.models import TransmissionLine
from datasets.models import Inspection, InspectionImage

from .views import dataset_slug

User = get_user_model()

_MEDIA = tempfile.mkdtemp(prefix="aptransco_test_reports_")


def png(color=(255, 0, 0)):
    buf = BytesIO()
    PILImage.new("RGB", (8, 8), color).save(buf, format="PNG")
    return SimpleUploadedFile("x.png", buf.getvalue(), content_type="image/png")


class DatasetSlugTests(TestCase):
    def test_slug(self):
        self.assertEqual(dataset_slug("Cross Arms"), "cross_arms")
        self.assertEqual(dataset_slug("Legs & Stub Angles"), "legs_stub_angles")


@override_settings(MEDIA_ROOT=_MEDIA)
class ExportTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user("u", password="pw")
        self.staff = User.objects.create_user("s", password="pw", is_staff=True)
        self.line = TransmissionLine.objects.create(
            line_name="132KV Export Line", voltage="132KV"
        )
        self.cat = Category.objects.create(name="Component")
        self.sub = SubCategory.objects.create(category=self.cat, name="Peak")

        # Approved inspection with 2 images.
        approved = Inspection.objects.create(
            transmission_line=self.line, location_id="A1",
            status=Inspection.APPROVED, uploaded_by=self.user,
        )
        for c in [(1, 0, 0), (0, 1, 0)]:
            InspectionImage.objects.create(
                inspection=approved, subcategory=self.sub, image=png(c)
            )
        # Submitted (not yet approved) inspection with 1 image — must be excluded.
        submitted = Inspection.objects.create(
            transmission_line=self.line, location_id="A2",
            status=Inspection.SUBMITTED, uploaded_by=self.user,
        )
        InspectionImage.objects.create(
            inspection=submitted, subcategory=self.sub, image=png((0, 0, 1))
        )

    def test_index_requires_staff(self):
        self.client.login(username="u", password="pw")
        self.assertEqual(self.client.get(reverse("reports")).status_code, 302)
        self.client.login(username="s", password="pw")
        self.assertEqual(self.client.get(reverse("reports")).status_code, 200)

    def test_zip_contains_only_approved_images(self):
        self.client.login(username="s", password="pw")
        resp = self.client.get(reverse("export_category_zip", args=[self.cat.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/zip")
        zf = zipfile.ZipFile(BytesIO(resp.getvalue()))
        names = zf.namelist()
        self.assertEqual(len(names), 2)  # only the 2 approved images
        self.assertTrue(all(n.startswith("peak/") for n in names))

    def test_metadata_csv_covers_all_images(self):
        self.client.login(username="s", password="pw")
        resp = self.client.get(reverse("export_metadata_csv"))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("inspection_id", body)  # header
        self.assertEqual(body.strip().count("\n"), 3)  # header + 3 images

    def test_metadata_xlsx_staff_only(self):
        self.client.login(username="u", password="pw")
        self.assertEqual(
            self.client.get(reverse("export_metadata_xlsx")).status_code, 302
        )
        self.client.login(username="s", password="pw")
        resp = self.client.get(reverse("export_metadata_xlsx"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spreadsheet", resp["Content-Type"])
