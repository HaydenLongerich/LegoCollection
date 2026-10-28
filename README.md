# BrickLedger

A calm, local-first desktop workspace for tracking a LEGO collection and the sets you sell. It stores your records in a SQLite database on your computer - no account or internet connection required.

## What is included

- Collection catalogue with set details, condition, and pricing
- Live portfolio figures: paid, estimated value, potential profit, and listed value
- A sale log that records fees and shipping, then automatically marks the set sold
- Search and status filters
- CSV export for the collection and sales history
- BrickEconomy Sets CSV import with a review screen and a batch Keeping/For sale choice
- A searchable offline set catalogue backed by your included `Sets` folder
- Separate Boxes and Instructions inventories with search, sorting, notes, and CSV export
- A charcoal, white, and teal interface built with Python's standard library

## Run it

1. Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/) if you do not already have it.
2. In this folder, run:

   ```powershell
   python main.py
   ```

You can also double-click `run_brickledger.bat` on Windows.

The first launch creates `data/brickledger.db`. Your data stays on this machine. The `exports` folder is used when you export CSV files from the app.

## How the Sets folder is used

The `Sets` folder is your master reference catalogue. When adding a collection item, select **Browse** next to Set Number to search its set numbers, names, and themes, then choose a matching set to fill the form.

Your own collection and sales records are saved separately in `data/brickledger.db`. Removing a set in BrickLedger only removes it from *your collection*; it never changes the catalogue files in `Sets`.

## Import a BrickEconomy collection

Open **Data & exports**, select **Import BrickEconomy CSV**, and choose your `BrickEconomy-Sets.csv` file. BrickLedger previews the records before anything is added, then lets you import the whole batch as either **Keeping** or **For sale**.

## Boxes and instructions

Open **Boxes** or **Instructions** in the sidebar. Add a record manually or select **Browse sets** in the add/edit window to choose from the offline catalogue. You do not need to own the matching set. Each record has a set number, name, theme, condition, storage location, and notes. Double-click a row to edit it, or select it and use **Edit** or **Delete**.

Use **Copy checked sets** to bring across collection entries with the matching Box or Instructions checkbox ticked. This includes checked sold sets. Previously copied entries are skipped, and existing accessory details are preserved. Copies start with condition **Good**; update that to the actual condition of the box or booklet. They have their own notes and location.

These inventories are independent after copying: editing, selling, deleting, or unticking a set does not remove its box or instructions record. Deleting an accessory does not untick the set; copying checked sets again can re-add it. Each record represents one box or instruction booklet/set of booklets. Extra copies can be added separately.

Search matches set details, condition, storage location, and notes. **Theme A-Z** orders themes alphabetically and names alphabetically within each theme. **Export CSV** saves the current search results in the selected order. Both inventories are stored in the same local SQLite database as your collection and sales, and do not change the dashboard's set values.

## Verification

Run the inventory checks with `python -m unittest discover -s tests -v`.

## Project layout

```
main.py                 Application entry point
brickfolio/             Interface and database code
data/                   Local SQLite database (created automatically)
exports/                CSV exports
```

No third-party packages are required. BrickLedger uses Tkinter, the desktop UI
component included with normal Python installers. If `python main.py` reports
that it cannot find `init.tcl`, rerun the official Python installer and choose
**Modify -> tcl/tk and IDLE**; this computer's current Python installation is
missing that optional component.
