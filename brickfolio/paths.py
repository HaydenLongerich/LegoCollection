"""Where BrickLedger reads its bundled files and writes the user's own data.

Running from the source folder (python main.py, or the local BrickLedger.exe that
sits next to the code), everything lives in the project folder as before.

The downloadable BrickLedger.exe unpacks its code to a temporary folder on every
launch, so personal data must go somewhere permanent instead:
%LOCALAPPDATA%\\BrickLedger (data\\ and exports\\ inside it).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Read-only resources shipped with the app: Sets catalogue, logo, set images.
RESOURCE_ROOT = Path(__file__).resolve().parent.parent


def _is_bundled_copy() -> bool:
    bundle = getattr(sys, "_MEIPASS", None)
    if not getattr(sys, "frozen", False) or not bundle:
        return False
    return RESOURCE_ROOT == Path(bundle).resolve()


def _user_root() -> Path:
    if _is_bundled_copy():
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "BrickLedger"
    return RESOURCE_ROOT


# Writable, private: the database, image cache, and CSV exports.
USER_ROOT = _user_root()
DATA_PATH = USER_ROOT / "data"
EXPORTS_PATH = USER_ROOT / "exports"
