"""The BrickLedger desktop interface."""

from __future__ import annotations

import os
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from PIL import ImageTk

from .catalog import (
    CatalogSet,
    OfflineCatalog,
    SPEED_CHAMPIONS_VARIANTS,
    speed_champions_brand,
    speed_champions_variant,
)
from .brickeconomy import ImportBatch, read_collection_csv
from .database import Database, EXPORTS_PATH
from .paths import DATA_PATH
from .images import SetImageCache
from .lego_spreadsheet import read_main_sales_spreadsheet


COLORS = {
    # Hayden Longerich portfolio palette: near-black surfaces and its exact
    # electric chartreuse accent.
    "black": "#070708",
    "ink": "#F4F4F0",
    "ink_soft": "#222225",
    "paper": "#0D0D0F",
    "paper_alt": "#131315",
    "card": "#18181B",
    "line": "#303034",
    "muted": "#99999F",
    "brick": "#D2FF00",
    "brick_dark": "#B8DF00",
    "accent": "#D2FF00",
    "accent_hover": "#BFE800",
    "yellow": "#D2FF00",
    "sage": "#253012",
    "sage_ink": "#D2FF00",
    "blue": "#192629",
    "blue_ink": "#A9DDE5",
    "lavender": "#28212E",
    "lavender_ink": "#D8B7EA",
    "danger": "#FF777D",
    "selection": "#344000",
    "heading": "#202023",
    "hover": "#252528",
    "nav_muted": "#A7A7AD",
    "complete": "#243000",
    "success_bg": "#1C260E",
    "warning_bg": "#27260C",
    "danger_bg": "#32191C",
    "danger_hover": "#482126",
}

