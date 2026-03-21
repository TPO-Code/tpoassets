from __future__ import annotations

from pathlib import Path


class IconDirectoryRegistry:
    def __init__(self) -> None:
        self._dirs: list[Path] = []

    def add(self, directory: str | Path) -> Path:
        path = Path(directory).expanduser().resolve()
        key = self._key(path)
        if all(self._key(existing) != key for existing in self._dirs):
            self._dirs.append(path)
        return path

    def clear(self) -> None:
        self._dirs.clear()

    def paths(self) -> list[Path]:
        return list(self._dirs)

    @staticmethod
    def _key(path: Path) -> str:
        try:
            return str(path.resolve()).lower()
        except Exception:
            return str(path).lower()


ICON_DIRS = IconDirectoryRegistry()