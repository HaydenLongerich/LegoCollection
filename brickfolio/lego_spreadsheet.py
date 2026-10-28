"""Import support for the owner's Excel LEGO sales spreadsheet."""

from __future__ import annotations

import math
import posixpath
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree as ET


NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

REQUIRED_HEADERS = {
    "set name": "title",
    "set number": "set_number",
    "retired": "retired",
    "purchase price (cad)": "purchase_price",
    "condition (new/used)": "condition",
    "selling price (cad)": "sold_price",
    "net profit (cad)": "net_profit",
    "notes": "notes",
}

MAX_WORKBOOK_BYTES = 50 * 1024 * 1024
MAX_XML_MEMBER_BYTES = 20 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 500
MAX_COMPRESSION_RATIO = 1_000
MAX_SPREADSHEET_ROWS = 100_000
MAX_SPREADSHEET_COLUMNS = 256


@dataclass(frozen=True)
class SpreadsheetSale:
    title: str
    set_number: str
    retired: str
    purchase_price: float
    condition: str
    sold_price: float
    net_profit: float
    notes: str


@dataclass(frozen=True)
class SpreadsheetSalesBatch:
    records: list[SpreadsheetSale]
    skipped_rows: int


def read_main_sales_spreadsheet(path: str | Path) -> SpreadsheetSalesBatch:
    """Read the MAIN sheet from the owner's xlsx sales spreadsheet."""
    path = Path(path)
    if not path.is_file():
        raise ValueError("The selected spreadsheet does not exist.")
    if path.stat().st_size > MAX_WORKBOOK_BYTES:
        raise ValueError("This spreadsheet is too large to import safely (50 MB maximum).")
    try:
        with ZipFile(path) as workbook:
            _validate_workbook(workbook)
            shared_strings = _read_shared_strings(workbook)
            sheet_path = _find_sheet_path(workbook, "main")
            if sheet_path is None:
                raise ValueError("No sheet named MAIN was found in this workbook.")

            root = _read_xml(workbook, sheet_path)
            rows = root.findall(".//main:sheetData/main:row", NS)
            if not rows:
                raise ValueError("The MAIN sheet is empty.")
            if len(rows) > MAX_SPREADSHEET_ROWS:
                raise ValueError("This spreadsheet has too many rows to import safely (100,000 maximum).")

            header_values = _row_values(rows[0], shared_strings)
            header_map = _header_map(header_values)
            missing = [label for label in REQUIRED_HEADERS if label not in header_map]
            if missing:
                expected = ", ".join(REQUIRED_HEADERS)
                raise ValueError(f"The MAIN sheet is missing columns. Expected: {expected}")

            records: list[SpreadsheetSale] = []
            skipped = 0
            for row in rows[1:]:
                values = _row_values(row, shared_strings)
                record = _record_from_values(values, header_map)
                if record is None:
                    skipped += 1
                else:
                    records.append(record)
            return SpreadsheetSalesBatch(records=records, skipped_rows=skipped)
    except BadZipFile as exc:
        raise ValueError("This is not a valid .xlsx spreadsheet.") from exc


def _validate_workbook(workbook: ZipFile) -> None:
    members = workbook.infolist()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise ValueError("This spreadsheet contains too many files to import safely.")
    if sum(member.file_size for member in members) > MAX_UNCOMPRESSED_BYTES:
        raise ValueError("This spreadsheet expands beyond the safe import limit.")
    for member in members:
        if member.flag_bits & 0x1:
            raise ValueError("Encrypted spreadsheets cannot be imported.")
        if member.file_size > MAX_XML_MEMBER_BYTES and member.filename.lower().endswith(".xml"):
            raise ValueError("This spreadsheet contains an XML part that is too large to import safely.")
        if member.file_size > 1_000_000 and member.file_size / max(member.compress_size, 1) > MAX_COMPRESSION_RATIO:
            raise ValueError("This spreadsheet has an unsafe compression ratio.")


def _read_xml(workbook: ZipFile, member_name: str) -> ET.Element:
    try:
        member = workbook.getinfo(member_name)
    except KeyError as exc:
        raise ValueError("This spreadsheet is missing a required internal file.") from exc
    if member.file_size > MAX_XML_MEMBER_BYTES:
        raise ValueError("This spreadsheet contains an XML part that is too large to import safely.")
    content = workbook.read(member)
    lowered = content.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise ValueError("Spreadsheet XML declarations and entities are not allowed.")
    try:
        return ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError("This spreadsheet contains invalid XML.") from exc


