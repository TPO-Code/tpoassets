from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import convert_raw_assets


RAW_FILE_ICON = """<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" xmlns:bx="https://boxy-svg.com">
  <style>
    :root {
      --foreground: currentColor;
      --color-1: #ffd43b;
      --color-2: #3776ab;
    }
  </style>
  <defs>
    <bx:grid x="0" y="0" width="4" height="4"/>
  </defs>
  <path style="fill: none; stroke: rgb(0, 0, 0); stroke-width: 3px;" d="M 12 4 L 32 4 L 52 24 L 52 60 L 12 60 L 12 4 Z"/>
  <path style="fill: none; stroke: rgb(0, 0, 0); stroke-width: 3px;" d="M 32 4 C 32 4 32 24 32 24 C 32 24 52 24 52 24 L 32 4"/>
  <text style="fill: none; stroke: rgb(0, 0, 0); stroke-width: 3px;" transform="matrix(0.952469, 0.00059, 0, 0.857644, 2.092994, 8.327618)"><tspan x="14.601" y="46.086">&lt;&gt;</tspan><tspan x="14.6" dy="1em">&#8203;</tspan></text>
</svg>
"""

RAW_IMAGE_ICON = """<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" xmlns:bx="https://boxy-svg.com">
  <defs>
    <bx:grid x="0" y="0" width="4" height="4"/>
  </defs>
  <path style="fill: none; stroke: rgb(0, 0, 0); stroke-width: 3px;" d="M 12 4 L 32 4 L 52 24 L 52 60 L 12 60 L 12 4 Z"/>
  <ellipse style="stroke: rgb(0, 0, 0); stroke-width: 3px; fill: none;" cx="22.465" cy="35.47" rx="3.495" ry="3.47"/>
</svg>
"""

RAW_TEXT_ICON = """<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="16 28.4481 33.7039 18.7579">
  <defs>
    <style>
      :root {
        --foreground: currentColor;
        --color-1: #ffd43b;
        --color-2: #3776ab;
      }
    </style>
  </defs>
  <text style="fill: none; font-family: FreeMono; font-size: 28px; stroke: rgb(0, 0, 0); stroke-width: 3px;">cpp</text>
</svg>
"""

RAW_BRUSH_ICON = """<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <path style="fill: rgb(255, 0, 0); stroke: rgb(0, 0, 0); stroke-width: 3px;" d="M 0 0 L 8 8"/>
  <circle fill="#00ff00" stroke="rgb(0, 0, 0)" stroke-width="2" cx="10" cy="10" r="4"/>
</svg>
"""

RAW_THREE_BRUSH_ICON = """<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <circle fill="#ff0000" cx="10" cy="10" r="4"/>
  <circle fill="#00ff00" cx="20" cy="10" r="4"/>
  <circle fill="#0000ff" cx="30" cy="10" r="4"/>
</svg>
"""

RAW_EMPTY_TEXT = """<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="71 14 7 31">
  <text style="white-space: pre;"> </text>
</svg>
"""


class ConvertRawAssetsTests(unittest.TestCase):
    def test_convert_file_icon_rewrites_strokes_and_strips_boxy_bits(self) -> None:
        converted = convert_raw_assets.convert_svg_text(RAW_FILE_ICON)

        self.assertIn('viewBox="0 0 64 64"', converted)
        self.assertIn("stroke: var(--foreground)", converted)
        self.assertIn("&lt;&gt;", converted)
        self.assertNotIn("--color-1", converted)
        self.assertNotIn("boxy-svg", converted)
        self.assertNotIn("<defs", converted)

    def test_convert_line_art_without_text(self) -> None:
        converted = convert_raw_assets.convert_svg_text(RAW_IMAGE_ICON)

        self.assertIn("<ellipse", converted)
        self.assertIn("stroke: var(--foreground)", converted)
        self.assertNotIn("no visible label text", converted)

    def test_convert_text_icon_keeps_text_and_rewrites_strokes(self) -> None:
        converted = convert_raw_assets.convert_svg_text(RAW_TEXT_ICON)

        self.assertIn("<text", converted)
        self.assertIn("stroke: var(--foreground)", converted)
        self.assertIn(">cpp</text>", converted)

    def test_convert_assigns_up_to_two_fill_slots(self) -> None:
        converted = convert_raw_assets.convert_svg_text(RAW_BRUSH_ICON)

        self.assertIn("--color-1: rgb(255, 0, 0);", converted)
        self.assertIn("--color-2: #00ff00;", converted)
        self.assertIn("fill: var(--color-1)", converted)
        self.assertIn('fill="var(--color-2)"', converted)
        self.assertIn('stroke="var(--foreground)"', converted)

    def test_convert_rejects_more_than_two_fill_slots(self) -> None:
        with self.assertRaisesRegex(ValueError, "more than two brush colors"):
            convert_raw_assets.convert_svg_text(RAW_THREE_BRUSH_ICON)

    def test_convert_directory_writes_assets_and_skips_invalid_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp, tempfile.TemporaryDirectory() as out_tmp:
            raw_dir = Path(raw_tmp)
            output_dir = Path(out_tmp)
            (raw_dir / "angle_bracket_file.svg").write_text(RAW_FILE_ICON, encoding="utf-8")
            (raw_dir / "image.svg").write_text(RAW_IMAGE_ICON, encoding="utf-8")
            (raw_dir / "h.svg").write_text(RAW_EMPTY_TEXT, encoding="utf-8")

            results = convert_raw_assets.convert_directory(raw_dir, output_dir, clean=True)

            converted = [result for result in results if result.status == "converted"]
            skipped = [result for result in results if result.status == "skipped"]

            self.assertEqual(2, len(converted))
            self.assertEqual(1, len(skipped))
            self.assertTrue((output_dir / "files" / "angle_bracket_file.svg").is_file())
            self.assertTrue((output_dir / "files" / "image.svg").is_file())
            self.assertEqual("h.svg", skipped[0].source.name)


if __name__ == "__main__":
    unittest.main()
