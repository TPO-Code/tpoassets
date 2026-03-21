# Icon Authoring Guide

This project loads SVGs from `tpo_assets/assets/icons` and can optionally recolor them when they are rendered through `tpo_assets.icon()`.

If you want an icon to work well with the package, follow the conventions below.

---

## Directory And Naming Rules

- Store icons under `src/tpo_assets/assets/icons/`.
- Use lowercase file names.
- Use `.svg` files only.
- Use forward-slash directory structure such as `ui/power.svg` or `files/txt.svg`.
- Nested directories are allowed, for example `ui/buttons/exit.svg`.
- Keep names stable because lookup is path-based.

Lookup examples:

- `icon("ui/power")` -> `ui/power.svg`
- `icon("ui/buttons/exit")` -> `ui/buttons/exit.svg`
- `icon(".txt")` -> `files/txt.svg`
- `icon("files/txt")` -> `files/txt.svg`

If you want a root-level icon, place it directly under `src/tpo_assets/assets/icons/`, for example `none.svg`.

---

## Supported Color Variables

The renderer understands these CSS custom properties:

- `--foreground`
- `--color-1`
- `--color-2`

These map to the Python API like this:

- `foreground=` -> `--foreground`
- `color_1=` -> `--color-1`
- `color_2=` -> `--color-2`

Use those exact variable names. Other custom property names are ignored by the recoloring API.

---

## Recommended SVG Pattern

Define the variables in a `<style>` block and then use them through `var(...)`.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <style>
    :root {
      --foreground: currentColor;
      --color-1: #ffd43b;
      --color-2: #3776ab;
    }
  </style>

  <path d="..." style="stroke: var(--foreground); fill: none;"/>
  <path d="..." style="fill: var(--color-1);"/>
  <path d="..." style="fill: var(--color-2);"/>
</svg>
```

For a monochrome icon, you usually only need `--foreground`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <style>
    :root {
      --foreground: currentColor;
    }
  </style>

  <path d="..." style="stroke: var(--foreground); fill: none;"/>
</svg>
```

---

## Important Behavior

### `foreground`

If the SVG defines `--foreground`, passing `foreground="#rrggbb"` replaces that value.

### `color_1` and `color_2`

If the SVG defines `--color-1` or `--color-2`, passing `color_1=` or `color_2=` replaces those values.

If the variable is not defined in the SVG, that option has no effect.

### `mono=True`

`mono=True` makes defined accent channels transparent:

- `--color-1` -> `transparent`
- `--color-2` -> `transparent`

`--foreground` is left alone.

### `silhouette=True`

`silhouette=True` forces all defined channels to the resolved foreground color:

- `--foreground`
- `--color-1`
- `--color-2`

If both `mono=True` and `silhouette=True` are used, `silhouette` wins because all channels are collapsed to the foreground color.

---

## What To Avoid

- Do not assume a plain `currentColor` stroke or fill will be recolored by `tpo_assets`.

If you want recoloring support, route the color through the supported CSS variables:

```svg
style="stroke: var(--foreground)"
```

not just:

```svg
stroke="currentColor"
```

---

## Suggested Defaults

These defaults work well for most icons:

- `--foreground: currentColor`
- `--color-1`: the primary accent color for the asset
- `--color-2`: the secondary accent color for the asset

If an icon is single-color, omit `--color-1` and `--color-2`.

If an icon is two-tone or three-tone, define only the channels you actually use.

---

## Example File Icon

```svg
<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <style>
    :root {
      --foreground: currentColor;
      --color-1: #ffd43b;
      --color-2: #3776ab;
    }
  </style>

  <path d="M 13.929 4 L 38 4 ..." style="stroke: var(--foreground); fill: none; stroke-width: 3px;"/>
  <path d="M 38 4 L 54 20 ..." style="stroke: var(--foreground); fill: none; stroke-width: 3px;"/>
  <path d="M 16 16 L 30 16" style="stroke: var(--foreground); fill: none; stroke-width: 4px;"/>
</svg>
```

---

## Checklist

Before adding a new icon, check:

- the file is in the correct directory
- the file name is lowercase and lookup-friendly
- the SVG has a `viewBox`
- recolorable shapes use `var(--foreground)`, `var(--color-1)`, or `var(--color-2)`
- unused variables are omitted
- the icon still looks correct with `mono=True`
- the icon still looks correct with `silhouette=True`

---

## Previewing

Use [generate_icons_png.py](generate_icons_png.py) to generate an `icons.png` sheet for the current icon set and test different foreground/background/color combinations.
