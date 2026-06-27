from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import urlencode

from datasets.models import Inspection, InspectionImage

staff_required = user_passes_test(lambda u: u.is_staff)

PAGE_SIZE = 25


def healthz(request):
    """Liveness/readiness probe for deployment — verifies DB connectivity.

    Public (no auth) so a load balancer or uptime monitor can hit it; returns
    503 if the database is unreachable so traffic isn't routed to a broken node.
    """
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False
    return JsonResponse(
        {"status": "ok" if db_ok else "error", "database": db_ok},
        status=200 if db_ok else 503,
    )


@login_required
def home(request):
    """Role-based landing. Regular users go to the upload page; staff get the
    separate admin dashboard — the two areas are not mixed."""
    if request.user.is_staff:
        return redirect("staff_dashboard")
    return redirect("upload")


@login_required
def my_inspections(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()

    inspections = (
        Inspection.objects
        .filter(uploaded_by=request.user)
        .select_related("transmission_line")
        .annotate(image_count=Count("images"))
    )

    if q:
        inspections = inspections.filter(
            Q(location_id__icontains=q)
            | Q(transmission_line__line_name__icontains=q)
        )
    if status:
        inspections = inspections.filter(status=status)

    # .annotate(Count(...)) drops the model's default Meta ordering, so order
    # explicitly before paginating to keep pages stable.
    inspections = inspections.order_by("-created_at")
    page_obj = Paginator(inspections, PAGE_SIZE).get_page(request.GET.get("page"))

    # Query string (minus page) so pagination links keep the active filters.
    params = {k: v for k, v in (("q", q), ("status", status)) if v}
    querystring = urlencode(params)

    return render(request, "dashboard/my_inspections.html", {
        "inspections": page_obj,
        "page_obj": page_obj,
        "querystring": querystring,
        "q": q,
        "status": status,
        "status_choices": Inspection.STATUS_CHOICES,
    })


@login_required
@staff_required
def staff_dashboard(request):
    status_counts = dict(
        Inspection.objects.values_list("status").annotate(n=Count("id"))
    )
    by_status = [
        (label, status_counts.get(value, 0))
        for value, label in Inspection.STATUS_CHOICES
    ]

    by_category = (
        InspectionImage.objects
        .values("subcategory__category__name")
        .annotate(n=Count("id"))
        .order_by("subcategory__category__name")
    )
    top_lines = (
        Inspection.objects
        .values("transmission_line__line_name")
        .annotate(n=Count("id"))
        .order_by("-n")[:10]
    )
    by_user = (
        Inspection.objects
        .values("uploaded_by__username")
        .annotate(n=Count("id"))
        .order_by("-n")[:10]
    )
    pending_qs = (
        Inspection.objects
        .filter(status=Inspection.SUBMITTED)
        .select_related("transmission_line", "uploaded_by")
        .annotate(image_count=Count("images"))
        .order_by("-created_at")
    )
    pending = Paginator(pending_qs, PAGE_SIZE).get_page(request.GET.get("page"))

    return render(request, "dashboard/staff.html", {
        "total_inspections": Inspection.objects.count(),
        "total_images": InspectionImage.objects.count(),
        "by_status": by_status,
        "by_category": by_category,
        "top_lines": top_lines,
        "by_user": by_user,
        "pending": pending,
        "page_obj": pending,
    })
