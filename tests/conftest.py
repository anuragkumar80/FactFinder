import sys
from pathlib import Path

# Ensure FactFinder directory is always in sys.path regardless of where pytest is run from
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from backend import config


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Every test gets its own empty SQLite file."""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
