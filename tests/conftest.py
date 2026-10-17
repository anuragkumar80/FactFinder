import pytest
from backend import config


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Every test gets its own empty SQLite file."""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
