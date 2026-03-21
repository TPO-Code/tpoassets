from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
SETTINGS_PATH = ROOT / "local.json"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtCore import QByteArray, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tpo_assets import all_icon_assets, clear_icon_cache, icon, icon_path
from tpo_assets.resolver import BUILTIN_FILE_ICON_ALIASES
from tpo_assets.qt import _read_text, _render_svg


COLUMNS = 10
LABEL_HEIGHT = 36
PAGE_MARGIN = 28
SECTION_GAP = 24
HEADING_HEIGHT = 30
HEADING_GAP = 8
OUTPUT_PATH = ROOT / "icons.png"


@dataclass(frozen=True)
class RenderOptions:
    background: str
    foreground: str | None
    color_1: str | None
    color_2: str | None
    antialiasing: bool
    icon_border: bool
    border_color: str
    icon_size: int
    spacing: int
    column_count: int
    mono: bool
    silhouette: bool


def normalized_color(text: str) -> str | None:
    value = text.strip()
    if not value:
        return None

    color = QColor(value)
    if not color.isValid():
        raise ValueError(f"Invalid color value: {text!r}")
    return color.name(QColor.NameFormat.HexRgb)


def contrasting_text_color(background: QColor) -> QColor:
    return QColor("#ffffff") if background.lightness() < 128 else QColor("#111111")


def grouped_asset_names() -> list[tuple[str, list[str]]]:
    assets_by_section = all_icon_assets()
    all_names = {
        asset_name
        for section_assets in assets_by_section.values()
        for asset_name in section_assets
    }

    # Alias-only built-in file icons do not exist as standalone SVG files,
    # so include them as synthetic entries in the generated sheet.
    for alias_name in BUILTIN_FILE_ICON_ALIASES:
        all_names.add(f"files/{alias_name}")

    grouped: dict[str, list[str]] = {}
    for asset_name in sorted(all_names):
        asset_path = PurePosixPath(asset_name)
        directory = "root" if len(asset_path.parts) == 1 else str(asset_path.parent)
        grouped.setdefault(directory, []).append(asset_name)

    return [
        (directory, sorted(asset_names))
        for directory, asset_names in sorted(
            grouped.items(),
            key=lambda item: (item[0] != "root", item[0]),
        )
    ]


def cell_width(options: RenderOptions) -> int:
    return max(options.icon_size + options.spacing, 104)


def cell_height(options: RenderOptions) -> int:
    return options.icon_size + options.spacing + LABEL_HEIGHT


def image_height_for_groups(
    groups: list[tuple[str, list[str]]],
    options: RenderOptions,
) -> int:
    height = PAGE_MARGIN
    for _, asset_names in groups:
        rows = max(1, math.ceil(len(asset_names) / options.column_count))
        height += HEADING_HEIGHT + HEADING_GAP + (rows * cell_height(options)) + SECTION_GAP
    return height + PAGE_MARGIN - SECTION_GAP


def safe_icon_output_name(icon_name: str) -> str:
    cleaned = icon_name.strip().lower()
    if cleaned.startswith("."):
        cleaned = cleaned[1:]
    cleaned = cleaned.replace("\\", "_").replace("/", "_")
    cleaned = cleaned.replace(" ", "_")
    return cleaned or "icon"


def apply_render_hints(painter: QPainter, antialiasing: bool) -> None:
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, antialiasing)


