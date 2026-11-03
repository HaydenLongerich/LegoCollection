"""Small, offline lookup layer for the included Rebrickable-style CSV files."""

from __future__ import annotations

import csv
import gzip
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SETS_FILE = ROOT / "Sets" / "sets.csv.gz"
THEMES_FILE = ROOT / "Sets" / "themes.csv.gz"

# Rebrickable's catalogue uses some historic and sub-theme labels that are
# useful for archival detail but noisy in a personal collection view.
THEME_ALIASES = {
    "cuusoo": "Ideas",
    "lego ideas": "Ideas",
    "lego ideas and cuusoo": "Ideas",
    "ultimate collector series": "Star Wars",
}

SPEED_CHAMPIONS_VARIANTS = ("6-stud", "Polybags", "8-stud")
SPEED_CHAMPIONS_EXCLUDED = {
    "5004550-1",  # collection pack
    "5004559-1",  # collection pack
    "66647-1",    # bundle
    "66802-1",    # collector's pack
    "75995-1",    # promotional team gift, not a retail set
    "TRUPODIUM-1",  # podium accessory
}
SPEED_CHAMPIONS_POLYBAGS = {
    "30342-1", "30343-1", "30434-1", "30657-1", "30683-1", "30709-1", "30734-1",
}

SPEED_CHAMPIONS_BRANDS = (
    (("mercedes-amg", "mercedes amg", "mercedes pit"), "Mercedes-AMG"),
    (("aston martin",), "Aston Martin"),
    (("red bull",), "Red Bull Racing"),
    (("visa cash app",), "RB"),
    (("scuderia ferrari", "laferrari", "f14 t", "458 italia", "ferrari"), "Ferrari"),
    (("mclaren",), "McLaren"),
    (("lamborghini",), "Lamborghini"),
    (("koenigsegg",), "Koenigsegg"),
    (("chevrolet",), "Chevrolet"),
    (("corvette",), "Chevrolet"),
    (("mopar", "dodge"), "Dodge"),
    (("ford", "hoonicorn"), "Ford"),
    (("porsche",), "Porsche"),
    (("nissan",), "Nissan"),
    (("toyota",), "Toyota"),
    (("audi",), "Audi"),
    (("bmw",), "BMW"),
    (("jaguar",), "Jaguar"),
    (("mini",), "MINI"),
    (("bugatti",), "Bugatti"),
    (("pagani",), "Pagani"),
    (("lotus",), "Lotus"),
    (("alpine",), "Alpine"),
    (("sauber",), "Sauber"),
    (("haas",), "Haas"),
    (("williams",), "Williams"),
    (("apxgp",), "APXGP"),
    (("f1 academy",), "F1 Academy"),
    (("lightning mcqueen",), "Disney / Pixar"),
    (("time machine",), "DeLorean"),
)


def normalise_theme(theme: str) -> str:
    """Return the concise collector-facing theme name."""
    clean = theme.strip()
    return THEME_ALIASES.get(clean.casefold(), clean)


@dataclass(frozen=True)
class CatalogSet:
    set_number: str
    name: str
    year: str
    theme: str
    parts: str
    image_url: str = ""


def speed_champions_variant(record: CatalogSet) -> str | None:
    """Classify only the car sets counted by this collector."""
    set_number = record.set_number.upper()
    if record.theme.casefold() != "speed champions" or set_number in SPEED_CHAMPIONS_EXCLUDED:
        return None
    if set_number in SPEED_CHAMPIONS_POLYBAGS:
        return "Polybags"
    try:
        year = int(record.year)
        parts = int(record.parts)
    except ValueError:
        return None
    if parts <= 0:
        return None
    if year <= 2019:
        return "6-stud"
    if set_number.startswith(("768", "769", "772")):
        return "8-stud"
    return None


def speed_champions_brand(name: str) -> str:
    """Return a collector-friendly marque for Speed Champions sorting."""
    clean = name.strip()
    lowered = clean.casefold()
    for aliases, brand in SPEED_CHAMPIONS_BRANDS:
        if any(alias in lowered for alias in aliases):
            return brand
    return clean


class OfflineCatalog:
    """Lazy, in-memory index so looking up a set never needs a network call."""

    def __init__(self) -> None:
        self._index: dict[str, CatalogSet] | None = None
        self._records: list[CatalogSet] | None = None

    def lookup(self, set_number: str) -> CatalogSet | None:
        self._ensure_loaded()
        clean = set_number.strip().upper()
        if clean and "-" not in clean:
            clean = f"{clean}-1"
        return self._index.get(clean) if self._index else None

    def search(self, query: str = "", theme: str = "All themes", limit: int = 250) -> list[CatalogSet]:
        """Find sets by number, name, or theme without mutating the source data."""
        self._ensure_loaded()
        query = query.strip().casefold()
        records = self._records or []
        results = [
            record for record in records
            if (theme == "All themes" or record.theme == theme)
            and (not query or query in record.set_number.casefold() or query in record.name.casefold() or query in record.theme.casefold())
        ]
        return results[:limit]

    def themes(self) -> list[str]:
        self._ensure_loaded()
        return sorted({record.theme for record in self._records or [] if record.theme})

    @staticmethod
    def available() -> bool:
        return SETS_FILE.exists() and THEMES_FILE.exists()

    def _ensure_loaded(self) -> None:
        if self._index is not None:
            return
        self._index, self._records = self._load()

    def _load(self) -> tuple[dict[str, CatalogSet], list[CatalogSet]]:
        if not self.available():
            return {}, []
        with gzip.open(THEMES_FILE, "rt", encoding="utf-8-sig", newline="") as source:
            themes = {row["id"]: row["name"] for row in csv.DictReader(source)}
        with gzip.open(SETS_FILE, "rt", encoding="utf-8-sig", newline="") as source:
            records = [
                CatalogSet(
                    set_number=row["set_num"], name=row["name"], year=row["year"],
                    theme=normalise_theme(themes.get(row["theme_id"], "")), parts=row["num_parts"],
                    image_url=row.get("img_url", "").strip(),
                )
                for row in csv.DictReader(source)
            ]
        records.sort(key=lambda record: (record.name.casefold(), record.set_number.casefold()))
        return {record.set_number.upper(): record for record in records}, records
