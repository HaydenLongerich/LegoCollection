"""SQLite persistence for BrickLedger.

The database layer intentionally uses only the Python standard library so the app
can be copied to another computer and run without a package-install step.
"""

from __future__ import annotations

import csv
import re
import shutil
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from .catalog import normalise_theme


ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = ROOT / "data" / "brickledger.db"
LEGACY_DATABASE_PATH = ROOT / "data" / "studledger.db"
EXPORTS_PATH = ROOT / "exports"

COLLECTION_EXPORT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("set_number", "Set #"),
    ("title", "Set Name"),
    ("theme", "Theme"),
    ("condition", "Condition"),
    ("purchase_price", "Paid"),
    ("estimated_value", "Estimated Value"),
    ("status", "Status"),
    ("notes", "Notes"),
    ("built", "Built"),
    ("disassembled", "Disassembled"),
    ("has_box", "Box"),
    ("has_instructions", "Instructions"),
    ("created_at", "Date Added"),
)


class Database:
    def __init__(self, path: Path = DATABASE_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path == DATABASE_PATH and not path.exists() and LEGACY_DATABASE_PATH.exists():
            shutil.copy2(LEGACY_DATABASE_PATH, path)
        EXPORTS_PATH.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA trusted_schema = OFF")
        self.connection.execute("PRAGMA secure_delete = ON")
        self.connection.execute("PRAGMA busy_timeout = 5000")
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS collection (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                set_number TEXT NOT NULL,
                title TEXT NOT NULL,
                theme TEXT DEFAULT '',
                condition TEXT NOT NULL DEFAULT 'Used',
                quantity INTEGER NOT NULL DEFAULT 1,
                purchase_price REAL NOT NULL DEFAULT 0,
                estimated_value REAL NOT NULL DEFAULT 0,
                target_price REAL NOT NULL DEFAULT 0,
                location TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Keeping',
                notes TEXT DEFAULT '',
                built INTEGER NOT NULL DEFAULT 0,
                disassembled INTEGER NOT NULL DEFAULT 0,
                has_box INTEGER NOT NULL DEFAULT 0,
                has_instructions INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_id INTEGER,
                platform TEXT NOT NULL DEFAULT 'Other',
                sold_price REAL NOT NULL DEFAULT 0,
                fees REAL NOT NULL DEFAULT 0,
                shipping REAL NOT NULL DEFAULT 0,
                sold_on TEXT NOT NULL,
                buyer TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(collection_id) REFERENCES collection(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_collection_status ON collection(status);
            CREATE INDEX IF NOT EXISTS idx_sales_sold_on ON sales(sold_on);

            CREATE TABLE IF NOT EXISTS accessories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL CHECK(kind IN ('Box', 'Instructions')),
                set_number TEXT NOT NULL CHECK(length(trim(set_number)) > 0),
                title TEXT NOT NULL CHECK(length(trim(title)) > 0),
                theme TEXT NOT NULL DEFAULT '',
                condition TEXT NOT NULL DEFAULT 'Good',
                location TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                source_collection_id INTEGER REFERENCES collection(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(kind, source_collection_id)
            );
            CREATE INDEX IF NOT EXISTS idx_accessories_kind ON accessories(kind);
            """
        )
        self.connection.commit()
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(collection)")}
        for column in ("built", "disassembled", "has_box", "has_instructions"):
            if column not in columns:
                self.connection.execute(f"ALTER TABLE collection ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0")
        self.connection.execute("UPDATE collection SET condition = 'Used' WHERE condition = 'Used + B&I'")
        self.connection.execute("UPDATE collection SET condition = 'Collection' WHERE condition = 'Complete'")
        self.connection.commit()
        rows_to_clean = self.connection.execute(
            "SELECT id, notes FROM collection WHERE notes LIKE ? OR notes LIKE ? OR notes LIKE ? OR notes LIKE ? OR notes LIKE ?",
            ("%Imported from BrickEconomy%", "%Subtheme:%", "%Year:%", "%Retail:%", "%Collection date:%"),
        ).fetchall()
        for row in rows_to_clean:
            self.connection.execute(
                "UPDATE collection SET notes = ? WHERE id = ?",
                (self._clean_collection_notes(row["notes"]), row["id"]),
            )
        self.connection.commit()
        # Keep earlier entries aligned with the concise labels used by the
        # catalogue picker. The Sets reference files are never modified.
        self.connection.executemany(
            "UPDATE collection SET theme = ? WHERE LOWER(theme) = ?",
            [(replacement, original) for original, replacement in {
                "cuusoo": "Ideas",
                "lego ideas": "Ideas",
                "lego ideas and cuusoo": "Ideas",
                "ultimate collector series": "Star Wars",
            }.items()],
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    @staticmethod
    def _accessory_kind(kind: str) -> str:
        if kind not in {"Box", "Instructions"}:
            raise ValueError("Choose Boxes or Instructions.")
        return kind

    def accessories(self, kind: str, query: str = "", sort: str = "Alphabetical A-Z") -> list[sqlite3.Row]:
        self._accessory_kind(kind)
        order = {
            "Alphabetical A-Z": "title COLLATE NOCASE, set_number COLLATE NOCASE, id",
            "Alphabetical Z-A": "title COLLATE NOCASE DESC, set_number COLLATE NOCASE, id",
            "Theme A-Z": "theme COLLATE NOCASE, title COLLATE NOCASE, set_number COLLATE NOCASE, id",
            "Set number": "set_number COLLATE NOCASE, title COLLATE NOCASE, id",
        }.get(sort, "title COLLATE NOCASE, id")
        term = f"%{query.strip()}%"
        return self.connection.execute(
            f"""SELECT * FROM accessories WHERE kind = ? AND
                (set_number LIKE ? OR title LIKE ? OR theme LIKE ? OR condition LIKE ?
                 OR location LIKE ? OR notes LIKE ?) ORDER BY {order}""",
            (kind, term, term, term, term, term, term),
        ).fetchall()

    def get_accessory(self, item_id: int) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM accessories WHERE id = ?", (item_id,)).fetchone()

    def save_accessory(self, kind: str, values: dict[str, Any], item_id: int | None = None) -> int:
        self._accessory_kind(kind)
        columns = ("set_number", "title", "theme", "condition", "location", "notes")
        prepared = {key: str(values.get(key, "")).strip() for key in columns}
        if not prepared["set_number"] or not prepared["title"]:
            raise ValueError("Set number and set name are required.")
        prepared["theme"] = normalise_theme(prepared["theme"])
        prepared["condition"] = prepared["condition"] or "Good"
        with self.connection:
            if item_id is not None:
                assignments = ", ".join(f"{column} = ?" for column in columns)
                cursor = self.connection.execute(
                    f"UPDATE accessories SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND kind = ?",
                    (*[prepared[key] for key in columns], item_id, kind),
                )
                if not cursor.rowcount:
                    raise ValueError("This record no longer exists. Refresh the list and try again.")
                return item_id
            cursor = self.connection.execute(
                f"INSERT INTO accessories (kind, {', '.join(columns)}) VALUES (?, {', '.join('?' for _ in columns)})",
                (kind, *[prepared[key] for key in columns]),
            )
            return int(cursor.lastrowid)

    def delete_accessory(self, item_id: int) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM accessories WHERE id = ?", (item_id,))

    def import_checked_accessories(self, kind: str) -> int:
        self._accessory_kind(kind)
        flag = "has_box" if kind == "Box" else "has_instructions"
        # These are independent possessions; copying never changes the set or its prices.
        with self.connection:
            cursor = self.connection.execute(
                f"""INSERT INTO accessories (kind, set_number, title, theme, source_collection_id)
                    SELECT ?, set_number, title, COALESCE(theme, ''), id FROM collection
                    WHERE {flag} = 1
                    ON CONFLICT(kind, source_collection_id) DO NOTHING""",
                (kind,),
            )
            return cursor.rowcount

    def export_accessories(self, destination: Path, kind: str, query: str = "", sort: str = "Alphabetical A-Z") -> int:
        rows = self.accessories(kind, query, sort)
        columns = {"kind": "Type", "set_number": "Set #", "title": "Set Name", "theme": "Theme",
                   "condition": "Condition", "location": "Storage Location", "notes": "Notes"}
        with destination.open("w", newline="", encoding="utf-8-sig") as output:
            writer = csv.DictWriter(output, fieldnames=list(columns.values()))
            writer.writeheader()
            writer.writerows(
                {
                    label: self._safe_csv_value(" ".join(str(row[key]).split()))
                    for key, label in columns.items()
                }
                for row in rows
            )
        return len(rows)

    @staticmethod
    def _clean_collection_notes(value: Any) -> str:
        notes = str(value or "").replace("Imported from BrickEconomy", "")
        automatic_pattern = re.compile(r"^(Subtheme|Year|Retail|Collection date):\s*", re.IGNORECASE)
        lines = [line.strip() for line in notes.replace("\r\n", "\n").split("\n")]
        return "\n".join(line for line in lines if line and not automatic_pattern.match(line))

    @staticmethod
    def _truthy(value: Any) -> int:
        return 1 if str(value or "0").strip().lower() in {"1", "true", "yes", "built", "checked", "on"} else 0

    def _prepare_collection_values(self, values: dict[str, Any]) -> dict[str, Any]:
        prepared = {**values, "theme": normalise_theme(str(values.get("theme", "")))}
        prepared["notes"] = self._clean_collection_notes(prepared.get("notes", ""))
        prepared["quantity"] = 1
        if prepared.get("condition") == "Used + B&I":
            prepared["condition"] = "Used"
        elif prepared.get("condition") == "Complete":
            prepared["condition"] = "Collection"
        for column in ("built", "disassembled", "has_box", "has_instructions"):
            prepared[column] = self._truthy(prepared.get(column, 0))
        return prepared

    def add_set(self, values: dict[str, Any]) -> int:
        columns = (
            "set_number", "title", "theme", "condition", "quantity",
            "purchase_price", "estimated_value", "status", "notes", "built",
            "disassembled", "has_box", "has_instructions",
        )
        values = self._prepare_collection_values(values)
        cursor = self.connection.execute(
            f"INSERT INTO collection ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
            tuple(values.get(column, "") for column in columns),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def add_sets(self, items: Iterable[dict[str, Any]]) -> int:
        """Add an import batch in one transaction."""
        columns = (
            "set_number", "title", "theme", "condition", "quantity",
            "purchase_price", "estimated_value", "status", "notes", "built",
            "disassembled", "has_box", "has_instructions",
        )
        rows = []
        for item in items:
            values = self._prepare_collection_values(item)
            rows.append(tuple(values.get(column, "") for column in columns))
        if not rows:
            return 0
        self.connection.executemany(
            f"INSERT INTO collection ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
            rows,
        )
        self.connection.commit()
        return len(rows)

    def update_set(self, item_id: int, values: dict[str, Any]) -> None:
        columns = (
            "set_number", "title", "theme", "condition", "quantity",
            "purchase_price", "estimated_value", "status", "notes", "built",
            "disassembled", "has_box", "has_instructions",
        )
        values = self._prepare_collection_values(values)
        assignments = ", ".join(f"{column} = ?" for column in columns)
        self.connection.execute(
            f"UPDATE collection SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (*tuple(values.get(column, "") for column in columns), item_id),
        )
        self.connection.commit()

    def delete_set(self, item_id: int) -> None:
        self.connection.execute("DELETE FROM collection WHERE id = ?", (item_id,))
        self.connection.commit()

    def collection(
        self,
        query: str = "",
        status: str = "All",
        condition: str = "All",
        built: str = "All",
        sort: str = "Status then A-Z",
    ) -> list[sqlite3.Row]:
        terms: list[Any] = []
        where: list[str] = []
        if query.strip():
            where.append("(set_number LIKE ? OR title LIKE ? OR theme LIKE ? OR notes LIKE ?)")
            wildcard = f"%{query.strip()}%"
            terms.extend([wildcard, wildcard, wildcard, wildcard])
        if status != "All":
            where.append("status = ?")
            terms.append(status)
        if condition != "All":
            where.append("condition = ?")
            terms.append(condition)
        if built == "Built":
            where.append("built = 1")
        elif built == "Not built":
            where.append("built = 0")
        order_by = {
            "Alphabetical A-Z": "title COLLATE NOCASE ASC, set_number COLLATE NOCASE ASC",
            "Alphabetical Z-A": "title COLLATE NOCASE DESC, set_number COLLATE NOCASE ASC",
            "Status then A-Z": "status = 'Sold', status COLLATE NOCASE ASC, title COLLATE NOCASE ASC",
            "Theme A-Z": "theme COLLATE NOCASE ASC, title COLLATE NOCASE ASC, set_number COLLATE NOCASE ASC",
            "Highest paid": "purchase_price DESC, title COLLATE NOCASE ASC",
            "Lowest paid": "purchase_price ASC, title COLLATE NOCASE ASC",
            "Highest value": "estimated_value DESC, title COLLATE NOCASE ASC",
            "Lowest value": "estimated_value ASC, title COLLATE NOCASE ASC",
            "Newest added": "created_at DESC, id DESC",
            "Oldest added": "created_at ASC, id ASC",
        }.get(sort, "status = 'Sold', title COLLATE NOCASE ASC")
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        return self.connection.execute(
            f"SELECT * FROM collection {clause} ORDER BY {order_by}",
            terms,
        ).fetchall()

    def get_set(self, item_id: int) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM collection WHERE id = ?", (item_id,)).fetchone()

    def available_to_sell(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM collection WHERE status != 'Sold' ORDER BY title COLLATE NOCASE"
        ).fetchall()

    def record_sale(self, values: dict[str, Any]) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO sales (collection_id, platform, sold_price, fees, shipping, sold_on, buyer, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                values.get("collection_id"), values["platform"], values["sold_price"],
                values["fees"], values["shipping"], values["sold_on"],
                values.get("buyer", ""), values.get("notes", ""),
            ),
        )
        if values.get("collection_id"):
            self.connection.execute(
                "UPDATE collection SET status = 'Sold', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (values["collection_id"],),
            )
        self.connection.commit()
        return int(cursor.lastrowid)


    def import_spreadsheet_sales(self, records: Iterable[Any], sold_on: str) -> int:
        """Import sold-set rows from the owner's spreadsheet.

        The source sheet stores net profit rather than platform fees. To keep the
        existing Sales page truthful, imported costs are stored in the fees field
        so the displayed "You kept" value equals the spreadsheet net profit.
        """
        count = 0
        with self.connection:
            for record in records:
                imported_costs = max(float(record.sold_price) - float(record.net_profit), 0.0)
                notes = ["Imported from personal LEGO spreadsheet"]
                if record.retired:
                    notes.append(f"Retired: {record.retired}")
                if record.notes:
                    notes.append(record.notes)

                cursor = self.connection.execute(
                    """
                    INSERT INTO collection (
                        set_number, title, theme, condition, quantity,
                        purchase_price, estimated_value, status, notes
                    )
                    VALUES (?, ?, '', ?, 1, ?, ?, 'Sold', ?)
                    """,
                    (
                        record.set_number,
                        record.title,
                        record.condition,
                        record.purchase_price,
                        record.sold_price,
                        "\n".join(notes),
                    ),
                )
                collection_id = int(cursor.lastrowid)
                self.connection.execute(
                    """
                    INSERT INTO sales (
                        collection_id, platform, sold_price, fees, shipping,
                        sold_on, buyer, notes
                    )
                    VALUES (?, 'Spreadsheet import', ?, ?, 0, ?, '', ?)
                    """,
                    (
                        collection_id,
                        record.sold_price,
                        imported_costs,
                        sold_on,
                        f"Imported net profit: ${record.net_profit:,.2f} CAD",
                    ),
                )
                count += 1
        return count


    def get_sale(self, sale_id: int) -> sqlite3.Row | None:
        return self.connection.execute(
            """
            SELECT sales.*, collection.set_number, collection.title
            FROM sales LEFT JOIN collection ON collection.id = sales.collection_id
            WHERE sales.id = ?
            """,
            (sale_id,),
        ).fetchone()

    def update_sale(self, sale_id: int, values: dict[str, Any]) -> None:
        self.connection.execute(
            """
            UPDATE sales
            SET platform = ?, sold_price = ?, fees = ?, shipping = ?, sold_on = ?, notes = ?
            WHERE id = ?
            """,
            (
                values["platform"], values["sold_price"], values["fees"],
                values.get("shipping", 0), values["sold_on"], values.get("notes", ""), sale_id,
            ),
        )
        self.connection.commit()


    def delete_sale(self, sale_id: int) -> None:
        sale = self.get_sale(sale_id)
        if sale is None:
            return
        with self.connection:
            self.connection.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
            collection_id = sale["collection_id"]
            if collection_id:
                remaining = self.connection.execute(
                    "SELECT COUNT(*) FROM sales WHERE collection_id = ?",
                    (collection_id,),
                ).fetchone()[0]
                if remaining == 0:
                    self.connection.execute(
                        "UPDATE collection SET status = 'For sale', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'Sold'",
                        (collection_id,),
                    )

    def sales(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT sales.*, collection.set_number, collection.title
            FROM sales LEFT JOIN collection ON collection.id = sales.collection_id
            ORDER BY sold_on DESC, sales.id DESC
            """
        ).fetchall()

    def dashboard_metrics(self) -> dict[str, float | int]:
        row = self.connection.execute(
            """
            SELECT
              COUNT(*) AS items,
              COALESCE(SUM(quantity), 0) AS piecesets,
              COALESCE(SUM(purchase_price * quantity), 0) AS paid,
              COALESCE(SUM(estimated_value * quantity), 0) AS value,
              COALESCE(SUM(CASE WHEN status = 'For sale' THEN estimated_value * quantity ELSE 0 END), 0) AS listed,
              COALESCE(SUM(CASE WHEN status = 'For sale' THEN purchase_price * quantity ELSE 0 END), 0) AS listed_paid
            FROM collection WHERE status != 'Sold'
            """
        ).fetchone()
        sales = self.connection.execute(
            """
            SELECT COALESCE(SUM(sold_price - fees - shipping), 0) AS net_sales,
                   COUNT(*) AS sales_count
            FROM sales
            """
        ).fetchone()
        return {
            "items": int(row["items"]),
            "piecesets": int(row["piecesets"]),
            "paid": float(row["paid"]),
            "value": float(row["value"]),
            "listed": float(row["listed"]),
            "listed_paid": float(row["listed_paid"]),
            "net_sales": float(sales["net_sales"]),
            "sales_count": int(sales["sales_count"]),
        }

    def recent_activity(self, limit: int | None = None) -> list[sqlite3.Row]:
        query = """
            SELECT * FROM (
                SELECT 'set' AS kind, id, set_number, title, theme, condition, status, built, quantity,
                       created_at AS happened_at, purchase_price AS amount, estimated_value AS value,
                       '' AS context
                FROM collection
                UNION ALL
                SELECT 'sale' AS kind, sales.id, COALESCE(collection.set_number, ''),
                       COALESCE(collection.title, 'Standalone sale'), COALESCE(collection.theme, ''),
                       COALESCE(collection.condition, ''), 'Sold', COALESCE(collection.built, 0), 1,
                       sold_on, sold_price, sold_price - fees - shipping, platform
                FROM sales LEFT JOIN collection ON collection.id = sales.collection_id
            ) ORDER BY happened_at DESC, id DESC
        """
        parameters: tuple[int, ...] = ()
        if limit is not None:
            query += " LIMIT ?"
            parameters = (limit,)
        return self.connection.execute(query, parameters).fetchall()

    def export_collection(
        self,
        destination: Path,
        query: str = "",
        status: str = "All",
        condition: str = "All",
        built: str = "All",
        sort: str = "Status then A-Z",
        columns: Iterable[str] | None = None,
    ) -> int:
        rows = self.collection(query=query, status=status, condition=condition, built=built, sort=sort)
        self._write_csv(destination, self._collection_export_rows(rows, columns))
        return len(rows)

    def _collection_export_rows(self, rows: Iterable[sqlite3.Row], columns: Iterable[str] | None = None) -> list[dict[str, Any]]:
        selected = list(columns or [key for key, _label in COLLECTION_EXPORT_COLUMNS])
        allowed = {key for key, _label in COLLECTION_EXPORT_COLUMNS}
        selected = [key for key in selected if key in allowed]
        if not selected:
            selected = [key for key, _label in COLLECTION_EXPORT_COLUMNS]
        labels = dict(COLLECTION_EXPORT_COLUMNS)
        return [
            {labels[key]: self._format_collection_export_value(key, row[key]) for key in selected}
            for row in rows
        ]

    @staticmethod
    def _format_collection_export_value(key: str, value: Any) -> Any:
        if key in {"purchase_price", "estimated_value"}:
            return f"${float(value or 0):,.2f}"
        if key == "built":
            return "Built" if int(value or 0) else ""
        if key == "disassembled":
            return "Disassembled" if int(value or 0) else ""
        if key == "has_box":
            return "Box" if int(value or 0) else ""
        if key == "has_instructions":
            return "Instructions" if int(value or 0) else ""
        if key == "created_at" and value:
            return str(value).split(" ", 1)[0]
        if key == "notes":
            return " ".join(str(value or "").split())
        return value

    def export_sales(self, destination: Path) -> None:
        rows = self.sales()
        self._write_csv(destination, rows)

    @staticmethod
    def _write_csv(destination: Path, rows: Iterable[sqlite3.Row | dict[str, Any]]) -> None:
        rows = list(rows)
        with destination.open("w", newline="", encoding="utf-8-sig") as output:
            if not rows:
                return
            first = rows[0]
            fieldnames = list(first.keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(
                {key: Database._safe_csv_value(value) for key, value in dict(row).items()}
                for row in rows
            )

    @staticmethod
    def _safe_csv_value(value: Any) -> Any:
        """Keep user-controlled text from becoming a spreadsheet formula."""
        if not isinstance(value, str):
            return value
        candidate = value.lstrip(" \t\r\n")
        if candidate.startswith(("=", "+", "-", "@", "＝", "＋", "－", "＠")):
            return f"\t{value}"
        return value

    @staticmethod
    def today() -> str:
        return date.today().isoformat()
