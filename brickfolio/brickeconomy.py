"""Import parsing for BrickEconomy collection CSV exports."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


REQUIRED_COLUMNS = {"Number", "Theme", "Year", "Paid", "Value", "Condition"}
NAME_COLUMNS = ("SetName", "Name")


@dataclass(frozen=True)
class BrickEconomySet:
    set_number: str
    title: str
    theme: str
    condition: str
    purchase_price: float
    estimated_value: float
    notes: str


@dataclass(frozen=True)
class ImportBatch:
    records: list[BrickEconomySet]
    skipped_rows: int


def read_collection_csv(path: str | Path) -> ImportBatch:
    """Read the documented BrickEconomy Sets export without changing the file."""
    with Path(path).open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        headers = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - headers
        if missing or not any(column in headers for column in NAME_COLUMNS):
            expected = "Number, Theme, Subtheme, Year, SetName, Retail, Paid, Value, Condition, Date, Notes"
            raise ValueError(f"This does not look like a BrickEconomy Sets export. Expected columns: {expected}")
        records: list[BrickEconomySet] = []
        skipped = 0
        for row in reader:
            set_number = (row.get("Number") or "").strip()
            title = next(((row.get(column) or "").strip() for column in NAME_COLUMNS if (row.get(column) or "").strip()), "")
            if not set_number or not title:
                skipped += 1
                continue
            records.append(
                BrickEconomySet(
                    set_number=set_number,
                    title=title,
                    theme=(row.get("Theme") or "").strip(),
                    condition=map_condition(row.get("Condition") or ""),
                    purchase_price=parse_amount(row.get("Paid") or ""),
                    estimated_value=parse_amount(row.get("Value") or ""),
                    notes=build_notes(row),
                )
            )
    return ImportBatch(records=records, skipped_rows=skipped)


def parse_amount(value: str) -> float:
    clean = value.strip().replace("$", "").replace(",", "")
    try:
        return float(clean) if clean else 0.0
    except ValueError:
        return 0.0


def map_condition(value: str) -> str:
    key = value.strip().casefold().replace(" ", "")
    mapping = {
        "new": "New",
        "sealed": "Sealed",
        "usedcomplete": "Complete",
        "usedasnew": "Used",
        "usedincomplete": "Incomplete",
        "incomplete": "Incomplete",
        "used": "Used",
    }
    return mapping.get(key, "Used")


def build_notes(row: dict[str, str]) -> str:
    """Carry over only notes the user actually had in BrickEconomy."""
    original_notes = (row.get("Notes") or "").strip()
    return "" if original_notes == "Imported from BrickEconomy" else original_notes
