# tpo-assets

`tpo_assets` is a small Python package for resolving packaged SVG icons and loading them as Qt `QIcon`s.

It is designed for applications that want:

- a bundled icon set
- optional project-specific icon overrides
- file-extension icon lookup
- lightweight SVG recoloring for icons that define CSS color variables

It does not manage themes, widget sizing, or application styling.

---

## Installation

Standard install:

```bash
pip install tpo-assets
```

If you use `uv`:

```bash
uv add tpo-assets
```

`PySide6` is a required dependency.

---

## What It Looks Like In Code

```python
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QPushButton

from tpo_assets import add_icon_search_dir, icon

add_icon_search_dir("/path/to/myproject/assets/icons")

btn = QPushButton("Text file")
btn.setIcon(icon(".txt", foreground="#e6e6e6"))
btn.setIconSize(QSize(20, 20))
```

That call can:

- resolve a packaged icon
- allow a project override from a registered icon directory
- perform file-extension lookup through `files/<extension>.svg`
- return a Qt `QIcon`

---

## Usage

`tpo_assets` supports three lookup styles.

### 1. Explicit category lookup

Use this for bundled or custom icons that live under a category directory:

```python
icon("ui/power")
icon("files/txt")
icon("ui/power.svg")  # ".svg" is accepted and normalized away
```

This is the most reliable form because it matches the on-disk asset path.

### 2. File-extension lookup

If the name starts with `.`, it is resolved as a file icon request:

```python
icon(".txt")
icon(".py")
icon(".md")
```

For example, `".txt"` looks for `files/txt.svg`.

If the specific extension icon is missing, the resolver next tries `files/default.svg` when one exists in a registered custom directory or in the packaged assets. If nothing matches, resolution ultimately falls back to `none.svg`.

Built-in assets can also define aliases for common extensions. For example, `.html` and `.xml` can resolve to the packaged `files/angle_bracket_file.svg` icon without affecting custom icon libraries.

### 3. Root-level lookup

Plain names without a `/` are treated as root-level icons:

```python
icon("none")
```

This does not search inside categories like `ui/` or `files/`. If you want `ui/power`, request `ui/power` explicitly rather than `power`.

---

## Lookup Order

When resolving an icon, `tpo_assets` checks:

1. registered custom icon directories
2. packaged built-in icons
3. fallbacks for the request type

Fallback behavior depends on the request:

- `".txt"` or `"files/txt"`: tries `files/default.svg` if available, then ends at `none.svg`
- `"ui/power"` or `"power"`: falls back to `none.svg`
- empty or invalid names: resolve to `none.svg`

---

## Custom Icon Directories

Applications can register one or more additional icon directories:

```python
from tpo_assets import add_icon_search_dir

add_icon_search_dir("/path/to/myproject/assets/icons")
```

These directories are checked before the packaged icons, so a project can override specific assets without modifying the package.

Custom directories should mirror the packaged structure.

Example:

```text
myproject/
└── assets/
    └── icons/
        ├── none.svg
        ├── ui/
        │   └── power.svg
        └── files/
            ├── default.svg
            └── txt.svg
```

---

## SVG Recoloring

`tpo_assets.icon()` can rewrite CSS variables defined inside an SVG before loading it into Qt.

```python
icon("files/txt", foreground="#d8dee9")
icon("files/txt", mono=True)
icon("files/txt", silhouette=True, foreground="#000000")
```

Supported keyword arguments:

- `foreground`
- `color_1`
- `color_2`
- `mono`
- `silhouette`

### Supported SVG pattern

Recoloring works for SVGs that define CSS variables such as:

```svg
<style>
  :root {
    --foreground: currentColor;
    --color-1: #ffd43b;
    --color-2: #3776ab;
  }
</style>

<path style="stroke: var(--foreground)"/>
<path style="fill: var(--color-1)"/>
<path style="fill: var(--color-2)"/>
```

Behavior:

- `foreground` overrides `--foreground` when it exists
- `color_1` overrides `--color-1` when it exists
- `color_2` overrides `--color-2` when it exists
- `mono=True` makes defined accent channels transparent
- `silhouette=True` forces all defined channels to the resolved foreground color

Icons that do not define these CSS variables are still loaded normally, but they are not recolored by this mechanism.

---

## Bundled Assets

The package currently ships with:

- `none`
- `files/py`
- `files/txt`
- `ui/power`
- `ui/settings`
- `ui/internet_0` through `ui/internet_4`
- `ui/media/play`, `pause`, `previous`, `next`
- `ui/media/skip_forward`, `skip_back`, `stop`
- `ui/media/shuffle`, `loop_track`, `loop_playlist`, `loop_off`
- `ui/volume_1` through `ui/volume_3`
- `ui/volume_muted`

You can inspect the available asset names at runtime:

```python
from tpo_assets import all_icon_assets

print(all_icon_assets())
```

For icon authoring conventions, see [ICON_GUIDE.md](ICON_GUIDE.md).

---

## Qt Example

```python
import sys

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget

from tpo_assets import add_icon_search_dir, icon


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("tpo_assets example")

        add_icon_search_dir("/path/to/myproject/assets/icons")

        central = QWidget()
        layout = QVBoxLayout(central)
        self.setCentralWidget(central)

        btn_power = QPushButton("Power")
        btn_power.setIcon(icon("ui/power"))
        btn_power.setIconSize(QSize(24, 24))
        layout.addWidget(btn_power)

        btn_text = QPushButton("Text file")
        btn_text.setIcon(icon(".txt", foreground="#eceff4"))
        btn_text.setIconSize(QSize(24, 24))
        layout.addWidget(btn_text)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    raise SystemExit(app.exec())
```

---

## API

### `tpo_assets`

#### `add_icon_search_dir(directory)`

Register a custom icon directory.

#### `clear_icon_search_dirs()`

Remove all registered custom icon directories.

#### `registered_icon_search_dirs()`

Return the currently registered custom icon directories.

#### `icon_path(name)`

Resolve an icon request to a concrete SVG path.

#### `icon_paths(name)`

Return the resolution chain for debugging.

#### `all_icon_assets()`

Return discovered built-in and custom icons grouped by section.

#### `icon(name, *, foreground="#FFFFFF", color_1=None, color_2=None, mono=False, silhouette=False)`

Resolve an icon and return it as a `QIcon`.

#### `clear_icon_cache()`

Clear the generated Qt icon cache.

---

## Development

Editable install:

```bash
uv pip install -e .
```

If package metadata or bundled assets changed:

```bash
uv pip install -e . --reinstall
```

---

## License

MIT
