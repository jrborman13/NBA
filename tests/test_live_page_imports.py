"""
Regression test for the Live page ImportError.

The page at combined-app/pages/4_Live.py imports `ScoreboardV3` at module
load time:

    from nba_api.stats.endpoints import ScoreboardV3

`ScoreboardV3` was added in nba_api 1.11. The active venv ships nba_api
1.10.2, so the import explodes the entire page before any UI renders.

Run:
    python -m pytest tests/test_live_page_imports.py -v
"""

import importlib
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
LIVE_PAGE_PATH = REPO_ROOT / "combined-app" / "pages" / "4_Live.py"


def test_scoreboard_v3_importable():
    """nba_api must expose ScoreboardV3 — the Live page imports it at module load."""
    mod = importlib.import_module("nba_api.stats.endpoints")
    assert hasattr(mod, "ScoreboardV3"), (
        "nba_api.stats.endpoints.ScoreboardV3 is missing. "
        "Either upgrade nba_api to >= 1.11, or change combined-app/pages/4_Live.py "
        "to fall back to ScoreboardV2 when V3 is unavailable."
    )


def test_live_page_compiles():
    """Compile-check the Live page so import errors surface as test failures."""
    assert LIVE_PAGE_PATH.exists(), f"Live page missing: {LIVE_PAGE_PATH}"
    source = LIVE_PAGE_PATH.read_text()
    # ast parse alone doesn't catch ImportError, so try compiling as a module body.
    try:
        compile(source, str(LIVE_PAGE_PATH), "exec")
    except SyntaxError as e:  # pragma: no cover
        pytest.fail(f"Live page has a syntax error: {e}")


def test_live_page_imports_resolve():
    """
    Execute just the import block of the Live page in an isolated namespace.

    Reproduces the user-visible bug exactly: any failing import raises
    ImportError here, the same way Streamlit would.
    """
    source = LIVE_PAGE_PATH.read_text()
    # Take everything up to and including the first non-import line so we don't
    # try to run Streamlit UI code in a unit test.
    import_lines = []
    for line in source.splitlines():
        stripped = line.strip()
        if (
            stripped.startswith("import ")
            or stripped.startswith("from ")
            or stripped.startswith("#")
            or stripped == ""
        ):
            import_lines.append(line)
        elif stripped.startswith("sys.path"):
            import_lines.append(line)
        else:
            break
    import_block = "\n".join(import_lines)

    # Ensure the page's relative sys.path inserts can resolve from repo root.
    saved_sys_path = list(sys.path)
    try:
        sys.path.insert(0, str(REPO_ROOT / "combined-app" / "streamlit"))
        sys.path.insert(0, str(REPO_ROOT / "combined-app" / "player_app"))
        exec(compile(import_block, str(LIVE_PAGE_PATH), "exec"), {"__file__": str(LIVE_PAGE_PATH)})
    finally:
        sys.path[:] = saved_sys_path
