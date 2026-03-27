from pathlib import Path

from smart_locator.cache import SmartLocatorCache


def test_cache_round_trip(tmp_path: Path):
    cache = SmartLocatorCache(tmp_path / "cache.db")
    payload = {"elements": [{"label": "Username"}]}
    cache.set("https://example.test", "login form", payload)
    assert cache.get("https://example.test", "login form") == payload


def test_cache_invalidate_and_clear(tmp_path: Path):
    cache = SmartLocatorCache(tmp_path / "cache.db")
    cache.set("https://example.test", "login form", {"elements": []})
    cache.set("https://example.test", "signup form", {"elements": []})
    cache.invalidate("https://example.test", "login form")
    assert cache.get("https://example.test", "login form") is None
    assert cache.clear() == 1
