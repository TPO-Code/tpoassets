from __future__ import annotations

import hashlib
import re
import tempfile
from pathlib import Path

from PySide6.QtGui import QIcon

from .api import icon_path

_QICON_CACHE: dict[
    tuple[str, str | None, str | None, str | None, bool, bool],
    QIcon,
] = {}

_CSS_VAR_DEF_RE = re.compile(r"(--([a-zA-Z0-9_-]+)\s*:\s*)([^;]+)(;)")
_CSS_VAR_USE_RE_TEMPLATE = r"var\(\s*--{var_name}\s*(?:,\s*([^)]+))?\)"
_HEX_RGBA_RE = re.compile(r"^#([0-9a-fA-F]{8})$")
_HEX_RGBA_SHORT_RE = re.compile(r"^#([0-9a-fA-F]{4})$")
_STYLE_ALPHA_COLOR_RE = re.compile(r"(?P<prop>fill|stroke)\s*:\s*#(?P<argb>[0-9a-fA-F]{8})\s*;")
_ATTR_ALPHA_COLOR_RE = re.compile(r'(?P<prop>fill|stroke)=\"#(?P<argb>[0-9a-fA-F]{8})\"')


def icon(
    name: str,
    *,
    foreground: str | None = "#FFFFFF",
    color_1: str | None = None,
    color_2: str | None = None,
    mono: bool = False,
    silhouette: bool = False,
) -> QIcon:
    """
    Resolve an icon by name and optionally override SVG color variables.

    SVG assets should define only the variables they actually use, for example:

        <style>
          :root {
            --foreground: currentColor;
            --color-1: #ffd43b;
            --color-2: #3776ab;
          }
        </style>

    And then use them like:

        stroke: var(--foreground);
        fill: var(--color-1);
        fill: var(--color-2);

    Behavior:
    - normal:
        icon("files/py")
        icon("files/py", foreground="#e6e6e6")
        icon("files/py", color_1="#ff00ff")
    - mono:
        icon("files/py", mono=True)
        icon("files/py", mono=True, foreground="#ff0000")
      Result:
        defined accent channels become transparent
    - silhouette:
        icon("files/py", silhouette=True)
        icon("files/py", silhouette=True, foreground="#000000")
      Result:
        all defined channels become the foreground/currentColor
    """
    path = icon_path(name)

    if not _needs_render(
        foreground=foreground,
        color_1=color_1,
        color_2=color_2,
        mono=mono,
        silhouette=silhouette,
    ):
        return QIcon(str(path))

    cache_key = (str(path), foreground, color_1, color_2, mono, silhouette)
    cached_icon = _QICON_CACHE.get(cache_key)
    if cached_icon is not None and not cached_icon.isNull():
        return cached_icon

    if path.suffix.lower() != ".svg":
        qicon = QIcon(str(path))
        _QICON_CACHE[cache_key] = qicon
        return qicon

    svg_text = _read_text(path)
    rendered_text = _render_svg(
        svg_text,
        foreground=foreground,
        color_1=color_1,
        color_2=color_2,
        mono=mono,
        silhouette=silhouette,
    )
    rendered_path = _materialize_svg(
        path,
        rendered_text,
        foreground=foreground,
        color_1=color_1,
        color_2=color_2,
        mono=mono,
        silhouette=silhouette,
    )

    qicon = QIcon(str(rendered_path))
    _QICON_CACHE[cache_key] = qicon
    return qicon


def clear_icon_cache() -> None:
    _QICON_CACHE.clear()


def _needs_render(
    *,
    foreground: str | None,
    color_1: str | None,
    color_2: str | None,
    mono: bool,
    silhouette: bool,
) -> bool:
    return any((
        foreground is not None,
        color_1 is not None,
        color_2 is not None,
        mono,
        silhouette,
    ))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _render_svg(
    svg_text: str,
    *,
    foreground: str | None,
    color_1: str | None,
    color_2: str | None,
    mono: bool,
    silhouette: bool,
) -> str:
    defined_vars = _extract_css_var_definitions(svg_text)
    if not defined_vars:
        return svg_text

    resolved_vars = _resolve_slot_values(
        defined_vars,
        foreground=foreground,
        color_1=color_1,
        color_2=color_2,
        mono=mono,
        silhouette=silhouette,
    )

    rendered = svg_text

    # Pass 1: update variable definitions in the style block.
    rendered = _replace_css_var_definitions(rendered, resolved_vars)

    # Pass 2: replace var(--...) usages with concrete values for renderer compatibility.
    for var_name, value in resolved_vars.items():
        rendered = _replace_css_var_usage(rendered, var_name, value)

    # Pass 3: resolve any leftovers that use fallbacks.
    rendered = _resolve_remaining_var_functions(rendered)

    # Pass 4: split alpha-bearing colors into RGB + explicit opacity,
    # which is more reliable for Qt's SVG renderer than embedded alpha.
    rendered = _expand_alpha_paint_properties(rendered)

    return rendered


def _extract_css_var_definitions(svg_text: str) -> dict[str, str]:
    definitions: dict[str, str] = {}
    for match in _CSS_VAR_DEF_RE.finditer(svg_text):
        var_name = match.group(2).strip()
        value = match.group(3).strip()
        definitions[var_name] = value
    return definitions


