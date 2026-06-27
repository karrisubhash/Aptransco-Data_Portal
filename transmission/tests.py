import os
import tempfile

from django.core.management import call_command
from django.test import TestCase

from .models import TransmissionLine
from .management.commands.import_transmission_data import normalize_voltage


class NormalizeVoltageTests(TestCase):
    def test_uppercases_unit(self):
        self.assertEqual(normalize_voltage("132kV"), "132KV")

    def test_collapses_whitespace(self):
        self.assertEqual(normalize_voltage("132 KV"), "132KV")
        self.assertEqual(normalize_voltage(" 220 kv "), "220KV")

    def test_already_canonical(self):
        self.assertEqual(normalize_voltage("400KV"), "400KV")


class ImportCommandTests(TestCase):
    def _write_csv(self, rows):
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("lin_nm,volt\n")
            for name, volt in rows:
                fh.write(f"{name},{volt}\n")
        self.addCleanup(os.remove, path)
        return path

    def test_import_creates_normalized_lines(self):
        path = self._write_csv([
            ("132KV Vemagiri-Rajahmundry", "132kV"),
            ("220KV Some Line", "220 KV"),
        ])
        call_command("import_transmission_data", path)
        self.assertEqual(TransmissionLine.objects.count(), 2)
        self.assertEqual(
            TransmissionLine.objects.get(line_name="132KV Vemagiri-Rajahmundry").voltage,
            "132KV",
        )

    def test_import_is_idempotent_on_unique_name(self):
        path = self._write_csv([("132KV Dup Line", "132KV")])
        call_command("import_transmission_data", path)
        call_command("import_transmission_data", path)  # re-run
        self.assertEqual(
            TransmissionLine.objects.filter(line_name="132KV Dup Line").count(), 1
        )
