import pytest

@pytest.fixture(autouse=True)
def mock_price_db(monkeypatch):
    monkeypatch.setattr('src.db.price_history.price_db.get_state', lambda k: None)
