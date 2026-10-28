"""The BrickLedger desktop interface."""

from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from .catalog import CatalogSet, OfflineCatalog
from .brickeconomy import ImportBatch, read_collection_csv
from .database import Database, EXPORTS_PATH
from .lego_spreadsheet import read_main_sales_spreadsheet


COLORS = {
    # Shared with the Hayden Longerich portfolio: warm paper, olive ink,
    # botanical neutrals, and one bright chartreuse accent.
    "ink": "#242A23",
    "ink_soft": "#465337",
    "paper": "#F5F4EE",
    "paper_alt": "#EFEFE6",
    "card": "#FBFBF6",
    "line": "#CBD0C0",
    "muted": "#69745E",
    "brick": "#6D863B",
    "brick_dark": "#465C32",
    "accent": "#D5ED97",
    "accent_hover": "#C7DF87",
    "yellow": "#D5ED97",
    "sage": "#D9E5C5",
    "sage_ink": "#465C32",
    "blue": "#E2E8D8",
    "blue_ink": "#566A42",
    "lavender": "#E8EBDD",
    "lavender_ink": "#5F6955",
    "danger": "#9A3E43",
    "selection": "#DCE9BC",
    "heading": "#E8EBDF",
    "hover": "#DFE4D5",
    "nav_muted": "#B9C3A4",
    "complete": "#E7F2C6",
    "success_bg": "#E5EDDA",
    "warning_bg": "#F0EBD5",
    "danger_bg": "#F3E4E2",
    "danger_hover": "#EBD4D1",
}

FONT = "Segoe UI"


def money(value: float | int) -> str:
    return f"${float(value):,.2f}"


def short_money(value: float | int) -> str:
    value = float(value)
    return f"${value / 1000:.1f}k" if abs(value) >= 1000 else money(value)


class BrickLedgerApp(tk.Tk):
    """Top-level window and shared navigation state."""

    def __init__(self) -> None:
        super().__init__()
        self.title("BrickLedger — Collection desk")
        self.geometry("1440x900")
        self.minsize(1120, 720)
        self.configure(bg=COLORS["paper"])
        self.db = Database()
        self.catalog = OfflineCatalog()
        self.nav_buttons: dict[str, tk.Button] = {}
        self.pages: dict[str, BasePage] = {}
        self._setup_style()
        self._build_shell()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.show_page("Overview")

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=COLORS["card"], foreground=COLORS["ink"], fieldbackground=COLORS["card"],
            borderwidth=0, rowheight=46, font=(FONT, 10),
        )
        style.map("Treeview", background=[("selected", COLORS["selection"])], foreground=[("selected", COLORS["ink"])])
        style.configure(
            "Treeview.Heading",
            background=COLORS["paper_alt"], foreground=COLORS["muted"], relief="flat",
            font=(FONT, 8, "bold"), padding=(14, 13),
        )
        style.map("Treeview.Heading", background=[("active", COLORS["hover"])])
        style.configure(
            "TCombobox", fieldbackground=COLORS["card"], background=COLORS["card"],
            foreground=COLORS["ink"], bordercolor=COLORS["line"], lightcolor=COLORS["line"],
            darkcolor=COLORS["line"], padding=7, font=(FONT, 10),
        )
        style.map("TCombobox", fieldbackground=[("readonly", COLORS["card"])])
        style.map("TCombobox", selectbackground=[("readonly", COLORS["selection"])],
                  selectforeground=[("readonly", COLORS["ink"])])
        style.configure("TScrollbar", background=COLORS["line"], troughcolor=COLORS["paper"],
                        arrowcolor=COLORS["muted"], bordercolor=COLORS["paper"],
                        lightcolor=COLORS["line"], darkcolor=COLORS["line"])
        style.map("TScrollbar", background=[("active", COLORS["muted"])])
        style.configure("Activity.TNotebook", background=COLORS["card"], borderwidth=0)
        style.configure("Activity.TNotebook.Tab", background=COLORS["heading"], foreground=COLORS["muted"],
                        font=(FONT, 10, "bold"), padding=(12, 9))
        style.map("Activity.TNotebook.Tab", background=[("selected", COLORS["selection"])],
                  foreground=[("selected", COLORS["ink"])])
        self.option_add("*TCombobox*Listbox.background", COLORS["card"])
        self.option_add("*TCombobox*Listbox.foreground", COLORS["ink"])
        self.option_add("*TCombobox*Listbox.selectBackground", COLORS["selection"])
        self.option_add("*TCombobox*Listbox.selectForeground", COLORS["ink"])

    def _build_shell(self) -> None:
        navigation = tk.Frame(self, bg=COLORS["ink"], width=248)
        navigation.pack(side="left", fill="y")
        navigation.pack_propagate(False)

        brand = tk.Frame(navigation, bg=COLORS["ink"])
        brand.pack(fill="x", padx=28, pady=(34, 44))
        mark = tk.Canvas(brand, width=13, height=38, bg=COLORS["ink"], highlightthickness=0)
        mark.pack(side="left")
        mark.create_oval(2, 14, 10, 22, fill=COLORS["accent"], outline="")
        identity = tk.Frame(brand, bg=COLORS["ink"])
        identity.pack(side="left", padx=(11, 0))
        tk.Label(identity, text="brickledger.", bg=COLORS["ink"], fg=COLORS["paper"],
                 font=(FONT, 18, "bold")).pack(anchor="w")
        tk.Label(identity, text="Your collection, considered.", bg=COLORS["ink"], fg=COLORS["nav_muted"],
                 font=(FONT, 8)).pack(anchor="w", pady=(1, 0))

        tk.Label(
            navigation, text="COLLECTION / 2026", bg=COLORS["ink"], fg=COLORS["nav_muted"],
            font=(FONT, 8, "bold"), anchor="w",
        ).pack(fill="x", padx=30, pady=(0, 12))
        nav_items = (
            ("00", "Overview"), ("01", "Collection"), ("02", "Boxes"),
            ("03", "Instructions"), ("04", "Sales desk"), ("05", "Data & exports"),
        )
        for number, label in nav_items:
            button = tk.Button(
                navigation, text=f"{number}   {label}", anchor="w", command=lambda name=label: self.show_page(name),
                bg=COLORS["ink"], fg=COLORS["nav_muted"], activebackground=COLORS["ink_soft"], activeforeground=COLORS["paper"],
                relief="flat", bd=0, font=(FONT, 10), padx=18, pady=13, cursor="hand2",
            )
            button.pack(fill="x", padx=14, pady=2)
            self.nav_buttons[label] = button

        bottom = tk.Frame(navigation, bg=COLORS["ink"])
        bottom.pack(side="bottom", fill="x", padx=30, pady=30)
        tk.Label(bottom, text="LOCAL-FIRST / PRIVATE", bg=COLORS["ink"], fg=COLORS["accent"], font=(FONT, 8, "bold")).pack(anchor="w")
        tk.Label(bottom, text="No account. No cloud. Just your sets.", bg=COLORS["ink"], fg=COLORS["nav_muted"], font=(FONT, 8)).pack(anchor="w", pady=(6, 0))

        workspace = tk.Frame(self, bg=COLORS["paper"])
        workspace.pack(side="left", fill="both", expand=True)
        topbar = tk.Frame(workspace, bg=COLORS["paper"], height=88,
                          highlightbackground=COLORS["line"], highlightthickness=0)
        topbar.pack(fill="x", padx=46)
        topbar.pack_propagate(False)
        self.breadcrumb = tk.Label(topbar, text="00 / OVERVIEW", bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 9, "bold"))
        self.breadcrumb.pack(side="left", pady=34)
        date_text = datetime.now().strftime("%A, %B %-d") if os.name != "nt" else datetime.now().strftime("%A, %B %#d")
        tk.Label(topbar, text=date_text.upper(), bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 8, "bold")).pack(side="right", pady=34)

        self.page_host = tk.Frame(workspace, bg=COLORS["paper"])
        self.page_host.pack(fill="both", expand=True, padx=46, pady=(4, 38))

    def show_page(self, name: str) -> None:
        from .accessories import BoxesPage, InstructionsPage

        page_type: type[BasePage]
        page_type = {
            "Overview": OverviewPage,
            "Collection": CollectionPage,
            "Boxes": BoxesPage,
            "Instructions": InstructionsPage,
            "Sales desk": SalesPage,
            "Data & exports": DataPage,
        }[name]
        for page in self.pages.values():
            page.pack_forget()
        if name not in self.pages:
            self.pages[name] = page_type(self.page_host, self)
        page = self.pages[name]
        page.pack(fill="both", expand=True)
        page.refresh()
        page_number = {"Overview": "00", "Collection": "01", "Boxes": "02", "Instructions": "03", "Sales desk": "04", "Data & exports": "05"}[name]
        self.breadcrumb.configure(text=f"{page_number} / {name.upper()}")
        for label, button in self.nav_buttons.items():
            selected = label == name
            button.configure(
                bg=COLORS["accent"] if selected else COLORS["ink"],
                fg=COLORS["ink"] if selected else COLORS["nav_muted"],
            )

    def refresh_everything(self) -> None:
        for page in self.pages.values():
            page.refresh()

    def close(self) -> None:
        self.db.close()
        self.destroy()


class BasePage(tk.Frame):
    def __init__(self, parent: tk.Misc, app: BrickLedgerApp) -> None:
        super().__init__(parent, bg=COLORS["paper"])
        self.app = app

    def refresh(self) -> None:
        """Refresh dynamic values; overridden by pages that need it."""


def title_block(parent: tk.Misc, eyebrow: str, title: str, copy: str) -> tk.Frame:
    block = tk.Frame(parent, bg=COLORS["paper"])
    tk.Label(block, text=f"●  {eyebrow.upper()}", bg=COLORS["paper"], fg=COLORS["brick"], font=(FONT, 8, "bold")).pack(anchor="w")
    tk.Label(block, text=title, bg=COLORS["paper"], fg=COLORS["ink"], font=(FONT, 30, "bold")).pack(anchor="w", pady=(7, 4))
    tk.Label(block, text=copy, bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 10)).pack(anchor="w")
    return block


