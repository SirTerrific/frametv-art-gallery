---
type: operations
title: Diagnostics and failure modes
description: How to turn up logging, how a failed TV call is reported and what each part of the failure log line means, the known ways a Frame TV stops answering, and how the update check behaves.
tags: [diagnostics, logging, troubleshooting, tv, failure-modes, update-check]
sources:
  - id: openwiki-source-7872be2c059c5659d94804ea
    resource: repo://backend/app.py
  - id: openwiki-source-ba30ebcb023436412b51c6d9
    resource: repo://backend/utils/frame_tv.py
  - id: openwiki-source-a74be312010be245530dc464
    resource: repo://backend/utils/tv_connection.py
  - id: openwiki-source-912a1ff2967d1aceca07a022
    resource: repo://frontend/app/routes/tvGallery.tsx
generated: { by: "claude-code", at: "2026-10-27T18:55:06.371Z" }
verified:
  - by: openwiki/0.7.2
    at: 2026-10-27T18:55:06.371Z
---

# Diagnostics and failure modes

Most support problems with this app are a Frame TV that stops answering. This page explains what the app tells you when that happens, and which of those signals to trust.

## Turning the log up

By default only warnings and errors reach the log, so the step-by-step lines the TV code writes at INFO are dropped. Setting `FRAME_TV_LOG_LEVEL` to `INFO` or `DEBUG` configures the root logger and the `utils` logger, which makes those lines visible without rebuilding the image. When the variable is unset nothing is configured and the app stays as quiet as before (`backend/app.py` lines 69 to 75).

The gallery fetch is the best example. With INFO on, it logs when the art channel is ready and asks for the content list, and again when the list comes back with its number of entries (`backend/utils/frame_tv.py`, in `get_tv_gallery_images`). The last of those lines you see tells you how far the TV got.

## How a failure reaches the browser

The route handlers turn the three TV exception types into different HTTP statuses so the frontend can react to each:

| Exception | Status | Body |
| --- | --- | --- |
| `FrameTVUnavailableError` | 503 | `tv_unavailable: true` |
| `FrameTVTimeoutError` | 504 | `TV request timed out` |
| `FrameTVConnectionError` | 503 | `TV is unavailable` |

<!-- openwiki: broken internal link [/openwiki/tv/connection-and-session.md] link "/openwiki/tv/connection-and-session.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
The gallery endpoint shows the pattern (`backend/app.py` lines 1204 to 1212). `FrameTVUnavailableError` is the cooldown case: the app declined to contact a TV that failed a moment ago (see [TV connection layer](/openwiki/tv/connection-and-session.md)).

Sending artwork goes further and adds a machine-readable `code` next to the message, so the browser can show help that matches the cause: `tv_busy` (503, the single art channel is in use), `tv_timeout` (504, the TV did not answer, which can mean it is fully off or waiting for the pairing prompt to be accepted) and `tv_unreachable` (503, the connection failed). Any other failure keeps the generic 500 or 400 (`backend/app.py` lines 1147 to 1167). The frontend turns these codes into a plain explanation and exposes the status through `TVError.code`.

## Testing a connection from the UI

Two read-only routes let the app check a TV without disturbing uploads in progress:

- `GET /api/tv/<ip>/reachability` is the cheap check behind the connection light in the header. It only reads the TV's plain HTTP endpoint on port 8001, so it never takes the art channel (`backend/app.py` lines 1449 to 1458).
- `GET /api/tv/<ip>/diagnostics` is behind the Test connection button in Settings. It returns the HTTP probe plus one art session that reads the art API version, whether art mode is on and how many artworks the TV holds, together with whether a MAC address is saved for waking the TV (`backend/app.py` lines 1460 to 1483, `backend/utils/frame_tv.py` lines 853 to 893).

The probe reports the model, the latency and `reported_power_state`. That last value is the firmware's own word and is not trusted alone: some firmware reports `standby` while the TV is showing art, so the art session decides. When the art session fails, `art_error` is one of `unreachable` (the probe got no answer), `busy` (another call holds the channel), `timeout` (the channel opened and stayed silent), `refused` (the connection failed) or `error` (anything else, logged). The panel maps each to advice (`frontend/app/components/TvDiagnosticsPanel.tsx`, `frontend/app/utils/tvApi.ts` lines 66 to 85).

A TV that answers the probe but whose art session times out is either fully off or waiting for a pairing prompt to be accepted on its screen; the app's own message says so, but which of the two it is cannot be told from the app.

## Reading the timeout log line

When a call runs past its deadline, `_tv_call` logs one warning:

```
TV 192.0.2.10 timed out fetching gallery images from — open: 1.4s, action: unfinished, 3 frame(s), 2048 byte(s) received, token sent
```

The parts are:

- **`open`** is how long the remote-control channel took to open. `unfinished` means the TV never completed that handshake.
- **`action`** is how long the requested operation ran. `unfinished` means it was still running when the deadline hit. `open` finished but `action` did not is the typical shape of a TV that accepts the connection and then does not answer the request.
- **The traffic figure** counts frames and bytes received from the TV during the call.
- **`token sent` or `absent`** says whether a pairing token was presented.

The call is also marked as failed for that TV, which starts the cooldown, and a `FrameTVTimeoutError` is raised (`backend/utils/tv_connection.py` lines 447 to 482).

### Why the traffic figure can be trusted

The counters are created when the worker thread starts and deleted when it unwinds (`backend/utils/tv_connection.py` lines 143 to 157 and 316 to 322). Closing the session unblocks the worker, and the worker then deletes its counter, so a figure read after the close can say `no traffic recorded` for a call that did receive frames. The timeout branch avoids that by reading the description and the raw frame count into local variables before it closes the session, and only then logs (`backend/utils/tv_connection.py` lines 447 to 469). The stall watchdog follows the same order: it reads the traffic figure before it closes the connection (`backend/utils/tv_connection.py` lines 428 to 437).

