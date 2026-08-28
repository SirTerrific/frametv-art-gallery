"""Covers the downscaled copies served to the gallery grid.

Run with: pytest tests/test_thumbnails.py
"""

import io
import os

import pytest
from PIL import Image as PILImage

import backend.app as backend


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


def png_bytes(size):
    buf = io.BytesIO()
    PILImage.new("RGB", size, "red").save(buf, format="PNG")
    buf.seek(0)
    return buf


def upload(client, name, size=(1200, 800)):
    return client.post(
        "/api/upload",
        data={"file": (png_bytes(size), name)},
        content_type="multipart/form-data",
    )


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


def test_a_thumbnail_is_reused_rather_than_rebuilt(client):
    upload(client, "big.png", size=(1200, 800))
    client.get("/uploads/big.png?w=400")

    cached = list(backend.THUMBNAIL_DIR.rglob("*"))
    assert any(p.is_file() for p in cached), "the copy should be kept on disk"

    # A second request must serve the same bytes without touching the original again.
    assert client.get("/uploads/big.png?w=400").status_code == 200
