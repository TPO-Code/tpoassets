from __future__ import annotations

from pathlib import Path

from .registry import ICON_DIRS
from .resolver import list_icon_assets, resolve_icon_path, resolve_icon_search_paths


def add_icon_search_dir(directory: str | Path) -> Path:
    """
    Register a project/user icon directory.

    Expected structure mirrors the packaged icons, for example:
        my_icons/
            txt.svg
            none.svg
            files/
                default.svg
                py.svg
    """
    return ICON_DIRS.add(directory)


def clear_icon_search_dirs() -> None:
    ICON_DIRS.clear()


def registered_icon_search_dirs() -> list[Path]:
    return ICON_DIRS.paths()


def icon_path(name: str) -> Path:
    """
    Resolve an icon name to a concrete SVG file path.

    Modes:
      - "txt"       -> generic icon lookup, fallback none.svg
      - ".txt"      -> file extension lookup, fallback files/default.svg
      - "files/txt" -> explicit category lookup, fallback files/default.svg
    """
    return resolve_icon_path(name)


def icon_paths(name: str) -> list[Path]:
    """
    Return the likely resolution chain for debugging.
    First item is the actual chosen path when possible.
    """
    return resolve_icon_search_paths(name)


def all_icon_assets() -> dict[str, list[str]]:
    """
    Returns a unified list of all built-in and user-defined icons 
    divided into sections based on their directory structure.
    """
    return list_icon_assets()    