def button(parent: tk.Misc, text: str, command: Callable[[], None], kind: str = "primary", width: int | None = None) -> tk.Button:
    palette = {
        "primary": (COLORS["ink"], COLORS["paper"], COLORS["ink_soft"]),
        "ink": (COLORS["ink"], COLORS["paper"], COLORS["ink_soft"]),
        "soft": (COLORS["accent"], COLORS["ink"], COLORS["accent_hover"]),
        "plain": (COLORS["card"], COLORS["ink"], COLORS["heading"]),
        "danger": (COLORS["danger_bg"], COLORS["danger"], COLORS["danger_hover"]),
    }
    bg, fg, active = palette[kind]
    return tk.Button(
        parent, text=text, command=command, bg=bg, fg=fg, activebackground=active, activeforeground=fg,
        relief="flat", bd=0, font=(FONT, 9, "bold"), padx=17, pady=11, cursor="hand2", width=width,
        disabledforeground=COLORS["muted"] if kind in {"soft", "plain", "danger"} else COLORS["nav_muted"],
    )


def make_toplevel_window_resizable(window: tk.Toplevel, min_width: int = 760, min_height: int = 480, maximize: bool = False) -> None:
    """Make a popup behave like a normal Windows window with resize/maximize controls."""
    window.resizable(True, True)
    window.minsize(min_width, min_height)
    window.bind("<F11>", lambda _event: toggle_fullscreen(window), add="+")
    if maximize:
        window.after(50, lambda: maximize_window(window))


def maximize_window(window: tk.Toplevel) -> None:
    try:
        window.state("zoomed")
    except tk.TclError:
        try:
            window.attributes("-zoomed", True)
        except tk.TclError:
            pass


def toggle_fullscreen(window: tk.Toplevel) -> None:
    is_fullscreen = bool(window.attributes("-fullscreen"))
    window.attributes("-fullscreen", not is_fullscreen)


class MetricCard(tk.Frame):
    def __init__(self, parent: tk.Misc, label: str, accent: str, note: str) -> None:
        super().__init__(parent, bg=COLORS["card"], highlightbackground=COLORS["line"], highlightthickness=1)
        edge = tk.Frame(self, bg=accent, width=5)
        edge.pack(side="left", fill="y")
        body = tk.Frame(self, bg=COLORS["card"])
        body.pack(side="left", fill="both", expand=True, padx=19, pady=18)
        tk.Label(body, text=label.upper(), bg=COLORS["card"], fg=COLORS["muted"], font=(FONT, 8, "bold")).pack(anchor="w")
        self.value = tk.Label(body, text="-", bg=COLORS["card"], fg=COLORS["ink"], font=(FONT, 22, "bold"))
        self.value.pack(anchor="w", pady=(10, 3))
        self.note = tk.Label(body, text=note, bg=COLORS["card"], fg=COLORS["muted"], font=(FONT, 9))
        self.note.pack(anchor="w")

    def set(self, value: str, note: str | None = None) -> None:
        self.value.configure(text=value)
        if note is not None:
            self.note.configure(text=note)