def render_icon_pixmap(icon_name: str, options: RenderOptions) -> QPixmap:
    path = icon_path(icon_name.strip())

    if path.suffix.lower() != ".svg":
        return icon(
            icon_name.strip(),
            foreground=options.foreground,
            color_1=options.color_1,
            color_2=options.color_2,
            mono=options.mono,
            silhouette=options.silhouette,
        ).pixmap(QSize(options.icon_size, options.icon_size))

    svg_text = _read_text(path)
    rendered_svg = _render_svg(
        svg_text,
        foreground=options.foreground,
        color_1=options.color_1,
        color_2=options.color_2,
        mono=options.mono,
        silhouette=options.silhouette,
    )

    pixmap = QPixmap(options.icon_size, options.icon_size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    apply_render_hints(painter, options.antialiasing)
    renderer = QSvgRenderer(QByteArray(rendered_svg.encode("utf-8")))
    renderer.render(painter, QRect(0, 0, options.icon_size, options.icon_size))
    painter.end()
    return pixmap


def load_local_settings() -> dict[str, object]:
    if not SETTINGS_PATH.is_file():
        return {}

    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_local_settings(data: dict[str, object]) -> None:
    SETTINGS_PATH.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def generate_icon_sheet(options: RenderOptions, output_path: Path) -> tuple[Path, int]:
    groups = grouped_asset_names()
    if not groups:
        raise RuntimeError("No icons were found.")

    clear_icon_cache()

    width = PAGE_MARGIN * 2 + (options.column_count * cell_width(options))
    height = image_height_for_groups(groups, options)

    background_color = QColor(options.background)
    text_color = contrasting_text_color(background_color)
    border_color = QColor(options.border_color)

    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(background_color)

    painter = QPainter(image)
    apply_render_hints(painter, options.antialiasing)
    painter.setPen(QPen(text_color))

    heading_font = QFont()
    heading_font.setPointSize(13)
    heading_font.setBold(True)

    label_font = QFont()
    label_font.setPointSize(9)

    y = PAGE_MARGIN
    total_icons = 0

    for directory, asset_names in groups:
        painter.setFont(heading_font)
        painter.drawText(
            QRect(PAGE_MARGIN, y, width - (PAGE_MARGIN * 2), HEADING_HEIGHT),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            directory,
        )
        y += HEADING_HEIGHT + HEADING_GAP

        painter.setFont(label_font)

        for index, asset_name in enumerate(asset_names):
            column = index % options.column_count
            row = index // options.column_count
            current_cell_width = cell_width(options)
            current_cell_height = cell_height(options)
            cell_x = PAGE_MARGIN + (column * current_cell_width)
            cell_y = y + (row * current_cell_height)
            icon_x = cell_x + (current_cell_width - options.icon_size) // 2
            icon_y = cell_y
            text_y = icon_y + options.icon_size + max(6, options.spacing // 2)

            icon_name = PurePosixPath(asset_name).name
            if options.icon_border:
                painter.setPen(QPen(border_color, 1.4))
                painter.drawRoundedRect(
                    icon_x - 5,
                    icon_y - 5,
                    options.icon_size + 10,
                    options.icon_size + 10,
                    6,
                    6,
                )
                painter.setPen(QPen(text_color))

            pixmap = render_icon_pixmap(asset_name, options)
            painter.drawPixmap(icon_x, cell_y, pixmap)

            text_rect = QRect(
                cell_x + 4,
                text_y,
                current_cell_width - 8,
                LABEL_HEIGHT,
            )
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignHCenter
                | Qt.AlignmentFlag.AlignTop
                | Qt.TextFlag.TextWordWrap,
                icon_name,
            )
            total_icons += 1

        rows = max(1, math.ceil(len(asset_names) / options.column_count))
        y += rows * current_cell_height + SECTION_GAP

    painter.end()

    if not image.save(str(output_path), "PNG"):
        raise RuntimeError(f"Failed to save {output_path}")

    return output_path, total_icons


def render_single_icon_png(
    icon_name: str,
    options: RenderOptions,
    output_path: Path,
) -> Path:
    if not icon_name.strip():
        raise ValueError("Single icon name cannot be blank.")

    clear_icon_cache()

    background_color = QColor(options.background)
    border_padding = 12 if options.icon_border else 0
    canvas_size = max(256, options.icon_size + (options.spacing * 2) + border_padding + 24)
    image = QImage(canvas_size, canvas_size, QImage.Format.Format_ARGB32)
    image.fill(background_color)

    painter = QPainter(image)
    apply_render_hints(painter, options.antialiasing)

    pixmap = render_icon_pixmap(icon_name, options)
    icon_x = (canvas_size - pixmap.width()) // 2
    icon_y = (canvas_size - pixmap.height()) // 2

    if options.icon_border:
        painter.setPen(QPen(QColor(options.border_color), 1.6))
        painter.drawRoundedRect(
            icon_x - 5,
            icon_y - 5,
            options.icon_size + 10,
            options.icon_size + 10,
            6,
            6,
        )

    painter.drawPixmap(icon_x, icon_y, pixmap)
    painter.end()

    if not image.save(str(output_path), "PNG"):
        raise RuntimeError(f"Failed to save {output_path}")

    return output_path


class ColorField(QWidget):
    def __init__(self, label: str, default: str = "", *, allow_blank: bool = True) -> None:
        super().__init__()
        self.label = label
        self.allow_blank = allow_blank
        self.line_edit = QLineEdit(default)
        if allow_blank:
            self.line_edit.setPlaceholderText("Leave blank to ignore")
        else:
            self.line_edit.setPlaceholderText("Required")

        pick_button = QPushButton("Pick")
        pick_button.clicked.connect(self.pick_color)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.line_edit)
        layout.addWidget(pick_button)

    def pick_color(self) -> None:
        initial = QColor(self.line_edit.text().strip() or "#111111")
        if not initial.isValid():
            initial = QColor("#111111")

        color = QColorDialog.getColor(initial, self, f"Select {self.label}")
        if color.isValid():
            self.line_edit.setText(color.name(QColor.NameFormat.HexRgb))

    def value(self) -> str | None:
        value = normalized_color(self.line_edit.text())
        if value is None and not self.allow_blank:
            raise ValueError(f"{self.label} cannot be blank.")
        return value


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("tpo_assets icon sheet generator")
        self.resize(620, 360)

        self.background_field = ColorField("background", "#ffffff", allow_blank=False)
        self.foreground_field = ColorField("foreground", "#111111")
        self.color_1_field = ColorField("color_1")
        self.color_2_field = ColorField("color_2")
        self.border_color_field = ColorField("border color", "#d0d0d0", allow_blank=False)
        self.single_icon_field = QLineEdit(".py")
        self.single_icon_field.setPlaceholderText("Example: .py or files/py")
        self.antialiasing_checkbox = QCheckBox("Antialiasing")
        self.antialiasing_checkbox.setChecked(True)
        self.icon_border_checkbox = QCheckBox("Icon Border")
        self.mono_checkbox = QCheckBox("Mono")
        self.silhouette_checkbox = QCheckBox("Silhouette")
        self.icon_size_spin = QSpinBox()
        self.icon_size_spin.setRange(16, 256)
        self.icon_size_spin.setValue(48)
        self.spacing_spin = QSpinBox()
        self.spacing_spin.setRange(0, 96)
        self.spacing_spin.setValue(18)
        self.column_count_spin = QSpinBox()
        self.column_count_spin.setRange(1, 30)
        self.column_count_spin.setValue(COLUMNS)
        self.status_label = QLabel(f"Output: {OUTPUT_PATH}")
        self.status_label.setWordWrap(True)

        generate_button = QPushButton("Generate Sheet")
        generate_button.clicked.connect(self.generate_sheet)

        generate_single_button = QPushButton("Generate Single Icon")
        generate_single_button.clicked.connect(self.generate_single_icon)

        form = QFormLayout()
        form.addRow("Background", self.background_field)
        form.addRow("Foreground", self.foreground_field)
        form.addRow("Color 1", self.color_1_field)
        form.addRow("Color 2", self.color_2_field)
        form.addRow("Border Color", self.border_color_field)
        form.addRow("Icon Size", self.icon_size_spin)
        form.addRow("Spacing", self.spacing_spin)
        form.addRow("Columns", self.column_count_spin)
        form.addRow("Single Icon", self.single_icon_field)

        checkbox_row = QHBoxLayout()
        checkbox_row.addWidget(self.antialiasing_checkbox)
        checkbox_row.addWidget(self.icon_border_checkbox)
        checkbox_row.addWidget(self.mono_checkbox)
        checkbox_row.addWidget(self.silhouette_checkbox)
        checkbox_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(checkbox_row)
        layout.addWidget(generate_button)
        layout.addWidget(generate_single_button)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        self.apply_saved_settings(load_local_settings())

    def current_options(self) -> RenderOptions:
        return RenderOptions(
            background=self.background_field.value(),
            foreground=self.foreground_field.value(),
            color_1=self.color_1_field.value(),
            color_2=self.color_2_field.value(),
            antialiasing=self.antialiasing_checkbox.isChecked(),
            icon_border=self.icon_border_checkbox.isChecked(),
            border_color=self.border_color_field.value(),
            icon_size=self.icon_size_spin.value(),
            spacing=self.spacing_spin.value(),
            column_count=self.column_count_spin.value(),
            mono=self.mono_checkbox.isChecked(),
            silhouette=self.silhouette_checkbox.isChecked(),
        )

    def collect_settings(self) -> dict[str, object]:
        return {
            "background": self.background_field.line_edit.text(),
            "foreground": self.foreground_field.line_edit.text(),
            "color_1": self.color_1_field.line_edit.text(),
            "color_2": self.color_2_field.line_edit.text(),
            "border_color": self.border_color_field.line_edit.text(),
            "single_icon": self.single_icon_field.text(),
            "antialiasing": self.antialiasing_checkbox.isChecked(),
            "icon_border": self.icon_border_checkbox.isChecked(),
            "mono": self.mono_checkbox.isChecked(),
            "silhouette": self.silhouette_checkbox.isChecked(),
            "icon_size": self.icon_size_spin.value(),
            "spacing": self.spacing_spin.value(),
            "column_count": self.column_count_spin.value(),
        }

    def apply_saved_settings(self, settings: dict[str, object]) -> None:
        if not settings:
            return

        self.background_field.line_edit.setText(str(settings.get("background", "#ffffff")))
        self.foreground_field.line_edit.setText(str(settings.get("foreground", "#111111")))
        self.color_1_field.line_edit.setText(str(settings.get("color_1", "")))
        self.color_2_field.line_edit.setText(str(settings.get("color_2", "")))
        self.border_color_field.line_edit.setText(
            str(settings.get("border_color", "#d0d0d0"))
        )
        self.single_icon_field.setText(str(settings.get("single_icon", ".py")))
        self.antialiasing_checkbox.setChecked(bool(settings.get("antialiasing", True)))
        self.icon_border_checkbox.setChecked(bool(settings.get("icon_border", False)))
        self.mono_checkbox.setChecked(bool(settings.get("mono", False)))
        self.silhouette_checkbox.setChecked(bool(settings.get("silhouette", False)))
        self.icon_size_spin.setValue(int(settings.get("icon_size", 48)))
        self.spacing_spin.setValue(int(settings.get("spacing", 18)))
        self.column_count_spin.setValue(int(settings.get("column_count", COLUMNS)))

    def persist_settings(self) -> None:
        save_local_settings(self.collect_settings())

    def generate_sheet(self) -> None:
        try:
            self.persist_settings()
            output_path, total_icons = generate_icon_sheet(self.current_options(), OUTPUT_PATH)
        except Exception as exc:
            self.status_label.setText(str(exc))
            QMessageBox.critical(self, "Generation failed", str(exc))
            return

        message = f"Generated {output_path} with {total_icons} icons."
        self.status_label.setText(message)
        QMessageBox.information(self, "Generation complete", message)

    def generate_single_icon(self) -> None:
        icon_name = self.single_icon_field.text().strip()
        output_name = f"{safe_icon_output_name(icon_name)}.png"
        output_path = ROOT / output_name

        try:
            self.persist_settings()
            generated_path = render_single_icon_png(
                icon_name,
                self.current_options(),
                output_path,
            )
        except Exception as exc:
            self.status_label.setText(str(exc))
            QMessageBox.critical(self, "Generation failed", str(exc))
            return

        message = f"Generated {generated_path}"
        self.status_label.setText(message)
        QMessageBox.information(self, "Generation complete", message)

    def closeEvent(self, event) -> None:
        self.persist_settings()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
