from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class SignupTests(TestCase):
    def test_signup_page_renders(self):
        self.assertEqual(self.client.get(reverse("signup")).status_code, 200)

    def test_signup_creates_regular_user_and_logs_in(self):
        resp = self.client.post(reverse("signup"), {
            "username": "newinspector",
            "password1": "Str0ngP@ssw0rd!",
            "password2": "Str0ngP@ssw0rd!",
        })
        self.assertEqual(resp.status_code, 302)  # -> home dispatcher
        user = User.objects.get(username="newinspector")
        self.assertFalse(user.is_staff)  # self-registration is non-staff
        self.assertIn("_auth_user_id", self.client.session)  # logged in

    def test_password_mismatch_rejected(self):
        resp = self.client.post(reverse("signup"), {
            "username": "mismatch",
            "password1": "Str0ngP@ssw0rd!",
            "password2": "different",
        })
        self.assertEqual(resp.status_code, 200)  # re-rendered with errors
        self.assertFalse(User.objects.filter(username="mismatch").exists())

    def test_authenticated_user_redirected_away(self):
        User.objects.create_user("existing", password="pw")
        self.client.login(username="existing", password="pw")
        resp = self.client.get(reverse("signup"))
        self.assertEqual(resp.status_code, 302)
