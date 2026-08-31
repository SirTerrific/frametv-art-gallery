"""Covers the Wake-on-LAN packet and the endpoint that sends it.

Run with: pytest tests/test_wake_on_lan.py
"""

import os

import pytest

import app as backend
from utils.frame_tv import _magic_packet


@pytest.fixture
def client():
    backend.app.config["TESTING"] = True
    with backend.app.app_context():
        backend.db.drop_all()
        backend.db.create_all()
    return backend.app.test_client()


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


def test_a_saved_mac_is_used_when_the_request_carries_none(client, monkeypatch):
    with backend.app.app_context():
        backend.db.session.add(
            backend.TV(ip="192.0.2.21", name="Living room", mac="aa:bb:cc:dd:ee:ff", token="1")
        )
        backend.db.session.commit()

    sent = {}
    monkeypatch.setattr(
        backend, "power_on", lambda ip, mac, token=None: sent.update(ip=ip, mac=mac)
    )
    res = client.post("/api/tv/192.0.2.21/on", json={})
    assert res.status_code == 200
    assert sent == {"ip": "192.0.2.21", "mac": "aa:bb:cc:dd:ee:ff"}


def test_a_mac_can_be_added_to_a_tv_that_has_none(client):
    with backend.app.app_context():
        backend.db.session.add(backend.TV(ip="192.0.2.22", name="Bedroom", token="1"))
        backend.db.session.commit()

    res = client.patch("/api/tvs/192.0.2.22", json={"mac": " aa:bb:cc:dd:ee:ff "})
    assert res.status_code == 200
    with backend.app.app_context():
        assert backend.TV.query.filter_by(ip="192.0.2.22").first().mac == "aa:bb:cc:dd:ee:ff"
