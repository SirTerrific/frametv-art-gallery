---
type: architecture
title: TV connection layer
description: How every call to a Samsung Frame TV is made and bounded — the per-TV lock, thread-pool deadline, stall watchdog, cooldown, half-open connection cleanup, token capture and error types — and which settings tune it.
tags: [tv, connection, timeouts, locking, samsungtvws, reliability]
sources:
  - id: openwiki-source-7872be2c059c5659d94804ea
    resource: repo://backend/app.py
  - id: openwiki-source-31da078a7907297ef877dbe6
    resource: repo://backend/tests/test_frame_tv_timeouts.py
  - id: openwiki-source-ba30ebcb023436412b51c6d9
    resource: repo://backend/utils/frame_tv.py
  - id: openwiki-source-a74be312010be245530dc464
    resource: repo://backend/utils/tv_connection.py
generated: { by: "claude-code", at: "2026-10-27T18:55:06.371Z" }
verified:
  - by: openwiki/0.5.1
    at: 2026-09-21T12:08:00.549Z
---

# TV connection layer

A Frame TV is a slow, single-tenant device. It serves one art channel, it can go quiet mid-request, and the library the app uses to talk to it (`samsungtvws`) waits on a read with no overall time limit. Everything in `backend/utils/tv_connection.py` exists so that one bad TV cannot hang a request, block the other TVs, or leave the set in a state that breaks the next call.

Route handlers never call the library directly. They call functions in `backend/utils/frame_tv.py`, which describe what to ask a TV, and each of those goes through one function, `_tv_call`, which decides how to ask.

## Two modules, one entry point

`tv_connection.py` owns connections: locks, deadlines, cleanup, the session object and the exception types. `frame_tv.py` owns operations: listing images, uploading, deleting, switching modes, thumbnails.

`frame_tv.py` keeps the older names available. It re-exports the exception classes, the session class and a few helpers from `tv_connection`, and defines its own thin `_tv_call` that fills in the session factory and the busy wait, then delegates. The point of the indirection is that tests can patch the session factory in one place (`backend/utils/frame_tv.py` lines 894 to 920).

## What one call does

`_tv_call(ip, description, action, ...)` runs `action(session)` against one TV. In order (`backend/utils/tv_connection.py` lines 383 to 493):

1. **Cooldown check.** If this is a background call and the TV failed recently, it raises `FrameTVUnavailableError` immediately instead of contacting the TV.
2. **Take the per-TV lock.** Only one call talks to a given TV at a time. If the lock is not free within the wait limit, it raises `FrameTVUnavailableError` saying the TV stayed busy.
3. **Clear stale connections.** Any connection an earlier, abandoned call left open to this TV is closed first.
4. **Run on a worker thread.** The session is created and the work is submitted to a thread pool. The calling thread waits on the result with the deadline as a timeout. This is the essential trick: the library cannot be made to time out overall, so the timeout is enforced from outside.
5. **Open, then act.** On the worker it opens the remote-control channel unless the caller passed `open_remote=False`, then runs the action, recording how long each phase took.
6. **Settle the outcome.** See below.

The pool is bounded by `FRAME_TV_MAX_PARALLEL_CALLS` (default 8) per worker process (`backend/utils/tv_connection.py` lines 351 to 353).

### Outcomes

| Outcome | What happens |
| --- | --- |
| Success | The TV is marked up (its cooldown marker is removed), any new token is captured, the session is closed, and the result is returned. |
| Deadline passed | The traffic description and frame count are read first, then the session is closed to unblock the worker, any new token is captured, the TV is marked down, a diagnostic line is logged, and `FrameTVTimeoutError` is raised. If no frame arrived, a second line with the TV's own state is logged from a background thread, so it never delays the error. |
| Exception from the action | The session is closed and any new token is captured. If it looks like a connection problem the TV is marked down and a connection or timeout error is raised. Otherwise the original exception is re-raised untouched. |

That last distinction matters. An error the TV itself reports, such as a rejected request or an unknown content id, is not a connection fault, so it must not put the TV into cooldown and must reach the caller unchanged (`backend/utils/tv_connection.py` lines 371 to 380 and 483 to 489). A test guards this (`test_tv_errors_are_not_swallowed_as_connection_errors`).

## The per-TV lock

The lock has two layers. A thread lock per IP serialises threads inside one process. On systems with `fcntl` it is backed by a lock file per TV under `instance/tv_locks`, taken with a non-blocking `flock` and retried every 100 ms, which makes it hold across all gunicorn worker processes (`backend/utils/tv_connection.py` lines 216 to 265). Without `fcntl`, as on Windows, only the in-process lock applies.

The two waits differ on purpose. A background read waits only as long as its own deadline, so a page load does not queue for long. A deliberate action, where someone pressed a button and is waiting for that TV, waits up to `FRAME_TV_BUSY_WAIT` (default 90 seconds) so it can queue behind a long read instead of failing (`backend/utils/tv_connection.py` line 395).

Upload, delete, play, brightness, power-off, art mode and matte changes are the deliberate calls: they pass `skip_when_down=False` (`backend/utils/frame_tv.py`, for example lines 177, 233, 249 and 357).

## The cooldown

A failed call touches a marker file, `instance/tv_down/tv-<ip>`. A later background call reads the file's modification time, and if it is younger than `FRAME_TV_DOWN_COOLDOWN` seconds (default 30) it is refused at once with `FrameTVUnavailableError`. A success deletes the marker (`backend/utils/tv_connection.py` lines 189 to 213).

