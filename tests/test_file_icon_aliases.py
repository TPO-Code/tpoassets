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

from tpo_assets import add_icon_search_dir, clear_icon_search_dirs, icon_path, icon_paths


class FileIconAliasTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_icon_search_dirs()

    def test_builtin_alias_resolves_to_packaged_icon(self) -> None:
        resolved = icon_path(".html")

        self.assertEqual("angle_bracket_file.svg", resolved.name)
        self.assertEqual("files", resolved.parent.name)

    def test_builtin_alias_applies_to_explicit_files_lookup(self) -> None:
        resolved = icon_path("files/xml")

        self.assertEqual("angle_bracket_file.svg", resolved.name)
        self.assertEqual("files", resolved.parent.name)

    def test_direct_python_file_icon_resolves_without_alias(self) -> None:
        resolved = icon_path(".py")

        self.assertEqual("py.svg", resolved.name)
        self.assertEqual("files", resolved.parent.name)

    def test_custom_file_icon_wins_before_builtin_alias(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="tpoassets-alias-"))
        try:
            (root / "files").mkdir(parents=True)
            custom_icon = root / "files" / "html.svg"
            custom_icon.write_text("<svg/>", encoding="utf-8")

            add_icon_search_dir(root)

            resolved = icon_path(".html")
            search_paths = icon_paths(".html")

            self.assertEqual(custom_icon, resolved)
            self.assertEqual(custom_icon, search_paths[0])
            self.assertTrue(
                any(path.name == "angle_bracket_file.svg" for path in search_paths[1:])
            )
        finally:
            clear_icon_search_dirs()
            shutil.rmtree(root)
