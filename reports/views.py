import csv
import io
import zipfile

from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.text import slugify

from openpyxl import Workbook

from masterdata.models import Category
from datasets.models import Inspection, InspectionImage


staff_required = user_passes_test(lambda u: u.is_staff)

# Images that belong to an Approved inspection (the exportable dataset).
APPROVED = Q(inspection__status=Inspection.APPROVED)

METADATA_HEADERS = [
    "inspection_id", "transmission_line", "location_id", "category",
    "subcategory", "status", "uploaded_by", "created_at", "image_path",
]


def dataset_slug(name):
    """Lowercase, underscore-separated folder/class name for the AI dataset.

    "Cross Arms" -> "cross_arms", "Legs & Stub Angles" -> "legs_stub_angles".
    """
    return slugify(name).replace("-", "_")


def _metadata_rows():
    images = (
        InspectionImage.objects
        .select_related(
            "inspection__transmission_line",
            "subcategory__category",
            "inspection__uploaded_by",
        )
        .order_by("inspection_id", "id")
    )
    for img in images:
        insp = img.inspection
        yield [
            insp.id,
            insp.transmission_line.line_name,
            insp.location_id,
            img.subcategory.category.name,
            img.subcategory.name,
            insp.get_status_display(),
            insp.uploaded_by.get_username(),
            img.created_at.strftime("%Y-%m-%d %H:%M"),
            img.image.name,
        ]


@login_required
@staff_required
def index(request):
    categories = (
        Category.objects
        .annotate(approved_images=Count(
            "subcategories__images",
            filter=Q(subcategories__images__inspection__status=Inspection.APPROVED),
        ))
        .order_by("name")
    )
    return render(request, "reports/index.html", {
        "categories": categories,
        "total_images": InspectionImage.objects.count(),
        "approved_images": InspectionImage.objects.filter(APPROVED).count(),
    })


@login_required
@staff_required
def export_category_zip(request, category_id):
    category = get_object_or_404(Category, pk=category_id)

    images = (
        InspectionImage.objects
        .filter(APPROVED, subcategory__category=category)
        .select_related("subcategory")
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for img in images:
            sub_slug = dataset_slug(img.subcategory.name)
            basename = img.image.name.rsplit("/", 1)[-1]
            # Prefix with inspection id to avoid filename collisions across
            # inspections within the same subcategory folder.
            arcname = f"{sub_slug}/{img.inspection_id}_{basename}"
            with img.image.open("rb") as fh:
                zf.writestr(arcname, fh.read())

    buffer.seek(0)
    filename = f"{dataset_slug(category.name)}s.zip"  # Component -> components.zip
    response = HttpResponse(buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@staff_required
def export_metadata_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="dataset_metadata.csv"'
    writer = csv.writer(response)
    writer.writerow(METADATA_HEADERS)
    for row in _metadata_rows():
        writer.writerow(row)
    return response


@login_required
@staff_required
def export_metadata_xlsx(request):
    wb = Workbook()
    ws = wb.active
    ws.title = "Images"
    ws.append(METADATA_HEADERS)
    for row in _metadata_rows():
        ws.append(row)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
    response["Content-Disposition"] = 'attachment; filename="dataset_metadata.xlsx"'
    return response
