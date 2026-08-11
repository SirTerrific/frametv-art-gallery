"""Covers reporting the same artwork uploaded twice under different names.

Run with: pytest tests/test_duplicate_uploads.py
"""

import io
import os

import pytest
from PIL import Image as PILImage

import app as backend


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


def upload(client, name, colour="red"):
    buf = io.BytesIO()
    PILImage.new("RGB", (120, 80), colour).save(buf, format="PNG")
    buf.seek(0)
    return client.post(
        "/api/upload",
        data={"file": (buf, name)},
        content_type="multipart/form-data",
    )


def test_the_same_artwork_under_another_name_is_reported(client):
    upload(client, "original.png", colour="blue")
    res = upload(client, "copy.png", colour="blue")

    assert res.get_json()["duplicate_of"] == "original.png"
    # ...and it is still stored: silently dropping a requested upload would be worse.
    assert "copy.png" in client.get("/api/images").get_json()["images"]


def test_a_different_image_is_not_flagged(client):
    upload(client, "one.png", colour="blue")
    assert upload(client, "two.png", colour="green").get_json()["duplicate_of"] is None


def test_re_uploading_the_same_name_is_not_its_own_duplicate(client):
    upload(client, "same.png", colour="blue")
    assert upload(client, "same.png", colour="blue").get_json()["duplicate_of"] is None


def test_a_twin_whose_file_is_gone_is_not_reported(client):
    """The row can outlive the file; pointing at something deleted helps nobody."""
    upload(client, "original.png", colour="blue")
    os.remove(os.path.join(backend.app.config["UPLOAD_FOLDER"], "original.png"))

    assert upload(client, "copy.png", colour="blue").get_json()["duplicate_of"] is None


# --- reconcile ---

def test_reconcile_picks_up_and_drops_files(client):
    upload(client, "kept.png")

    # A file dropped in by hand, and a row whose file went away.
    stray = os.path.join(backend.app.config["UPLOAD_FOLDER"], "stray.png")
    PILImage.new("RGB", (120, 80), "purple").save(stray)
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


def test_reconcile_leaves_album_membership_alone(client):
    upload(client, "kept.png")
    with backend.app.app_context():
        album = backend.Album(name="Holiday")
        backend.db.session.add(album)
        backend.db.session.commit()
        image = backend.Image.query.filter_by(filename="kept.png").first()
        image.album_id = album.id
        backend.db.session.commit()
        album_id = album.id

    client.post("/api/images/reconcile")

    with backend.app.app_context():
        assert backend.Image.query.filter_by(filename="kept.png").first().album_id == album_id
