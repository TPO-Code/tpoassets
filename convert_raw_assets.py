from __future__ import annotations

import argparse
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_RAW_DIR = ROOT / "raw"
DEFAULT_OUTPUT_DIR = ROOT / "converted"
SVG_NS = "http://www.w3.org/2000/svg"
BOXY_NS = "https://boxy-svg.com"
ZERO_WIDTH_CHARS = {
    "\u200b",
    "\u200c",
    "\u200d",
    "\ufeff",
}
INVISIBLE_PAINT_VALUES = {"", "none", "transparent"}
GRAPHIC_TAGS = {
    "circle",
    "ellipse",
    "line",
    "path",
    "polygon",
    "polyline",
    "rect",
    "text",
    "tspan",
}


@dataclass(frozen=True)
class ConversionResult:
    source: Path
    status: str
    output_path: Path | None = None
    reason: str | None = None


@dataclass
class PaintContext:
    fill_slots: dict[str, str]
    fill_defaults: list[str]
    has_convertible_graphics: bool = False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert SVG files from raw/ into normalized tpoassets-compatible "
            "assets under converted/."
        )
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help="Directory containing raw SVG files. Defaults to ./raw.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to write converted assets into. Defaults to ./converted.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not remove the output directory before generating assets.",
    )
    return parser.parse_args(argv)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def namespace_name(name: str) -> str | None:
    if not name.startswith("{"):
        return None
    return name[1:].split("}", 1)[0]


