import pandas as pd

from django.core.management.base import BaseCommand
from transmission.models import TransmissionLine


def normalize_voltage(value):
    """Normalize voltage strings to a canonical form.

    Collapses internal whitespace and uppercases the unit so that
    '132KV', '132kV' and '132 Kv' all become '132KV'.
    """
    return "".join(str(value).split()).upper()


class Command(BaseCommand):
    help = "Import transmission lines from CSV"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str)

    def handle(self, *args, **kwargs):

        csv_file = kwargs["csv_file"]

        df = pd.read_csv(csv_file)

        imported = 0
        skipped = 0

        for _, row in df.iterrows():

            line_name = str(row["lin_nm"]).strip()
            voltage = normalize_voltage(row["volt"])

            if not line_name:
                continue

            obj, created = TransmissionLine.objects.get_or_create(
                line_name=line_name,
                defaults={
                    "voltage": voltage
                }
            )

            if created:
                imported += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS("Import Completed"))
        self.stdout.write(f"Imported : {imported}")
        self.stdout.write(f"Skipped  : {skipped}")