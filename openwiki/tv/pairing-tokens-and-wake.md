---
type: workflow
title: Pairing, tokens, discovery and wake
description: How a TV is added and paired, how the token a TV hands back is kept, how network discovery actually finds TVs and why it fails in Docker's bridge network, and how Wake-on-LAN is sent.
tags: [tv, pairing, token, discovery, wake-on-lan, networking, docker]
sources:
  - id: openwiki-source-7872be2c059c5659d94804ea
    resource: repo://backend/app.py
  - id: openwiki-source-3641e44aef067384d4965781
    resource: repo://backend/docker-compose.yml
  - id: openwiki-source-33cbfc7e7a71efa3be86a374
    resource: repo://backend/models.py
  - id: openwiki-source-ba30ebcb023436412b51c6d9
    resource: repo://backend/utils/frame_tv.py
  - id: openwiki-source-a74be312010be245530dc464
    resource: repo://backend/utils/tv_connection.py
  - id: openwiki-source-23a8828f83b2075e11c50219
    resource: repo://backend/utils/tv_discovery.py
  - id: openwiki-source-463c99d2c8ebb24e2bc02214
    resource: repo://frontend/app/routes/settings.tsx
generated: { by: "claude-code", at: "2026-10-27T18:55:06.371Z" }
verified:
  - by: openwiki/0.5.1
    at: 2026-09-21T12:08:00.549Z
---

# Pairing, tokens, discovery and wake

This page covers how the app first meets a TV and how it keeps recognising it: adding a TV, the token that proves the app is authorised, finding TVs on the network, and waking one that is off.

## Adding a TV

The Settings page posts to `POST /api/tvs` with an address and, optionally, a name and MAC. The handler refuses an address that is already stored, then opens a connection to the TV to obtain a token (`backend/app.py` lines 986 to 1028).

Opening that connection is what makes a Frame TV show an on-screen prompt asking whether to allow the app. The handler waits for the person to accept, then reads the token the TV issues, and stores a new `TV` row with the address, name, MAC and token.

The details that matter:

- **The wait is bounded.** The connection is built with `FRAME_TV_PAIRING_TIMEOUT` (default 45 seconds). Without it the socket has no read timeout at all, a prompt nobody answers would hold the request until gunicorn killed the worker, and the half-open socket it left behind would hold the TV's single art channel and make every later call time out. The connection is also closed in a `finally`, so a refused or failed pairing does not leak it (`backend/app.py` lines 998 to 1009).
- **The token must be all digits.** Whatever form the library returns, it is normalised to a string, and anything that is missing or not numeric is rejected with 403 and the message that the person must accept pairing on the TV (`backend/app.py` lines 1010 to 1018).
- **Failures are generic.** The handler catches `FrameTVError` and then any other exception. A pairing timeout comes from the underlying library, not from the app's own error types, so it lands in the generic branch and returns a 500 with "Unexpected error while adding TV" (`backend/app.py` lines 1019 to 1024).
- **An existing address cannot be added again.** Adding is refused with 400 when the address exists, so anything that must be changed on an existing TV is done with `PATCH /api/tvs/<ip>` instead.

## Keeping the token

A Frame TV issues a fresh token each time a client connects and stops honouring the previous one. If the app kept only the token from pairing, every later connection would present a stale one and the TV would ask the person to allow the app again, every time.

<!-- openwiki: broken internal link [/openwiki/tv/connection-and-session.md] link "/openwiki/tv/connection-and-session.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
So the connection layer captures the newest token after every call, including calls that fail, and hands it to an observer that writes it to the TV's row. The token arrives during the handshake, so even a call that dies later has learned the one the TV expects next time (`backend/app.py` lines 186 to 207 and `backend/utils/tv_connection.py` lines 416 to 424). See [TV connection layer](/openwiki/tv/connection-and-session.md).

The token is stored as text on the `TV` row (`backend/models.py` line 34). It is sent back to the TV on every call and is never shown to the frontend as part of the TV list.

