"""Covers the connection indicator, the "Test connection" diagnostics, and the readable
errors a failed send now returns.

Run with: pytest tests/test_tv_diagnostics.py
"""

import io
import json
import os

import pytest
from PIL import Image as PILImage

import app as backend
from utils import frame_tv
from utils.tv_connection import (
    FrameTVConnectionError,
    FrameTVTimeoutError,
    FrameTVUnavailableError,
)


@pytest.fixture
def client():
    backend.app.config["TESTING"] = True
    with backend.app.app_context():
        backend.db.drop_all()
        backend.db.create_all()
    return backend.app.test_client()


def add_tv(ip, mac=None):
    with backend.app.app_context():
        backend.db.session.add(backend.TV(ip=ip, name="TV", token="1", mac=mac))
        backend.db.session.commit()


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def device_payload(**device):
    return FakeResponse(json.dumps({"device": device}).encode())


# --- the plain HTTP probe ---

def test_the_probe_reads_the_tvs_own_description(monkeypatch):
    monkeypatch.setattr(
        frame_tv.urllib.request,
        "urlopen",
        lambda url, timeout: device_payload(
            modelName="QN43LS03DAFXZC", FrameTVSupport="true", PowerState="standby"
        ),
    )
    probe = frame_tv.probe_tv("192.0.2.40")
    assert probe["reachable"] is True
    assert probe["model"] == "QN43LS03DAFXZC"
    assert probe["frame_tv_support"] is True
    assert probe["reported_power_state"] == "standby"


def test_a_silent_tv_probes_as_unreachable(monkeypatch):
    def refuse(url, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(frame_tv.urllib.request, "urlopen", refuse)
    assert frame_tv.probe_tv("192.0.2.41") == {"reachable": False}


def test_the_probe_only_asks_the_tvs_http_port(monkeypatch):
    seen = []

    def capture(url, timeout):
        seen.append(url)
        return device_payload()

    monkeypatch.setattr(frame_tv.urllib.request, "urlopen", capture)
    frame_tv.probe_tv("192.0.2.42")
    assert seen == ["http://192.0.2.42:8001/api/v2/"]


# --- the endpoints ---

def test_reachability_of_an_unknown_tv_is_a_404(client):
    assert client.get("/api/tv/192.0.2.50/reachability").status_code == 404


def test_reachability_reports_the_probe(client, monkeypatch):
    add_tv("192.0.2.51")
    monkeypatch.setattr(backend, "probe_tv", lambda ip: {"reachable": True, "latency_ms": 12})
    res = client.get("/api/tv/192.0.2.51/reachability")
    assert res.status_code == 200
    assert res.get_json() == {"reachable": True, "latency_ms": 12}


def test_diagnostics_skips_the_art_session_when_the_tv_is_unreachable(client, monkeypatch):
    add_tv("192.0.2.52")
    monkeypatch.setattr(backend, "probe_tv", lambda ip: {"reachable": False})

    def must_not_run(ip, token=None):
        raise AssertionError("the art channel must not be opened for an unreachable TV")

    monkeypatch.setattr(backend, "diagnose_tv", must_not_run)
    body = client.get("/api/tv/192.0.2.52/diagnostics").get_json()
    assert body["art"] is None
    assert body["art_error"] == "unreachable"


def test_diagnostics_returns_what_the_art_session_read(client, monkeypatch):
    add_tv("192.0.2.53", mac="aa:bb:cc:dd:ee:ff")
    monkeypatch.setattr(backend, "probe_tv", lambda ip: {"reachable": True})
    monkeypatch.setattr(
        backend, "diagnose_tv",
        lambda ip, token=None: {"api_version": "5.0.1.0", "art_mode": True, "artwork_count": 84},
    )
    body = client.get("/api/tv/192.0.2.53/diagnostics").get_json()
    assert body["art"] == {"api_version": "5.0.1.0", "art_mode": True, "artwork_count": 84}
    assert body["art_error"] is None
    assert body["has_mac"] is True


@pytest.mark.parametrize(
    "error, expected",
    [
        (FrameTVUnavailableError("busy"), "busy"),
        (FrameTVTimeoutError("silent"), "timeout"),
        (FrameTVConnectionError("refused"), "refused"),
    ],
)
def test_diagnostics_names_why_the_art_session_failed(client, monkeypatch, error, expected):
    add_tv("192.0.2.54")
    monkeypatch.setattr(backend, "probe_tv", lambda ip: {"reachable": True})

    def fail(ip, token=None):
        raise error

    monkeypatch.setattr(backend, "diagnose_tv", fail)
    body = client.get("/api/tv/192.0.2.54/diagnostics").get_json()
    assert body["art_error"] == expected
    assert body["art"] is None


# --- sending: the error says what to do ---

def upload(client, name):
    buf = io.BytesIO()
    PILImage.new("RGB", (60, 40), "red").save(buf, format="PNG")
    buf.seek(0)
    return client.post("/api/upload", data={"file": (buf, name)}, content_type="multipart/form-data")


@pytest.mark.parametrize(
    "error, status, code",
    [
        (FrameTVUnavailableError("busy"), 503, "tv_busy"),
        (FrameTVTimeoutError("silent"), 504, "tv_timeout"),
        (FrameTVConnectionError("down"), 503, "tv_unreachable"),
    ],
)
def test_a_failed_send_carries_a_code_and_a_readable_message(client, monkeypatch, error, status, code):
    upload(client, "diag.png")
    add_tv("192.0.2.60")

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(backend, "upload_artwork", fail)
    res = client.post("/api/tv/send", json={"ip": "192.0.2.60", "filename": "diag.png"})
    assert res.status_code == status
    body = res.get_json()
    assert body["code"] == code
    assert body["error"] and "Traceback" not in body["error"]
