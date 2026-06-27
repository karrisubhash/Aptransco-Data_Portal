from django.db import models
from django.contrib.auth import get_user_model

from transmission.models import TransmissionLine
from masterdata.models import SubCategory

from .utils import upload_path

User = get_user_model()


class Inspection(models.Model):

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (SUBMITTED, "Submitted"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    ]

    transmission_line = models.ForeignKey(
        TransmissionLine,
        on_delete=models.CASCADE,
        related_name="inspections"
    )

    location_id = models.CharField(max_length=100)

    remarks = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=DRAFT,
    )

    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="inspections"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # "My Inspections" filters by owner (newest first); the review queue
            # and stats filter by status.
            models.Index(fields=["uploaded_by", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.transmission_line} - {self.location_id}"


class InspectionImage(models.Model):

    inspection = models.ForeignKey(
        Inspection,
        on_delete=models.CASCADE,
        related_name="images"
    )

    # No `category` column on purpose: it is reached via subcategory.category,
    # keeping the schema normalized (one source of truth).
    subcategory = models.ForeignKey(
        SubCategory,
        on_delete=models.PROTECT,
        related_name="images"
    )

    # max_length defaults to 100; the upload_path() folders + filename easily
    # exceed that, so widen the column to the usual filesystem/DB limit.
    image = models.ImageField(upload_to=upload_path, max_length=255)

    # SHA-256 of the file content, used to deduplicate uploads (§ dedup). Indexed
    # so "has this exact image been uploaded before?" is a fast lookup. Blank for
    # legacy rows until `manage.py backfill_checksums` is run.
    checksum = models.CharField(max_length=64, blank=True, default="", db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    @property
    def category(self):
        """Derived from the subcategory — not stored on this row."""
        return self.subcategory.category

    def __str__(self):
        return f"{self.inspection.location_id} - {self.subcategory.name}"
