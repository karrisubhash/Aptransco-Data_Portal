from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from dashboard.views import healthz

# Brand the Django admin to match the portal (header, browser title, index heading).
admin.site.site_header = "APTRANSCO Administration"
admin.site.site_title = "APTRANSCO Admin"
admin.site.index_title = "Dataset Portal Administration"

urlpatterns = [
    # Liveness/readiness probe (no auth) — kept at the top so a load balancer
    # hitting /healthz is never shadowed by the catch-all app includes below.
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("dashboard.urls")),
    path("", include("datasets.urls")),
    path("reports/", include("reports.urls")),
]

# Serve uploaded media during development.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
