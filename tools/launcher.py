"""Entry point compiled into BrickLedger.exe.

Two builds come from this file (see tools/build_exe.ps1):

* Local exe (default): bundles only Python and the libraries listed below, and
  loads main.py + brickfolio/ from the folder next to the exe on every start, so
  code changes show up without rebuilding.
* Release exe (-Release): also packs brickfolio/, the Sets catalogue and assets,
  so it works on its own after a download. Personal data goes to
  %LOCALAPPDATA%\\BrickLedger (see brickfolio/paths.py).

Rebuild only when the app starts importing a module that is not listed here;
tests/test_launcher.py checks this automatically.
"""

from __future__ import annotations

import os
import runpy
import sys
import traceback
from pathlib import Path

# --- Modules the live source code needs at runtime (bundled into the exe). ---
import concurrent.futures  # noqa: F401
import csv  # noqa: F401
import ctypes  # noqa: F401
import dataclasses  # noqa: F401
import datetime  # noqa: F401
import gzip  # noqa: F401
import math  # noqa: F401
import posixpath  # noqa: F401
import queue  # noqa: F401
import re  # noqa: F401
import shutil  # noqa: F401
import sqlite3  # noqa: F401
import ssl  # noqa: F401
import tkinter  # noqa: F401
import tkinter.filedialog  # noqa: F401
import tkinter.messagebox  # noqa: F401
import tkinter.ttk  # noqa: F401
import typing  # noqa: F401
import urllib.parse  # noqa: F401
import urllib.request  # noqa: F401
import xml.etree.ElementTree  # noqa: F401
import zipfile  # noqa: F401

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageTk  # noqa: F401


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def show_error(title: str, message: str) -> None:
    try:
        root = tkinter.Tk()
        root.withdraw()
        tkinter.messagebox.showerror(title, message, parent=root)
        root.destroy()
    except Exception:
        print(f"{title}\n{message}", file=sys.stderr)


def run_bundled_copy() -> None:
    """Downloaded release exe: the app's code is packed inside the exe."""
    try:
        from brickfolio.app import BrickLedgerApp
    except ModuleNotFoundError as error:
        if error.name and error.name.startswith("brickfolio"):
            show_error(
                "BrickLedger",
                "This BrickLedger.exe runs the code next to it. Keep it in the BrickLedger "
                f"folder beside main.py, or download the standalone exe from GitHub.\n\nLooked in: {project_root()}",
            )
            return
        raise
    BrickLedgerApp().mainloop()


def main() -> None:
    root = project_root()
    entry = root / "main.py"
    has_source = entry.is_file() and (root / "brickfolio").is_dir()
    try:
        if not has_source:
            run_bundled_copy()
            return
        # Local exe beside the code: always run the latest source.
        os.chdir(root)
        sys.path.insert(0, str(root))
        runpy.run_path(str(entry), run_name="__main__")
    except ModuleNotFoundError as error:
        show_error(
            "BrickLedger needs a rebuild",
            f"The app now uses '{error.name}', which this exe does not include.\n\n"
            "Rebuild it by running tools\\build_exe.ps1.",
        )
    except Exception:
        show_error("BrickLedger stopped unexpectedly", traceback.format_exc(limit=8))


if __name__ == "__main__":
    main()