class OverviewPage(BasePage):
    def __init__(self, parent: tk.Misc, app: BrickLedgerApp) -> None:
        super().__init__(parent, app)
        header_row = tk.Frame(self, bg=COLORS["paper"])
        header_row.pack(fill="x")
        header = title_block(header_row, "Your bricks, in focus", "A clearer view of the collection.", "What you own, what it is worth, and what is ready to move.")
        header.pack(side="left", anchor="nw")
        actions = tk.Frame(header_row, bg=COLORS["paper"])
        actions.pack(side="right", anchor="ne", pady=(13, 0))
        button(actions, "+ Add a set", self.open_add).pack(side="left")
        button(actions, "Record sale", self.open_sale, "ink").pack(side="left", padx=(8, 0))

        cards = tk.Frame(self, bg=COLORS["paper"])
        cards.pack(fill="x", pady=(29, 21))
        for column in range(4):
            cards.columnconfigure(column, weight=1, uniform="metric")
        self.cards: list[MetricCard] = []
        for index, values in enumerate((
            ("Collection value", COLORS["yellow"], "Based on your estimates"),
            ("Potential gain", COLORS["sage"], "Value less your cost"),
            ("Ready to sell", COLORS["blue"], "Estimated value of active listings"),
            ("Sales net", COLORS["lavender"], "After fees and shipping"),
        )):
            card = MetricCard(cards, *values)
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 7, 0 if index == 3 else 7))
            self.cards.append(card)

        lower = tk.Frame(self, bg=COLORS["paper"])
        lower.pack(fill="both", expand=True)
        lower.columnconfigure(0, weight=13)
        lower.columnconfigure(1, weight=10)
        lower.rowconfigure(0, weight=1)

        portfolio = tk.Frame(lower, bg=COLORS["card"], highlightbackground=COLORS["line"], highlightthickness=1)
        portfolio.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        phead = tk.Frame(portfolio, bg=COLORS["card"])
        phead.pack(fill="x", padx=22, pady=(21, 8))
        tk.Label(phead, text="COLLECTION COMPOSITION", bg=COLORS["card"], fg=COLORS["ink"], font=(FONT, 12, "bold")).pack(side="left")
        self.item_count = tk.Label(phead, text="", bg=COLORS["card"], fg=COLORS["muted"], font=(FONT, 9))
        self.item_count.pack(side="right")
        self.composition = tk.Frame(portfolio, bg=COLORS["card"])
        self.composition.pack(fill="both", expand=True, padx=22, pady=(8, 22))

        activity = tk.Frame(lower, bg=COLORS["card"], highlightbackground=COLORS["line"], highlightthickness=1)
        activity.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        tabs = ttk.Notebook(activity, style="Activity.TNotebook", width=1, height=1)
        tabs.pack(fill="both", expand=True, padx=12, pady=12)
        recent_sales = tk.Frame(tabs, bg=COLORS["card"])
        movement = tk.Frame(tabs, bg=COLORS["card"])
        tabs.add(recent_sales, text="Recent sales")
        tabs.add(movement, text="Recent movement")
        self.recent_sales_note = tk.Label(recent_sales, bg=COLORS["card"], fg=COLORS["muted"], font=(FONT, 9), anchor="w")
        self.recent_sales_note.pack(fill="x", padx=8, pady=10)
        button(recent_sales, "View all sales", self.open_sales_history, "soft").pack(side="bottom", anchor="e", padx=8, pady=(8, 0))
        sales_table = tk.Frame(recent_sales, bg=COLORS["card"])
        sales_table.pack(fill="both", expand=True)
        self.recent_sales_tree = ttk.Treeview(sales_table, columns=("date", "set", "sold", "profit"),
                                             show="headings", selectmode="browse", height=5)
        for key, label, width, anchor in (("date", "SOLD", 100, "w"), ("set", "SET", 170, "w"),
                                          ("sold", "SOLD FOR", 105, "e"), ("profit", "PROFIT", 100, "e")):
            self.recent_sales_tree.heading(key, text=label, anchor=anchor)
            self.recent_sales_tree.column(key, width=width, minwidth=width, anchor=anchor, stretch=key == "set")
        self.recent_sales_tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(sales_table, orient="vertical", command=self.recent_sales_tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(sales_table, orient="horizontal", command=self.recent_sales_tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        sales_table.columnconfigure(0, weight=1)
        sales_table.rowconfigure(0, weight=1)
        self.recent_sales_tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.recent_sales_tree.bind("<Double-1>", self.open_recent_sale)
        self.recent_sales_tree.bind("<Return>", self.open_recent_sale)
        self.activity_list = tk.Frame(movement, bg=COLORS["card"])
        self.activity_list.pack(fill="both", expand=True, padx=22, pady=(13, 18))

    def open_sales_history(self, sale_id: str | None = None) -> None:
        self.app.show_page("Sales desk")
        page = self.app.pages["Sales desk"]
        page.search_var.set("")
        if sale_id and page.tree.exists(sale_id):
            page.tree.selection_set(sale_id)
            page.tree.focus(sale_id)
            page.tree.see(sale_id)
            page.update_edit_state()

    def open_recent_sale(self, _event: tk.Event | None = None) -> None:
        selection = self.recent_sales_tree.selection()
        if selection:
            self.open_sales_history(selection[0])

    def open_add(self) -> None:
        SetDialog(self, self.app, on_saved=self.app.refresh_everything)

    def open_sale(self) -> None:
        SaleDialog(self, self.app, on_saved=self.app.refresh_everything)

    def refresh(self) -> None:
        metrics = self.app.db.dashboard_metrics()
        gain = float(metrics["value"]) - float(metrics["paid"])
        margin = (gain / float(metrics["paid"]) * 100) if metrics["paid"] else 0
        self.cards[0].set(short_money(metrics["value"]), f"Across {metrics['piecesets']} set{'' if metrics['piecesets'] == 1 else 's'} on hand")
        self.cards[1].set(short_money(gain), f"{margin:+.1f}% against your cost")
        self.cards[2].set(short_money(metrics["listed"]), "Sets currently marked for sale")
        self.cards[3].set(short_money(metrics["net_sales"]), f"From {metrics['sales_count']} recorded sale{'' if metrics['sales_count'] == 1 else 's'}")
        self.item_count.configure(text=f"{metrics['items']} catalogue entries")

        selected = self.recent_sales_tree.selection()
        for item in self.recent_sales_tree.get_children():
            self.recent_sales_tree.delete(item)
        sales = self.app.db.sales()[:10]
        self.recent_sales_note.configure(text="Latest 10 sales - newest sale date first" if sales else "No sales recorded yet.")
        for sale in sales:
            label = f"{sale['set_number']} - {sale['title']}" if sale["title"] else "Standalone sale"
            profit = float(sale["sold_price"]) - float(sale["fees"]) - float(sale["shipping"])
            self.recent_sales_tree.insert("", "end", iid=str(sale["id"]),
                                          values=(sale["sold_on"], label, money(sale["sold_price"]), money(profit)))
        if selected and self.recent_sales_tree.exists(selected[0]):
            self.recent_sales_tree.selection_set(selected[0])

        for child in self.composition.winfo_children():
            child.destroy()
        groups = [
            ("Paid so far", metrics["paid"], COLORS["yellow"], "What went into the collection"),
            ("Estimated now", metrics["value"], COLORS["sage"], "Your current working value"),
            ("Unrealized gain", gain, COLORS["brick"], "Before marketplace costs"),
        ]
        for label, value, shade, note in groups:
            row = tk.Frame(self.composition, bg=COLORS["paper"])
            row.pack(fill="x", pady=5)
            tk.Frame(row, bg=shade, width=7, height=44).pack(side="left")
            labels = tk.Frame(row, bg=COLORS["paper"])
            labels.pack(side="left", fill="x", expand=True, padx=12, pady=8)
            tk.Label(labels, text=label, bg=COLORS["paper"], fg=COLORS["ink"], font=(FONT, 10, "bold")).pack(anchor="w")
            tk.Label(labels, text=note, bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 8)).pack(anchor="w")
            tk.Label(row, text=money(value), bg=COLORS["paper"], fg=COLORS["ink"], font=(FONT, 11, "bold")).pack(side="right", padx=14)

        for child in self.activity_list.winfo_children():
            child.destroy()
        activity = self.app.db.recent_activity()
        if not activity:
            tk.Label(self.activity_list, text="Your workbench is clear.\nAdd your first set to begin.", justify="left", bg=COLORS["card"], fg=COLORS["muted"], font=(FONT, 10)).pack(anchor="w", pady=15)
            return
        for index, event in enumerate(activity):
            row = tk.Frame(self.activity_list, bg=COLORS["card"])
            row.pack(fill="x", pady=7)
            symbol = "SALE" if event["kind"] == "sale" else "ADD"
            bg = COLORS["lavender"] if event["kind"] == "sale" else COLORS["blue"]
            fg = COLORS["lavender_ink"] if event["kind"] == "sale" else COLORS["blue_ink"]
            tk.Label(row, text=symbol, width=3, bg=bg, fg=fg, font=(FONT, 11, "bold"), pady=3).pack(side="left")
            text = tk.Frame(row, bg=COLORS["card"])
            text.pack(side="left", padx=10, fill="x", expand=True)
            tk.Label(text, text=event["label"], bg=COLORS["card"], fg=COLORS["ink"], font=(FONT, 9, "bold"), anchor="w").pack(fill="x")
            tk.Label(text, text=f"{event['detail']} - {'Sold' if event['kind'] == 'sale' else 'Added'}", bg=COLORS["card"], fg=COLORS["muted"], font=(FONT, 8), anchor="w").pack(fill="x")
            tk.Label(row, text=money(event["amount"]), bg=COLORS["card"], fg=COLORS["sage_ink"] if event["kind"] == "sale" else COLORS["ink"], font=(FONT, 9, "bold")).pack(side="right")


class CollectionPage(BasePage):
    columns = ("set_number", "title", "theme", "condition", "paid", "value", "status", "notes", "built", "disassembled", "box", "instructions")

    def __init__(self, parent: tk.Misc, app: BrickLedgerApp) -> None:
        super().__init__(parent, app)
        header_row = tk.Frame(self, bg=COLORS["paper"])
        header_row.pack(fill="x")
        header = title_block(header_row, "The catalogue", "Every brick has a place.", "Keep a clear, sellable record of the sets in your orbit.")
        header.pack(side="left", anchor="nw")
        actions = tk.Frame(header_row, bg=COLORS["paper"])
        actions.pack(side="right", anchor="ne", pady=(13, 0))
        button(actions, "+ Add a set", self.add_set).pack(side="left", padx=(0, 8))
        self.edit_button = button(actions, "Edit", self.edit_selected, "soft")
        self.edit_button.pack(side="left")
        self.sold_button = button(actions, "Mark sold", self.mark_selected_sold, "ink")
        self.sold_button.pack(side="left", padx=(8, 0))
        self.delete_button = button(actions, "Delete", self.delete_selected, "danger")
        self.delete_button.pack(side="left", padx=(8, 0))

        section_bar = tk.Frame(self, bg=COLORS["paper"])
        section_bar.pack(fill="x", pady=(18, 0))
        self.section_buttons: dict[str, tk.Button] = {}
        for status, accent, detail in (
            ("Keeping", COLORS["sage"], "Sets staying in your collection"),
            ("For sale", COLORS["yellow"], "Sets ready to move on"),
        ):
            section = tk.Button(
                section_bar, text="", command=lambda value=status: self.select_section(value),
                justify="left", anchor="w", bg=COLORS["card"], fg=COLORS["ink"], activebackground=COLORS["hover"],
                activeforeground=COLORS["ink"], relief="flat", bd=0, cursor="hand2", padx=17, pady=13,
                font=(FONT, 10, "bold"), highlightthickness=1, highlightbackground=COLORS["line"],
            )
            section.pack(side="left", fill="x", expand=True, padx=(0, 7) if status == "Keeping" else (7, 0))
            self.section_buttons[status] = section
            section._accent = accent  # type: ignore[attr-defined]
            section._detail = detail  # type: ignore[attr-defined]

        toolbar = tk.Frame(self, bg=COLORS["paper"])
        toolbar.pack(fill="x", pady=(15, 13))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.load_rows())
        search_shell = tk.Frame(toolbar, bg=COLORS["card"], highlightthickness=1, highlightbackground=COLORS["line"])
        search_shell.pack(side="left")
        tk.Label(search_shell, text="Search", bg=COLORS["card"], fg=COLORS["muted"], font=(FONT, 13)).pack(side="left", padx=(10, 3))
        search = tk.Entry(search_shell, textvariable=self.search_var, bg=COLORS["card"], fg=COLORS["ink"], insertbackground=COLORS["ink"], relief="flat", font=(FONT, 10), width=34, highlightthickness=0)
        search.pack(side="left", ipady=9, padx=(0, 5))
        self.status_var = tk.StringVar(value="All")
        status = ttk.Combobox(toolbar, textvariable=self.status_var, values=("All", "Keeping", "For sale", "Parting out", "Sold"), width=13, state="readonly")
        status.pack(side="left", padx=10)
        status.bind("<<ComboboxSelected>>", lambda _event: self.load_rows())
        self.count_label = tk.Label(toolbar, text="", bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 9))
        self.count_label.pack(side="right", pady=8)

        table_card = tk.Frame(self, bg=COLORS["card"], highlightbackground=COLORS["line"], highlightthickness=1)
        table_card.pack(fill="both", expand=True)
        tree_frame = tk.Frame(table_card, bg=COLORS["card"])
        tree_frame.pack(fill="both", expand=True, padx=1, pady=1)
        headings = {"set_number": "SET #", "title": "SET NAME", "theme": "THEME", "condition": "CONDITION", "paid": "PAID", "value": "EST. VALUE", "status": "STATUS", "notes": "NOTES", "built": "BUILT", "disassembled": "DISASSEMBLED", "box": "BOX", "instructions": "INSTRUCTIONS"}
        self.tree = ttk.Treeview(tree_frame, columns=self.columns, show="headings", selectmode="browse")
        widths = {"set_number": 100, "title": 310, "theme": 170, "condition": 110, "paid": 90, "value": 105, "status": 95, "notes": 280, "built": 70, "disassembled": 125, "box": 65, "instructions": 115}
        numeric_columns = {"paid", "value"}
        stretch_columns = {"title", "notes"}
        for column in self.columns:
            anchor = "e" if column in numeric_columns else "w"
            self.tree.heading(column, text=headings[column], anchor=anchor)
            self.tree.column(column, width=widths[column], minwidth=widths[column], anchor=anchor, stretch=column in stretch_columns)
        self.tree.tag_configure("sold", foreground=COLORS["muted"])
        self.tree.tag_configure("complete", background=COLORS["complete"])
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        xscrollbar = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        xscrollbar.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        self.tree.configure(yscrollcommand=scrollbar.set, xscrollcommand=xscrollbar.set)
        self.tree.bind("<Double-1>", lambda _event: self.edit_selected())
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self.update_actions())
        self.update_actions()

    def selected_id(self) -> int | None:
        selected = self.tree.selection()
        return int(selected[0]) if selected else None

    def update_actions(self) -> None:
        item_id = self.selected_id()
        state = "normal" if item_id else "disabled"
        self.edit_button.configure(state=state)
        self.delete_button.configure(state=state)
        sold_state = "disabled"
        if item_id:
            record = self.app.db.get_set(item_id)
            if record and record["status"] != "Sold":
                sold_state = "normal"
        self.sold_button.configure(state=sold_state)

    def add_set(self) -> None:
        SetDialog(self, self.app, on_saved=self.app.refresh_everything)

    def select_section(self, status: str) -> None:
        self.status_var.set(status)
        self.load_rows()

    def refresh_sections(self) -> None:
        for status, section in self.section_buttons.items():
            records = self.app.db.collection(status=status)
            total_value = sum(float(record["estimated_value"]) * int(record["quantity"]) for record in records)
            detail = getattr(section, "_detail")
            accent = getattr(section, "_accent")
            active = self.status_var.get() == status
            section.configure(
                text=f"{status.upper()}\n{len(records)} set{'' if len(records) == 1 else 's'} - {short_money(total_value)}\n{detail}",
                bg=COLORS["success_bg"] if active and status == "Keeping" else COLORS["warning_bg"] if active else COLORS["card"],
                highlightbackground=accent if active else COLORS["line"],
                highlightthickness=2 if active else 1,
            )

    def edit_selected(self) -> None:
        item_id = self.selected_id()
        if item_id:
            SetDialog(self, self.app, item_id=item_id, on_saved=self.app.refresh_everything)

    def mark_selected_sold(self) -> None:
        item_id = self.selected_id()
        record = self.app.db.get_set(item_id) if item_id else None
        if not record:
            return
        if record["status"] == "Sold":
            messagebox.showinfo("Already sold", "This set is already marked as sold.", parent=self)
            return
        SaleDialog(self, self.app, selected_collection_id=item_id, selected_record=record, on_saved=self.app.refresh_everything)

    def delete_selected(self) -> None:
        item_id = self.selected_id()
        record = self.app.db.get_set(item_id) if item_id else None
        if not record:
            return
        if messagebox.askyesno("Remove set", f"Remove {record['set_number']} - {record['title']} from your catalogue\n\nSales history will be retained.", parent=self):
            self.app.db.delete_set(item_id)
            self.app.refresh_everything()

    def load_rows(self) -> None:
        if not hasattr(self, "tree"):
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        rows = self.app.db.collection(self.search_var.get(), self.status_var.get())
        for row in rows:
            tags = []
            if row["condition"] == "Complete":
                tags.append("complete")
            if row["status"] == "Sold":
                tags.append("sold")
            notes = " ".join(str(row["notes"] or "").split())
            built = "Built" if int(row["built"] or 0) else ""
            disassembled = "Disassembled" if int(row["disassembled"] or 0) else ""
            box = "Box" if int(row["has_box"] or 0) else ""
            instructions = "Instructions" if int(row["has_instructions"] or 0) else ""
            self.tree.insert(
                "", "end", iid=str(row["id"]), tags=tuple(tags),
                values=(row["set_number"], row["title"], row["theme"] or "-", row["condition"], money(row["purchase_price"]), money(row["estimated_value"]), row["status"], notes, built, disassembled, box, instructions),
            )
        self.count_label.configure(text=f"{len(rows)} set record{'' if len(rows) == 1 else 's'}")
        self.refresh_sections()
        self.update_actions()

    def refresh(self) -> None:
        self.refresh_sections()
        self.load_rows()


