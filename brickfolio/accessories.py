"""Independent inventories for physical boxes and instruction booklets."""

from __future__ import annotations

import sqlite3
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .app import (
    BasePage, BrickLedgerApp, CatalogPicker, COLORS, FONT, button,
    make_toplevel_window_resizable, title_block,
)
from .catalog import CatalogSet
from .database import EXPORTS_PATH


class AccessoryPage(BasePage):
    columns = ("set_number", "title", "theme", "condition", "location", "notes")

    def __init__(self, parent: tk.Misc, app: BrickLedgerApp) -> None:
        super().__init__(parent, app)
        self.kind = "Box"
        self.label = "Boxes"
        header = tk.Frame(self, bg=COLORS["paper"])
        header.pack(fill="x", pady=(0, 18))
        heading = title_block(
            header,
            "Physical archive",
            "Boxes & instructions",
            "Keep both accessory inventories together, then switch views without leaving the page.",
        )
        heading.pack(side="left")
        self.add_button = button(header, "+ Add box", self.add)
        self.add_button.pack(side="right", anchor="ne", pady=(12, 0))

        switcher = tk.Frame(self, bg=COLORS["paper"])
        switcher.pack(fill="x", pady=(0, 16))
        self.kind_buttons: dict[str, tk.Button] = {}
        for kind, label in (("Box", "Boxes"), ("Instructions", "Instructions")):
            control = tk.Button(
                switcher, text=label, command=lambda selected=kind: self.select_kind(selected),
                relief="flat", bd=0, cursor="hand2", font=(FONT, 10, "bold"), padx=24, pady=11,
            )
            control.pack(side="left", padx=(0, 8))
            self.kind_buttons[kind] = control
        self._style_kind_buttons()

        toolbar = tk.Frame(self, bg=COLORS["paper"])
        toolbar.pack(fill="x", pady=(0, 12))
        self.query = tk.StringVar()
        self.sort = tk.StringVar(value="Alphabetical A-Z")
        tk.Label(toolbar, text="Search", bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 10)).pack(side="left", padx=(0, 8))
        search = tk.Entry(toolbar, textvariable=self.query, width=25, bg=COLORS["card"], fg=COLORS["ink"],
                          insertbackground=COLORS["ink"], relief="flat", font=(FONT, 10),
                          highlightthickness=1, highlightbackground=COLORS["line"], highlightcolor=COLORS["brick"])
        search.pack(side="left", fill="x", expand=True, ipady=8)
        sorter = ttk.Combobox(toolbar, textvariable=self.sort, state="readonly", width=20,
                              values=("Alphabetical A-Z", "Alphabetical Z-A", "Theme A-Z", "Set number"))
        sorter.pack(side="left", padx=12)
        self.count = tk.Label(toolbar, bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 9))
        self.count.pack(side="right")

        footer = tk.Frame(self, bg=COLORS["paper"])
        footer.pack(side="bottom", fill="x", pady=(12, 0))
        self.edit_button = button(footer, "Edit", self.edit, "soft")
        self.edit_button.pack(side="left")
        self.delete_button = button(footer, "Delete", self.delete, "danger")
        self.delete_button.pack(side="left", padx=8)
        button(footer, "Export CSV", self.export, "ink").pack(side="right")

        table = tk.Frame(self, bg=COLORS["card"], highlightbackground=COLORS["line"], highlightthickness=1)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=self.columns, show="headings", selectmode="browse")
        labels = ("SET #", "SET NAME", "THEME", "CONDITION", "STORAGE LOCATION", "NOTES")
        widths = (95, 250, 150, 110, 155, 240)
        for key, label, width in zip(self.columns, labels, widths):
            self.tree.heading(key, text=label, anchor="w")
            self.tree.column(key, width=width, minwidth=width, stretch=key in {"title", "notes"}, anchor="w")
        self.tree.tag_configure("complete", background=COLORS["complete"])
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self.update_actions())
        self.tree.bind("<Double-1>", lambda _event: self.edit())
        self.query.trace_add("write", lambda *_: self.refresh())
        sorter.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        self.update_actions()

    def select_kind(self, kind: str) -> None:
        self.kind = kind
        self.label = "Boxes" if kind == "Box" else "Instructions"
        self.add_button.configure(text="+ Add box" if kind == "Box" else "+ Add instructions")
        self._style_kind_buttons()
        self.refresh()

    def _style_kind_buttons(self) -> None:
        for kind, control in self.kind_buttons.items():
            active = kind == self.kind
            control.configure(
                bg=COLORS["accent"] if active else COLORS["card"],
                fg=COLORS["black"] if active else COLORS["ink"],
                activebackground=COLORS["accent_hover"] if active else COLORS["hover"],
                activeforeground=COLORS["black"] if active else COLORS["ink"],
            )

    def selected_id(self) -> int | None:
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def update_actions(self) -> None:
        state = "normal" if self.selected_id() is not None else "disabled"
        self.edit_button.configure(state=state)
        self.delete_button.configure(state=state)

    def refresh(self) -> None:
        try:
            rows = self.app.db.accessories(self.kind, self.query.get(), self.sort.get())
        except sqlite3.Error as error:
            messagebox.showerror("Could not load records", str(error), parent=self)
            return
        selected = self.selected_id()
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in rows:
            self.tree.insert("", "end", iid=str(row["id"]),
                             values=tuple(" ".join(str(row[key]).split()) for key in self.columns),
                             tags=("complete",) if row["condition"] == "Complete" else ())
        if selected is not None and self.tree.exists(str(selected)):
            self.tree.selection_set(str(selected))
        self.count.configure(text=f"{len(rows)} record{'' if len(rows) == 1 else 's'}")
        self.update_actions()

    def add(self) -> None:
        AccessoryDialog(self, self.app, self.kind)

    def edit(self) -> None:
        item_id = self.selected_id()
        if item_id is not None:
            AccessoryDialog(self, self.app, self.kind, item_id)

    def delete(self) -> None:
        item_id = self.selected_id()
        if item_id is None:
            return
        try:
            row = self.app.db.get_accessory(item_id)
            if row and messagebox.askyesno("Delete record", f"Delete {self.kind.lower()} for {row['set_number']} - {row['title']}?", parent=self):
                self.app.db.delete_accessory(item_id)
                self.app.refresh_everything()
        except sqlite3.Error as error:
            messagebox.showerror("Could not delete record", str(error), parent=self)

    def copy_checked(self) -> None:
        if not messagebox.askyesno(
            "Copy checked sets",
            f"Copy sets with the {self.kind} checkbox ticked into {self.label}?\n\n"
            "Previously copied records are skipped. Each copy is tracked separately from the set, "
            "including its condition and notes. Checked sold sets are included.", parent=self,
        ):
            return
        try:
            count = self.app.db.import_checked_accessories(self.kind)
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Could not copy records", str(error), parent=self)
            return
        self.app.refresh_everything()
        messagebox.showinfo("Records copied", f"Added {count} record{'' if count == 1 else 's'} to {self.label}.", parent=self)

    def export(self) -> None:
        target = filedialog.asksaveasfilename(
            parent=self, title=f"Export {self.label.lower()}", initialdir=EXPORTS_PATH,
            initialfile=f"brickledger-{self.label.lower()}-{datetime.now():%Y-%m-%d}.csv",
            defaultextension=".csv", filetypes=[("CSV file", "*.csv")],
        )
        if not target:
            return
        try:
            count = self.app.db.export_accessories(Path(target), self.kind, self.query.get(), self.sort.get())
        except (OSError, sqlite3.Error) as error:
            messagebox.showerror("Could not export records", str(error), parent=self)
            return
        messagebox.showinfo("Export complete", f"Saved {count} records to:\n{target}", parent=self)


