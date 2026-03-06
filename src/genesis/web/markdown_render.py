"""Markdown-to-HTML rendering with mtime-based caching."""

from __future__ import annotations

import functools
from pathlib import Path

import mistune

_renderer = mistune.create_markdown(escape=False)


@functools.lru_cache(maxsize=8)
def _render_cached(path_str: str, mtime: float) -> str:
    return _renderer(Path(path_str).read_text(encoding="utf-8"))


def render_markdown_file(path: Path) -> str:
    """Return rendered HTML for a markdown file. Cached until file changes."""
    stat = path.stat()
    return _render_cached(str(path), stat.st_mtime)