FONT = "Segoe UI"
APP_ROOT = Path(__file__).resolve().parent.parent


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
        self._set_app_icon()
        self.db = Database()
        self.catalog = OfflineCatalog()
        self.image_cache = SetImageCache(self)
        self.nav_buttons: dict[str, tk.Button] = {}
        self.pages: dict[str, BasePage] = {}
        self._fullscreen = False
        self._setup_style()
        self._build_shell()
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.exit_fullscreen)
        if os.name == "nt":
            self.after(0, lambda: self.state("zoomed"))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.show_page("Overview")

    def _set_app_icon(self) -> None:
        """Use the BrickLedger logo for this window and every dialog."""
        icon = APP_ROOT / "assets" / "brickledger.ico"
        if os.name == "nt" and not getattr(sys, "frozen", False):
            # Running from `python main.py`: give BrickLedger its own taskbar
            # button and logo instead of grouping under Python. The exe already
            # gets its own button, so it keeps Windows' default grouping.
            try:
                import ctypes

                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BrickLedger.Desktop")
            except (AttributeError, OSError):
                pass
        if os.name == "nt" and icon.is_file():
            try:
                self.iconbitmap(default=str(icon))
            except tk.TclError:
                pass

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
        self.option_add("*TCombobox*Listbox.background", COLORS["card"])
        self.option_add("*TCombobox*Listbox.foreground", COLORS["ink"])
        self.option_add("*TCombobox*Listbox.selectBackground", COLORS["selection"])
        self.option_add("*TCombobox*Listbox.selectForeground", COLORS["ink"])

    def _build_shell(self) -> None:
        navigation = tk.Frame(self, bg=COLORS["black"], width=256)
        navigation.pack(side="left", fill="y")
        navigation.pack_propagate(False)

        brand = tk.Frame(navigation, bg=COLORS["black"])
        brand.pack(fill="x", padx=28, pady=(34, 44))
        mark = tk.Canvas(brand, width=13, height=38, bg=COLORS["black"], highlightthickness=0)
        mark.pack(side="left")
        mark.create_oval(2, 14, 10, 22, fill=COLORS["accent"], outline="")
        identity = tk.Frame(brand, bg=COLORS["black"])
        identity.pack(side="left", padx=(11, 0))
        tk.Label(identity, text="brickledger.", bg=COLORS["black"], fg=COLORS["ink"],
                 font=(FONT, 18, "bold")).pack(anchor="w")
        tk.Label(identity, text="Your collection, considered.", bg=COLORS["black"], fg=COLORS["nav_muted"],
                 font=(FONT, 8)).pack(anchor="w", pady=(1, 0))

        tk.Label(
            navigation, text="LEDGER / 2026", bg=COLORS["black"], fg=COLORS["nav_muted"],
            font=(FONT, 8, "bold"), anchor="w",
        ).pack(fill="x", padx=30, pady=(0, 12))
        nav_items = (
            ("00", "Overview"), ("01", "All Sets"), ("02", "My Collection"),
            ("03", "Boxes & Instructions"), ("04", "Sales"), ("05", "Exports"),
        )
        for number, label in nav_items:
            button = tk.Button(
                navigation, text=f"{number}   {label}", anchor="w", command=lambda name=label: self.show_page(name),
                bg=COLORS["black"], fg=COLORS["nav_muted"], activebackground=COLORS["ink_soft"], activeforeground=COLORS["ink"],
                relief="flat", bd=0, font=(FONT, 10), padx=18, pady=13, cursor="hand2",
            )
            button.pack(fill="x", padx=14, pady=2)
            self.nav_buttons[label] = button

        bottom = tk.Frame(navigation, bg=COLORS["black"])
        bottom.pack(side="bottom", fill="x", padx=30, pady=30)
        tk.Label(bottom, text="LOCAL-FIRST / PRIVATE", bg=COLORS["black"], fg=COLORS["accent"], font=(FONT, 8, "bold")).pack(anchor="w")
        tk.Label(bottom, text="No account. No cloud. Just your sets.", bg=COLORS["black"], fg=COLORS["nav_muted"], font=(FONT, 8)).pack(anchor="w", pady=(6, 0))

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
        from .accessories import AccessoriesPage

        page_type: type[BasePage]
        page_type = {
            "Overview": OverviewPage,
            "All Sets": CollectionPage,
            "My Collection": MyCollectionPage,
            "Boxes & Instructions": AccessoriesPage,
            "Sales": SalesPage,
            "Exports": DataPage,
        }[name]
        for page in self.pages.values():
            page.pack_forget()
        if name not in self.pages:
            self.pages[name] = page_type(self.page_host, self)
        page = self.pages[name]
        page.pack(fill="both", expand=True)
        page.refresh()
        page_number = {"Overview": "00", "All Sets": "01", "My Collection": "02", "Boxes & Instructions": "03", "Sales": "04", "Exports": "05"}[name]
        self.breadcrumb.configure(text=f"{page_number} / {name.upper()}")
        for label, button in self.nav_buttons.items():
            selected = label == name
            button.configure(
                bg=COLORS["accent"] if selected else COLORS["black"],
                fg=COLORS["black"] if selected else COLORS["nav_muted"],
            )

    def refresh_everything(self) -> None:
        for page in self.pages.values():
            page.refresh()

    def toggle_fullscreen(self, _event: tk.Event | None = None) -> str:
        self._fullscreen = not self._fullscreen
        self.attributes("-fullscreen", self._fullscreen)
        return "break"

    def exit_fullscreen(self, _event: tk.Event | None = None) -> str:
        if self._fullscreen:
            self._fullscreen = False
            self.attributes("-fullscreen", False)
        return "break"

    def close(self) -> None:
        self.image_cache.close()
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
        "primary": (COLORS["accent"], COLORS["black"], COLORS["accent_hover"]),
        "ink": (COLORS["black"], COLORS["ink"], COLORS["ink_soft"]),
        "soft": (COLORS["card"], COLORS["ink"], COLORS["hover"]),
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
        header = title_block(header_row, "Your bricks, in focus", "A clearer view of the collection.", "What you own, what you paid, and what is ready to move.")
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
            ("Collection paid", COLORS["yellow"], "What you paid for sets on hand"),
            ("Potential gain", COLORS["sage"], "Value less your cost"),
            ("Ready to sell", COLORS["blue"], "What you paid for active listings"),
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
        activity_body = tk.Frame(activity, bg=COLORS["card"])
        activity_body.pack(fill="both", expand=True, padx=12, pady=12)
        activity_tabs = tk.Frame(activity_body, bg=COLORS["card"])
        activity_tabs.pack(fill="x", pady=(0, 10))
        self.activity_tab_buttons: dict[str, tk.Button] = {}
        for label in ("Recent sales", "Recent movement"):
            tab = tk.Button(
                activity_tabs, text=label, command=lambda selected=label: self.show_activity_tab(selected),
                bg=COLORS["heading"], fg=COLORS["muted"], activebackground=COLORS["selection"],
                activeforeground=COLORS["ink"], relief="flat", bd=0, highlightthickness=0,
                font=(FONT, 9, "bold"), padx=13, pady=9, cursor="hand2",
            )
            tab.pack(side="left", padx=(0, 4))
            self.activity_tab_buttons[label] = tab
        self.activity_content = tk.Frame(activity_body, bg=COLORS["card"])
        self.activity_content.pack(fill="both", expand=True)
        recent_sales = tk.Frame(self.activity_content, bg=COLORS["card"])
        movement = tk.Frame(self.activity_content, bg=COLORS["card"])
        self.activity_tabs = {"Recent sales": recent_sales, "Recent movement": movement}
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
        self.activity_note = tk.Label(movement, bg=COLORS["card"], fg=COLORS["muted"],
                                      font=(FONT, 9), anchor="w")
        self.activity_note.pack(fill="x", padx=8, pady=(0, 10))
        movement_table = tk.Frame(movement, bg=COLORS["card"])
        movement_table.pack(fill="both", expand=True)
        movement_columns = ("date", "action", "set", "details", "amount", "value")
        self.activity_tree = ttk.Treeview(
            movement_table, columns=movement_columns, show="headings", selectmode="browse", height=8
        )
        for key, label, width, anchor, stretch in (
            ("date", "WHEN", 125, "w", False),
            ("action", "MOVE", 65, "w", False),
            ("set", "SET", 210, "w", True),
            ("details", "DETAILS", 290, "w", True),
            ("amount", "PURCHASE / SOLD", 115, "e", False),
            ("value", "VALUE / NET", 105, "e", False),
        ):
            self.activity_tree.heading(key, text=label, anchor=anchor)
            self.activity_tree.column(key, width=width, minwidth=width, anchor=anchor, stretch=stretch)
        self.activity_tree.grid(row=0, column=0, sticky="nsew")
        movement_vertical = ttk.Scrollbar(movement_table, orient="vertical", command=self.activity_tree.yview)
        movement_vertical.grid(row=0, column=1, sticky="ns")
        movement_horizontal = ttk.Scrollbar(movement_table, orient="horizontal", command=self.activity_tree.xview)
        movement_horizontal.grid(row=1, column=0, sticky="ew")
        movement_table.columnconfigure(0, weight=1)
        movement_table.rowconfigure(0, weight=1)
        self.activity_tree.configure(yscrollcommand=movement_vertical.set, xscrollcommand=movement_horizontal.set)
        self.activity_tree.bind("<Double-1>", self.open_recent_movement)
        self.activity_tree.bind("<Return>", self.open_recent_movement)
        self.show_activity_tab("Recent sales")

    def show_activity_tab(self, selected: str) -> None:
        for label, frame in self.activity_tabs.items():
            frame.pack_forget()
            active = label == selected
            self.activity_tab_buttons[label].configure(
                bg=COLORS["selection"] if active else COLORS["heading"],
                fg=COLORS["accent"] if active else COLORS["muted"],
            )
        self.activity_tabs[selected].pack(fill="both", expand=True)

    def open_recent_movement(self, _event: tk.Event | None = None) -> None:
        selection = self.activity_tree.selection()
        if not selection:
            return
        kind, item_id = selection[0].split(":", 1)
        if kind == "sale":
            self.open_sales_history(item_id)
            return
        self.app.show_page("All Sets")
        page = self.app.pages["All Sets"]
        if page.tree.exists(item_id):
            page.tree.selection_set(item_id)
            page.tree.focus(item_id)
            page.tree.see(item_id)
            page.update_actions()

    def open_sales_history(self, sale_id: str | None = None) -> None:
        self.app.show_page("Sales")
        page = self.app.pages["Sales"]
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
        self.cards[0].set(short_money(metrics["paid"]), f"Across {metrics['piecesets']} set{'' if metrics['piecesets'] == 1 else 's'} on hand · est. value {short_money(metrics['value'])}")
        self.cards[1].set(short_money(gain), f"{margin:+.1f}% against your cost")
        self.cards[2].set(short_money(metrics["listed_paid"]), f"Sets marked for sale · est. value {short_money(metrics['listed'])}")
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

        activity = self.app.db.recent_activity()
        selected_activity = self.activity_tree.selection()
        for item in self.activity_tree.get_children():
            self.activity_tree.delete(item)
        if not activity:
            self.activity_note.configure(text="No movement yet. Add your first set to begin.")
            return
        self.activity_note.configure(text=f"All {len(activity):,} movements · newest first · double-click to open")
        for event in activity:
            is_sale = event["kind"] == "sale"
            set_label = f"{event['set_number']} · {event['title']}" if event["set_number"] else event["title"]
            if is_sale:
                details = " · ".join(value for value in (event["context"], "Sold", event["theme"]) if value)
            else:
                built = "Built" if int(event["built"] or 0) else "Not built"
                quantity = f"Qty {event['quantity']}" if int(event["quantity"] or 1) > 1 else ""
                details = " · ".join(
                    value for value in (event["status"], event["condition"], built, event["theme"], quantity) if value
                )
            self.activity_tree.insert(
                "", "end", iid=f"{event['kind']}:{event['id']}",
                values=(
                    str(event["happened_at"]),
                    "SALE" if is_sale else "ADD",
                    set_label,
                    details,
                    money(event["amount"]),
                    money(event["value"]),
                ),
            )
        if selected_activity and self.activity_tree.exists(selected_activity[0]):
            self.activity_tree.selection_set(selected_activity[0])


