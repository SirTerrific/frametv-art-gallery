"""Covers deleting art from a TV, and the records that follow it.

Run with: pytest tests/test_tv_delete.py
"""

import io

import pytest
from PIL import Image as PILImage

import app as backend


@pytest.fixture
def client():
    backend.app.config["TESTING"] = True
    with backend.app.app_context():
        backend.db.drop_all()
        backend.db.create_all()
    return backend.app.test_client()


def upload(client, name):
    buf = io.BytesIO()
    PILImage.new("RGB", (60, 40), "red").save(buf, format="PNG")
    buf.seek(0)
    return client.post(
        "/api/upload",
        data={"file": (buf, name)},
        content_type="multipart/form-data",
    )


def _tv_with_uploads(ip, pairs):
    """A TV plus the record that some images sit on it under given content ids."""
    with backend.app.app_context():
        tv = backend.TV(ip=ip, name="TV", token="1")
        backend.db.session.add(tv)
        backend.db.session.commit()
        for filename, content_id in pairs:
            image = backend.Image.query.filter_by(filename=filename).first()
            backend.db.session.add(
                backend.UploadedImage(image_id=image.id, tv_id=tv.id, content_id=content_id)
            )
        backend.db.session.commit()
        return tv.id


def _content_ids(tv_id):
    with backend.app.app_context():
        return {u.content_id for u in backend.UploadedImage.query.filter_by(tv_id=tv_id).all()}


# --- deleting a selection in one call ---

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


# --- keeping the records in step with the TV ---

def test_deleting_one_image_from_the_tv_forgets_it(client, monkeypatch):
    upload(client, "a.png")
    upload(client, "b.png")
    tv_id = _tv_with_uploads("192.0.2.60", [("a.png", "C1"), ("b.png", "C2")])

    monkeypatch.setattr(backend, "delete_tv_image", lambda *a, **k: True)
    assert client.delete("/api/tv/192.0.2.60/gallery/C1").status_code == 200
    assert _content_ids(tv_id) == {"C2"}


def test_deleting_a_selection_forgets_all_of_it(client, monkeypatch):
    for name in ("a.png", "b.png", "c.png"):
        upload(client, name)
    tv_id = _tv_with_uploads("192.0.2.61", [("a.png", "C1"), ("b.png", "C2"), ("c.png", "C3")])

    monkeypatch.setattr(backend, "delete_tv_images", lambda ip, ids, token=None: len(ids))
    assert client.post("/api/tv/192.0.2.61/gallery/delete", json={"content_ids": ["C1", "C3"]}).status_code == 200
    assert _content_ids(tv_id) == {"C2"}


def test_emptying_the_tv_forgets_everything(client, monkeypatch):
    upload(client, "a.png")
    tv_id = _tv_with_uploads("192.0.2.62", [("a.png", "C1")])

    monkeypatch.setattr(backend, "delete_all_images_from_tv", lambda *a, **k: None)
    assert client.delete("/api/tv/192.0.2.62/images").status_code == 200
    assert _content_ids(tv_id) == set()
