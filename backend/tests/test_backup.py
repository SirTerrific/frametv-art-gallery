"""Covers the downloadable backup archive.

Run with: pytest tests/test_backup.py
"""

import io
import os
import tempfile
import zipfile

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


def upload(client, name):
    buf = io.BytesIO()
    PILImage.new("RGB", (60, 40), "red").save(buf, format="PNG")
    buf.seek(0)
    return client.post(
        "/api/upload",
        data={"file": (buf, name)},
        content_type="multipart/form-data",
    )


def test_the_backup_contains_the_database_and_the_uploads(client):
    upload(client, "kept.png")
    res = client.get("/api/backup")
    assert res.status_code == 200

    with zipfile.ZipFile(io.BytesIO(res.data)) as archive:
        names = archive.namelist()
        assert "instance/frametv.db" in names
        assert "uploads/kept.png" in names
        assert archive.read("instance/frametv.db").startswith(b"SQLite format 3")


def test_the_backup_is_readable_and_leaves_nothing_behind(client):
    """The archive is built in a temp directory that has to be cleaned up after."""
    upload(client, "kept.png")
    before = set(os.listdir(tempfile.gettempdir()))

    res = client.get("/api/backup")
    assert res.status_code == 200
    with zipfile.ZipFile(io.BytesIO(res.data)) as archive:
        assert archive.testzip() is None, "the archive should not be corrupt"

    # The archive cannot be deleted while it is still open, so the cleanup rides on
    # the response being closed. A real server always closes it; the test client only
    # does so when asked.
    res.close()

    leftovers = {
        name for name in set(os.listdir(tempfile.gettempdir())) - before
        if name.startswith("frametv-backup-")
    }
    assert leftovers == set(), f"temporary files were left behind: {leftovers}"
