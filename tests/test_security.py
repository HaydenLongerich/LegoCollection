import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from brickfolio.brickeconomy import parse_amount, read_collection_csv
from brickfolio.database import Database
from brickfolio.lego_spreadsheet import _read_xml, _validate_workbook


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.exports = patch("brickfolio.database.EXPORTS_PATH", self.root / "exports")
        self.exports.start()
        self.db = Database(self.root / "ledger.db")

    def tearDown(self):
        self.db.close()
        self.exports.stop()
        self.temp.cleanup()

    def test_database_security_pragmas_are_enabled(self):
        self.assertEqual(self.db.connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        self.assertEqual(self.db.connection.execute("PRAGMA trusted_schema").fetchone()[0], 0)
        self.assertEqual(self.db.connection.execute("PRAGMA secure_delete").fetchone()[0], 1)
        self.assertEqual(self.db.connection.execute("PRAGMA busy_timeout").fetchone()[0], 5000)

    def test_exports_neutralize_spreadsheet_formulas(self):
        self.db.add_set({
            "set_number": "1000-1", "title": "=HYPERLINK(\"https://example.invalid\")",
            "theme": "City", "condition": "Used", "purchase_price": 1,
            "estimated_value": 2, "status": "Keeping", "notes": "  +SUM(1,1)",
        })
        destination = self.root / "collection.csv"
        self.db.export_collection(destination)
        with destination.open(encoding="utf-8-sig", newline="") as source:
            row = next(csv.DictReader(source))
        self.assertTrue(row["Set Name"].startswith("\t="))
        self.assertTrue(row["Notes"].startswith("\t+"))

    def test_csv_import_rejects_oversized_files_and_nonfinite_amounts(self):
        destination = self.root / "collection.csv"
        destination.write_text("Number,Theme,Year,Paid,Value,Condition,SetName\n", encoding="utf-8")
        with patch("brickfolio.brickeconomy.MAX_IMPORT_BYTES", 1):
            with self.assertRaisesRegex(ValueError, "too large"):
                read_collection_csv(destination)
        self.assertEqual(parse_amount("NaN"), 0.0)
        self.assertEqual(parse_amount("Infinity"), 0.0)

    def test_workbook_guard_rejects_excessive_expansion(self):
        destination = self.root / "unsafe.xlsx"
        with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
            archive.writestr("xl/worksheets/sheet1.xml", "A" * 1_100_000)
        with ZipFile(destination) as workbook, patch(
            "brickfolio.lego_spreadsheet.MAX_COMPRESSION_RATIO", 10
        ):
            with self.assertRaisesRegex(ValueError, "compression ratio"):
                _validate_workbook(workbook)

    def test_workbook_xml_rejects_entity_declarations(self):
        destination = self.root / "entity.xlsx"
        with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
            archive.writestr("xl/workbook.xml", '<!DOCTYPE x [<!ENTITY y "value">]><x>&y;</x>')
        with ZipFile(destination) as workbook:
            with self.assertRaisesRegex(ValueError, "entities"):
                _read_xml(workbook, "xl/workbook.xml")


if __name__ == "__main__":
    unittest.main()