class SalesPage(BasePage):
    columns = ("sold_on", "set", "platform", "sold_price", "costs", "net")

    def __init__(self, parent: tk.Misc, app: BrickLedgerApp) -> None:
        super().__init__(parent, app)
        header_row = tk.Frame(self, bg=COLORS["paper"])
        header_row.pack(fill="x")
        header = title_block(header_row, "The selling desk", "Turn value into momentum.", "Record the full cost of each sale, so the number you keep is always the one you see.")
        header.pack(side="left", anchor="nw")
        actions = tk.Frame(header_row, bg=COLORS["paper"])
        actions.pack(side="right", anchor="ne", pady=(13, 0))
        button(actions, "+ Record a sale", self.record_sale).pack(side="left")
        self.edit_sale_button = button(actions, "Edit sale", self.edit_selected_sale, "soft")
        self.edit_sale_button.pack(side="left", padx=(8, 0))
        self.delete_sale_button = button(actions, "Delete sale", self.delete_selected_sale, "danger")
        self.delete_sale_button.pack(side="left", padx=(8, 0))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh())

        strip = tk.Frame(self, bg=COLORS["ink"])
        strip.pack(fill="x", pady=(29, 15))
        strip_inner = tk.Frame(strip, bg=COLORS["ink"])
        strip_inner.pack(fill="x", padx=22, pady=15)
        self.sales_stat = tk.Label(strip_inner, text="", bg=COLORS["ink"], fg="#FFFFFF", font=(FONT, 15, "bold"))
        self.sales_stat.pack(side="left")
        self.sales_note = tk.Label(strip_inner, text="", bg=COLORS["ink"], fg=COLORS["nav_muted"], font=(FONT, 10))
        self.sales_note.pack(side="left", padx=17)

        toolbar = tk.Frame(self, bg=COLORS["paper"])
        toolbar.pack(fill="x", pady=(0, 12))
        search_shell = tk.Frame(toolbar, bg=COLORS["card"], highlightthickness=1, highlightbackground=COLORS["line"])
        search_shell.pack(side="left")
        tk.Label(search_shell, text="Search", bg=COLORS["card"], fg=COLORS["muted"], font=(FONT, 13)).pack(side="left", padx=(10, 3))
        search = tk.Entry(search_shell, textvariable=self.search_var, bg=COLORS["card"], fg=COLORS["ink"], insertbackground=COLORS["ink"], relief="flat", font=(FONT, 10), width=38, highlightthickness=0)
        search.pack(side="left", ipady=9, padx=(0, 5))

        table_card = tk.Frame(self, bg=COLORS["card"], highlightbackground=COLORS["line"], highlightthickness=1)
        table_card.pack(fill="both", expand=True)
        tree_frame = tk.Frame(table_card, bg=COLORS["card"])
        tree_frame.pack(fill="both", expand=True, padx=1, pady=1)
        headings = {"sold_on": "SOLD", "set": "SET", "platform": "PLATFORM", "sold_price": "SOLD FOR", "costs": "COST", "net": "YOU KEPT"}
        self.tree = ttk.Treeview(tree_frame, columns=self.columns, show="headings", selectmode="browse")
        widths = {"sold_on": 110, "set": 275, "platform": 130, "sold_price": 115, "costs": 140, "net": 120}
        for column in self.columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor="e" if column in {"sold_price", "costs", "net"} else "w", stretch=column == "set")
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self.update_edit_state())
        self.tree.bind("<Double-1>", lambda _event: self.edit_selected_sale())
        self.update_edit_state()

    def selected_sale_id(self) -> int | None:
        selected = self.tree.selection()
        return int(selected[0]) if selected else None

    def update_edit_state(self) -> None:
        state = "normal" if self.selected_sale_id() else "disabled"
        self.edit_sale_button.configure(state=state)
        self.delete_sale_button.configure(state=state)

    def record_sale(self) -> None:
        SaleDialog(self, self.app, on_saved=self.app.refresh_everything)

    def edit_selected_sale(self) -> None:
        sale_id = self.selected_sale_id()
        sale = self.app.db.get_sale(sale_id) if sale_id else None
        if not sale:
            return
        EditSaleDialog(self, self.app, sale, on_saved=self.app.refresh_everything)

    def delete_selected_sale(self) -> None:
        sale_id = self.selected_sale_id()
        sale = self.app.db.get_sale(sale_id) if sale_id else None
        if not sale:
            return
        label = f"{sale['set_number']} - {sale['title']}" if sale["title"] else "Standalone sale"
        if not messagebox.askyesno(
            "Delete sale",
            f"Delete this sale?\n\n{label}\n{money(sale['sold_price'])}",
            parent=self,
        ):
            return
        self.app.db.delete_sale(sale_id)
        self.app.refresh_everything()

    def refresh(self) -> None:
        rows = self.app.db.sales()
        query = self.search_var.get().strip().casefold() if hasattr(self, "search_var") else ""
        if query:
            rows = [row for row in rows if self._sale_matches(row, query)]
        for item in self.tree.get_children():
            self.tree.delete(item)
        gross = 0.0
        net = 0.0
        for row in rows:
            costs = float(row["fees"]) + float(row["shipping"])
            kept = float(row["sold_price"]) - costs
            gross += float(row["sold_price"])
            net += kept
            title = f"{row['set_number']} - {row['title']}" if row["title"] else "Standalone sale"
            self.tree.insert("", "end", iid=str(row["id"]), values=(row["sold_on"], title, row["platform"], money(row["sold_price"]), money(costs), money(kept)))
        self.sales_stat.configure(text=f"{money(net)} net proceeds")
        suffix = "" if len(rows) == 1 else "s"
        self.sales_note.configure(text=f"{len(rows)} sale{suffix} - {money(gross)} gross revenue")
        self.update_edit_state()

    def _sale_matches(self, row: Any, query: str) -> bool:
        fields = (
            row["sold_on"], row["set_number"], row["title"], row["platform"],
            row["buyer"], row["notes"], money(row["sold_price"]),
        )
        return any(query in str(value or "").casefold() for value in fields)


