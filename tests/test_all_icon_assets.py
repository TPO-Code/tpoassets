from __future__ import annotations

import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path


def _install_pyside6_stub() -> None:
    if "PySide6.QtGui" in sys.modules:
        return

    qtgui = types.ModuleType("PySide6.QtGui")

    class QIcon:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def isNull(self) -> bool:
            return False

    qtgui.QIcon = QIcon

    pyside6 = types.ModuleType("PySide6")
    pyside6.QtGui = qtgui

    sys.modules["PySide6"] = pyside6
    sys.modules["PySide6.QtGui"] = qtgui


_install_pyside6_stub()

from tpo_assets import add_icon_search_dir, all_icon_assets, clear_icon_search_dirs


class AllIconAssetsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="tpoassets-test-"))

    def tearDown(self) -> None:
        clear_icon_search_dirs()
        shutil.rmtree(self.root)

    def test_nested_icons_are_listed_with_full_relative_path(self) -> None:
        (self.root / "ui" / "network" / "wifi").mkdir(parents=True)
        (self.root / "ui" / "network" / "wifi" / "strong.svg").write_text(
            "<svg/>",
            encoding="utf-8",
        )
        (self.root / "files" / "code" / "python").mkdir(parents=True)
        (self.root / "files" / "code" / "python" / "dark.svg").write_text(
            "<svg/>",
            encoding="utf-8",
        )
        (self.root / "none.svg").write_text("<svg/>", encoding="utf-8")

        add_icon_search_dir(self.root)

        assets = all_icon_assets()

        self.assertIn("ui/network/wifi/strong", assets["ui"])
        self.assertIn("files/code/python/dark", assets["files"])
        self.assertIn("none", assets["general"])


if __name__ == "__main__":
    unittest.main()
