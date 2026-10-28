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
                )
                for row in csv.DictReader(source)
            ]
        records.sort(key=lambda record: (record.name.casefold(), record.set_number.casefold()))
        return {record.set_number.upper(): record for record in records}, records