class DataPage(BasePage):
    def __init__(self, parent: tk.Misc, app: BrickLedgerApp) -> None:
        super().__init__(parent, app)
        header = title_block(self, "Your local archive", "Data that stays yours.", "Export clean records whenever it is time for accounting, insurance, or a fresh spreadsheet.")
        header.pack(anchor="nw")

        panels = tk.Frame(self, bg=COLORS["paper"])
        panels.pack(fill="x", pady=(31, 16))
        for column in range(2):
            panels.columnconfigure(column, weight=1, uniform="panel")
        collection_card = self._make_export_panel(panels, 0, "Collection catalogue", "Export set records using the settings below.", "Export collection CSV", self.export_collection, COLORS["yellow"])
        self._make_collection_export_settings(collection_card)
        self._make_export_panel(panels, 1, "Sales ledger", "Every sale with fees, postage, platform, and net proceeds.", "Export sales CSV", self.export_sales, COLORS["lavender"])

        importer = tk.Frame(self, bg=COLORS["ink"], highlightbackground=COLORS["ink"], highlightthickness=1)
        importer.pack(fill="x", pady=(0, 10))
        importer_copy = tk.Frame(importer, bg=COLORS["ink"])
        importer_copy.pack(side="left", fill="x", expand=True, padx=21, pady=17)
        tk.Label(importer_copy, text="BRING IN YOUR BRICKECONOMY COLLECTION", bg=COLORS["ink"], fg=COLORS["yellow"], font=(FONT, 8, "bold")).pack(anchor="w")
        tk.Label(importer_copy, text="Preview your Sets export, then choose Keeping or For sale before importing.", bg=COLORS["ink"], fg=COLORS["nav_muted"], font=(FONT, 10)).pack(anchor="w", pady=(4, 0))
        button(importer, "Import BrickEconomy CSV", self.import_brickeconomy).pack(side="right", padx=21, pady=21)

        sales_importer = tk.Frame(self, bg=COLORS["card"], highlightbackground=COLORS["line"], highlightthickness=1)
        sales_importer.pack(fill="x", pady=(0, 16))
        sales_copy = tk.Frame(sales_importer, bg=COLORS["card"])
        sales_copy.pack(side="left", fill="x", expand=True, padx=21, pady=17)
        tk.Label(sales_copy, text="IMPORT YOUR SOLD SET SPREADSHEET", bg=COLORS["card"], fg=COLORS["brick"], font=(FONT, 8, "bold")).pack(anchor="w")
        tk.Label(sales_copy, text="Reads the MAIN sheet with set name, set number, purchase price, selling price, net profit, condition, and notes.", bg=COLORS["card"], fg=COLORS["ink"], font=(FONT, 10)).pack(anchor="w", pady=(4, 0))
        button(sales_importer, "Import Excel sales", self.import_personal_spreadsheet, "ink").pack(side="right", padx=21, pady=21)

        source = tk.Frame(self, bg=COLORS["card"], highlightbackground=COLORS["line"], highlightthickness=1)
        source.pack(fill="x", pady=(3, 0))
        tk.Label(source, text="LOCAL DATABASE", bg=COLORS["card"], fg=COLORS["muted"], font=(FONT, 8, "bold")).pack(anchor="w", padx=21, pady=(19, 3))
        tk.Label(source, text="BrickLedger stores your records in one portable SQLite file.", bg=COLORS["card"], fg=COLORS["ink"], font=(FONT, 12, "bold")).pack(anchor="w", padx=21)
        self.path_label = tk.Label(source, text="", bg=COLORS["card"], fg=COLORS["muted"], font=(FONT, 9))
        self.path_label.pack(anchor="w", padx=21, pady=(5, 16))
        row = tk.Frame(source, bg=COLORS["card"])
        row.pack(fill="x", padx=21, pady=(0, 20))
        button(row, "Open data folder", self.open_data_folder, "soft").pack(side="left")

    def _make_export_panel(self, parent: tk.Misc, column: int, title: str, copy: str, action: str, command: Callable[[], None], accent: str) -> tk.Frame:
        card = tk.Frame(parent, bg=COLORS["card"], highlightbackground=COLORS["line"], highlightthickness=1)
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 8) if column == 0 else (8, 0))
        tk.Frame(card, bg=accent, height=5).pack(fill="x")
        tk.Label(card, text=title, bg=COLORS["card"], fg=COLORS["ink"], font=(FONT, 13, "bold")).pack(anchor="w", padx=21, pady=(19, 5))
        tk.Label(card, text=copy, bg=COLORS["card"], fg=COLORS["muted"], font=(FONT, 9), justify="left", wraplength=315).pack(anchor="w", padx=21)
        button(card, action, command, "ink").pack(anchor="w", padx=21, pady=(20, 20))
        return card

    def _make_collection_export_settings(self, card: tk.Misc) -> None:
        settings = tk.Frame(card, bg=COLORS["card"])
        settings.pack(fill="x", padx=21, pady=(0, 18))
        tk.Label(settings, text="EXPORT SETTINGS", bg=COLORS["card"], fg=COLORS["muted"], font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 4))
        self.export_search_var = tk.StringVar()
        self.export_status_var = tk.StringVar(value="All")
        self.export_condition_var = tk.StringVar(value="All")
        self.export_built_var = tk.StringVar(value="All")
        self.export_sort_var = tk.StringVar(value="Status then A-Z")
        rows = (
            ("Search", self.export_search_var, None),
            ("Status", self.export_status_var, ("All", "Keeping", "For sale", "Parting out", "Sold")),
            ("Condition", self.export_condition_var, ("All", "New", "Sealed", "Complete", "Used", "Incomplete")),
            ("Built", self.export_built_var, ("All", "Built", "Not built")),
            ("Sort", self.export_sort_var, ("Status then A-Z", "Theme A-Z", "Alphabetical A-Z", "Alphabetical Z-A", "Highest value", "Lowest value", "Newest added", "Oldest added")),
        )
        for index, (label, variable, values) in enumerate(rows):
            row = tk.Frame(settings, bg=COLORS["card"])
            row.pack(fill="x", pady=(7 if index else 4, 0))
            tk.Label(row, text=label.upper(), bg=COLORS["card"], fg=COLORS["muted"], font=(FONT, 8, "bold"), width=10, anchor="w").pack(side="left")
            if values is None:
                field = tk.Entry(row, textvariable=variable, bg=COLORS["paper"], fg=COLORS["ink"], insertbackground=COLORS["ink"], relief="flat", font=(FONT, 9), highlightthickness=1, highlightbackground=COLORS["line"], highlightcolor=COLORS["blue_ink"])
                field.pack(side="left", fill="x", expand=True, ipady=5)
            else:
                field = ttk.Combobox(row, textvariable=variable, values=values, state="readonly")
                field.pack(side="left", fill="x", expand=True)

        tk.Label(settings, text="INCLUDE COLUMNS", bg=COLORS["card"], fg=COLORS["muted"], font=(FONT, 8, "bold")).pack(anchor="w", pady=(13, 4))
        column_grid = tk.Frame(settings, bg=COLORS["card"])
        column_grid.pack(fill="x")
        self.export_column_vars: dict[str, tk.BooleanVar] = {}
        columns = (
            ("set_number", "Set #"),
            ("title", "Set name"),
            ("theme", "Theme"),
            ("condition", "Condition"),
            ("purchase_price", "Paid"),
            ("estimated_value", "Value"),
            ("status", "Status"),
            ("notes", "Notes"),
            ("built", "Built"),
            ("disassembled", "Disassembled"),
            ("has_box", "Box"),
            ("has_instructions", "Instructions"),
            ("created_at", "Date added"),
        )
        for index, (key, label) in enumerate(columns):
            var = tk.BooleanVar(value=True)
            self.export_column_vars[key] = var
            check = tk.Checkbutton(
                column_grid, text=label, variable=var, bg=COLORS["card"], fg=COLORS["ink"],
                activebackground=COLORS["card"], activeforeground=COLORS["ink"],
                selectcolor=COLORS["paper"], font=(FONT, 9), relief="flat", anchor="w",
            )
            check.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 10), pady=1)
        for column in range(2):
            column_grid.columnconfigure(column, weight=1)

        quick = tk.Frame(settings, bg=COLORS["card"])
        quick.pack(fill="x", pady=(8, 0))
        tiny = (FONT, 8, "bold")
        select_all = button(quick, "Select all", lambda: self._set_export_columns(True), "soft")
        select_all.configure(font=tiny, padx=9, pady=6)
        select_all.pack(side="left")
        hide_prices = button(quick, "Hide prices", self._hide_export_prices, "soft")
        hide_prices.configure(font=tiny, padx=9, pady=6)
        hide_prices.pack(side="left", padx=(7, 0))

    def _set_export_columns(self, selected: bool) -> None:
        for variable in self.export_column_vars.values():
            variable.set(selected)

    def _hide_export_prices(self) -> None:
        for key in ("purchase_price", "estimated_value"):
            self.export_column_vars[key].set(False)

    def _destination(self, initial_name: str) -> Path | None:
        selected = filedialog.asksaveasfilename(
            parent=self, title="Save CSV export", initialdir=EXPORTS_PATH, initialfile=initial_name,
            defaultextension=".csv", filetypes=[("CSV file", "*.csv")],
        )
        return Path(selected) if selected else None

    def export_collection(self) -> None:
        target = self._destination(f"brickledger-collection-{datetime.now():%Y-%m-%d}.csv")
        if target:
            columns = [key for key, variable in self.export_column_vars.items() if variable.get()]
            if not columns:
                messagebox.showerror("Choose columns", "Select at least one column to include in the export.", parent=self)
                return
            count = self.app.db.export_collection(
                target,
                query=self.export_search_var.get(),
                status=self.export_status_var.get(),
                condition=self.export_condition_var.get(),
                built=self.export_built_var.get(),
                sort=self.export_sort_var.get(),
                columns=columns,
            )
            messagebox.showinfo("Collection exported", f"Saved {count} collection record{'' if count == 1 else 's'} to:\n{target}", parent=self)

    def export_sales(self) -> None:
        target = self._destination(f"brickledger-sales-{datetime.now():%Y-%m-%d}.csv")
        if target:
            self.app.db.export_sales(target)
            messagebox.showinfo("Sales exported", f"Saved sales export to:\n{target}", parent=self)


    def import_personal_spreadsheet(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self, title="Choose your LEGO sales spreadsheet", initialdir=Path.home() / "Desktop",
            filetypes=[("Excel workbook", "*.xlsx"), ("All files", "*.*")],
        )
        if not selected:
            return
        try:
            batch = read_main_sales_spreadsheet(selected)
        except Exception as error:
            messagebox.showerror("Spreadsheet import failed", str(error), parent=self)
            return
        if not batch.records:
            messagebox.showinfo("No sales to import", "No valid sold set records were found in the MAIN sheet.", parent=self)
            return
        skipped = (
            f"\n\nSkipped {batch.skipped_rows} blank or incomplete row{'s' if batch.skipped_rows != 1 else ''}."
            if batch.skipped_rows else ""
        )
        confirm = messagebox.askyesno(
            "Import spreadsheet sales",
            f"Import {len(batch.records)} sold set record{'s' if len(batch.records) != 1 else ''} from MAIN\n\n"
            "Each row will be added as a sold collection item and linked sale."
            f"{skipped}",
            parent=self,
        )
        if not confirm:
            return
        try:
            count = self.app.db.import_spreadsheet_sales(batch.records, self.app.db.today())
        except Exception as error:
            messagebox.showerror("Spreadsheet import failed", str(error), parent=self)
            return
        self.app.refresh_everything()
        messagebox.showinfo("Spreadsheet sales imported", f"Imported {count} sold set record{'s' if count != 1 else ''}.", parent=self)

    def import_brickeconomy(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self, title="Choose a BrickEconomy Sets export", initialdir=Path.home() / "Downloads",
            filetypes=[("BrickEconomy CSV", "*.csv"), ("All files", "*.*")],
        )
        if not selected:
            return
        try:
            batch = read_collection_csv(selected)
        except (OSError, ValueError, UnicodeError) as error:
            messagebox.showerror("Could not read CSV", str(error), parent=self)
            return
        if not batch.records:
            messagebox.showinfo("No sets to import", "No valid set records were found in that file.", parent=self)
            return
        BrickEconomyImportDialog(self, self.app, Path(selected), batch)

    def open_data_folder(self) -> None:
        folder = str(EXPORTS_PATH.parent / "data")
        try:
            if os.name == "nt":
                os.startfile(folder)  # type: ignore[attr-defined]
            else:
                messagebox.showinfo("Data folder", folder, parent=self)
        except OSError as error:
            messagebox.showerror("Could not open folder", str(error), parent=self)

    def refresh(self) -> None:
        self.path_label.configure(text=str(self.app.db.connection.execute("PRAGMA database_list").fetchone()[2]))