Read the figure as `N frame(s), M byte(s) received`. `no traffic recorded` is now a real statement: the TV sent no frame on this connection, or the worker never started.

The `open` and `action` timings and the traffic figure should agree with each other. Opening the remote channel waits for the TV's connect event, so `open: 1.4s` beside zero frames is a contradiction worth reporting.

### The extra state line

When the raw frame count is zero, the code asks the TV for its own report and logs it as a second warning, for example `TV 192.0.2.10: the TV reports PowerState=on, FrameTVSupport=true, name=Frame 43`. It does this with a plain HTTP request to port 8001 that needs no token and no websocket, so it can answer when the art channel does not. If even that fails, it says the TV did not answer its info endpoint either (`backend/utils/tv_connection.py` lines 23 to 43).

The request runs on its own daemon thread named `frametv-state-probe`. The probe can take seconds, and the caller is already past its deadline, so waiting for it would delay the error and hold the TV's lock just to write a log line. The consequence is that this line can appear after the 504 has been returned, and a test has to wait for the thread (`backend/utils/tv_connection.py` lines 470 to 479).

`PowerState=on` beside no frames is the signature of a wedged art channel; see below.

## The stall watchdog

A call may also pass a `stall_timeout`. A watchdog thread checks once a second how long it has been since the TV last delivered a frame, and if that exceeds the limit it logs `TV ... sent nothing for Ns while ...` with the current step and closes the connection, which unblocks the worker (`backend/utils/tv_connection.py` lines 426 to 439). The default is 25 seconds through `FRAME_TV_STALL_TIMEOUT`, which is longer than the 20 second call deadline, so for an ordinary call the deadline fires first.

## Known ways a Frame TV stops answering

A Frame TV serves a single art channel, and most of these come from that one fact.

- **The art channel is wedged.** The TV accepts the websocket and never sends anything on it. The remote channel still opens, and the TV's own HTTP endpoint still reports it is on, so the app reads as unable to reach a TV that is running fine. In the one case where this was observed on a real TV, restarting the container did not clear it and unplugging the TV from the wall did; no software-side reset is known.
- **A connection was left half open.** A pairing handshake with no deadline used to park a request until gunicorn killed the worker, leaving a socket the TV kept treating as the art channel's owner. The pairing call now has its own timeout, `FRAME_TV_PAIRING_TIMEOUT`, and closes the connection even when the handshake fails (`backend/app.py` lines 998 to 1009).
- **Another client may hold the channel.** Because there is only one, any second client of the same TV, such as a phone app, would compete for it. This follows from the single-channel limit and has not been reproduced in this project.
<!-- openwiki: broken internal link [/openwiki/tv/gallery-and-thumbnails.md] link "/openwiki/tv/gallery-and-thumbnails.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- **One request holds the channel for too long.** A single request for every thumbnail on a TV occupies the channel for the whole transfer, and anything else aimed at that TV queues behind it and times out. The frontend therefore asks for thumbnails a batch at a time and the backend takes an exclusive lock per TV (`frontend/app/routes/tvGallery.tsx` lines 17 to 20, and see [TV gallery and thumbnails](/openwiki/tv/gallery-and-thumbnails.md)).

A failed call also puts the TV in a short cooldown, `FRAME_TV_DOWN_COOLDOWN` seconds, during which background reads are refused immediately instead of piling up (`backend/utils/tv_connection.py` lines 189 to 213).

## Missing logs on a first start

<!-- openwiki: broken internal link [/openwiki/architecture/data-model-and-migrations.md] link "/openwiki/architecture/data-model-and-migrations.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
If a brand new data directory produced no `utils.*` log lines at all, the cause was alembic, not the app: `migrations/env.py` used to call `fileConfig` with its default of disabling every existing logger, and the stamp of a fresh database runs it inside the gunicorn process. It now passes `disable_existing_loggers=False` (`backend/migrations/env.py` lines 12 to 18). An image older than v2.3.2 still has the fault; restarting the container works around it, because the second start finds an existing database and skips the stamp. See [Data model and migrations](/openwiki/architecture/data-model-and-migrations.md).

## The update check

`/api/status` reports the running version and whether a newer release exists. It asks the GitHub releases API for the latest release of the fork's repository, with a 5 second timeout, and caches the answer in the `app_settings` table for 24 hours (`backend/app.py` lines 318 to 351).

If GitHub cannot be reached or answers with an error, it logs the problem and serves the cached answer instead. It compares versions with `packaging` and falls back to plain inequality when a version cannot be parsed (`backend/app.py` lines 352 to 387). The repository it queries is set in one line, and it must name the repository whose images are actually running, otherwise the app announces updates that no image it runs will ever carry (`backend/app.py` line 323).

## Related pages

<!-- openwiki: broken internal link [/openwiki/tv/connection-and-session.md] link "/openwiki/tv/connection-and-session.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [TV connection layer](/openwiki/tv/connection-and-session.md)
<!-- openwiki: broken internal link [/openwiki/tv/gallery-and-thumbnails.md] link "/openwiki/tv/gallery-and-thumbnails.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [TV gallery and thumbnails](/openwiki/tv/gallery-and-thumbnails.md)
<!-- openwiki: broken internal link [/openwiki/tv/pairing-tokens-and-wake.md] link "/openwiki/tv/pairing-tokens-and-wake.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [Pairing, tokens, discovery and wake](/openwiki/tv/pairing-tokens-and-wake.md)