class CollectionPage(BasePage):
    columns = ("set_number", "title", "theme", "condition", "paid", "value", "status", "notes", "built", "disassembled")
    condition_filter = "All"
    page_eyebrow = "The complete ledger"
    page_title = "Every set, one clear view."
    page_copy = "Search, filter, edit, and value every set from a single workspace."

    def __init__(self, parent: tk.Misc, app: BrickLedgerApp) -> None:
        super().__init__(parent, app)
        header_row = tk.Frame(self, bg=COLORS["paper"])
        header_row.pack(fill="x")
        header = title_block(header_row, self.page_eyebrow, self.page_title, self.page_copy)
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
        headings = {"set_number": "SET #", "title": "SET NAME", "theme": "THEME", "condition": "CONDITION", "paid": "PAID", "value": "EST. VALUE", "status": "STATUS", "notes": "NOTES", "built": "BUILT", "disassembled": "DISASSEMBLED"}
        self.tree = ttk.Treeview(tree_frame, columns=self.columns, show="headings", selectmode="browse")
        widths = {"set_number": 100, "title": 310, "theme": 170, "condition": 115, "paid": 90, "value": 105, "status": 95, "notes": 280, "built": 70, "disassembled": 125}
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
            records = self.app.db.collection(status=status, condition=self.condition_filter)
            total_paid = sum(float(record["purchase_price"]) * int(record["quantity"]) for record in records)
            total_value = sum(float(record["estimated_value"]) * int(record["quantity"]) for record in records)
            detail = getattr(section, "_detail")
            accent = getattr(section, "_accent")
            active = self.status_var.get() == status
            section.configure(
                text=f"{status.upper()}\n{len(records)} set{'' if len(records) == 1 else 's'} - Paid {short_money(total_paid)} · Worth {short_money(total_value)}\n{detail}",
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
        rows = self.app.db.collection(
            self.search_var.get(), self.status_var.get(), condition=self.condition_filter
        )
        for row in rows:
            tags = []
            if row["condition"] == "Collection":
                tags.append("complete")
            if row["status"] == "Sold":
                tags.append("sold")
            notes = " ".join(str(row["notes"] or "").split())
            built = "Built" if int(row["built"] or 0) else ""
            disassembled = "Disassembled" if int(row["disassembled"] or 0) else ""
            self.tree.insert(
                "", "end", iid=str(row["id"]), tags=tuple(tags),
                values=(row["set_number"], row["title"], row["theme"] or "-", row["condition"], money(row["purchase_price"]), money(row["estimated_value"]), row["status"], notes, built, disassembled),
            )
        self.count_label.configure(text=f"{len(rows)} set record{'' if len(rows) == 1 else 's'}")
        self.refresh_sections()
        self.update_actions()

    def refresh(self) -> None:
        self.refresh_sections()
        self.load_rows()


class MyCollectionPage(BasePage):
    """A visual, image-led view of sets marked as part of the collection."""

    def __init__(self, parent: tk.Misc, app: BrickLedgerApp) -> None:
        super().__init__(parent, app)
        self._photos: list[ImageTk.PhotoImage] = []
        self._gallery_generation = 0
        self._gallery_tasks: list[tuple[Callable[[], tk.Frame], int, int, int]] = []
        self._gallery_signature: tuple[Any, ...] | None = None
        self._refresh_job: str | None = None
        self._retired_galleries: list[tuple[tk.Frame, list[tk.Widget]]] = []
        self._gallery_cleanup_job: str | None = None
        self._gallery_columns = 4
        self._reflow_job: str | None = None
        self._lazy_images: dict[tk.Label, tuple[str, str]] = {}
        self._lazy_image_job: str | None = None

        header_row = tk.Frame(self, bg=COLORS["paper"])
        header_row.pack(fill="x")
        title_block(
            header_row,
            "Your personal collection",
            "Your Collection",
            "Track your Speed Champions progress and browse the collection as a visual gallery.",
        ).pack(side="left", anchor="nw")
        header_actions = tk.Frame(header_row, bg=COLORS["paper"])
        header_actions.pack(side="right", anchor="ne", pady=(13, 0))
        button(header_actions, "+ Add a set", self.add_set).pack(anchor="e")
        self.collection_totals = tk.Label(
            header_actions, text="", bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 9, "bold")
        )
        self.collection_totals.pack(anchor="e", pady=(10, 0))
        self.collection_money = tk.Label(
            header_actions, text="", bg=COLORS["paper"], fg=COLORS["accent"], font=(FONT, 9, "bold")
        )
        self.collection_money.pack(anchor="e", pady=(4, 0))

        progress = tk.Frame(self, bg=COLORS["card"], highlightbackground=COLORS["line"], highlightthickness=1)
        progress.pack(fill="x", pady=(25, 17))
        progress_copy = tk.Frame(progress, bg=COLORS["card"])
        progress_copy.pack(side="left", fill="both", expand=True, padx=22, pady=17)
        tk.Label(progress_copy, text="SPEED CHAMPIONS COMPLETION", bg=COLORS["card"], fg=COLORS["accent"],
                 font=(FONT, 8, "bold")).pack(anchor="w")
        self.speed_value = tk.Label(progress_copy, text="—", bg=COLORS["card"], fg=COLORS["ink"],
                                    font=(FONT, 22, "bold"))
        self.speed_value.pack(anchor="w", pady=(4, 1))
        self.speed_note = tk.Label(progress_copy, text="", bg=COLORS["card"], fg=COLORS["muted"],
                                   font=(FONT, 9))
        self.speed_note.pack(anchor="w")
        progress_visual = tk.Frame(progress, bg=COLORS["card"], width=540, height=112)
        progress_visual.pack(side="right", fill="y", padx=22, pady=18)
        progress_visual.pack_propagate(False)
        progress_top = tk.Frame(progress_visual, bg=COLORS["card"])
        progress_top.pack(fill="x")
        self.speed_stats = tk.Label(progress_top, text="", bg=COLORS["card"], fg=COLORS["accent"],
                                    font=(FONT, 9, "bold"))
        self.speed_stats.pack(side="left", anchor="w", pady=(3, 0))
        self.progress_percent = tk.Label(progress_top, text="", bg=COLORS["card"], fg=COLORS["accent"],
                                         font=(FONT, 14, "bold"))
        self.progress_percent.pack(side="right", anchor="e")
        self.progress_bar = tk.Canvas(progress_visual, height=12, bg=COLORS["heading"], highlightthickness=0)
        self.progress_bar.pack(fill="x", pady=(11, 0))
        self.progress_bar.bind("<Configure>", lambda _event: self._draw_progress())
        self._progress_ratio = 0.0
        variants = tk.Frame(progress_visual, bg=COLORS["card"])
        variants.pack(fill="x", pady=(12, 0))
        self.variant_values: dict[str, tk.Label] = {}
        for index, variant in enumerate(SPEED_CHAMPIONS_VARIANTS):
            cell = tk.Frame(variants, bg=COLORS["heading"])
            cell.pack(side="left", fill="x", expand=True, padx=(0 if index == 0 else 4, 0 if index == 2 else 4))
            tk.Label(cell, text=variant.upper(), bg=COLORS["heading"], fg=COLORS["muted"],
                     font=(FONT, 7, "bold")).pack(anchor="w", padx=9, pady=(6, 1))
            value = tk.Label(cell, text="—", bg=COLORS["heading"], fg=COLORS["ink"], font=(FONT, 10, "bold"))
            value.pack(anchor="w", padx=9, pady=(0, 6))
            self.variant_values[variant] = value

        toolbar = tk.Frame(self, bg=COLORS["paper"])
        toolbar.pack(fill="x", pady=(0, 12))
        search_shell = tk.Frame(toolbar, bg=COLORS["card"], highlightthickness=1, highlightbackground=COLORS["line"])
        search_shell.pack(side="left", fill="x", expand=True)
        tk.Label(search_shell, text="Search collection", bg=COLORS["card"], fg=COLORS["muted"],
                 font=(FONT, 10)).pack(side="left", padx=(12, 8))
        self.search_var = tk.StringVar()
        search = tk.Entry(search_shell, textvariable=self.search_var, bg=COLORS["card"], fg=COLORS["ink"],
                          insertbackground=COLORS["ink"], relief="flat", font=(FONT, 10), highlightthickness=0)
        search.pack(side="left", fill="x", expand=True, ipady=9, padx=(0, 8))
        sort_shell = tk.Frame(toolbar, bg=COLORS["paper"])
        sort_shell.pack(side="left", padx=(12, 0))
        tk.Label(sort_shell, text="SPEED CHAMPIONS SORT", bg=COLORS["paper"], fg=COLORS["muted"],
                 font=(FONT, 7, "bold")).pack(anchor="w")
        self.speed_sort_var = tk.StringVar(value="Brand")
        speed_sort = ttk.Combobox(
            sort_shell,
            textvariable=self.speed_sort_var,
            values=("Brand", "Year released", "Pieces (most–less)", "Alphabetical order"),
            state="readonly",
            width=21,
        )
        speed_sort.pack(anchor="w", pady=(2, 0))
        speed_sort.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        view_shell = tk.Frame(toolbar, bg=COLORS["paper"])
        view_shell.pack(side="left", padx=(10, 0))
        tk.Label(view_shell, text="SPEED CHAMPIONS VIEW", bg=COLORS["paper"], fg=COLORS["muted"],
                 font=(FONT, 7, "bold")).pack(anchor="w")
        self.speed_view_var = tk.StringVar(value="Separate 6 & 8 stud")
        speed_view = ttk.Combobox(
            view_shell,
            textvariable=self.speed_view_var,
            values=("Separate 6 & 8 stud", "All together"),
            state="readonly",
            width=19,
        )
        speed_view.pack(anchor="w", pady=(2, 0))
        speed_view.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        self.count_label = tk.Label(toolbar, text="", bg=COLORS["paper"], fg=COLORS["muted"], font=(FONT, 9))
        self.count_label.pack(side="right", padx=(16, 0))
        self.search_var.trace_add("write", lambda *_: self._schedule_refresh())

        gallery_shell = tk.Frame(self, bg=COLORS["paper"])
        gallery_shell.pack(fill="both", expand=True)
        self.gallery_canvas = tk.Canvas(gallery_shell, bg=COLORS["paper"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(gallery_shell, orient="vertical", command=self._scroll_gallery)
        scrollbar.pack(side="right", fill="y")
        self.gallery_canvas.pack(side="left", fill="both", expand=True)
        self.gallery_canvas.configure(yscrollcommand=scrollbar.set)
        self.gallery = tk.Frame(self.gallery_canvas, bg=COLORS["paper"])
        self.gallery_window = self.gallery_canvas.create_window((0, 0), window=self.gallery, anchor="nw")
        self.gallery_canvas.itemconfigure(self.gallery_window, width=max(self.gallery_canvas.winfo_width(), 1))
        self.gallery.bind("<Configure>", self._update_scroll_region)
        self.gallery_canvas.bind("<Configure>", self._resize_gallery)
        self.gallery_canvas.bind("<Enter>", self._bind_wheel)
        self.gallery_canvas.bind("<Leave>", self._unbind_wheel)

    def add_set(self) -> None:
        SetDialog(self, self.app, on_saved=self.app.refresh_everything)

    def add_catalog_set(self, record: CatalogSet) -> None:
        dialog = SetDialog(self, self.app, on_saved=self.app.refresh_everything)
        dialog.apply_catalog_set(record)
        dialog.vars["condition"].set("Collection")
        dialog.vars["status"].set("Keeping")

    def edit_set(self, item_id: int) -> None:
        SetDialog(self, self.app, item_id=item_id, on_saved=self.app.refresh_everything)

    def refresh(self) -> None:
        all_collection = self.app.db.collection(condition="Collection", sort="Alphabetical A-Z")
        query = self.search_var.get().strip().casefold() if hasattr(self, "search_var") else ""
        rows = [row for row in all_collection if not query or self._matches(row, query)]
        missing = self._refresh_speed_champions(all_collection)
        visible_missing = [record for record in missing if not query or self._catalog_matches(record, query)]
        signature = (
            tuple((int(row["id"]), str(row["updated_at"])) for row in rows),
            tuple(record.set_number for record in visible_missing),
            self.speed_sort_var.get(),
            self.speed_view_var.get(),
        )
        if signature != self._gallery_signature:
            self._gallery_signature = signature
            self._build_gallery(rows, visible_missing)
        self.count_label.configure(text=f"{len(rows)} of {len(all_collection)} sets")
        total_built = sum(bool(int(row["built"] or 0)) for row in all_collection)
        total_pieces = sum(self._row_piece_count(row) for row in all_collection)
        self.collection_totals.configure(
            text=f"{len(all_collection):,} SETS   ·   {total_built:,} BUILT   ·   {total_pieces:,} PIECES"
        )
        total_paid = sum(float(row["purchase_price"] or 0) * int(row["quantity"] or 1) for row in all_collection)
        total_value = sum(float(row["estimated_value"] or 0) * int(row["quantity"] or 1) for row in all_collection)
        self.collection_money.configure(
            text=f"PAID {money(total_paid)}   ·   WORTH {money(total_value)}"
        )

    def _schedule_refresh(self) -> None:
        if self._refresh_job is not None:
            try:
                self.after_cancel(self._refresh_job)
            except tk.TclError:
                pass
        self._refresh_job = self.after(140, self._run_scheduled_refresh)

    def _run_scheduled_refresh(self) -> None:
        self._refresh_job = None
        self.refresh()

    @staticmethod
    def _matches(row: Any, query: str) -> bool:
        return any(query in str(row[key] or "").casefold() for key in ("set_number", "title", "theme", "notes"))

    @staticmethod
    def _catalog_matches(record: CatalogSet, query: str) -> bool:
        return any(
            query in str(value or "").casefold()
            for value in (record.set_number, record.name, record.theme, record.year, record.parts)
        )

    @staticmethod
    def _missing_speed_champions(catalogue: list[CatalogSet], rows: list[Any]) -> list[CatalogSet]:
        owned_numbers = {str(row["set_number"]).strip().upper() for row in rows}
        return [record for record in catalogue if record.set_number.upper() not in owned_numbers]

    def _refresh_speed_champions(self, rows: list[Any]) -> list[CatalogSet]:
        all_speed_champions = self.app.catalog.search(theme="Speed Champions", limit=100_000)
        catalogue = [record for record in all_speed_champions if speed_champions_variant(record) is not None]
        missing = self._missing_speed_champions(catalogue, rows)
        total = len(catalogue)
        remaining = len(missing)
        owned = total - remaining
        ratio = owned / total if total else 0.0
        self._progress_ratio = ratio
        self.speed_value.configure(text=f"{owned} / {total} sets")
        self.speed_note.configure(text=f"{remaining} remaining in the current catalogue" if remaining else "Current catalogue complete")
        self.progress_percent.configure(text=f"{ratio * 100:.1f}%")
        owned_numbers = {str(row["set_number"]).strip().upper() for row in rows}
        owned_speed_rows = [
            row for row in rows
            if (record := self.app.catalog.lookup(str(row["set_number"]))) is not None
            and speed_champions_variant(record) is not None
        ]
        speed_built = sum(bool(int(row["built"] or 0)) for row in owned_speed_rows)
        speed_pieces = sum(self._row_piece_count(row) for row in owned_speed_rows)
        self.speed_stats.configure(text=f"{speed_built:,} BUILT   ·   {speed_pieces:,} OWNED PIECES")
        for variant in SPEED_CHAMPIONS_VARIANTS:
            variant_records = [record for record in catalogue if speed_champions_variant(record) == variant]
            variant_owned = sum(record.set_number.upper() in owned_numbers for record in variant_records)
            self.variant_values[variant].configure(text=f"{variant_owned} / {len(variant_records)}")
        self._draw_progress()
        return missing

    def _row_piece_count(self, row: Any) -> int:
        record = self.app.catalog.lookup(str(row["set_number"]))
        if not record:
            return 0
        try:
            quantity = max(int(row["quantity"] or 1), 1)
            return max(int(record.parts), 0) * quantity
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _record_piece_count(record: CatalogSet) -> int:
        try:
            return max(int(record.parts), 0)
        except (TypeError, ValueError):
            return 0

    def _speed_record_sort_key(self, record: CatalogSet) -> tuple[Any, ...]:
        selected = self.speed_sort_var.get() if hasattr(self, "speed_sort_var") else "Brand"
        if selected == "Year released":
            return (-int(record.year or 0), record.name.casefold())
        if selected == "Pieces (most–less)":
            return (-self._record_piece_count(record), record.name.casefold())
        if selected == "Alphabetical order":
            return (record.name.casefold(),)
        return (speed_champions_brand(record.name).casefold(), record.name.casefold())

    def _speed_row_sort_key(self, row: Any) -> tuple[Any, ...]:
        record = self.app.catalog.lookup(str(row["set_number"]))
        if record:
            return self._speed_record_sort_key(record)
        return (str(row["title"] or "").casefold(),)

    def _draw_progress(self) -> None:
        if not hasattr(self, "progress_bar"):
            return
        width = max(self.progress_bar.winfo_width(), 1)
        self.progress_bar.delete("all")
        self.progress_bar.create_rectangle(0, 0, width, 12, fill=COLORS["heading"], outline="")
        self.progress_bar.create_rectangle(0, 0, width * self._progress_ratio, 12, fill=COLORS["accent"], outline="")

    def _build_gallery(self, rows: list[Any], missing: list[CatalogSet]) -> None:
        self._gallery_generation += 1
        generation = self._gallery_generation
        self._gallery_tasks = []
        old_gallery = self.gallery
        old_window = self.gallery_window
        old_children = list(old_gallery.winfo_children())
        self.gallery = tk.Frame(self.gallery_canvas, bg=COLORS["paper"])
        self.gallery_window = self.gallery_canvas.create_window((0, 0), window=self.gallery, anchor="nw")
        self.gallery.bind("<Configure>", self._update_scroll_region)
        self.gallery_canvas.delete(old_window)
        self._retired_galleries.append((old_gallery, old_children))
        if self._gallery_cleanup_job is None:
            self._gallery_cleanup_job = self.after(70, self._cleanup_retired_gallery)
        self._photos.clear()
        self._lazy_images.clear()
        self.gallery_canvas.yview_moveto(0)
        columns = self._desired_columns(self.gallery_canvas.winfo_width())
        self._gallery_columns = columns
        for column in range(columns):
            self.gallery.columnconfigure(column, weight=1, uniform="collection-card")
        if not rows and not missing:
            tk.Label(self.gallery, text="No collection or missing sets match this search.", bg=COLORS["paper"], fg=COLORS["muted"],
                     font=(FONT, 11)).grid(row=0, column=0, columnspan=columns, pady=50)
            return
        groups: dict[str, list[Any]] = {}
        separate_speed = self.speed_view_var.get() != "All together"
        for row in rows:
            theme = str(row["theme"] or "Other")
            section = theme
            if separate_speed and theme.casefold() == "speed champions":
                record = self.app.catalog.lookup(str(row["set_number"]))
                variant = speed_champions_variant(record) if record else None
                if variant:
                    section = f"Speed Champions · {variant}"
            groups.setdefault(section, []).append(row)

        variant_order = {variant.casefold(): index for index, variant in enumerate(SPEED_CHAMPIONS_VARIANTS)}

        def section_order(section: str) -> tuple[int, int, str]:
            prefix, _, variant = section.partition(" · ")
            if prefix.casefold() == "speed champions":
                return 0, variant_order.get(variant.casefold(), len(variant_order)), section.casefold()
            return 1, 0, section.casefold()

        themes = sorted(groups, key=section_order)
        gallery_row = 0
        if missing:
            missing_sections = (
                [
                    (f"Missing Speed Champions · {variant}", [record for record in missing if speed_champions_variant(record) == variant])
                    for variant in SPEED_CHAMPIONS_VARIANTS
                ]
                if separate_speed
                else [("Missing Speed Champions", list(missing))]
            )
            for missing_title, variant_missing in missing_sections:
                if not variant_missing:
                    continue
                variant_missing.sort(key=self._speed_record_sort_key)
                missing_pieces = sum(self._record_piece_count(record) for record in variant_missing)
                self._make_theme_header(
                    missing_title,
                    len(variant_missing),
                    piece_count=missing_pieces,
                    missing=True,
                ).grid(
                    row=gallery_row, column=0, columnspan=columns, sticky="ew", pady=(0 if gallery_row == 0 else 10, 12)
                )
                gallery_row += 1
                for index, record in enumerate(variant_missing):
                    column = index % columns
                    self._gallery_tasks.append(
                        (lambda selected=record: self._make_missing_card(selected), gallery_row + index // columns, column, columns)
                    )
                gallery_row += (len(variant_missing) + columns - 1) // columns
        for theme in themes:
            theme_rows = groups[theme]
            if theme.casefold().startswith("speed champions"):
                theme_rows.sort(key=self._speed_row_sort_key)
            else:
                theme_rows.sort(key=lambda row: str(row["title"] or "").casefold())
            section_built = sum(bool(int(row["built"] or 0)) for row in theme_rows)
            section_pieces = sum(self._row_piece_count(row) for row in theme_rows)
            self._make_theme_header(
                theme,
                len(theme_rows),
                built_count=section_built,
                piece_count=section_pieces,
                paid=sum(float(row["purchase_price"] or 0) * int(row["quantity"] or 1) for row in theme_rows),
                worth=sum(float(row["estimated_value"] or 0) * int(row["quantity"] or 1) for row in theme_rows),
            ).grid(
                row=gallery_row, column=0, columnspan=columns, sticky="ew", pady=(10 if gallery_row else 0, 12)
            )
            gallery_row += 1
            for index, row in enumerate(theme_rows):
                column = index % columns
                self._gallery_tasks.append(
                    (lambda selected=row: self._make_set_card(selected), gallery_row + index // columns, column, columns)
                )
            gallery_row += (len(theme_rows) + columns - 1) // columns
        self._render_gallery_batch(generation)

    def _render_gallery_batch(self, generation: int) -> None:
        if generation != self._gallery_generation:
            return
        batch, self._gallery_tasks = self._gallery_tasks[:2], self._gallery_tasks[2:]
        for factory, row, column, columns in batch:
            factory().grid(
                row=row, column=column, sticky="nsew",
                padx=(0 if column == 0 else 7, 0 if column == columns - 1 else 7),
                pady=(0, 14),
            )
        if self._gallery_tasks:
            self.after(30, self._render_gallery_batch, generation)

    def _cleanup_retired_gallery(self) -> None:
        self._gallery_cleanup_job = None
        if not self._retired_galleries:
            return
        gallery, children = self._retired_galleries[0]
        if children:
            child = children.pop()
            try:
                child.destroy()
            except tk.TclError:
                pass
        else:
            try:
                gallery.destroy()
            except tk.TclError:
                pass
            self._retired_galleries.pop(0)
        if self._retired_galleries:
            self._gallery_cleanup_job = self.after(30, self._cleanup_retired_gallery)

    def _make_theme_header(
        self,
        theme: str,
        count: int,
        built_count: int | None = None,
        piece_count: int = 0,
        missing: bool = False,
        paid: float | None = None,
        worth: float | None = None,
    ) -> tk.Frame:
        header = tk.Frame(self.gallery, bg=COLORS["paper"])
        title = tk.Frame(header, bg=COLORS["paper"])
        title.pack(side="left")
        accent = COLORS["danger"] if missing else COLORS["accent"]
        tk.Frame(title, bg=accent, width=4, height=26).pack(side="left", padx=(0, 11))
        tk.Label(title, text=theme.upper(), bg=COLORS["paper"], fg=COLORS["ink"],
                 font=(FONT, 12, "bold")).pack(side="left")
        suffix = "SET" if count == 1 else "SETS"
        tk.Label(title, text=f"{count} {suffix}", bg=COLORS["danger_bg"] if missing else COLORS["heading"], fg=accent,
                 font=(FONT, 8, "bold"), padx=9, pady=4).pack(side="left", padx=11)
        if built_count is not None:
            tk.Label(title, text=f"{built_count:,} BUILT", bg=COLORS["heading"], fg=COLORS["ink"],
                     font=(FONT, 8, "bold"), padx=9, pady=4).pack(side="left", padx=(0, 7))
        tk.Label(title, text=f"{piece_count:,} PIECES", bg=COLORS["heading"], fg=COLORS["muted"],
                 font=(FONT, 8, "bold"), padx=9, pady=4).pack(side="left")
        if paid is not None:
            tk.Label(title, text=f"PAID {money(paid)}", bg=COLORS["heading"], fg=COLORS["accent"],
                     font=(FONT, 8, "bold"), padx=9, pady=4).pack(side="left", padx=(7, 0))
        if worth is not None:
            tk.Label(title, text=f"WORTH {money(worth)}", bg=COLORS["heading"], fg=COLORS["ink"],
                     font=(FONT, 8, "bold"), padx=9, pady=4).pack(side="left", padx=(7, 0))
        tk.Frame(header, bg=COLORS["line"], height=1).pack(side="left", fill="x", expand=True, padx=(14, 0))
        return header

    def _make_missing_card(self, record: CatalogSet) -> tk.Frame:
        card = tk.Frame(self.gallery, bg=COLORS["card"], highlightbackground=COLORS["danger_bg"], highlightthickness=1)
        image_label = tk.Label(card, text="IMAGE LOADING", bg=COLORS["card"], fg=COLORS["muted"],
                               font=(FONT, 8, "bold"), width=30, height=9)
        image_label.pack(fill="x")
        body = tk.Frame(card, bg=COLORS["card"])
        body.pack(fill="both", expand=True, padx=14, pady=12)
        top = tk.Frame(body, bg=COLORS["card"])
        top.pack(fill="x")
        tk.Label(top, text=record.set_number, bg=COLORS["card"], fg=COLORS["accent"],
                 font=(FONT, 8, "bold")).pack(side="left")
        tk.Label(top, text="MISSING", bg=COLORS["danger_bg"], fg=COLORS["danger"],
                 font=(FONT, 7, "bold"), padx=7, pady=2).pack(side="right")
        tk.Label(body, text=record.name, bg=COLORS["card"], fg=COLORS["ink"],
                 font=(FONT, 10, "bold"), anchor="w", justify="left", wraplength=225, height=2).pack(fill="x", pady=(4, 3))
        tk.Label(body, text=f"{record.year}  ·  {record.parts} pieces", bg=COLORS["card"], fg=COLORS["muted"],
                 font=(FONT, 8), anchor="w").pack(fill="x")
        footer = tk.Frame(body, bg=COLORS["card"])
        footer.pack(fill="x", pady=(10, 0))
        tk.Label(footer, text="NOT IN COLLECTION", bg=COLORS["card"], fg=COLORS["danger"],
                 font=(FONT, 8, "bold")).pack(side="left")
        add = button(footer, "+ Add", lambda selected=record: self.add_catalog_set(selected), "primary")
        add.configure(font=(FONT, 8, "bold"), padx=10, pady=5)
        add.pack(side="right")
        if record.image_url:
            self._register_lazy_image(image_label, record.set_number, record.image_url)
        else:
            image_label.configure(text="IMAGE UNAVAILABLE")
        return card

    def _make_set_card(self, row: Any) -> tk.Frame:
        card = tk.Frame(self.gallery, bg=COLORS["card"], highlightbackground=COLORS["line"], highlightthickness=1)
        image_label = tk.Label(card, text="IMAGE LOADING", bg=COLORS["card"], fg=COLORS["muted"],
                               font=(FONT, 8, "bold"), width=30, height=9)
        image_label.pack(fill="x")
        catalog_set = self.app.catalog.lookup(str(row["set_number"]))
        body = tk.Frame(card, bg=COLORS["card"])
        body.pack(fill="both", expand=True, padx=14, pady=12)
        top = tk.Frame(body, bg=COLORS["card"])
        top.pack(fill="x")
        tk.Label(top, text=str(row["set_number"]), bg=COLORS["card"], fg=COLORS["accent"],
                 font=(FONT, 8, "bold")).pack(side="left")
        built = bool(int(row["built"] or 0))
        tk.Label(top, text="BUILT" if built else "NOT BUILT",
                 bg=COLORS["success_bg"] if built else COLORS["heading"],
                 fg=COLORS["accent"] if built else COLORS["muted"],
                 font=(FONT, 7, "bold"), padx=7, pady=2).pack(side="right")
        tk.Label(body, text=str(row["title"]), bg=COLORS["card"], fg=COLORS["ink"],
                 font=(FONT, 10, "bold"), anchor="w", justify="left", wraplength=225, height=2).pack(fill="x", pady=(4, 3))
        meta = f"{catalog_set.year}  ·  {catalog_set.parts} pieces" if catalog_set else "Catalogue details unavailable"
        tk.Label(body, text=meta, bg=COLORS["card"], fg=COLORS["muted"],
                 font=(FONT, 8), anchor="w").pack(fill="x")
        footer = tk.Frame(body, bg=COLORS["card"])
        footer.pack(fill="x", pady=(10, 0))
        tk.Label(footer, text=f"Paid {money(row['purchase_price'])}", bg=COLORS["card"], fg=COLORS["ink"],
                 font=(FONT, 10, "bold")).pack(side="left")
        edit = button(footer, "Edit", lambda item_id=int(row["id"]): self.edit_set(item_id), "soft")
        edit.configure(font=(FONT, 8, "bold"), padx=10, pady=5)
        edit.pack(side="right")

        if catalog_set and catalog_set.image_url:
            self._register_lazy_image(image_label, catalog_set.set_number, catalog_set.image_url)
        else:
            image_label.configure(text="IMAGE UNAVAILABLE")
        return card

    def _apply_image(self, target: tk.Label, image: Any) -> None:
        if image is None:
            if target.winfo_exists():
                target.configure(text="IMAGE UNAVAILABLE")
            return
        try:
            if not target.winfo_exists():
                return
            photo = ImageTk.PhotoImage(image)
            self._photos.append(photo)
            target.configure(image=photo, text="", width=250, height=155)
        except tk.TclError:
            pass

    def _update_scroll_region(self, _event: tk.Event) -> None:
        self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all"))
        self._schedule_visible_images()

    def _resize_gallery(self, event: tk.Event) -> None:
        self.gallery_canvas.itemconfigure(self.gallery_window, width=event.width)
        desired = self._desired_columns(event.width)
        if desired != self._gallery_columns:
            if self._reflow_job is not None:
                try:
                    self.after_cancel(self._reflow_job)
                except tk.TclError:
                    pass
            self._reflow_job = self.after(180, self._reflow_gallery)
        self._schedule_visible_images()

    @staticmethod
    def _desired_columns(width: int) -> int:
        return max(2, min(7, max(width, 1) // 285))

    def _reflow_gallery(self) -> None:
        self._reflow_job = None
        desired = self._desired_columns(self.gallery_canvas.winfo_width())
        if desired == self._gallery_columns:
            return
        self._gallery_columns = desired
        self._gallery_signature = None
        self.refresh()

    def _register_lazy_image(self, target: tk.Label, set_number: str, image_url: str) -> None:
        self._lazy_images[target] = (set_number, image_url)
        self._schedule_visible_images()

    def _schedule_visible_images(self) -> None:
        if self._lazy_image_job is None:
            self._lazy_image_job = self.after(35, self._load_visible_images)

    def _load_visible_images(self) -> None:
        self._lazy_image_job = None
        if not self._lazy_images or not self.gallery_canvas.winfo_ismapped():
            return
        canvas_top = self.gallery_canvas.winfo_rooty()
        canvas_height = max(self.gallery_canvas.winfo_height(), 1)
        preload = canvas_height
        visible_top = canvas_top - preload
        visible_bottom = canvas_top + canvas_height + preload
        requested = 0
        more_visible = False
        for target, request in list(self._lazy_images.items()):
            try:
                if not target.winfo_exists():
                    self._lazy_images.pop(target, None)
                    continue
                if not target.winfo_ismapped():
                    continue
                target_top = target.winfo_rooty()
                target_bottom = target_top + max(target.winfo_height(), 1)
            except tk.TclError:
                self._lazy_images.pop(target, None)
                continue
            if target_bottom < visible_top or target_top > visible_bottom:
                continue
            if requested >= 2:
                more_visible = True
                continue
            set_number, image_url = self._lazy_images.pop(target)
            self.app.image_cache.request(
                set_number,
                image_url,
                lambda image, image_target=target: self._apply_image(image_target, image),
            )
            requested += 1
        if more_visible:
            self._lazy_image_job = self.after(45, self._load_visible_images)

    def _scroll_gallery(self, *args: str) -> None:
        self.gallery_canvas.yview(*args)
        self._schedule_visible_images()

    def _bind_wheel(self, _event: tk.Event) -> None:
        self.gallery_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_wheel(self, _event: tk.Event) -> None:
        self.gallery_canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.gallery_canvas.yview_scroll(int(-event.delta / 120), "units")
        self._schedule_visible_images()


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

        strip = tk.Frame(self, bg=COLORS["black"])
        strip.pack(fill="x", pady=(29, 15))
        strip_inner = tk.Frame(strip, bg=COLORS["black"])
        strip_inner.pack(fill="x", padx=22, pady=15)
        self.sales_stat = tk.Label(strip_inner, text="", bg=COLORS["black"], fg=COLORS["ink"], font=(FONT, 15, "bold"))
        self.sales_stat.pack(side="left")
        self.sales_note = tk.Label(strip_inner, text="", bg=COLORS["black"], fg=COLORS["nav_muted"], font=(FONT, 10))
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
        header = title_block(self, "Your local archive", "Exports, all in one place.", "Create clean records for accounting, insurance, or a fresh spreadsheet.")
        header.pack(anchor="nw")

        panels = tk.Frame(self, bg=COLORS["paper"])
        panels.pack(fill="x", pady=(31, 16))
        for column in range(2):
            panels.columnconfigure(column, weight=1, uniform="panel")
        collection_card = self._make_export_panel(panels, 0, "Collection catalogue", "Export set records using the settings below.", "Export collection CSV", self.export_collection, COLORS["yellow"])
        self._make_collection_export_settings(collection_card)
        self._make_export_panel(panels, 1, "Sales ledger", "Every sale with fees, postage, platform, and net proceeds.", "Export sales CSV", self.export_sales, COLORS["lavender"])

        importer = tk.Frame(self, bg=COLORS["black"], highlightbackground=COLORS["line"], highlightthickness=1)
        importer.pack(fill="x", pady=(0, 10))
        importer_copy = tk.Frame(importer, bg=COLORS["black"])
        importer_copy.pack(side="left", fill="x", expand=True, padx=21, pady=17)
        tk.Label(importer_copy, text="BRING IN YOUR BRICKECONOMY COLLECTION", bg=COLORS["black"], fg=COLORS["yellow"], font=(FONT, 8, "bold")).pack(anchor="w")
        tk.Label(importer_copy, text="Preview your Sets export, then choose Keeping or For sale before importing.", bg=COLORS["black"], fg=COLORS["nav_muted"], font=(FONT, 10)).pack(anchor="w", pady=(4, 0))
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
            ("Condition", self.export_condition_var, ("All", "Collection", "New", "Sealed", "Used", "Incomplete")),
            ("Built", self.export_built_var, ("All", "Built", "Not built")),
            ("Sort", self.export_sort_var, ("Status then A-Z", "Theme A-Z", "Alphabetical A-Z", "Alphabetical Z-A", "Highest paid", "Lowest paid", "Highest value", "Lowest value", "Newest added", "Oldest added")),
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
        folder = str(DATA_PATH)
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
        head = tk.Frame(self, bg=COLORS["black"])
        head.pack(fill="x")
        tk.Label(head, text="BRICKECONOMY IMPORT", bg=COLORS["black"], fg=COLORS["yellow"], font=(FONT, 8, "bold")).pack(anchor="w", padx=22, pady=(15, 2))
        tk.Label(head, text="Review before the sets join your ledger.", bg=COLORS["black"], fg=COLORS["ink"], font=(FONT, 16, "bold")).pack(anchor="w", padx=22, pady=(0, 15))

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
        head = tk.Frame(self, bg=COLORS["black"])
        head.pack(fill="x")
        tk.Label(head, text="OFFLINE SET CATALOGUE", bg=COLORS["black"], fg=COLORS["yellow"], font=(FONT, 8, "bold")).pack(anchor="w", padx=24, pady=(18, 2))
        tk.Label(head, text="Choose a set from your Sets folder.", bg=COLORS["black"], fg=COLORS["ink"], font=(FONT, 17, "bold")).pack(anchor="w", padx=24, pady=(0, 18))

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
        self._build()
        self.bind("<Escape>", lambda _event: self.destroy())
        self.after(50, lambda: self.focus_force())

    def _value(self, key: str, fallback: Any = "") -> str:
        return str(self.record[key]) if self.record is not None and self.record[key] is not None else str(fallback)

    def _build(self) -> None:
        head = tk.Frame(self, bg=COLORS["black"])
        head.pack(fill="x")
        heading_copy = tk.Frame(head, bg=COLORS["black"])
        heading_copy.pack(side="left", fill="x", expand=True, padx=26, pady=(14, 14))
        tk.Label(heading_copy, text="SET CARD", bg=COLORS["black"], fg=COLORS["yellow"], font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 2))
        heading = "Edit the details that matter." if self.record else "Add a set to your ledger."
        tk.Label(heading_copy, text=heading, bg=COLORS["black"], fg=COLORS["ink"], font=(FONT, 17, "bold")).pack(anchor="w")
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
                field: tk.Widget = ttk.Combobox(cell, textvariable=var, values=("Collection", "New", "Sealed", "Used", "Incomplete"), state="readonly")
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
        for label, variable in (("Built", self.built_var), ("Disassembled", self.disassembled_var)):
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
        # Box and instruction inventories are managed on their combined page.
        # Preserve older flags while editing so hiding the controls never loses data.
        values["has_box"] = int(self.record["has_box"] or 0) if self.record else 0
        values["has_instructions"] = int(self.record["has_instructions"] or 0) if self.record else 0
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
        head = tk.Frame(self, bg=COLORS["black"])
        head.pack(fill="x")
        tk.Label(head, text="SALE ENTRY", bg=COLORS["black"], fg=COLORS["yellow"], font=(FONT, 8, "bold")).pack(anchor="w", padx=26, pady=(20, 2))
        tk.Label(head, text="Enter sale price and item cost.", bg=COLORS["black"], fg=COLORS["ink"], font=(FONT, 17, "bold")).pack(anchor="w", padx=26, pady=(0, 20))
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
        head = tk.Frame(self, bg=COLORS["black"])
        head.pack(fill="x")
        tk.Label(head, text="EDIT SALE", bg=COLORS["black"], fg=COLORS["yellow"], font=(FONT, 8, "bold")).pack(anchor="w", padx=26, pady=(20, 2))
        tk.Label(head, text=self._sale_title(), bg=COLORS["black"], fg=COLORS["ink"], font=(FONT, 17, "bold")).pack(anchor="w", padx=26, pady=(0, 20))

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