class BrickEconomyImportDialog(tk.Toplevel):
    """Review a BrickEconomy CSV and explicitly choose its collection status."""

    columns = ("set_number", "title", "theme", "condition", "paid", "value")

    def __init__(self, parent: tk.Misc, app: BrickLedgerApp, source_path: Path, batch: ImportBatch) -> None:
        super().__init__(parent)
        self.app = app
        self.source_path = source_path
        self.batch = batch
        self.status_var = tk.StringVar(value="Keeping")
        self.title("Review BrickEconomy import - BrickLedger")
        self.configure(bg=COLORS["paper"])
        make_toplevel_window_resizable(self, 900, 620, maximize=True)
        self.grab_set()
        self._build()
        self.bind("<Escape>", lambda _event: self.destroy())

    def _build(self) -> None:
        head = tk.Frame(self, bg=COLORS["ink"])
        head.pack(fill="x")
        tk.Label(head, text="BRICKECONOMY IMPORT", bg=COLORS["ink"], fg=COLORS["yellow"], font=(FONT, 8, "bold")).pack(anchor="w", padx=22, pady=(15, 2))
        tk.Label(head, text="Review before the sets join your ledger.", bg=COLORS["ink"], fg="#FFFFFF", font=(FONT, 16, "bold")).pack(anchor="w", padx=22, pady=(0, 15))

        summary = tk.Frame(self, bg=COLORS["paper"])
        summary.pack(fill="x", padx=22, pady=(13, 8))
        tk.Label(summary, text=f"{self.source_path.name}  |  {len(self.batch.records)} valid set record{'s' if len(self.batch.records) != 1 else ''}", bg=COLORS["paper"], fg=COLORS["ink"], font=(FONT, 10, "bold")).pack(anchor="w")
        if self.batch.skipped_rows:
            tk.Label(summary, text=f"{self.batch.skipped_rows} blank or incomplete row{'s were' if self.batch.skipped_rows != 1 else ' was'} skipped.", bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 9)).pack(anchor="w", pady=(3, 0))

        preview = tk.Frame(self, bg=COLORS["card"], highlightbackground=COLORS["line"], highlightthickness=1)
        preview.pack(fill="both", expand=True, padx=22, pady=(0, 11))
        tree_frame = tk.Frame(preview, bg=COLORS["card"])
        tree_frame.pack(fill="both", expand=True, padx=1, pady=1)
        headings = {"set_number": "SET #", "title": "SET NAME", "theme": "THEME", "condition": "CONDITION", "paid": "PAID", "value": "VALUE"}
        tree = ttk.Treeview(tree_frame, columns=self.columns, show="headings", selectmode="none", height=18)
        widths = {"set_number": 105, "title": 270, "theme": 140, "condition": 115, "paid": 90, "value": 90}
        for column in self.columns:
            tree.heading(column, text=headings[column])
            tree.column(column, width=widths[column], anchor="e" if column in {"paid", "value"} else "w", stretch=column == "title")
        for record in self.batch.records:
            tree.insert("", "end", values=(record.set_number, record.title, record.theme or "-", record.condition, money(record.purchase_price), money(record.estimated_value)))
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        xscrollbar = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        xscrollbar.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        tree.configure(yscrollcommand=scrollbar.set, xscrollcommand=xscrollbar.set)

        decision = tk.Frame(self, bg=COLORS["paper"])
        decision.pack(fill="x", padx=22, pady=(0, 9))
        tk.Label(decision, text="IMPORT EVERY SET AS", bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 5))
        choices = tk.Frame(decision, bg=COLORS["paper"])
        choices.pack(fill="x")
        for value, label, detail in (("Keeping", "Keeping", "Add to your personal collection"), ("For sale", "For sale", "Mark every imported set ready to sell")):
            choice = tk.Radiobutton(
                choices, text=f"{label} - {detail}", value=value, variable=self.status_var,
                command=self.update_import_label, bg=COLORS["paper"], fg=COLORS["ink"], activebackground=COLORS["paper"],
                activeforeground=COLORS["ink"], selectcolor=COLORS["card"], font=(FONT, 10),
                anchor="w", padx=3,
            )
            choice.pack(side="left", padx=(0, 24))

        footer = tk.Frame(self, bg=COLORS["paper"])
        footer.pack(fill="x", padx=22, pady=(0, 17))
        tk.Label(footer, text="Theme, paid price, value, condition, and notes will be preserved.", bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 9)).pack(side="left")
        button(footer, "Cancel", self.destroy, "soft").pack(side="right")
        self.import_button = button(footer, "", self.import_records)
        self.import_button.pack(side="right", padx=(0, 8))
        self.update_import_label()
        self.geometry("1180x760")

    def update_import_label(self) -> None:
        self.import_button.configure(text=f"Import as {self.status_var.get()}")

    def import_records(self) -> None:
        status = self.status_var.get()
        count = self.app.db.add_sets(
            {
                "set_number": record.set_number,
                "title": record.title,
                "theme": record.theme,
                "condition": record.condition,
                "quantity": 1,
                "purchase_price": record.purchase_price,
                "estimated_value": record.estimated_value,
                "status": status,
                "notes": record.notes,
                "built": 0,
                "disassembled": 0,
                "has_box": 0,
                "has_instructions": 0,
            }
            for record in self.batch.records
        )
        self.app.refresh_everything()
        messagebox.showinfo("Import complete", f"Imported {count} set record{'s' if count != 1 else ''} as {status}.", parent=self)
        self.destroy()


