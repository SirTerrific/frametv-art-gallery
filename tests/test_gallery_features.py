"""Covers the thumbnails, listing order, duplicate reporting, reconcile and backup.

Run with: pytest tests/test_gallery_features.py
"""

import io
import os
import zipfile
from datetime import datetime, timedelta

import pytest
from PIL import Image as PILImage

import app as backend
from utils import slideshow
from utils.frame_tv import _magic_packet


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


def png_bytes(size=(1200, 800), colour="red"):
    buf = io.BytesIO()
    PILImage.new("RGB", size, colour).save(buf, format="PNG")
    buf.seek(0)
    return buf


def upload(client, name, size=(1200, 800), colour="red"):
    return client.post(
        "/api/upload",
        data={"file": (png_bytes(size, colour), name)},
        content_type="multipart/form-data",
    )


# --- thumbnails ---

def test_a_width_returns_a_smaller_image(client):
    upload(client, "big.png", size=(1200, 800))

    full = client.get("/uploads/big.png")
    small = client.get("/uploads/big.png?w=400")

    assert full.status_code == small.status_code == 200
    assert PILImage.open(io.BytesIO(small.data)).width == 400
    assert len(small.data) < len(full.data), "the tile should be lighter than the original"


def test_the_original_is_served_without_a_width(client):
    upload(client, "big.png", size=(1200, 800))
    assert PILImage.open(io.BytesIO(client.get("/uploads/big.png").data)).width == 1200


@pytest.mark.parametrize("query", ["w=999", "w=abc", "w="])
def test_an_unsupported_width_falls_back_to_the_original(client, query):
    upload(client, "big.png", size=(1200, 800))
    res = client.get(f"/uploads/big.png?{query}")
    assert res.status_code == 200
    assert PILImage.open(io.BytesIO(res.data)).width == 1200


def test_an_image_smaller_than_the_tile_is_not_upscaled(client):
    upload(client, "tiny.png", size=(100, 60))
    res = client.get("/uploads/tiny.png?w=400")
    assert PILImage.open(io.BytesIO(res.data)).width == 100


# --- listing order and search ---

def test_images_are_listed_newest_first(client):
    for name in ("first.png", "second.png", "third.png"):
        upload(client, name)
    with backend.app.app_context():
        rows = {img.filename: img for img in backend.Image.query.all()}
        base = datetime(2026, 1, 1)
        rows["first.png"].created_at = base
        rows["second.png"].created_at = base + timedelta(days=1)
        rows["third.png"].created_at = base + timedelta(days=2)
        backend.db.session.commit()

    assert client.get("/api/images").get_json()["images"] == ["third.png", "second.png", "first.png"]
    assert client.get("/api/images?sort=oldest").get_json()["images"] == ["first.png", "second.png", "third.png"]
    assert client.get("/api/images?sort=name").get_json()["images"] == ["first.png", "second.png", "third.png"]


def test_the_listing_can_be_filtered_by_name(client):
    upload(client, "sunset.png")
    upload(client, "portrait.png")
    assert client.get("/api/images?q=SUN").get_json()["images"] == ["sunset.png"]
    assert client.get("/api/images?q=nothing").get_json()["images"] == []


# --- duplicates ---

def test_the_same_artwork_under_another_name_is_reported(client):
    upload(client, "original.png", colour="blue")
    res = upload(client, "copy.png", colour="blue")

    assert res.get_json()["duplicate_of"] == "original.png"
    # ...and it is still stored: silently dropping a requested upload would be worse.
    assert "copy.png" in client.get("/api/images").get_json()["images"]


def test_a_different_image_is_not_flagged(client):
    upload(client, "one.png", colour="blue")
    assert upload(client, "two.png", colour="green").get_json()["duplicate_of"] is None


# --- reconcile ---

def test_reconcile_picks_up_and_drops_files(client):
    upload(client, "kept.png")

    # A file dropped in by hand, and a row whose file went away.
    stray = os.path.join(backend.app.config["UPLOAD_FOLDER"], "stray.png")
    with open(stray, "wb") as handle:
        handle.write(png_bytes(colour="purple").read())
    with backend.app.app_context():
        backend.db.session.add(backend.Image(filename="ghost.png"))
        backend.db.session.commit()

    report = client.post("/api/images/reconcile").get_json()
    assert report["added"] == 1 and report["removed"] == 1

    with backend.app.app_context():
        names = {img.filename for img in backend.Image.query.all()}
    assert names == {"kept.png", "stray.png"}