def normalize_text_content(text: str) -> str:
    cleaned = "".join(ch for ch in text if ch not in ZERO_WIDTH_CHARS)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def normalize_paint_value(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    lowered = cleaned.lower()
    if lowered in INVISIBLE_PAINT_VALUES:
        return lowered
    if lowered == "currentcolor":
        return "currentColor"
    return cleaned


def is_visible_paint(value: str) -> bool:
    return normalize_paint_value(value).lower() not in INVISIBLE_PAINT_VALUES


def parse_style(style_text: str) -> dict[str, str]:
    declarations: dict[str, str] = {}
    for chunk in style_text.split(";"):
        piece = chunk.strip()
        if not piece or ":" not in piece:
            continue
        key, value = piece.split(":", 1)
        declarations[key.strip()] = value.strip()
    return declarations


def format_style(declarations: dict[str, str]) -> str:
    return "; ".join(f"{key}: {value}" for key, value in declarations.items()) + ";"


def assign_fill_slot(value: str, context: PaintContext) -> str:
    normalized = normalize_paint_value(value)
    if normalized == "currentColor":
        context.has_convertible_graphics = True
        return "var(--foreground)"

    existing_slot = context.fill_slots.get(normalized)
    if existing_slot is not None:
        context.has_convertible_graphics = True
        return existing_slot

    if len(context.fill_slots) >= 2:
        raise ValueError("more than two brush colors were found")

    slot_name = f"var(--color-{len(context.fill_slots) + 1})"
    context.fill_slots[normalized] = slot_name
    context.fill_defaults.append(normalized)
    context.has_convertible_graphics = True
    return slot_name


def rewrite_paint(value: str, prop: str, context: PaintContext) -> str:
    normalized = normalize_paint_value(value)
    if not is_visible_paint(normalized):
        return normalized

    if prop == "stroke":
        context.has_convertible_graphics = True
        return "var(--foreground)"

    if prop == "fill":
        return assign_fill_slot(normalized, context)

    return normalized


def clean_text_nodes(element: ET.Element) -> None:
    if element.text is not None:
        element.text = "".join(ch for ch in element.text if ch not in ZERO_WIDTH_CHARS)
    for child in element:
        if child.tail is not None:
            child.tail = "".join(ch for ch in child.tail if ch not in ZERO_WIDTH_CHARS)


def remove_unsupported_children(element: ET.Element) -> None:
    for child in list(element):
        child_namespace = namespace_name(child.tag)
        child_tag = local_name(child.tag)

        if child_namespace == BOXY_NS or child_tag in {"defs", "style"}:
            element.remove(child)
            continue

        remove_unsupported_children(child)

        if child_tag in {"text", "tspan"}:
            clean_text_nodes(child)
            if not normalize_text_content("".join(child.itertext())) and not list(child):
                element.remove(child)


def rewrite_attributes(
    element: ET.Element,
    context: PaintContext,
    *,
    is_root: bool,
) -> None:
    updated_attributes: dict[str, str] = {}
    style_declarations = parse_style(element.attrib.get("style", ""))

    for attr_name, attr_value in element.attrib.items():
        if attr_name == "style":
            continue

        if namespace_name(attr_name) is not None:
            continue

        key = local_name(attr_name)
        if key == "id":
            continue
        if is_root and key in {"height", "style", "width"}:
            continue

        if key in {"fill", "stroke"}:
            updated_attributes[key] = rewrite_paint(attr_value, key, context)
            continue

        updated_attributes[key] = attr_value

    for key in ("fill", "stroke"):
        if key not in style_declarations:
            continue
        style_declarations[key] = rewrite_paint(style_declarations[key], key, context)

    if style_declarations:
        updated_attributes["style"] = format_style(style_declarations)

    element.attrib.clear()
    element.attrib.update(updated_attributes)

    tag = local_name(element.tag)
    if tag in GRAPHIC_TAGS and tag != "tspan":
        if tag != "text" or normalize_text_content("".join(element.itertext())):
            context.has_convertible_graphics = True


def rewrite_tree(root: ET.Element, context: PaintContext) -> None:
    for element in root.iter():
        if namespace_name(element.tag) == BOXY_NS:
            continue
        rewrite_attributes(element, context, is_root=element is root)


def resolve_view_box(root: ET.Element) -> str:
    view_box = (root.attrib.get("viewBox") or "").strip()
    if view_box:
        return view_box

    width = (root.attrib.get("width") or "").strip().removesuffix("px")
    height = (root.attrib.get("height") or "").strip().removesuffix("px")
    if width and height:
        return f"0 0 {width} {height}"
    return "0 0 64 64"


def build_style_element(context: PaintContext) -> ET.Element:
    style_element = ET.Element(f"{{{SVG_NS}}}style")
    lines = ["    :root {", "      --foreground: currentColor;"]
    for index, color in enumerate(context.fill_defaults, start=1):
        lines.append(f"      --color-{index}: {color};")
    lines.append("    }")
    style_element.text = "\n" + "\n".join(lines) + "\n  "
    return style_element


def serialize_svg(root: ET.Element) -> str:
    ET.register_namespace("", SVG_NS)
    ET.indent(root, space="  ")
    rendered = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + rendered + "\n"


def target_output_path(source_path: Path, output_dir: Path) -> Path:
    return output_dir / "files" / source_path.name


def convert_svg_text(svg_text: str) -> str:
    root = ET.fromstring(svg_text)
    if local_name(root.tag) != "svg":
        raise ValueError("root element is not an SVG")

    view_box = resolve_view_box(root)
    remove_unsupported_children(root)

    context = PaintContext(fill_slots={}, fill_defaults=[])
    rewrite_tree(root, context)

    if not context.has_convertible_graphics:
        raise ValueError("no convertible graphics were found")

    root.attrib.clear()
    root.set("viewBox", view_box)
    root.insert(0, build_style_element(context))

    return serialize_svg(root)


def convert_svg_file(source_path: Path, output_dir: Path) -> ConversionResult:
    try:
        svg_text = source_path.read_text(encoding="utf-8")
        converted_text = convert_svg_text(svg_text)
    except ET.ParseError as exc:
        return ConversionResult(source_path, "skipped", reason=f"XML parse error: {exc}")
    except ValueError as exc:
        return ConversionResult(source_path, "skipped", reason=str(exc))

    output_path = target_output_path(source_path, output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(converted_text, encoding="utf-8")
    return ConversionResult(source_path, "converted", output_path=output_path)


def convert_directory(raw_dir: Path, output_dir: Path, *, clean: bool) -> list[ConversionResult]:
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[ConversionResult] = []
    for source_path in sorted(raw_dir.glob("*.svg")):
        results.append(convert_svg_file(source_path, output_dir))
    return results


def print_summary(results: list[ConversionResult], output_dir: Path) -> None:
    converted = [result for result in results if result.status == "converted"]
    skipped = [result for result in results if result.status == "skipped"]

    print(f"Converted {len(converted)} asset(s) into {output_dir}")
    for result in converted:
        assert result.output_path is not None
        print(f"  wrote {result.output_path.relative_to(output_dir.parent)}")

    if skipped:
        print(f"Skipped {len(skipped)} asset(s):")
        for result in skipped:
            reason = result.reason or "unknown reason"
            print(f"  skipped {result.source.name}: {reason}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    raw_dir = args.raw_dir.resolve()
    output_dir = args.output_dir.resolve()

    if not raw_dir.is_dir():
        print(f"Raw directory does not exist: {raw_dir}", file=sys.stderr)
        return 1

    results = convert_directory(raw_dir, output_dir, clean=not args.no_clean)
    print_summary(results, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
