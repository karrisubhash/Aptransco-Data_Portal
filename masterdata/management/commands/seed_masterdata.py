from django.core.management.base import BaseCommand

from masterdata.models import Category, SubCategory


# Initial taxonomy. Admins can add/edit more later via the admin — this command
# is idempotent (get_or_create) and safe to re-run.
TAXONOMY = {
    "Component": [
        "Peak",
        "Cage",
        "Cross Arms",
        "Body",
        "Legs & Stub Angles",
    ],
    "Defect": [
        "Vegetation",
        "Broken Insulator",
        "Corrosion",
        "Missing Hardware",
        "Conductor Damage",
        "Foreign Objects",
    ],
}


class Command(BaseCommand):
    help = "Seed the initial Category / SubCategory taxonomy (idempotent)."

    def handle(self, *args, **options):
        cats_created = 0
        subs_created = 0

        for category_name, subcategories in TAXONOMY.items():
            category, created = Category.objects.get_or_create(name=category_name)
            if created:
                cats_created += 1

            for sub_name in subcategories:
                _, sub_created = SubCategory.objects.get_or_create(
                    category=category,
                    name=sub_name,
                )
                if sub_created:
                    subs_created += 1

        self.stdout.write(self.style.SUCCESS("Master data seeded"))
        self.stdout.write(f"Categories created    : {cats_created}")
        self.stdout.write(f"Subcategories created : {subs_created}")