class BoxesPage(AccessoryPage):
    kind = "Box"
    label = "Boxes"


class InstructionsPage(AccessoryPage):
    kind = "Instructions"
    label = "Instructions"


class AccessoriesPage(AccessoryPage):
    """Combined boxes and instruction inventory used by the main navigation."""


class AccessoryDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, app: BrickLedgerApp, kind: str, item_id: int | None = None) -> None:
        super().__init__(parent)
        self.app, self.kind, self.item_id = app, kind, item_id
        record = app.db.get_accessory(item_id) if item_id is not None else None
        self.title(f"{'Edit' if record else 'Add'} {kind.lower()} - BrickLedger")
        self.configure(bg=COLORS["paper"])
        self.geometry("780x560")
        make_toplevel_window_resizable(self, 720, 520)
        self.grab_set()
        self.bind("<Escape>", lambda _event: self.destroy())
        header = tk.Frame(self, bg=COLORS["black"])
        header.pack(fill="x")
        tk.Label(header, text=f"{'Edit' if record else 'Add'} {kind.lower()}", bg=COLORS["black"], fg=COLORS["ink"],
                 font=(FONT, 18, "bold")).pack(side="left", padx=24, pady=18)
        button(header, "Browse sets", self.browse, "soft").pack(side="right", padx=24)
        footer = tk.Frame(self, bg=COLORS["paper"])
        footer.pack(side="bottom", fill="x", padx=24, pady=16)
        button(footer, "Cancel", self.destroy, "soft").pack(side="right")
        button(footer, "Save", self.save).pack(side="right", padx=8)
        form = tk.Frame(self, bg=COLORS["paper"])
        form.pack(fill="both", expand=True, padx=24, pady=12)
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)
        form.rowconfigure(3, weight=1)
        self.vars: dict[str, tk.StringVar] = {}
        fields = (("set_number", "Set number"), ("title", "Set name"), ("theme", "Theme"),
                  ("condition", "Condition"), ("location", "Storage location"))
        for index, (key, label) in enumerate(fields):
            cell = tk.Frame(form, bg=COLORS["paper"])
            cell.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 10) if index % 2 == 0 else (10, 0), pady=6)
            tk.Label(cell, text=label.upper(), bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 4))
            variable = tk.StringVar(value=record[key] if record else "Good" if key == "condition" else "")
            self.vars[key] = variable
            if key == "condition":
                field = ttk.Combobox(cell, textvariable=variable, state="readonly", values=("New", "Good", "Worn", "Damaged", "Incomplete", "Complete"))
            else:
                field = tk.Entry(cell, textvariable=variable, bg=COLORS["card"], fg=COLORS["ink"], insertbackground=COLORS["ink"],
                                 relief="flat", font=(FONT, 10), highlightthickness=1,
                                 highlightbackground=COLORS["line"], highlightcolor=COLORS["brick"])
            field.pack(fill="x", ipady=6)
        notes = tk.Frame(form, bg=COLORS["paper"])
        notes.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(6, 0))
        tk.Label(notes, text="NOTES", bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 4))
        self.notes = tk.Text(notes, height=4, wrap="word", bg=COLORS["card"], fg=COLORS["ink"],
                             insertbackground=COLORS["ink"], relief="flat", font=(FONT, 10), padx=8, pady=8,
                             highlightthickness=1, highlightbackground=COLORS["line"], highlightcolor=COLORS["brick"])
        self.notes.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(notes, orient="vertical", command=self.notes.yview)
        scroll.pack(side="right", fill="y")
        self.notes.configure(yscrollcommand=scroll.set)
        if record:
            self.notes.insert("1.0", record["notes"])

    def browse(self) -> None:
        if not self.app.catalog.available():
            messagebox.showinfo("Catalogue unavailable", "The Sets folder is unavailable. You can enter the set details manually.", parent=self)
            return
        picker = CatalogPicker(self, self.app.catalog, self.apply_catalog_set)
        self.wait_window(picker)
        if self.winfo_exists():
            self.grab_set()

    def apply_catalog_set(self, record: CatalogSet) -> None:
        self.vars["set_number"].set(record.set_number)
        self.vars["title"].set(record.name)
        self.vars["theme"].set(record.theme)

    def save(self) -> None:
        values = {key: variable.get() for key, variable in self.vars.items()}
        values["notes"] = self.notes.get("1.0", "end-1c")
        try:
            self.app.db.save_accessory(self.kind, values, self.item_id)
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Could not save record", str(error), parent=self)
            return
        self.app.refresh_everything()
        self.destroy()
