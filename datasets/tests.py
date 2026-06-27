import shutil
import tempfile
from io import BytesIO

from PIL import Image as PILImage

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from masterdata.models import Category, SubCategory
from transmission.models import TransmissionLine

from .models import Inspection, InspectionImage
from .utils import safe_file_name, safe_folder_name, sha256_of_file, upload_path

User = get_user_model()

_MEDIA = tempfile.mkdtemp(prefix="aptransco_test_media_")


def png_bytes(color=(255, 0, 0), size=(8, 8)):
    buf = BytesIO()
    PILImage.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def image_upload(name="photo.png", color=(255, 0, 0)):
    return SimpleUploadedFile(name, png_bytes(color), content_type="image/png")


class SafeNameTests(TestCase):
    def test_safe_folder_name_replaces_unsafe_chars(self):
        self.assertEqual(safe_folder_name("132KV Line A/B"), "132KV_Line_A_B")

    def test_safe_folder_name_preserves_case_and_hyphen(self):
        self.assertEqual(
            safe_folder_name("132KV Vemagiri-Rajahmundry"),
            "132KV_Vemagiri-Rajahmundry",
        )

    def test_safe_folder_name_collapses_repeats_and_strips(self):
        self.assertEqual(safe_folder_name("  a //  b  "), "a_b")

    def test_safe_file_name_unique_and_keeps_extension(self):
        a = safe_file_name("WhatsApp Image.44.12 PM.jpeg")
        b = safe_file_name("WhatsApp Image.44.12 PM.jpeg")
        self.assertTrue(a.endswith(".jpeg"))
        self.assertNotIn(" ", a)
        self.assertNotEqual(a, b)  # unique suffix per call

    def test_safe_file_name_handles_missing_extension(self):
        self.assertTrue(safe_file_name("noext").startswith("noext_"))


class ChecksumTests(TestCase):
    def test_identical_content_same_hash(self):
        data = png_bytes()
        self.assertEqual(
            sha256_of_file(SimpleUploadedFile("a.png", data)),
            sha256_of_file(SimpleUploadedFile("b.png", data)),
        )

    def test_different_content_different_hash(self):
        self.assertNotEqual(
            sha256_of_file(SimpleUploadedFile("a.png", png_bytes((255, 0, 0)))),
            sha256_of_file(SimpleUploadedFile("b.png", png_bytes((0, 255, 0)))),
        )

    def test_file_pointer_rewound(self):
        f = SimpleUploadedFile("a.png", png_bytes())
        sha256_of_file(f)
        self.assertEqual(f.tell(), 0)  # still readable for saving


@override_settings(MEDIA_ROOT=_MEDIA)
class UploadPathTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user("pathuser", password="x")
        self.line = TransmissionLine.objects.create(
            line_name="132KV A/B Line", voltage="132KV"
        )
        self.cat = Category.objects.create(name="Defect")
        self.sub = SubCategory.objects.create(category=self.cat, name="Vegetation")

    def test_upload_path_structure(self):
        insp = Inspection.objects.create(
            transmission_line=self.line, location_id="T 045", uploaded_by=self.user
        )
        img = InspectionImage(inspection=insp, subcategory=self.sub)
        parts = upload_path(img, "my photo.jpg").split("/")
        # media/<line>/<location>/<Category>/<SubCategory>/<file>
        self.assertEqual(parts[0], "132KV_A_B_Line")
        self.assertEqual(parts[1], "T_045")
        self.assertEqual(parts[2], "Defect")
        self.assertEqual(parts[3], "Vegetation")
        self.assertTrue(parts[4].endswith(".jpg"))


