import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brickfolio.database import Database


class AccessoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.exports = patch("brickfolio.database.EXPORTS_PATH", self.root / "exports")
        self.exports.start()
        self.db = Database(self.root / "ledger.db")
        self.values = {"set_number": "10300-1", "title": "Time Machine", "theme": "Icons",
                       "condition": "Good", "notes": "Booklet 2", "location": "Shelf A"}

    def tearDown(self):
        self.db.close()
        self.exports.stop()
        self.temp.cleanup()

    def add_set(self, **extra):
        return self.db.add_set({**self.values, "condition": "Complete", "purchase_price": 100,
                                "estimated_value": 150, "status": "Keeping", **extra})

    def test_independent_inventories_persist_and_leave_set_values_alone(self):
        set_id = self.add_set()
        before = self.db.dashboard_metrics()
        box = self.db.save_accessory("Box", self.values)
        manual = self.db.save_accessory("Instructions", self.values)
        self.assertEqual(len(self.db.accessories("Box")), 1)
        self.assertEqual(len(self.db.accessories("Instructions")), 1)
        self.db.save_accessory("Box", {**self.values, "notes": "Folded flat"}, box)
        self.db.delete_accessory(manual)
        self.assertEqual(self.db.get_set(set_id)["notes"], "Booklet 2")
        self.assertEqual(self.db.dashboard_metrics(), before)
        self.db.close()
        self.db = Database(self.root / "ledger.db")
        self.assertEqual(self.db.get_accessory(box)["notes"], "Folded flat")
        self.assertEqual(self.db.accessories("Instructions"), [])

    def test_checked_import_is_repeatable_preserves_edits_and_survives_set_removal(self):
        set_id = self.add_set(has_box=1, has_instructions=1, status="Sold")
        self.add_set(set_number="999-1", has_box=0, has_instructions=0)
        self.assertEqual(self.db.import_checked_accessories("Box"), 1)
        self.assertEqual(self.db.import_checked_accessories("Instructions"), 1)
        box = self.db.accessories("Box")[0]
        self.assertEqual(box["notes"], "")
        self.assertEqual(box["condition"], "Good")
        self.db.save_accessory("Box", {**dict(box), "notes": "My own notes"}, box["id"])
        self.assertEqual(self.db.import_checked_accessories("Box"), 0)
        self.assertEqual(self.db.get_accessory(box["id"])["notes"], "My own notes")
        self.db.delete_set(set_id)
        self.assertEqual(len(self.db.accessories("Box")), 1)
        self.assertIsNone(self.db.get_accessory(box["id"])["source_collection_id"])
        self.assertEqual(self.db.connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_validation_does_not_create_records(self):
        for values in ({**self.values, "title": " "}, {**self.values, "set_number": ""}):
            with self.assertRaises(ValueError):
                self.db.save_accessory("Box", values)
        with self.assertRaises(ValueError):
            self.db.save_accessory("Other", self.values)
        with self.assertRaises(ValueError):
            self.db.save_accessory("Box", self.values, 9999)
        self.assertEqual(self.db.accessories("Box"), [])

    def test_search_sort_and_csv_including_empty_headers(self):
        for title, theme in (("Zebra", "City"), ("Alpha", "City"), ("Beta", "Space")):
            self.db.save_accessory("Instructions", {**self.values, "title": title, "theme": theme})
        self.assertEqual([row["title"] for row in self.db.accessories("Instructions", sort="Theme A-Z")],
                         ["Alpha", "Zebra", "Beta"])
        self.assertEqual(len(self.db.accessories("Instructions", "shelf a")), 3)
        path = self.root / "out.csv"
        self.assertEqual(self.db.export_accessories(path, "Instructions", "City", "Theme A-Z"), 2)
        with path.open(encoding="utf-8-sig", newline="") as source:
            self.assertEqual([row["Set Name"] for row in csv.DictReader(source)], ["Alpha", "Zebra"])
        self.assertEqual(self.db.export_accessories(path, "Box"), 0)
        self.assertIn("Storage Location", path.read_text(encoding="utf-8-sig"))

    def test_schema_upgrade_keeps_existing_rows_exactly(self):
        self.add_set(has_box=1)
        original = [tuple(row) for row in self.db.connection.execute("SELECT * FROM collection")]
        self.db.connection.execute("DROP TABLE accessories")
        self.db.connection.commit()
        self.db.close()
        self.db = Database(self.root / "ledger.db")
        self.assertEqual([tuple(row) for row in self.db.connection.execute("SELECT * FROM collection")], original)
        self.assertEqual(self.db.accessories("Box"), [])
        self.assertEqual(self.db.connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")


if __name__ == "__main__":
    unittest.main()