class CatalogPicker(tk.Toplevel):
    """Search and choose from the user's included Sets catalogue."""

    columns = ("set_number", "name", "theme", "year", "parts")

    def __init__(self, parent: tk.Misc, catalog: OfflineCatalog, on_pick: Callable[[CatalogSet], None]) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.on_pick = on_pick
        self.results: dict[str, CatalogSet] = {}
        self.title("Choose a set - BrickLedger")
        self.configure(bg=COLORS["paper"])
        self.geometry("930x610")
        self.minsize(760, 480)
        make_toplevel_window_resizable(self, 760, 480)
        self.grab_set()
        self.query_var = tk.StringVar()
        self.theme_var = tk.StringVar(value="All themes")
        self._build()
        self.load_results()
        self.bind("<Escape>", lambda _event: self.destroy())

    def _build(self) -> None:
        head = tk.Frame(self, bg=COLORS["ink"])
        head.pack(fill="x")
        tk.Label(head, text="OFFLINE SET CATALOGUE", bg=COLORS["ink"], fg=COLORS["yellow"], font=(FONT, 8, "bold")).pack(anchor="w", padx=24, pady=(18, 2))
        tk.Label(head, text="Choose a set from your Sets folder.", bg=COLORS["ink"], fg="#FFFFFF", font=(FONT, 17, "bold")).pack(anchor="w", padx=24, pady=(0, 18))

        controls = tk.Frame(self, bg=COLORS["paper"])
        controls.pack(fill="x", padx=24, pady=(19, 11))
        tk.Label(controls, text="SEARCH", bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 8, "bold")).pack(side="left", padx=(0, 6))
        query = tk.Entry(controls, textvariable=self.query_var, bg=COLORS["card"], fg=COLORS["ink"], insertbackground=COLORS["ink"], relief="flat", font=(FONT, 10), width=36, highlightthickness=1, highlightbackground=COLORS["line"], highlightcolor=COLORS["blue_ink"])
        query.pack(side="left", ipady=8)
        tk.Label(controls, text="THEME", bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 8, "bold")).pack(side="left", padx=(14, 6))
        themes = ("All themes", *self.catalog.themes())
        theme = ttk.Combobox(controls, textvariable=self.theme_var, values=themes, state="readonly", width=22)
        theme.pack(side="left")
        self.count_label = tk.Label(controls, text="", bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 9))
        self.count_label.pack(side="right")
        self.query_var.trace_add("write", lambda *_: self.load_results())
        theme.bind("<<ComboboxSelected>>", lambda _event: self.load_results())

        table = tk.Frame(self, bg=COLORS["card"], highlightbackground=COLORS["line"], highlightthickness=1)
        table.pack(fill="both", expand=True, padx=24, pady=(0, 14))
        tree_frame = tk.Frame(table, bg=COLORS["card"])
        tree_frame.pack(fill="both", expand=True, padx=1, pady=1)
        headings = {"set_number": "SET #", "name": "SET NAME", "theme": "THEME", "year": "YEAR", "parts": "PARTS"}
        self.tree = ttk.Treeview(tree_frame, columns=self.columns, show="headings", selectmode="browse")
        widths = {"set_number": 110, "name": 340, "theme": 190, "year": 75, "parts": 85}
        for column in self.columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor="e" if column in {"year", "parts"} else "w", stretch=column == "name")
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self.update_choose_state())
        self.tree.bind("<Double-1>", lambda _event: self.choose())

        footer = tk.Frame(self, bg=COLORS["paper"])
        footer.pack(fill="x", padx=24, pady=(0, 21))
        tk.Label(footer, text="Showing up to 250 results. Search by set number, name, or theme.", bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 9)).pack(side="left")
        button(footer, "Cancel", self.destroy, "soft").pack(side="right")
        self.choose_button = button(footer, "Use selected set", self.choose)
        self.choose_button.pack(side="right", padx=(0, 8))
        self.choose_button.configure(state="disabled")

    def load_results(self) -> None:
        rows = self.catalog.search(self.query_var.get(), self.theme_var.get())
        self.results = {row.set_number: row for row in rows}
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in rows:
            self.tree.insert("", "end", iid=row.set_number, values=(row.set_number, row.name, row.theme or "-", row.year or "-", row.parts or "-"))
        suffix = "" if len(rows) == 1 else "s"
        self.count_label.configure(text=f"{len(rows)} match{suffix}")
        self.update_choose_state()

    def update_choose_state(self) -> None:
        self.choose_button.configure(state="normal" if self.tree.selection() else "disabled")

    def choose(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        record = self.results.get(selected[0])
        if record:
            self.on_pick(record)
            self.destroy()


class SetDialog(tk.Toplevel):
    """Add or edit a collection record."""

    def __init__(self, parent: tk.Misc, app: BrickLedgerApp, item_id: int | None = None, on_saved: Callable[[], None] | None = None) -> None:
        super().__init__(parent)
        self.app = app
        self.item_id = item_id
        self.on_saved = on_saved
        self.record = app.db.get_set(item_id) if item_id else None
        self.catalog = app.catalog
        self.title("Edit set" if self.record else "Add a set")
        self.configure(bg=COLORS["paper"])
        make_toplevel_window_resizable(self, 760, 560)
        self.grab_set()
        self.vars: dict[str, tk.StringVar] = {}
        self.built_var = tk.BooleanVar(value=bool(int(self._value("built", 0))))
        self.disassembled_var = tk.BooleanVar(value=bool(int(self._value("disassembled", 0))))
        self.box_var = tk.BooleanVar(value=bool(int(self._value("has_box", 0))))
        self.instructions_var = tk.BooleanVar(value=bool(int(self._value("has_instructions", 0))))
        self._build()
        self.bind("<Escape>", lambda _event: self.destroy())
        self.after(50, lambda: self.focus_force())

    def _value(self, key: str, fallback: Any = "") -> str:
        return str(self.record[key]) if self.record is not None and self.record[key] is not None else str(fallback)

    def _build(self) -> None:
        head = tk.Frame(self, bg=COLORS["ink"])
        head.pack(fill="x")
        heading_copy = tk.Frame(head, bg=COLORS["ink"])
        heading_copy.pack(side="left", fill="x", expand=True, padx=26, pady=(14, 14))
        tk.Label(heading_copy, text="SET CARD", bg=COLORS["ink"], fg=COLORS["yellow"], font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 2))
        heading = "Edit the details that matter." if self.record else "Add a set to your ledger."
        tk.Label(heading_copy, text=heading, bg=COLORS["ink"], fg="#FFFFFF", font=(FONT, 17, "bold")).pack(anchor="w")
        button(head, "Cancel", self.destroy, "soft").pack(side="right", padx=(0, 7), pady=18)
        button(head, "Save changes" if self.record else "Add set", self.save).pack(side="right", padx=(0, 7), pady=18)
        form = tk.Frame(self, bg=COLORS["paper"])
        form.pack(fill="both", expand=True, padx=26, pady=12)
        for column in range(2):
            form.columnconfigure(column, weight=1)
        fields = [
            ("set_number", "Set number", ""), ("title", "Set name", ""),
            ("theme", "Theme", ""), ("condition", "Condition", "Used"),
            ("purchase_price", "Purchase price", "0"), ("estimated_value", "Estimated value", "0"),
            ("status", "Collection status", "Keeping"),
        ]
        for index, (key, label, fallback) in enumerate(fields):
            row, column = divmod(index, 2)
            cell = tk.Frame(form, bg=COLORS["paper"])
            cell.grid(row=row, column=column, sticky="ew", padx=(0, 9) if column == 0 else (9, 0), pady=3)
            tk.Label(cell, text=label.upper(), bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 4))
            var = tk.StringVar(value=self._value(key, fallback))
            self.vars[key] = var
            if key == "condition":
                field: tk.Widget = ttk.Combobox(cell, textvariable=var, values=("New", "Sealed", "Complete", "Used", "Incomplete"), state="readonly")
            elif key == "status":
                field = ttk.Combobox(cell, textvariable=var, values=("Keeping", "For sale", "Parting out", "Sold"), state="readonly")
            else:
                field = tk.Entry(cell, textvariable=var, bg=COLORS["card"], fg=COLORS["ink"], insertbackground=COLORS["ink"], relief="flat", font=(FONT, 10), highlightthickness=1, highlightbackground=COLORS["line"], highlightcolor=COLORS["blue_ink"])
            if key == "set_number":
                entry_row = tk.Frame(cell, bg=COLORS["paper"])
                entry_row.pack(fill="x")
                field.pack(in_=entry_row, side="left", fill="x", expand=True, ipady=7)
                lookup = button(entry_row, "Find", self.lookup_catalog, "soft")
                lookup.configure(font=(FONT, 8, "bold"), padx=9, pady=8)
                lookup.pack(side="left", padx=(6, 0))
                browse = button(entry_row, "Browse", self.browse_catalog, "ink")
                browse.configure(font=(FONT, 8, "bold"), padx=9, pady=8)
                browse.pack(side="left", padx=(5, 0))
                self.catalog_status = tk.Label(cell, text="Search the included Sets catalogue", bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 8))
                self.catalog_status.pack(anchor="w", pady=(4, 0))
            else:
                field.pack(fill="x", ipady=7)
        notes_row = tk.Frame(form, bg=COLORS["paper"])
        notes_row.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(5, 1))
        tk.Label(notes_row, text="NOTES", bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 4))
        self.notes = tk.Text(notes_row, height=2, bg=COLORS["card"], fg=COLORS["ink"], insertbackground=COLORS["ink"], relief="flat", font=(FONT, 10), highlightthickness=1, highlightbackground=COLORS["line"], highlightcolor=COLORS["blue_ink"], padx=8, pady=6)
        self.notes.pack(fill="x")
        self.notes.insert("1.0", self._value("notes"))
        checks_row = tk.Frame(form, bg=COLORS["paper"])
        checks_row.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 1))
        for label, variable in (("Built", self.built_var), ("Disassembled", self.disassembled_var), ("Box", self.box_var), ("Instructions", self.instructions_var)):
            tk.Checkbutton(checks_row, text=label, variable=variable, bg=COLORS["paper"], fg=COLORS["ink"], activebackground=COLORS["paper"], activeforeground=COLORS["ink"], selectcolor=COLORS["card"], font=(FONT, 10, "bold"), relief="flat").pack(side="left", padx=(0, 14))
        self.geometry("760x620")

    def lookup_catalog(self) -> None:
        set_number = self.vars["set_number"].get().strip()
        if not set_number:
            messagebox.showinfo("Enter a set number", "Type a set number first, such as 10316-1.", parent=self)
            return
        if not self.catalog.available():
            messagebox.showinfo("Catalogue unavailable", "The Sets folder is not available in this copy of BrickLedger.", parent=self)
            return
        match = self.catalog.lookup(set_number)
        if not match:
            messagebox.showinfo("Not found", f"No local catalogue match was found for {set_number}.", parent=self)
            return
        self.apply_catalog_set(match)

    def browse_catalog(self) -> None:
        if not self.catalog.available():
            messagebox.showinfo("Catalogue unavailable", "The Sets folder is not available in this copy of BrickLedger.", parent=self)
            return
        CatalogPicker(self, self.catalog, self.apply_catalog_set)

    def apply_catalog_set(self, match: CatalogSet) -> None:
        self.vars["set_number"].set(match.set_number)
        self.vars["title"].set(match.name)
        self.vars["theme"].set(match.theme)
        self.catalog_status.configure(text=f"Selected: {match.theme} - {match.year} - {match.parts} parts", fg=COLORS["sage_ink"])

    def save(self) -> None:
        try:
            prices = {key: float(self.vars[key].get().replace("$", "").replace(",", "")) for key in ("purchase_price", "estimated_value")}
        except ValueError:
            messagebox.showerror("Check the numbers", "Prices must be valid numbers.", parent=self)
            return
        if not self.vars["set_number"].get().strip() or not self.vars["title"].get().strip():
            messagebox.showerror("A little more detail", "Set number and set name are required.", parent=self)
            return
        if any(value < 0 for value in prices.values()):
            messagebox.showerror("Check the numbers", "Prices cannot be negative.", parent=self)
            return
        values: dict[str, Any] = {key: variable.get().strip() for key, variable in self.vars.items()}
        values.update(prices)
        values["quantity"] = 1
        values["notes"] = self.notes.get("1.0", "end-1c").strip()
        values["built"] = 1 if self.built_var.get() else 0
        values["disassembled"] = 1 if self.disassembled_var.get() else 0
        values["has_box"] = 1 if self.box_var.get() else 0
        values["has_instructions"] = 1 if self.instructions_var.get() else 0
        if self.item_id:
            self.app.db.update_set(self.item_id, values)
        else:
            self.app.db.add_set(values)
        if self.on_saved:
            self.on_saved()
        self.destroy()


