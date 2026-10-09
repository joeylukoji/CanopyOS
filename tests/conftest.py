import pytest


@pytest.fixture(autouse=True)
def no_live_providers(monkeypatch):
    """Tests never call a configured paid or remote model accidentally."""
    monkeypatch.setenv("JEV_API_KEY", "")
    monkeypatch.setenv("GEMMA_ENDPOINT", "")
