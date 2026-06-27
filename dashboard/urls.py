from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    # Note: the /healthz probe route is registered once, at the top of the root
    # URLconf (config/urls.py), so it is never shadowed by an app include.
    path("my-inspections/", views.my_inspections, name="my_inspections"),
    path("staff/", views.staff_dashboard, name="staff_dashboard"),
]
