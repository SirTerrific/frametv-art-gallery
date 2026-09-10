"""Covers importing an artwork from a Reframed gallery page.

The address is typed in by hand and this app has no login, so the two things worth
holding down are where the page may be fetched from and how much may be downloaded.

Run with: pytest tests/test_reframed_import.py
"""

import os

import pytest

import app as backend
from utils import reframed_gallery


@pytest.fixture
def client():
    backend.app.config["TESTING"] = True
    with backend.app.app_context():
        backend.db.drop_all()
        backend.db.create_all()
    for name in os.listdir(backend.app.config["UPLOAD_FOLDER"]):
        path = os.path.join(backend.app.config["UPLOAD_FOLDER"], name)
        if os.path.isfile(path):
            os.remove(path)
    return backend.app.test_client()


PAGE = (
    '<html><body><img src="https://cdn.reframed.gallery/cdn-cgi/image/width=800/'
    'originals/the-great-wave.jpg"></body></html>'
)


class _Page:
    status_code = 200
    text = PAGE

    @staticmethod
    def raise_for_status():
        return None


class _Download:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=8192):
        for start in range(0, len(self._payload), chunk_size):
            yield self._payload[start:start + chunk_size]


# --- reading the page ---

def test_the_full_size_address_is_found_behind_the_resizing_proxy():
    """Reframed serves a resized copy in the page and the original on its CDN."""
    assert reframed_gallery.extract_cdn_url(PAGE) == (
        "https://cdn.reframed.gallery/originals/the-great-wave.jpg"
    )


def test_a_page_with_no_artwork_yields_nothing():
    assert reframed_gallery.extract_cdn_url("<html><body>nothing here</body></html>") is None


# --- where it may look ---

@pytest.mark.parametrize("elsewhere", [
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.13:8001/api/v2/",
    "https://reframed.gallery.example.com/art/1",
    "file:///etc/passwd",
])
def test_only_reframed_addresses_are_fetched(elsewhere, monkeypatch):
    """The URL comes straight from a browser bar, and the app has no login of its own."""
    def fail(*args, **kwargs):
        raise AssertionError("nothing outside Reframed should be requested")

    monkeypatch.setattr(reframed_gallery.requests, "get", fail)
    with pytest.raises(ValueError, match="not a Reframed gallery address"):
        reframed_gallery.get_image_from_reframed_gallery(elsewhere)


def test_a_reframed_subdomain_is_accepted(tmp_path, monkeypatch):
    monkeypatch.setattr(
        reframed_gallery.requests, "get",
        lambda url, **kwargs: _Page() if "cdn." not in url else _Download(b"\xff\xd8\xff" + b"x" * 32),
    )
    name = reframed_gallery.get_image_from_reframed_gallery(
        "https://www.reframed.gallery/art/42", location=str(tmp_path)
    )
    assert name == "the-great-wave.jpg"
    assert (tmp_path / name).read_bytes().startswith(b"\xff\xd8\xff")


# --- how much it may download ---

def test_an_oversized_artwork_is_refused_and_leaves_no_half_file(tmp_path, monkeypatch):
    """A partial file would show in the gallery as art no viewer can open."""
    monkeypatch.setattr(reframed_gallery, "MAX_ARTWORK_BYTES", 1024)
    monkeypatch.setattr(
        reframed_gallery.requests, "get",
        lambda url, **kwargs: _Page() if "cdn." not in url else _Download(b"x" * 5000),
    )
    with pytest.raises(ValueError, match="larger than this app accepts"):
        reframed_gallery.get_image_from_reframed_gallery(
            "https://reframed.gallery/art/42", location=str(tmp_path)
        )
    assert list(tmp_path.iterdir()) == []


# --- the endpoint ---

def test_an_imported_artwork_joins_the_gallery(client, monkeypatch):
    monkeypatch.setattr(
        reframed_gallery.requests, "get",
        lambda url, **kwargs: _Page() if "cdn." not in url else _Download(b"\xff\xd8\xff" + b"x" * 64),
    )
    res = client.post("/api/import/reframed", json={"url": "https://reframed.gallery/art/42"})
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert body["filename"] == "the-great-wave.jpg"

    with backend.app.app_context():
        stored = backend.Image.query.filter_by(filename="the-great-wave.jpg").first()
        assert stored is not None
        assert stored.sha256, "the digest is what later spots a duplicate"


def test_an_address_that_is_not_reframed_is_refused_with_a_reason(client, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("nothing outside Reframed should be requested")

    monkeypatch.setattr(reframed_gallery.requests, "get", fail)
    res = client.post("/api/import/reframed", json={"url": "http://169.254.169.254/"})
    assert res.status_code == 400
    assert "Reframed" in res.get_json()["error"]


def test_a_missing_url_is_refused(client):
    assert client.post("/api/import/reframed", json={}).status_code == 400