@override_settings(MEDIA_ROOT=_MEDIA)
class UploadViewTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user("inspector", password="pw12345!")
        self.line = TransmissionLine.objects.create(
            line_name="220KV Test Line", voltage="220KV"
        )
        self.cat = Category.objects.create(name="Component")
        self.peak = SubCategory.objects.create(category=self.cat, name="Peak")
        self.body = SubCategory.objects.create(category=self.cat, name="Body")
        self.url = reverse("upload")
        self.client.login(username="inspector", password="pw12345!")

    def _post(self, files, location="T045"):
        data = {
            "transmission_line": self.line.id,
            "location_id": location,
            "remarks": "test",
        }
        data.update(files)
        return self.client.post(self.url, data)

    def test_login_required(self):
        self.client.logout()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp.url)

    def test_valid_upload_creates_inspection_and_images(self):
        resp = self._post({
            f"subcategory_{self.peak.id}": image_upload("p.png", (255, 0, 0)),
            f"subcategory_{self.body.id}": image_upload("b.png", (0, 255, 0)),
        })
        self.assertEqual(Inspection.objects.count(), 1)
        insp = Inspection.objects.get()
        self.assertRedirects(resp, reverse("inspection_detail", args=[insp.id]))
        self.assertEqual(insp.status, Inspection.SUBMITTED)
        self.assertEqual(insp.images.count(), 2)
        self.assertTrue(all(img.checksum for img in insp.images.all()))

    def test_missing_line_and_location_blocks(self):
        resp = self.client.post(self.url, {
            "transmission_line": "",
            "location_id": "",
            f"subcategory_{self.peak.id}": image_upload(),
        })
        self.assertEqual(resp.status_code, 200)  # re-rendered with errors
        self.assertEqual(Inspection.objects.count(), 0)

    def test_no_images_blocks(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Inspection.objects.count(), 0)

    def test_invalid_image_skipped(self):
        bad = SimpleUploadedFile("x.png", b"not really an image", "image/png")
        resp = self._post({f"subcategory_{self.peak.id}": bad})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Inspection.objects.count(), 0)

    def test_duplicate_within_submission_skipped(self):
        data = png_bytes((10, 20, 30))
        resp = self._post({f"subcategory_{self.peak.id}": [
            SimpleUploadedFile("a.png", data, "image/png"),
            SimpleUploadedFile("b.png", data, "image/png"),
        ]})
        self.assertEqual(InspectionImage.objects.count(), 1)  # one dropped
        insp = Inspection.objects.get()
        self.assertRedirects(resp, reverse("inspection_detail", args=[insp.id]))

    def test_duplicate_against_existing_dataset_skipped(self):
        data = png_bytes((1, 2, 3))
        self._post({f"subcategory_{self.peak.id}":
                    SimpleUploadedFile("a.png", data, "image/png")})
        self.assertEqual(InspectionImage.objects.count(), 1)
        # Same content again -> nothing new saved, no second inspection.
        resp = self._post({f"subcategory_{self.peak.id}":
                           SimpleUploadedFile("c.png", data, "image/png")})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(InspectionImage.objects.count(), 1)
        self.assertEqual(Inspection.objects.count(), 1)

    @override_settings(MAX_IMAGE_UPLOAD_SIZE=10)
    def test_oversize_image_rejected(self):
        resp = self._post({f"subcategory_{self.peak.id}": image_upload()})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Inspection.objects.count(), 0)


@override_settings(MEDIA_ROOT=_MEDIA)
class DetailAndReviewTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.owner = User.objects.create_user("owner", password="pw")
        self.other = User.objects.create_user("other", password="pw")
        self.staff = User.objects.create_user("boss", password="pw", is_staff=True)
        self.line = TransmissionLine.objects.create(
            line_name="400KV Line", voltage="400KV"
        )
        self.insp = Inspection.objects.create(
            transmission_line=self.line, location_id="T1",
            status=Inspection.SUBMITTED, uploaded_by=self.owner,
        )

    def test_owner_can_view_detail(self):
        self.client.login(username="owner", password="pw")
        resp = self.client.get(reverse("inspection_detail", args=[self.insp.id]))
        self.assertEqual(resp.status_code, 200)

    def test_other_user_gets_404(self):
        self.client.login(username="other", password="pw")
        resp = self.client.get(reverse("inspection_detail", args=[self.insp.id]))
        self.assertEqual(resp.status_code, 404)

    def test_staff_can_view_any(self):
        self.client.login(username="boss", password="pw")
        resp = self.client.get(reverse("inspection_detail", args=[self.insp.id]))
        self.assertEqual(resp.status_code, 200)

    def test_non_staff_cannot_review(self):
        self.client.login(username="owner", password="pw")
        resp = self.client.post(
            reverse("review_inspection", args=[self.insp.id]),
            {"action": "approve"},
        )
        self.assertEqual(resp.status_code, 302)  # bounced to login
        self.insp.refresh_from_db()
        self.assertEqual(self.insp.status, Inspection.SUBMITTED)

    def test_staff_approve(self):
        self.client.login(username="boss", password="pw")
        self.client.post(
            reverse("review_inspection", args=[self.insp.id]),
            {"action": "approve"},
        )
        self.insp.refresh_from_db()
        self.assertEqual(self.insp.status, Inspection.APPROVED)

    def test_staff_reject(self):
        self.client.login(username="boss", password="pw")
        self.client.post(
            reverse("review_inspection", args=[self.insp.id]),
            {"action": "reject"},
        )
        self.insp.refresh_from_db()
        self.assertEqual(self.insp.status, Inspection.REJECTED)
