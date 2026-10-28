"""Covers the Immich settings API: the key is write-only, partial saves keep it, and the
provider is read from the saved settings on every call.

Run with: pytest tests/test_provider_settings.py
"""

import json

import pytest

import app as backend
import media_provider_routes


@pytest.fixture
def client():
    backend.app.config["TESTING"] = True
    with backend.app.app_context():
        backend.db.drop_all()
        backend.db.create_all()
    media_provider_routes._image_cache.clear()
    return backend.app.test_client()


def save(client, **fields):
    return client.post("/api/providers/immich", json=fields)


def test_the_api_key_is_never_sent_back(client):
    res = save(client, host="immich.lan", port=2283, api_key="sekret-key", enabled=True)
    assert res.status_code == 200
    assert res.get_json()["has_api_key"] is True
    for url in ("/api/providers", "/api/providers/immich"):
        assert "sekret-key" not in client.get(url).get_data(as_text=True)


def test_a_partial_save_keeps_the_stored_key(client):
    save(client, host="immich.lan", api_key="sekret-key", enabled=True)
    save(client, enabled=False)
    with backend.app.app_context():
        config = backend.ProviderConfig.query.filter_by(provider="immich").first()
        assert config.api_key == "sekret-key"
        assert config.host == "immich.lan"
        assert config.enabled is False


def test_a_save_without_a_json_body_is_refused(client):
    res = client.post("/api/providers/immich", data="nope", content_type="text/plain")
    assert res.status_code == 400


def test_the_provider_follows_the_saved_settings(client):
    assert client.get("/api/provider/albums").status_code == 404
    save(client, host="immich.lan", api_key="sekret-key", enabled=True)
    with backend.app.app_context():
        assert media_provider_routes.get_media_provider() is not None
    save(client, enabled=False)
    assert client.get("/api/provider/albums").status_code == 404


def test_an_unreachable_immich_gives_a_502_not_a_crash(client, monkeypatch):
    save(client, host="immich.lan", api_key="sekret-key", enabled=True)

    async def boom(self):
        raise OSError("down")

    monkeypatch.setattr("utils.immich_provider.ImmichProvider.get_albums", boom)
    res = client.get("/api/provider/albums")
    assert res.status_code == 502


def test_the_image_cache_stays_bounded(client, monkeypatch):
    save(client, host="immich.lan", api_key="sekret-key", enabled=True)

    async def fake(self, image_id, size="fullsize"):
        return b"x" * 10

    monkeypatch.setattr("utils.immich_provider.ImmichProvider.stream_image", fake)
    for i in range(media_provider_routes._IMAGE_CACHE_SIZE + 10):
        assert client.get(f"/api/provider/images/{i}/stream").status_code == 200
    assert len(media_provider_routes._image_cache) == media_provider_routes._IMAGE_CACHE_SIZE


def test_other_websites_get_no_cors_permission(client):
    res = client.get("/api/providers", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in res.headers
    assert res.headers["X-Content-Type-Options"] == "nosniff"


def test_the_old_form_routes_are_gone(client):
    assert client.post("/tv/192.0.2.9/on").status_code in (404, 405)


def test_a_failed_update_check_is_cached_for_a_short_while(client, monkeypatch):
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise OSError("github down")

    monkeypatch.setattr(backend.requests, "get", fail)
    assert client.get("/api/status").status_code == 200
    assert client.get("/api/status").status_code == 200
    assert len(calls) == 1
    with backend.app.app_context():
        entry = backend.AppSetting.query.filter_by(key="github_version_cache").first()
        assert json.loads(entry.value)["last_fetched"] > 0
