from collections import OrderedDict

from PIL import Image

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from masterdata.models import Category, SubCategory
from transmission.models import TransmissionLine

from .models import Inspection, InspectionImage
from .utils import sha256_of_file

staff_required = user_passes_test(lambda u: u.is_staff)


@login_required
def upload(request):
    categories = Category.objects.prefetch_related("subcategories").all()
    lines = TransmissionLine.objects.all()

    if request.method == "POST":
        line_id = request.POST.get("transmission_line")
        location_id = (request.POST.get("location_id") or "").strip()
        remarks = (request.POST.get("remarks") or "").strip()

        def render_form():
            return render(
                request,
                "datasets/upload.html",
                {
                    "categories": categories,
                    "lines": lines,
                    "selected_line": line_id or "",
                    "location_id": location_id,
                    "remarks": remarks,
                    "max_image_mb": settings.MAX_IMAGE_UPLOAD_SIZE // (1024 * 1024),
                },
            )

        # --- Hard validation: these block the whole submission. ---
        errors = []
        # line_id is "" when nothing is picked (and could be non-numeric junk);
        # guard the lookup so a bad value re-renders the form instead of 500ing.
        line = None
        if line_id:
            try:
                line = TransmissionLine.objects.filter(pk=line_id).first()
            except (ValueError, TypeError):
                line = None
        if not line:
            errors.append("Please select a transmission line.")
        if not location_id:
            errors.append("Location ID is required.")

        # Collect (subcategory, file) pairs from the dynamic, per-subcategory
        # file inputs. Field name is "subcategory_<id>" (see upload.html).
        pending = []
        for sub in SubCategory.objects.select_related("category").all():
            for f in request.FILES.getlist(f"subcategory_{sub.id}"):
                pending.append((sub, f))

        if not pending:
            errors.append("Please choose at least one image.")

        if errors:
            for e in errors:
                messages.error(request, e)
            return render_form()

        # --- Per-file processing: invalid / oversize / duplicate files are
        # skipped with a warning rather than failing the whole upload. ---
        warnings = []
        max_size = settings.MAX_IMAGE_UPLOAD_SIZE
        max_mb = max_size // (1024 * 1024)

        valid = []                 # [(subcategory, file, checksum)]
        seen_checksums = set()     # de-dupe within this single submission
        for sub, f in pending:
            if f.size > max_size:
                warnings.append(
                    f"“{f.name}” exceeds the {max_mb} MB limit and was skipped."
                )
                continue
            try:
                Image.open(f).verify()
                f.seek(0)
            except Exception:
                warnings.append(f"“{f.name}” is not a valid image and was skipped.")
                continue

            checksum = sha256_of_file(f)
            if checksum in seen_checksums:
                warnings.append(
                    f"“{f.name}” is a duplicate within this upload and was skipped."
                )
                continue
            seen_checksums.add(checksum)
            valid.append((sub, f, checksum))

        # De-dupe against images already stored in the dataset.
        if valid:
            already = set(
                InspectionImage.objects
                .filter(checksum__in=[c for _, _, c in valid])
                .values_list("checksum", flat=True)
            )
            if already:
                kept = []
                for sub, f, checksum in valid:
                    if checksum in already:
                        warnings.append(
                            f"“{f.name}” already exists in the dataset and was skipped."
                        )
                    else:
                        kept.append((sub, f, checksum))
                valid = kept

        if not valid:
            for w in warnings:
                messages.warning(request, w)
            messages.error(
                request, "No new images to save — every file was skipped."
            )
            return render_form()

        with transaction.atomic():
            inspection = Inspection.objects.create(
                transmission_line=line,
                location_id=location_id,
                remarks=remarks,
                status=Inspection.SUBMITTED,
                uploaded_by=request.user,
            )
            for sub, f, checksum in valid:
                InspectionImage.objects.create(
                    inspection=inspection,
                    subcategory=sub,
                    image=f,
                    checksum=checksum,
                )

        for w in warnings:
            messages.warning(request, w)
        skipped_note = f" ({len(warnings)} skipped)" if warnings else ""
        messages.success(
            request,
            f"Inspection #{inspection.id} submitted with "
            f"{len(valid)} image(s){skipped_note}.",
        )
        # Land the user on the inspection they just created so they immediately
        # see what they uploaded (grouped image preview).
        return redirect("inspection_detail", pk=inspection.id)

    return render(
        request,
        "datasets/upload.html",
        {
            "categories": categories,
            "lines": lines,
            "max_image_mb": settings.MAX_IMAGE_UPLOAD_SIZE // (1024 * 1024),
        },
    )


@login_required
def inspection_detail(request, pk):
    # Owners see their own inspections; staff can view any.
    qs = Inspection.objects.select_related("transmission_line", "uploaded_by")
    if not request.user.is_staff:
        qs = qs.filter(uploaded_by=request.user)
    inspection = get_object_or_404(qs, pk=pk)

    # Group images: category -> subcategory -> [images], preserving order.
    grouped = OrderedDict()
    for img in inspection.images.select_related("subcategory__category"):
        cat = img.subcategory.category.name
        sub = img.subcategory.name
        grouped.setdefault(cat, OrderedDict()).setdefault(sub, []).append(img)

    return render(
        request,
        "datasets/detail.html",
        {"inspection": inspection, "grouped": grouped},
    )


@login_required
@staff_required
def review_inspection(request, pk):
    inspection = get_object_or_404(Inspection, pk=pk)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "approve":
            inspection.status = Inspection.APPROVED
            # auto_now fields are only refreshed when listed in update_fields,
            # so include updated_at to record when the status changed.
            inspection.save(update_fields=["status", "updated_at"])
            messages.success(request, f"Inspection #{inspection.id} approved.")
        elif action == "reject":
            inspection.status = Inspection.REJECTED
            inspection.save(update_fields=["status", "updated_at"])
            messages.success(request, f"Inspection #{inspection.id} rejected.")

    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}
    ):
        return redirect(next_url)
    return redirect("staff_dashboard")