def _resolve_slot_values(
    defined_vars: dict[str, str],
    *,
    foreground: str | None,
    color_1: str | None,
    color_2: str | None,
    mono: bool,
    silhouette: bool,
) -> dict[str, str]:
    resolved = dict(defined_vars)

    if "foreground" in resolved and foreground is not None:
        resolved["foreground"] = foreground

    if "color-1" in resolved and color_1 is not None:
        resolved["color-1"] = color_1

    if "color-2" in resolved and color_2 is not None:
        resolved["color-2"] = color_2

    final_foreground = resolved.get("foreground", "currentColor")

    if silhouette:
        for key in ("foreground", "color-1", "color-2"):
            if key in resolved:
                resolved[key] = final_foreground

    if mono:
        for key in ("color-1", "color-2"):
            if key in resolved:
                resolved[key] = "transparent"

    return {
        key: _normalize_svg_color_value(value)
        for key, value in resolved.items()
    }


def _normalize_svg_color_value(value: str) -> str:
    text = str(value).strip()

    match = _HEX_RGBA_RE.match(text)
    if match:
        hex_value = match.group(1)
        red = hex_value[0:2]
        green = hex_value[2:4]
        blue = hex_value[4:6]
        alpha = hex_value[6:8]
        return f"#{alpha}{red}{green}{blue}"

    match = _HEX_RGBA_SHORT_RE.match(text)
    if match:
        short_value = match.group(1)
        expanded = "".join(ch * 2 for ch in short_value)
        red = expanded[0:2]
        green = expanded[2:4]
        blue = expanded[4:6]
        alpha = expanded[6:8]
        return f"#{alpha}{red}{green}{blue}"

    return text


def _format_alpha(alpha: int) -> str:
    return f"{alpha / 255:.4f}".rstrip("0").rstrip(".")


def _replace_css_var_definitions(svg_text: str, values: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        full_prefix = match.group(1)
        var_name = match.group(2).strip()
        trailing_semicolon = match.group(4)
        value = values.get(var_name, match.group(3).strip())
        return f"{full_prefix}{value}{trailing_semicolon}"

    return _CSS_VAR_DEF_RE.sub(repl, svg_text)


def _replace_css_var_usage(svg_text: str, var_name: str, value: str) -> str:
    pattern = _CSS_VAR_USE_RE_TEMPLATE.format(var_name=re.escape(var_name))
    return re.sub(pattern, value, svg_text)


def _resolve_remaining_var_functions(svg_text: str) -> str:
    """
    Resolve any remaining var(--name, fallback) usages to their fallback.
    If there is no fallback, leave them untouched.
    """
    def repl(match: re.Match[str]) -> str:
        fallback = match.group(1)
        if fallback is None:
            return match.group(0)
        return fallback.strip()

    pattern = r"var\(\s*--[^,\s)]+(?:\s*,\s*([^)]+))?\)"
    return re.sub(pattern, repl, svg_text)


def _expand_alpha_paint_properties(svg_text: str) -> str:
    def style_repl(match: re.Match[str]) -> str:
        prop = match.group("prop")
        argb = match.group("argb")
        alpha = int(argb[0:2], 16)
        rgb = argb[2:8]
        return f"{prop}: #{rgb}; {prop}-opacity: {_format_alpha(alpha)};"

    svg_text = _STYLE_ALPHA_COLOR_RE.sub(style_repl, svg_text)

    def attr_repl(match: re.Match[str]) -> str:
        prop = match.group("prop")
        argb = match.group("argb")
        alpha = int(argb[0:2], 16)
        rgb = argb[2:8]
        return f'{prop}="#{rgb}" {prop}-opacity="{_format_alpha(alpha)}"'

    return _ATTR_ALPHA_COLOR_RE.sub(attr_repl, svg_text)


def _materialize_svg(
    source_path: Path,
    svg_text: str,
    *,
    foreground: str | None,
    color_1: str | None,
    color_2: str | None,
    mono: bool,
    silhouette: bool,
) -> Path:
    cache_dir = _generated_svg_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    fingerprint = _svg_fingerprint(
        source_path,
        svg_text,
        foreground=foreground,
        color_1=color_1,
        color_2=color_2,
        mono=mono,
        silhouette=silhouette,
    )
    file_name = f"{source_path.stem}--{fingerprint}.svg"
    out_path = cache_dir / file_name

    if not out_path.is_file():
        out_path.write_text(svg_text, encoding="utf-8")

    return out_path


def _generated_svg_cache_dir() -> Path:
    return Path(tempfile.gettempdir()) / "tpo_assets_qt_svg_cache"


def _svg_fingerprint(
    source_path: Path,
    svg_text: str,
    *,
    foreground: str | None,
    color_1: str | None,
    color_2: str | None,
    mono: bool,
    silhouette: bool,
) -> str:
    h = hashlib.sha256()
    h.update(str(source_path).encode("utf-8", errors="replace"))
    h.update(b"\0")
    h.update(svg_text.encode("utf-8", errors="replace"))
    h.update(b"\0")
    h.update(str(foreground).encode("utf-8", errors="replace"))
    h.update(b"\0")
    h.update(str(color_1).encode("utf-8", errors="replace"))
    h.update(b"\0")
    h.update(str(color_2).encode("utf-8", errors="replace"))
    h.update(b"\0")
    h.update(str(mono).encode("utf-8", errors="replace"))
    h.update(b"\0")
    h.update(str(silhouette).encode("utf-8", errors="replace"))
    return h.hexdigest()[:16]