Using a file rather than a variable is what makes the cooldown shared between gunicorn workers. It exists to stop a gallery page, which fires many reads, from stampeding a TV that is already struggling. Deliberate actions ignore it.

## Closing what the library leaves open

The library opens websockets internally and gives the app no handle to close one that is stuck. `_ConnectionTracker` solves that. At import, the module replaces the `websocket` module that `samsungtvws.connection` uses with a wrapper. Each connection it creates is recorded against the thread that opened it, and its `recv` is wrapped to count frames and bytes and to report progress (`backend/utils/tv_connection.py` lines 79 to 140 and 486).

That record gives three things:

- A call that is abandoned can have its exact socket closed from another thread, which makes the blocked read raise instead of hanging forever.
- Before a new call starts, `reset_connections(ip)` closes any connection still recorded against that TV (`backend/utils/tv_connection.py` lines 268 to 281).
- Every frame that arrives counts as progress, which is what the stall watchdog watches.

## The stall watchdog

A caller may pass `stall_timeout`. A daemon thread then checks once a second how long it has been since a frame arrived. When that exceeds the limit it logs the silence and closes the session, which unblocks the worker. It is used for gallery listing and thumbnails, where a TV that starts talking and then stops is a real case. The default is 25 seconds through `FRAME_TV_STALL_TIMEOUT`, so for an ordinary call the 20 second deadline fires first (`backend/utils/tv_connection.py` lines 426 to 439).

## Keeping the token the TV hands back

<!-- openwiki: broken internal link [/openwiki/tv/pairing-tokens-and-wake.md] link "/openwiki/tv/pairing-tokens-and-wake.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
A Frame TV issues a fresh token when a client connects and stops honouring the previous one. After every call, successful or not, `_tv_call` asks the session for the newest token its channels received. If it differs from the one used, it hands it to a registered observer. `app.py` registers `_remember_tv_token`, which writes it to the TV's row (`backend/utils/tv_connection.py` lines 333 to 338 and 416 to 424, and `backend/app.py` lines 186 to 207). Keeping it even after a failure matters, because the token arrives during the handshake, so a call that dies later has still learned the one the TV expects next time. See [Pairing, tokens, discovery and wake](/openwiki/tv/pairing-tokens-and-wake.md).

## Error types

All of them live in `tv_connection.py` (`backend/utils/tv_connection.py` lines 63 to 76):

- `FrameTVError` is the base.
- `FrameTVConnectionError` covers a TV that cannot be reached or dropped the connection.
- `FrameTVTimeoutError` is a connection error raised when a deadline passes.
- `FrameTVUnavailableError` is a connection error raised without contacting the TV, for the cooldown and for a busy lock.

<!-- openwiki: broken internal link [/openwiki/operations/diagnostics-and-failure-modes.md] link "/openwiki/operations/diagnostics-and-failure-modes.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
Because the last two are subclasses, code that catches `FrameTVConnectionError` also catches them, and route handlers catch the most specific class first (see [Diagnostics and failure modes](/openwiki/operations/diagnostics-and-failure-modes.md)).

## Settings

Each is an environment variable read once at import. The defaults below are the current values.

| Variable | Default | Meaning |
| --- | --- | --- |
| `FRAME_TV_CALL_DEADLINE` | 20 | Seconds an ordinary call may take. |
| `FRAME_TV_UPLOAD_DEADLINE` | 120 | Deadline for uploads, which push a whole file. |
| `FRAME_TV_BUSY_WAIT` | 90 | How long a deliberate call queues behind another. |
| `FRAME_TV_SOCKET_TIMEOUT` | 8 | Read timeout for a single socket operation. |
| `FRAME_TV_PAIRING_TIMEOUT` | 45 | How long adding a TV waits for the on-screen prompt. |
| `FRAME_TV_DOWN_COOLDOWN` | 30 | Seconds a failed TV is skipped. |
| `FRAME_TV_STALL_TIMEOUT` | 25 | Seconds of silence before the watchdog closes a connection. |
| `FRAME_TV_MAX_PARALLEL_CALLS` | 8 | Worker threads per process. |

An invalid value is logged and replaced with the default (`backend/utils/tv_connection.py` lines 46 to 60).

Some of these defaults are declared twice, in `tv_connection.py` and in `frame_tv.py`, for example the call deadline, upload deadline and busy wait (`backend/utils/frame_tv.py` lines 24 to 26, `backend/utils/tv_connection.py` lines 56 to 60). Both read the same variable, so setting it changes both, but if you change a default in the code, change it in both places.

## Related pages

<!-- openwiki: broken internal link [/openwiki/tv/gallery-and-thumbnails.md] link "/openwiki/tv/gallery-and-thumbnails.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [TV gallery and thumbnails](/openwiki/tv/gallery-and-thumbnails.md)
<!-- openwiki: broken internal link [/openwiki/tv/pairing-tokens-and-wake.md] link "/openwiki/tv/pairing-tokens-and-wake.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [Pairing, tokens, discovery and wake](/openwiki/tv/pairing-tokens-and-wake.md)
<!-- openwiki: broken internal link [/openwiki/operations/diagnostics-and-failure-modes.md] link "/openwiki/operations/diagnostics-and-failure-modes.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [Diagnostics and failure modes](/openwiki/operations/diagnostics-and-failure-modes.md)
