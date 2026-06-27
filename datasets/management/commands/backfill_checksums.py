import hashlib

from django.core.management.base import BaseCommand

from datasets.models import InspectionImage


class Command(BaseCommand):
    help = (
        "Compute and store SHA-256 checksums for stored images. By default only "
        "images that don't yet have one are processed (safe to re-run)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Recompute checksums for every image, not just missing ones.",
        )

    def handle(self, *args, **options):
        qs = InspectionImage.objects.all()
        if not options["all"]:
            qs = qs.filter(checksum="")

        total = qs.count()
        updated = 0
        missing = 0

        for img in qs.iterator():
            try:
                digest = hashlib.sha256()
                with img.image.open("rb") as fh:
                    for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                        digest.update(chunk)
            except FileNotFoundError:
                missing += 1
                self.stderr.write(
                    f"Missing file for image #{img.id}: {img.image.name}"
                )
                continue

            img.checksum = digest.hexdigest()
            img.save(update_fields=["checksum"])
            updated += 1

        self.stdout.write(
            self.style.SUCCESS(f"Backfilled {updated}/{total} checksum(s).")
        )
        if missing:
            self.stdout.write(
                self.style.WARNING(f"{missing} image file(s) not found on disk.")
            )
