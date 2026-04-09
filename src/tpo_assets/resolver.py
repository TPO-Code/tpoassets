from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from importlib.resources import as_file, files

from .registry import ICON_DIRS

BUILTIN_FILE_ICON_ALIASES: dict[str, str] = {
    "htm": "angle_bracket_file",
    "html": "angle_bracket_file",
    "xhtml": "angle_bracket_file",
    "xml": "angle_bracket_file",
    "cpp": "curly_bracket_file",
    "h": "curly_bracket_file",
    "cu": "curly_bracket_file",
    "md": "hash_file",
    "svg": "image",
    "png": "image",
    "jpg": "image",
    "gif": "image",
}


@dataclass(frozen=True)
class IconRequest:
    raw: str
    mode: str
    category: str | None
    name: str
    fallback_name: str


def parse_icon_request(name: str) -> IconRequest:
    text = str(name or "").strip()
    if not text:
        return IconRequest(
            raw=text,
            mode="generic",
            category=None,
            name="",
            fallback_name="none.svg",
        )

    if text.startswith("."):
        ext = _normalize_extension(text)
        return IconRequest(
            raw=text,
            mode="file-extension",
            category="files",
            name=ext,
            fallback_name="default.svg",
        )

    if "/" in text:
        category, icon_name = _split_category_name(text)
        fallback = "default.svg" if category == "files" else "none.svg"
        return IconRequest(
            raw=text,
            mode="category",
            category=category,
            name=icon_name,
            fallback_name=fallback,
        )

    return IconRequest(
        raw=text,
        mode="generic",
        category=None,
        name=_normalize_name(text),
        fallback_name="none.svg",
    )


def resolve_icon_path(name: str) -> Path:
    request = parse_icon_request(name)

    direct = _find_requested_icon(request)
    if direct is not None:
        return direct

    builtin_alias = _find_builtin_file_alias_icon(request)
    if builtin_alias is not None:
        return builtin_alias

    fallback = _find_fallback_icon(request)
    if fallback is not None:
        return fallback

    packaged_none = _packaged_icon_path("none.svg")
    if packaged_none is not None:
        return packaged_none

    raise FileNotFoundError(
        f"Unable to resolve icon '{name}' and packaged 'none.svg' was not found."
    )


def resolve_icon_search_paths(name: str) -> list[Path]:
    request = parse_icon_request(name)
    results: list[Path] = []

    direct = _find_requested_icon(request)
    if direct is not None:
        results.append(direct)

    builtin_alias = _find_builtin_file_alias_icon(request)
    if builtin_alias is not None and builtin_alias not in results:
        results.append(builtin_alias)

    fallback = _find_fallback_icon(request)
    if fallback is not None and fallback not in results:
        results.append(fallback)

    packaged_none = _packaged_icon_path("none.svg")
    if packaged_none is not None and packaged_none not in results:
        results.append(packaged_none)

    return results


def _find_requested_icon(request: IconRequest) -> Path | None:
    if not request.name:
        return None

    relative = _relative_svg_path(request.category, request.name)

    for root in _custom_icon_roots():
        candidate = root / relative
        if candidate.is_file():
            return candidate

    packaged = _packaged_icon_path(relative)
    if packaged is not None:
        return packaged

    return None


def _find_fallback_icon(request: IconRequest) -> Path | None:
    if request.category == "files":
        for root in _custom_icon_roots():
            candidate = root / "files" / request.fallback_name
            if candidate.is_file():
                return candidate

        packaged = _packaged_icon_path(f"files/{request.fallback_name}")
        if packaged is not None:
            return packaged

    fallback_name = request.fallback_name
    for root in _custom_icon_roots():
        candidate = root / fallback_name
        if candidate.is_file():
            return candidate

    packaged = _packaged_icon_path(fallback_name)
    if packaged is not None:
        return packaged

    return None


def _find_builtin_file_alias_icon(request: IconRequest) -> Path | None:
    if request.category != "files" or not request.name:
        return None

    alias_name = BUILTIN_FILE_ICON_ALIASES.get(request.name)
    if not alias_name:
        return None

    return _packaged_icon_path(f"files/{alias_name}.svg")


def _custom_icon_roots() -> Iterable[Path]:
    return ICON_DIRS.paths()


def _relative_svg_path(category: str | None, name: str) -> str:
    file_name = f"{name}.svg"
    if category:
        return f"{category}/{file_name}"
    return file_name


def _split_category_name(text: str) -> tuple[str, str]:
    category, icon_name = text.split("/", 1)
    return _normalize_name(category), _normalize_name(icon_name)


def _normalize_extension(text: str) -> str:
    raw = text.strip().lower()
    if raw.startswith("."):
        raw = raw[1:]
    if not raw:
        return "default"
    return _normalize_name(raw)


def _normalize_name(text: str) -> str:
    value = str(text or "").strip().lower().replace("\\", "/")
    value = os.path.basename(value) if "/" not in value else value
    return value.strip("/").replace(".svg", "")


def _packaged_icon_path(relative: str) -> Path | None:
    resource = files("tpo_assets").joinpath("assets", "icons", relative)
    try:
        with as_file(resource) as path:
            if path.is_file():
                return Path(path)
    except FileNotFoundError:
        return None
    except Exception:
        return None
    return None

def list_icon_assets() -> dict[str, list[str]]:
    """
    Scan all registered and built-in icon directories and return a 
    structured dictionary of icons grouped by their top-level directory.
    """
    roots = list(_custom_icon_roots())
    pkg_resource = files("tpo_assets").joinpath("assets", "icons")
    
    with as_file(pkg_resource) as pkg_path:
        all_roots = [pkg_path] + roots
        registry: dict[str, set[str]] = {}
        
        for root in all_roots:
            if not root.is_dir():
                continue
            for svg_file in root.rglob("*.svg"):
                # Calculate relative path and strip extension
                rel_path = svg_file.relative_to(root).with_suffix("")
                parts = rel_path.parts
                
                # Determine section (top level folder or 'general' for root icons)
                section = parts[0] if len(parts) > 1 else "general"
                icon_path_str = "/".join(parts)
                
                registry.setdefault(section, set()).add(icon_path_str)
        
        # Sort sections and their contained icon paths alphabetically
        return {
            section: sorted(list(icons)) 
            for section, icons in sorted(registry.items())
        }
