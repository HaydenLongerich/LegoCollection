"""Make sure BrickLedger.exe bundles every module the live source imports."""

import ast
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "tools" / "launcher.py"
SOURCES = [ROOT / "main.py", *sorted((ROOT / "brickfolio").glob("*.py"))]


def imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
            # "from PIL import ImageTk" imports the PIL.ImageTk submodule;
            # "from typing import Any" imports a name, not a module.
            for alias in node.names:
                if is_module(f"{node.module}.{alias.name}"):
                    modules.add(f"{node.module}.{alias.name}")
    return modules


def is_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


class LauncherTests(unittest.TestCase):
    def test_launcher_bundles_every_runtime_import(self):
        bundled = imported_modules(LAUNCHER)
        needed = set().union(*(imported_modules(path) for path in SOURCES))
        needed = {name for name in needed if name.split(".")[0] not in {"brickfolio", "__future__"}}
        # Built-in modules are always available inside the exe.
        needed = {name for name in needed if name not in sys.builtin_module_names}
        # "import xml.etree.ElementTree" also bundles its parent package xml.etree.
        missing = sorted(
            name for name in needed
            if name not in bundled and not any(item.startswith(f"{name}.") for item in bundled)
        )
        self.assertEqual(
            missing, [],
            f"Add these imports to tools/launcher.py and run tools/build_exe.ps1: {missing}",
        )


if __name__ == "__main__":
    unittest.main()