def test_reconcile_backfills_hashes_and_names_duplicates(client):
    upload(client, "a.png", colour="teal")
    upload(client, "b.png", colour="teal")
    with backend.app.app_context():
        for img in backend.Image.query.all():
            img.sha256 = None
        backend.db.session.commit()

    report = client.post("/api/images/reconcile").get_json()
    assert report["hashed"] == 2
    assert sorted(report["duplicate_groups"][0]) == ["a.png", "b.png"]


# --- backup ---

def test_the_backup_contains_the_database_and_the_uploads(client):
    upload(client, "kept.png")
    res = client.get("/api/backup")
    assert res.status_code == 200

    with zipfile.ZipFile(io.BytesIO(res.data)) as archive:
        names = archive.namelist()
        assert "instance/frametv.db" in names
        assert "uploads/kept.png" in names
        assert archive.read("instance/frametv.db").startswith(b"SQLite format 3")


# --- wake on lan ---

def test_the_magic_packet_is_well_formed():
    packet = _magic_packet("AA:BB:CC:DD:EE:FF")
    assert len(packet) == 102
    assert packet[:6] == b"\xff" * 6
    assert packet[6:12] == bytes.fromhex("aabbccddeeff")
    assert _magic_packet("aa-bb-cc-dd-ee-ff") == packet
    assert _magic_packet("aabbccddeeff") == packet


@pytest.mark.parametrize("bad", ["", "zz:zz:zz:zz:zz:zz", "AA:BB:CC"])
def test_a_bad_mac_is_refused(bad):
    with pytest.raises(ValueError):
        _magic_packet(bad)


def test_waking_a_tv_without_a_mac_explains_itself(client):
    with backend.app.app_context():
        backend.db.session.add(backend.TV(ip="192.0.2.20", name="No MAC", token="1"))
        backend.db.session.commit()
    res = client.post("/api/tv/192.0.2.20/on", json={})
    assert res.status_code == 400
    assert "MAC" in res.get_json()["error"]


# --- slideshow ---

class FakeTV:
    def __init__(self, **kwargs):
        self.slideshow_enabled = True
        self.slideshow_album_id = 1
        self.slideshow_interval_minutes = 30
        self.slideshow_last_run = None
        self.__dict__.update(kwargs)


def test_a_tv_is_due_only_once_its_interval_has_passed():
    now = datetime(2026, 1, 1, 12, 0)
    assert slideshow._due(FakeTV(), now), "never run yet"
    assert not slideshow._due(FakeTV(slideshow_last_run=now - timedelta(minutes=5)), now)
    assert slideshow._due(FakeTV(slideshow_last_run=now - timedelta(minutes=31)), now)


@pytest.mark.parametrize("tv", [
    FakeTV(slideshow_enabled=False),
    FakeTV(slideshow_album_id=None),
    FakeTV(slideshow_interval_minutes=None),
    FakeTV(slideshow_interval_minutes=0),
])
def test_an_incomplete_slideshow_never_runs(tv):
    assert not slideshow._due(tv, datetime(2026, 1, 1, 12, 0))


# --- bulk delete on the TV ---

@pytest.mark.parametrize("payload,expected", [
    ({}, 400),
    ({"content_ids": "SAM-1"}, 400),
    ({"content_ids": ["SAM-1", 2]}, 400),
])
def test_bulk_tv_delete_rejects_bad_payloads(client, payload, expected):
    with backend.app.app_context():
        backend.db.session.add(backend.TV(ip="192.0.2.40", name="TV", token="1"))
        backend.db.session.commit()
    assert client.post("/api/tv/192.0.2.40/gallery/delete", json=payload).status_code == expected


def test_bulk_tv_delete_with_nothing_selected_touches_no_tv(client, monkeypatch):
    with backend.app.app_context():
        backend.db.session.add(backend.TV(ip="192.0.2.41", name="TV", token="1"))
        backend.db.session.commit()

    called = []
    monkeypatch.setattr(backend, "delete_tv_images", lambda *a, **k: called.append(a))
    res = client.post("/api/tv/192.0.2.41/gallery/delete", json={"content_ids": []})
    assert res.status_code == 200 and res.get_json()["deleted"] == 0
    assert called == []


