"""
Path resolution helper — makes the backend robust regardless of which
directory uvicorn is launched from.

Problem
-------
The .env defaults are RELATIVE: DATA_DIR=./datasets, CHROMA_PERSIST_DIR=./chroma_store.
When uvicorn is launched from the project root, ./datasets correctly points
at <root>/datasets. But it's much more common to launch uvicorn from inside
the backend/ folder (the README + Quick Start use that pattern), in which
case ./datasets resolves to <root>/backend/datasets — wrong.

Solution
--------
_resolve_dir(rel_path) tries the path in these locations, returning the
first one that exists:
  1. <cwd>/<rel_path>                       — runs from project root
  2. <cwd>/../<rel_path>                    — runs from backend/
  3. <project_root>/<rel_path>              — when we can detect the root
                                                via the marker files
If none exist, returns option 1 (so a missing-dir error appears at the
expected location and is clear in logs).
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional


# Files/folders that mark the project root unambiguously
_ROOT_MARKERS = ("render.yaml", "AI-Powered Smart Grid Energy Intelligence Assistant requirements.txt")


def _find_project_root(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up from `start` looking for a marker file. Returns root or None."""
    p = (start or Path.cwd()).resolve()
    for parent in [p, *p.parents]:
        for marker in _ROOT_MARKERS:
            if (parent / marker).exists():
                return parent
    return None


def resolve_dir(rel_or_abs: str, *, create: bool = False) -> Path:
    """
    Resolve a config path. Absolute paths are returned as-is.

    Relative paths try: cwd, cwd.parent (if cwd is 'backend'), project root.
    Returns the first existing candidate, else the first candidate.
    """
    p = Path(rel_or_abs)
    if p.is_absolute():
        if create:
            p.mkdir(parents=True, exist_ok=True)
        return p

    cwd = Path.cwd()
    candidates: list[Path] = [cwd / p]
    if cwd.name == "backend":
        candidates.append(cwd.parent / p)
    root = _find_project_root()
    if root is not None and root not in (cwd, cwd.parent):
        candidates.append(root / p)

    for c in candidates:
        if c.exists():
            return c

    chosen = candidates[0]
    if create:
        chosen.mkdir(parents=True, exist_ok=True)
    return chosen
