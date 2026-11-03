import tempfile
import unittest
from pathlib import Path

from brickfolio.app import MyCollectionPage
from brickfolio.catalog import CatalogSet, OfflineCatalog, speed_champions_brand, speed_champions_variant
from PIL import Image, ImageDraw

from brickfolio.images import SetImageCache, _safe_name, _transparent_thumbnail


class CatalogImageTests(unittest.TestCase):
    def test_catalog_exposes_rebrickable_image_urls(self):
        record = OfflineCatalog().lookup("75894-1")
        self.assertIsNotNone(record)
        self.assertTrue(record.image_url.startswith("https://cdn.rebrickable.com/"))

    def test_image_cache_rejects_unapproved_hosts(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "set.img"
            self.assertFalse(SetImageCache._download("https://example.invalid/set.jpg", destination))
            self.assertFalse(destination.exists())

    def test_cache_file_names_cannot_escape_the_cache(self):
        self.assertEqual(_safe_name("../76901-1"), ".._76901-1")
        self.assertNotIn("/", _safe_name("../../private"))
        self.assertNotIn("\\", _safe_name("..\\private"))

    def test_white_edge_background_becomes_transparent_png(self):
        source = Image.new("RGB", (100, 80), "white")
        ImageDraw.Draw(source).rectangle((25, 20, 75, 65), fill="#d2ff00")
        thumbnail = _transparent_thumbnail(source)
        self.assertEqual(thumbnail.mode, "RGBA")
        self.assertEqual(thumbnail.size, (250, 155))
        self.assertEqual(thumbnail.getpixel((0, 0))[3], 0)
        self.assertGreater(max(pixel[3] for pixel in thumbnail.getdata()), 240)

    def test_owned_speed_champion_disappears_from_missing_sets(self):
        catalogue = [
            CatalogSet("A-1", "Alpha", "2025", "Speed Champions", "100"),
            CatalogSet("B-1", "Beta", "2026", "Speed Champions", "200"),
        ]
        rows = [{"set_number": "A-1"}]
        self.assertEqual(
            [record.set_number for record in MyCollectionPage._missing_speed_champions(catalogue, rows)],
            ["B-1"],
        )
        rows.append({"set_number": "B-1"})
        self.assertEqual(MyCollectionPage._missing_speed_champions(catalogue, rows), [])

    def test_speed_champions_variants_exclude_non_set_packs(self):
        catalog = OfflineCatalog()
        self.assertEqual(speed_champions_variant(catalog.lookup("75899-1")), "6-stud")
        self.assertEqual(speed_champions_variant(catalog.lookup("30342-1")), "Polybags")
        self.assertEqual(speed_champions_variant(catalog.lookup("76895-1")), "8-stud")
        for set_number in ("5004550-1", "5004559-1", "66647-1", "66802-1", "75995-1", "TRUPODIUM-1"):
            self.assertIsNone(speed_champions_variant(catalog.lookup(set_number)))

    def test_speed_champions_brand_sorting_normalises_marques(self):
        self.assertEqual(speed_champions_brand("MERCEDES AMG PETRONAS Formula One Team"), "Mercedes-AMG")
        self.assertEqual(speed_champions_brand("LaFerrari"), "Ferrari")
        self.assertEqual(speed_champions_brand("Ken Block's '65 Ford Mustang Hoonicorn V1"), "Ford")
        self.assertEqual(speed_champions_brand("Oracle Red Bull Racing RB20 F1 Race Car"), "Red Bull Racing")

    def test_collection_columns_expand_across_fullscreen_widths(self):
        self.assertEqual(MyCollectionPage._desired_columns(600), 2)
        self.assertEqual(MyCollectionPage._desired_columns(1440), 5)
        self.assertEqual(MyCollectionPage._desired_columns(2560), 7)


if __name__ == "__main__":
    unittest.main()