def test_bulk_tv_delete_sends_the_whole_list_at_once(client, monkeypatch):
    """One call for the selection: the TV takes a list and serves one art channel."""
    with backend.app.app_context():
        backend.db.session.add(backend.TV(ip="192.0.2.42", name="TV", token="tok"))
        backend.db.session.commit()

    calls = []

    def fake_delete(ip, content_ids, token=None):
        calls.append((ip, list(content_ids), token))
        return len(content_ids)

    monkeypatch.setattr(backend, "delete_tv_images", fake_delete)
    res = client.post("/api/tv/192.0.2.42/gallery/delete", json={"content_ids": ["A", "B", "C"]})

    assert res.status_code == 200 and res.get_json()["deleted"] == 3
    assert len(calls) == 1, "the whole selection should go in a single call"
    assert calls[0] == ("192.0.2.42", ["A", "B", "C"], "tok")


def test_bulk_tv_delete_needs_a_known_tv(client):
    assert client.post("/api/tv/192.0.2.99/gallery/delete", json={"content_ids": ["A"]}).status_code == 404


def test_a_tv_in_use_is_left_alone():
    """Showing an image switches a Frame TV to art mode, cutting across whoever is watching."""
    tv = FakeTV(ip="192.0.2.30", token="1")
    asked = []

    def art_mode(ip, token=None):
        asked.append(ip)
        return False

    assert slideshow._is_showing_art(tv, art_mode, (OSError,)) is False
    assert asked == ["192.0.2.30"], "the TV should have been asked, not assumed"


def test_a_tv_already_showing_art_is_rotated():
    tv = FakeTV(ip="192.0.2.31", token="1")
    assert slideshow._is_showing_art(tv, lambda ip, token=None: True, (OSError,)) is True


def test_a_tv_that_cannot_be_read_is_treated_as_in_use():
    """Skipping a rotation is harmless; interrupting one is not."""
    tv = FakeTV(ip="192.0.2.32", token="1")

    def unreachable(ip, token=None):
        raise OSError("no route to host")

    assert slideshow._is_showing_art(tv, unreachable, (OSError,)) is False


def test_the_rotation_wraps_around():
    uploaded = [type("U", (), {"content_id": c})() for c in ("A", "B", "C")]
    assert slideshow._next_content_id(uploaded, None) == "A"
    assert slideshow._next_content_id(uploaded, "A") == "B"
    assert slideshow._next_content_id(uploaded, "C") == "A", "wraps to the start"
    assert slideshow._next_content_id(uploaded, "gone") == "A", "forgets an image that left"
    assert slideshow._next_content_id([], "A") is None


def test_the_slideshow_cannot_be_enabled_half_configured(client):
    with backend.app.app_context():
        backend.db.session.add(backend.TV(ip="192.0.2.21", name="TV", token="1"))
        backend.db.session.commit()

    res = client.patch("/api/tvs/192.0.2.21", json={"slideshow_enabled": True})
    assert res.status_code == 400

    client.post("/api/albums", json={"name": "Rotation"})
    album_id = client.get("/api/albums").get_json()["albums"][0]["id"]
    res = client.patch("/api/tvs/192.0.2.21", json={
        "slideshow_enabled": True,
        "slideshow_album_id": album_id,
        "slideshow_interval_minutes": 15,
    })
    assert res.status_code == 200

    tv = client.get("/api/tvs").get_json()["tvs"][0]
    assert tv["slideshow_enabled"] is True
    assert tv["slideshow_interval_minutes"] == 15


@pytest.mark.parametrize("payload", [
    {"slideshow_interval_minutes": 0},
    {"slideshow_interval_minutes": "soon"},
    {"slideshow_album_id": 999},
])
def test_invalid_slideshow_settings_are_refused(client, payload):
    with backend.app.app_context():
        backend.db.session.add(backend.TV(ip="192.0.2.22", name="TV", token="1"))
        backend.db.session.commit()
    assert client.patch("/api/tvs/192.0.2.22", json=payload).status_code in (400, 404)
