from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from masterdata.models import Category, SubCategory
from transmission.models import TransmissionLine
from datasets.models import Inspection

User = get_user_model()


class HealthCheckTests(TestCase):
    def test_healthz_ok(self):
        resp = self.client.get("/healthz")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")
        self.assertTrue(resp.json()["database"])

    def test_healthz_is_public(self):
        # No login required — usable by a load balancer.
        self.assertEqual(self.client.get("/healthz").status_code, 200)


class RoleDispatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u", password="pw")
        self.staff = User.objects.create_user("s", password="pw", is_staff=True)

    def test_regular_user_lands_on_upload(self):
        self.client.login(username="u", password="pw")
        resp = self.client.get(reverse("home"))
        self.assertRedirects(resp, reverse("upload"))

    def test_staff_lands_on_dashboard(self):
        self.client.login(username="s", password="pw")
        resp = self.client.get(reverse("home"))
        self.assertRedirects(resp, reverse("staff_dashboard"))

    def test_staff_dashboard_requires_staff(self):
        self.client.login(username="u", password="pw")
        self.assertEqual(
            self.client.get(reverse("staff_dashboard")).status_code, 302
        )


class MyInspectionsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u", password="pw")
        self.line = TransmissionLine.objects.create(
            line_name="220KV Dashboard Line", voltage="220KV"
        )
        for i in range(30):
            Inspection.objects.create(
                transmission_line=self.line, location_id=f"T{i}",
                status=Inspection.SUBMITTED, uploaded_by=self.user,
            )
        self.client.login(username="u", password="pw")

    def test_pagination_caps_page_size(self):
        resp = self.client.get(reverse("my_inspections"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["inspections"]), 25)  # PAGE_SIZE
        self.assertTrue(resp.context["page_obj"].has_next())

    def test_second_page(self):
        resp = self.client.get(reverse("my_inspections"), {"page": 2})
        self.assertEqual(len(resp.context["inspections"]), 5)

    def test_filter_by_location(self):
        resp = self.client.get(reverse("my_inspections"), {"q": "T7"})
        # T7 only (T70-79 don't exist; we made T0..T29) -> exactly one match.
        self.assertEqual(resp.context["page_obj"].paginator.count, 1)

    def test_only_own_inspections(self):
        other = User.objects.create_user("other", password="pw")
        Inspection.objects.create(
            transmission_line=self.line, location_id="OTHER",
            status=Inspection.SUBMITTED, uploaded_by=other,
        )
        resp = self.client.get(reverse("my_inspections"), {"q": "OTHER"})
        self.assertEqual(resp.context["page_obj"].paginator.count, 0)