class SaleDialog(tk.Toplevel):
    """Record a sale and calculate its net proceeds before saving it."""

    def __init__(
        self,
        parent: tk.Misc,
        app: BrickLedgerApp,
        selected_collection_id: int | None = None,
        selected_record: Any | None = None,
        on_saved: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.app = app
        self.on_saved = on_saved
        self.selected_collection_id = selected_collection_id
        self.selected_record = selected_record
        self.selected_catalog_set: CatalogSet | None = None
        self.title("Record a sale")
        self.configure(bg=COLORS["paper"])
        make_toplevel_window_resizable(self, 680, 420)
        self.grab_set()
        self._sets = app.db.available_to_sell()
        self.selection_map = {f"{row['set_number']} - {row['title']}": row["id"] for row in self._sets}
        selected_label = self._selected_sale_label()
        self.vars: dict[str, tk.StringVar] = {
            "set": tk.StringVar(value=selected_label),
            "platform": tk.StringVar(value="Facebook Marketplace"),
            "sold_price": tk.StringVar(value="0"),
            "item_cost": tk.StringVar(value=self._default_item_cost(selected_label)),
            "sold_on": tk.StringVar(value=app.db.today()),
        }
        self._build()
        self.bind("<Escape>", lambda _event: self.destroy())
        self.after(50, lambda: self.focus_force())

    def _selected_sale_label(self) -> str:
        if self.selected_record is not None:
            return f"{self.selected_record['set_number']} - {self.selected_record['title']}"
        for label, item_id in self.selection_map.items():
            if item_id == self.selected_collection_id:
                return label
        return "Standalone sale (no set selected)"

    def _default_item_cost(self, selected_label: str) -> str:
        if self.selected_record is not None:
            return f"{float(self.selected_record['purchase_price']):.2f}"
        item_id = self.selection_map.get(selected_label)
        record = self.app.db.get_set(item_id) if item_id else None
        if not record:
            return "0"
        return f"{float(record['purchase_price']):.2f}"

    def _build(self) -> None:
        head = tk.Frame(self, bg=COLORS["ink"])
        head.pack(fill="x")
        tk.Label(head, text="SALE ENTRY", bg=COLORS["ink"], fg=COLORS["yellow"], font=(FONT, 8, "bold")).pack(anchor="w", padx=26, pady=(20, 2))
        tk.Label(head, text="Enter sale price and item cost.", bg=COLORS["ink"], fg="#FFFFFF", font=(FONT, 17, "bold")).pack(anchor="w", padx=26, pady=(0, 20))
        form = tk.Frame(self, bg=COLORS["paper"])
        form.pack(fill="both", expand=True, padx=26, pady=21)
        for column in range(2):
            form.columnconfigure(column, weight=1)
        if self.selected_collection_id is not None:
            set_field = self._field(form, 0, 0, "set", "Which set sold")
            set_field.configure(state="readonly")
        else:
            self._sale_set_field(form, 0, 0)
        self._field(form, 0, 1, "platform", "Platform", combo=("Facebook Marketplace", "eBay"))
        self._field(form, 1, 0, "sold_price", "Sold for")
        self._field(form, 1, 1, "item_cost", "Item cost")
        profit_card = tk.Frame(form, bg=COLORS["success_bg"], highlightbackground=COLORS["sage"], highlightthickness=1)
        profit_card.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 6))
        tk.Label(profit_card, text="PROFIT", bg=COLORS["success_bg"], fg=COLORS["sage_ink"], font=(FONT, 8, "bold")).pack(anchor="w", padx=13, pady=(9, 1))
        self.profit_label = tk.Label(profit_card, text="$0.00", bg=COLORS["success_bg"], fg=COLORS["sage_ink"], font=(FONT, 17, "bold"))
        self.profit_label.pack(anchor="w", padx=13, pady=(0, 10))
        for key in ("sold_price", "item_cost"):
            self.vars[key].trace_add("write", lambda *_: self.update_profit())
        self.update_profit()
        actions = tk.Frame(self, bg=COLORS["paper"])
        actions.pack(fill="x", padx=26, pady=(0, 25))
        button(actions, "Cancel", self.destroy, "soft").pack(side="right")
        button(actions, "Save sale", self.save).pack(side="right", padx=(0, 8))
        self.geometry("680x430")

    def _sale_set_field(self, parent: tk.Misc, row: int, column: int) -> None:
        cell = tk.Frame(parent, bg=COLORS["paper"])
        cell.grid(row=row, column=column, sticky="ew", padx=(0, 9) if column == 0 else (9, 0), pady=6)
        tk.Label(cell, text="WHICH SET SOLD", bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 4))
        row_frame = tk.Frame(cell, bg=COLORS["paper"])
        row_frame.pack(fill="x")
        field = ttk.Combobox(row_frame, textvariable=self.vars["set"], values=("Standalone sale (no set selected)", *self.selection_map.keys()), state="readonly")
        field.pack(side="left", fill="x", expand=True, ipady=4)
        browse = button(row_frame, "Browse", self.browse_catalog_for_sale, "soft")
        browse.configure(font=(FONT, 8, "bold"), padx=9, pady=8)
        browse.pack(side="left", padx=(6, 0))

    def _field(self, parent: tk.Misc, row: int, column: int, key: str, label: str, combo: tuple[str, ...] | None = None) -> tk.Widget:
        cell = tk.Frame(parent, bg=COLORS["paper"])
        cell.grid(row=row, column=column, sticky="ew", padx=(0, 9) if column == 0 else (9, 0), pady=6)
        tk.Label(cell, text=label.upper(), bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 4))
        if combo:
            field: tk.Widget = ttk.Combobox(cell, textvariable=self.vars[key], values=combo, state="readonly")
        else:
            field = tk.Entry(cell, textvariable=self.vars[key], bg=COLORS["card"], fg=COLORS["ink"], insertbackground=COLORS["ink"], relief="flat", font=(FONT, 10), highlightthickness=1, highlightbackground=COLORS["line"], highlightcolor=COLORS["blue_ink"])
        field.pack(fill="x", ipady=7)
        return field

    def browse_catalog_for_sale(self) -> None:
        if not self.app.catalog.available():
            messagebox.showinfo("Catalogue unavailable", "The Sets folder is not available in this copy of BrickLedger.", parent=self)
            return
        CatalogPicker(self, self.app.catalog, self.apply_catalog_sale_set)

    def apply_catalog_sale_set(self, match: CatalogSet) -> None:
        self.selected_catalog_set = match
        self.vars["set"].set(f"{match.set_number} - {match.name}")

    def update_profit(self) -> None:
        try:
            profit = self._amount(self.vars["sold_price"].get()) - self._amount(self.vars["item_cost"].get())
            self.profit_label.configure(text=money(profit), fg=COLORS["sage_ink"] if profit >= 0 else COLORS["danger"])
        except ValueError:
            self.profit_label.configure(text="-", fg=COLORS["danger"])

    def save(self) -> None:
        try:
            sold_price = self._amount(self.vars["sold_price"].get())
            item_cost = self._amount(self.vars["item_cost"].get())
            datetime.strptime(self.vars["sold_on"].get(), "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Check the sale", "Sold for and item cost must be valid amounts.", parent=self)
            return
        if min(sold_price, item_cost) < 0:
            messagebox.showerror("Check the sale", "Sale amounts cannot be negative.", parent=self)
            return
        selected = self.vars["set"].get()
        collection_id = self.selected_collection_id if self.selected_collection_id is not None else self.selection_map.get(selected)
        if collection_id is None and self.selected_catalog_set is not None:
            collection_id = self.app.db.add_set({
                "set_number": self.selected_catalog_set.set_number,
                "title": self.selected_catalog_set.name,
                "theme": self.selected_catalog_set.theme,
                "condition": "Used",
                "quantity": 1,
                "purchase_price": item_cost,
                "estimated_value": sold_price,
                "status": "Sold",
                "notes": "Added from set catalogue while recording sale",
                "built": 0,
                "disassembled": 0,
                "has_box": 0,
                "has_instructions": 0,
            })
        values = {
            "collection_id": collection_id,
            "platform": self.vars["platform"].get(),
            "sold_price": sold_price,
            "fees": item_cost,
            "shipping": 0,
            "sold_on": self.vars["sold_on"].get(),
            "buyer": "",
            "notes": f"Item cost: {money(item_cost)}",
        }
        self.app.db.record_sale(values)
        if self.on_saved:
            self.on_saved()
        self.destroy()

    def _amount(self, value: str) -> float:
        return float(value.replace("$", "").replace(",", "").strip() or 0)

class EditSaleDialog(tk.Toplevel):
    """Edit an existing sale without creating a duplicate sale record."""

    def __init__(self, parent: tk.Misc, app: BrickLedgerApp, sale: Any, on_saved: Callable[[], None] | None = None) -> None:
        super().__init__(parent)
        self.app = app
        self.sale = sale
        self.on_saved = on_saved
        self.title("Edit sale")
        self.configure(bg=COLORS["paper"])
        make_toplevel_window_resizable(self, 680, 440)
        self.grab_set()
        item_cost = float(sale["fees"] or 0) + float(sale["shipping"] or 0)
        self.vars: dict[str, tk.StringVar] = {
            "platform": tk.StringVar(value=sale["platform"] or "Facebook Marketplace"),
            "sold_price": tk.StringVar(value=f"{float(sale['sold_price'] or 0):.2f}"),
            "item_cost": tk.StringVar(value=f"{item_cost:.2f}"),
            "sold_on": tk.StringVar(value=sale["sold_on"] or app.db.today()),
        }
        self._build()
        self.bind("<Escape>", lambda _event: self.destroy())
        self.after(50, lambda: self.focus_force())

    def _build(self) -> None:
        head = tk.Frame(self, bg=COLORS["ink"])
        head.pack(fill="x")
        tk.Label(head, text="EDIT SALE", bg=COLORS["ink"], fg=COLORS["yellow"], font=(FONT, 8, "bold")).pack(anchor="w", padx=26, pady=(20, 2))
        tk.Label(head, text=self._sale_title(), bg=COLORS["ink"], fg="#FFFFFF", font=(FONT, 17, "bold")).pack(anchor="w", padx=26, pady=(0, 20))

        form = tk.Frame(self, bg=COLORS["paper"])
        form.pack(fill="both", expand=True, padx=26, pady=21)
        for column in range(2):
            form.columnconfigure(column, weight=1)

        self._field(form, 0, 0, "platform", "Platform", combo=("Facebook Marketplace", "eBay"))
        self._field(form, 0, 1, "sold_on", "Date sold (YYYY-MM-DD)")
        self._field(form, 1, 0, "sold_price", "Sold for")
        self._field(form, 1, 1, "item_cost", "Item cost")

        profit_card = tk.Frame(form, bg=COLORS["success_bg"], highlightbackground=COLORS["sage"], highlightthickness=1)
        profit_card.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 6))
        tk.Label(profit_card, text="PROFIT", bg=COLORS["success_bg"], fg=COLORS["sage_ink"], font=(FONT, 8, "bold")).pack(anchor="w", padx=13, pady=(9, 1))
        self.profit_label = tk.Label(profit_card, text="$0.00", bg=COLORS["success_bg"], fg=COLORS["sage_ink"], font=(FONT, 17, "bold"))
        self.profit_label.pack(anchor="w", padx=13, pady=(0, 10))
        for key in ("sold_price", "item_cost"):
            self.vars[key].trace_add("write", lambda *_: self.update_profit())
        self.update_profit()

        actions = tk.Frame(self, bg=COLORS["paper"])
        actions.pack(fill="x", padx=26, pady=(0, 25))
        button(actions, "Cancel", self.destroy, "soft").pack(side="right")
        button(actions, "Save changes", self.save, "primary").pack(side="right", padx=(0, 8))
        self.geometry("680x440")

    def _sale_title(self) -> str:
        if self.sale["title"]:
            return f"{self.sale['set_number']} - {self.sale['title']}"
        return "Standalone sale"

    def _field(self, parent: tk.Misc, row: int, column: int, key: str, label: str, combo: tuple[str, ...] | None = None) -> tk.Widget:
        cell = tk.Frame(parent, bg=COLORS["paper"])
        cell.grid(row=row, column=column, sticky="ew", padx=(0, 9) if column == 0 else (9, 0), pady=6)
        tk.Label(cell, text=label.upper(), bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 4))
        if combo:
            field: tk.Widget = ttk.Combobox(cell, textvariable=self.vars[key], values=combo, state="readonly")
        else:
            field = tk.Entry(cell, textvariable=self.vars[key], bg=COLORS["card"], fg=COLORS["ink"], insertbackground=COLORS["ink"], relief="flat", font=(FONT, 10), highlightthickness=1, highlightbackground=COLORS["line"], highlightcolor=COLORS["blue_ink"])
        field.pack(fill="x", ipady=7)
        return field

    def update_profit(self) -> None:
        try:
            profit = self._amount(self.vars["sold_price"].get()) - self._amount(self.vars["item_cost"].get())
            self.profit_label.configure(text=money(profit), fg=COLORS["sage_ink"] if profit >= 0 else COLORS["danger"])
        except ValueError:
            self.profit_label.configure(text="-", fg=COLORS["danger"])

    def save(self) -> None:
        try:
            sold_price = self._amount(self.vars["sold_price"].get())
            item_cost = self._amount(self.vars["item_cost"].get())
            datetime.strptime(self.vars["sold_on"].get(), "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Check the sale", "Sold for, item cost, and sold date must be valid.", parent=self)
            return
        if min(sold_price, item_cost) < 0:
            messagebox.showerror("Check the sale", "Sale amounts cannot be negative.", parent=self)
            return
        self.app.db.update_sale(
            self.sale["id"],
            {
                "platform": self.vars["platform"].get(),
                "sold_price": sold_price,
                "fees": item_cost,
                "shipping": 0,
                "sold_on": self.vars["sold_on"].get(),
                "notes": f"Item cost: {money(item_cost)}",
            },
        )
        if self.on_saved:
            self.on_saved()
        self.destroy()

    def _amount(self, value: str) -> float:
        return float(value.replace("$", "").replace(",", "").strip() or 0)