def _read_shared_strings(workbook: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = _read_xml(workbook, "xl/sharedStrings.xml")
    return [_node_text(item) for item in root.findall("main:si", NS)]


def _find_sheet_path(workbook: ZipFile, sheet_name: str) -> str | None:
    workbook_root = _read_xml(workbook, "xl/workbook.xml")
    rels_root = _read_xml(workbook, "xl/_rels/workbook.xml.rels")
    relationships = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels_root
        if "Id" in rel.attrib and "Target" in rel.attrib
    }
    rel_key = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    for sheet in workbook_root.findall(".//main:sheet", NS):
        if sheet.attrib.get("name", "").strip().casefold() != sheet_name:
            continue
        relationship_id = sheet.attrib.get(rel_key, "")
        target = relationships.get(relationship_id, "").replace("\\", "/").lstrip("/")
        normalized = posixpath.normpath(target if target.startswith("xl/") else f"xl/{target}")
        if not normalized.startswith("xl/worksheets/") or normalized not in workbook.namelist():
            raise ValueError("The MAIN sheet points to an unsafe or missing internal file.")
        return normalized
    return None


def _row_values(row: ET.Element, shared_strings: list[str]) -> list[str]:
    values: dict[int, str] = {}
    for cell in row.findall("main:c", NS):
        column = _column_index(cell.attrib.get("r", "A1"))
        values[column] = _cell_value(cell, shared_strings)
    if not values:
        return []
    if max(values) >= MAX_SPREADSHEET_COLUMNS:
        raise ValueError("This spreadsheet has too many columns to import safely (256 maximum).")
    return [values.get(index, "") for index in range(max(values) + 1)]


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    inline = cell.find("main:is", NS)
    if inline is not None:
        return _node_text(inline).strip()
    value = cell.find("main:v", NS)
    if value is None or value.text is None:
        return ""
    raw = value.text.strip()
    if cell.attrib.get("t") == "s":
        try:
            return shared_strings[int(raw)].strip()
        except (ValueError, IndexError):
            return raw
    return raw


def _node_text(node: ET.Element) -> str:
    return "".join(text.text or "" for text in node.findall(".//main:t", NS))


def _column_index(reference: str) -> int:
    letters = "".join(char for char in reference if char.isalpha()).upper()
    index = 0
    for char in letters:
        index = index * 26 + ord(char) - ord("A") + 1
    return max(index - 1, 0)


def _header_map(values: list[str]) -> dict[str, int]:
    return {str(value).strip().casefold(): index for index, value in enumerate(values) if str(value).strip()}


def _record_from_values(values: list[str], header_map: dict[str, int]) -> SpreadsheetSale | None:
    def value(header: str) -> str:
        index = header_map[header]
        return values[index].strip() if index < len(values) else ""

    title = _clean_text(value("set name"))
    set_number = _clean_text(value("set number"))
    if not title or not set_number:
        return None

    return SpreadsheetSale(
        title=title,
        set_number=set_number,
        retired=_clean_text(value("retired")),
        purchase_price=_amount(value("purchase price (cad)")),
        condition=_condition(value("condition (new/used)")),
        sold_price=_amount(value("selling price (cad)")),
        net_profit=_amount(value("net profit (cad)")),
        notes=_clean_text(value("notes")),
    )


def _amount(value: str) -> float:
    clean = value.replace("$", "").replace(",", "").strip()
    if not clean:
        return 0.0
    try:
        amount = float(clean)
        return amount if math.isfinite(amount) else 0.0
    except ValueError:
        return 0.0


def _condition(value: str) -> str:
    normalized = value.strip().casefold()
    if "sealed" in normalized:
        return "Sealed"
    if "incomplete" in normalized:
        return "Incomplete"
    if "new" in normalized:
        return "New"
    return "Used"



def _clean_text(value: str) -> str:
    replacements = {
        "?": "",
        "?": "",
        "?": "",
        "?": "",
        "?": "",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return " ".join(value.split())
