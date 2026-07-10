import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database.db as db_module
import app as app_module


@pytest.fixture
def test_db_path(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(db_module, "DB_PATH", path)
    db_module.init_db()
    yield path
    os.remove(path)


@pytest.fixture
def app(test_db_path):
    app_module.app.config.update(TESTING=True)
    db_module.seed_db()
    yield app_module.app


@pytest.fixture
def client(app):
    return app.test_client()
