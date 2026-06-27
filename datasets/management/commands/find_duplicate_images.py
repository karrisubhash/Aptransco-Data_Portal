from django.core.management.base import BaseCommand
from django.db.models import Count

from datasets.models import InspectionImage


class Command(BaseCommand):
    help = (
        "Report images that share identical content (same SHA-256 checksum). "
        "Run backfill_checksums first if legacy rows have no checksum."
    )

    def handle(self, *args, **options):
        duplicate_groups = (
            InspectionImage.objects
            .exclude(checksum="")
            .values("checksum")
            .annotate(n=Count("id"))
            .filter(n__gt=1)
            .order_by("-n")
        )

        groups = 0
        redundant = 0
        for row in duplicate_groups:
            groups += 1
            redundant += row["n"] - 1
            images = (
                InspectionImage.objects
                .filter(checksum=row["checksum"])
                .select_related("inspection", "subcategory")
                .order_by("id")
            )
            self.stdout.write(f"\n{row['checksum'][:12]}…  ({row['n']} copies)")
            for img in images:
                self.stdout.write(
                    f"  - image #{img.id}  inspection #{img.inspection_id}  "
                    f"{img.subcategory.name}  {img.image.name}"
                )

        if groups:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{groups} duplicate group(s), {redundant} redundant image(s)."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("No duplicate images found."))