If the TV asks for authorisation again after an update, accept it once: the new token is then stored and it stops asking.

## Discovery

The Settings page can scan for TVs, through `GET /api/tvs/discover`. Discovery is a scan by unicast HTTP, not a broadcast (`backend/utils/tv_discovery.py` lines 6 to 46).

1. It works out the local /24 subnet by opening a UDP socket toward a public address and reading the socket's own IP. No packet is sent; the call only makes the operating system choose an outgoing interface.
2. It probes every address from `.1` to `.254` of that subnet with an HTTP request to `http://<ip>:8001/api/v2/`, using 60 threads and a 0.8 second timeout per address.
3. An address counts as a TV when the answer's device type contains "Samsung" or the model contains "FRAME". Each result reports the address, name, model, Wi-Fi MAC and whether the TV supports the Frame features.

Selecting a result in the page fills the add form, including the MAC, and offers to add it at once.

### Why it finds nothing in Docker's bridge network

The subnet comes from the address the scanner itself uses. On the host network that is the real LAN, so the scan covers it. In Docker's default bridge network the container's address belongs to Docker's own subnet, so the scan probes the wrong network and finds nothing. The scan is also limited to one /24, so a larger LAN is only partly covered.

The compose file's comment keeps the two reasons apart: Wake-on-LAN needs the broadcast to leave the bridge, and discovery fails on the bridge because the subnet it probes is Docker's, not yours. The practical advice is the same for both: on the bridge, add each TV by typing its address (`backend/docker-compose.yml` lines 9 to 14).

## Wake-on-LAN

A TV that is off has no network stack, so it cannot be asked to wake through its websocket. Wake-on-LAN sends a magic packet addressed to its MAC.

`power_on` builds the packet, which is six `0xFF` bytes followed by the MAC repeated sixteen times, and sends it by UDP broadcast to ports 7 and 9. It sends to two targets: the global broadcast address, which is what usually works, and the broadcast address of the TV's /24 subnet, which helps when a router forwards it and the host has several interfaces. It succeeds if at least one send worked, and raises a connection error if none did (`backend/utils/frame_tv.py` lines 300 to 348).

Points to know:

- **A broadcast cannot be acknowledged.** The app can report only that the packet was sent, never that the TV woke. See the troubleshooting section in the README for what has to be true on the TV: the setting that lets it wake from the network, and the MAC of the interface it actually uses, since Wi-Fi and Ethernet differ.
- **It needs the host network.** A broadcast sent from a bridged container stays on Docker's bridge. Only the host network puts it on the physical LAN (`backend/docker-compose.yml` lines 9 to 14).
- **It needs a MAC.** `POST /api/tv/<ip>/on` uses the MAC in the request, or falls back to the one stored on the TV, and answers 400 saying the TV has no MAC saved when neither exists (`backend/app.py` lines 1384 to 1391).
- **A malformed MAC is a 400, not a server error.** The packet builder rejects a MAC that is not twelve hex digits with a `ValueError`. The endpoint catches it before the app's own TV errors and answers 400 with "The MAC address is not valid", so the user is told what to fix instead of seeing a generic 500 (`backend/utils/frame_tv.py` lines 300 to 309 and `backend/app.py` lines 1379 to 1396).

A TV added by hand starts without a MAC, and adding it again is refused. The Settings page therefore shows a MAC field for any TV that lacks one, and saves it with `PATCH /api/tvs/<ip>`, which accepts a `mac` value (`backend/app.py` lines 925 to 940 and `frontend/app/routes/settings.tsx` lines 173 to 185 and 370 to 390). Discovery fills the MAC in automatically when a TV is added from a scan.

## Related pages

<!-- openwiki: broken internal link [/openwiki/tv/connection-and-session.md] link "/openwiki/tv/connection-and-session.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [TV connection layer](/openwiki/tv/connection-and-session.md)
<!-- openwiki: broken internal link [/openwiki/operations/deployment-and-release.md] link "/openwiki/operations/deployment-and-release.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [Deployment and release](/openwiki/operations/deployment-and-release.md)
