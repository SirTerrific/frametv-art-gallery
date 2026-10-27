---
type: workflow
title: Slideshow rotation
description: How a per-TV slideshow steps through an album on an interval, why exactly one gunicorn worker runs the loop, how it avoids interrupting someone who is watching, and how a stale image is handled.
tags: [slideshow, background-thread, gunicorn, flock, scheduling, workflow]
verified:
  - by: openwiki/0.5.1
    at: 2026-09-21T02:31:07.302Z
sources:
  - id: openwiki-source-7872be2c059c5659d94804ea
    resource: repo://backend/app.py
  - id: openwiki-source-bdcda08a153a6290f9c1105f
    resource: repo://backend/utils/slideshow.py
generated: { by: "claude-code", at: "2026-10-27T18:55:06.371Z" }
---

# Slideshow rotation

A TV can be set to rotate through an album on a timer: every so many minutes it switches to the next image. The rotation is a background thread inside the web app, not a separate service, so there is nothing extra to deploy. It lives in `backend/utils/slideshow.py`.

## What it rotates through

The slideshow never uploads anything. It only moves to an image that is already on the TV, so one rotation is a single short `select_image` call (`backend/utils/slideshow.py` lines 1 to 10).

To decide what is on the TV it uses the app's own upload records: the images in the chosen album that have been sent to that TV, in the order they were sent. It takes the entry after the one it showed last, and wraps around to the first at the end (`backend/utils/slideshow.py` lines 60 to 67 and 122 to 132).

Because of that, an album must be sent to the TV before its slideshow has anything to show. If the album has no images on that TV the loop logs that the album needs sending first, and records the attempt so an empty album does not retry on every tick (`backend/utils/slideshow.py` lines 133 to 140).

## Configuring it

<!-- openwiki: broken internal link [/openwiki/architecture/data-model-and-migrations.md] link "/openwiki/architecture/data-model-and-migrations.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
The settings live on the `TV` row: an enabled flag, an album, an interval in minutes, the time of the last rotation and the last content id shown (see [Data model and migrations](/openwiki/architecture/data-model-and-migrations.md)). They are changed through `PATCH /api/tvs/<ip>`, which validates them (`backend/app.py` lines 941 to 972):

- The album must exist. An unknown one is a 404 and a malformed id is a 400.
- The interval must be a whole number of at least one minute.
- The slideshow cannot be enabled without both an album and an interval. The request is refused with a message asking for both.

An empty value clears the album or the interval.

## Only one worker runs the loop

gunicorn starts several worker processes and every one imports the app, and with it this module. A plain thread would therefore fire each rotation once per worker. A lock file decides which single process owns the loop (`backend/utils/slideshow.py` lines 1 to 6).

At start-up each process tries to take an exclusive, non-blocking `flock` on `instance/slideshow.lock`. The one that succeeds runs the loop and keeps the file handle open for as long as it lives. Every other process logs that another worker runs the slideshow and does nothing (`backend/app.py` line 158 and `backend/utils/slideshow.py` lines 32 to 48 and 106 to 110).

Keeping the handle open is the point of the design: if the owning process dies, the operating system releases the lock, and the next worker that starts can take it. Without `fcntl`, as on Windows, there is no arbitration and the process simply becomes the owner, which is acceptable only for a single-process development server (`backend/utils/slideshow.py` lines 32 to 41).

The lock is claimed once, at start-up. A worker that was not chosen does not retry later, so if the owner dies while the other workers keep running, nothing takes over until a new worker starts.

Setting `FRAME_TV_SLIDESHOW` to `0`, `false` or `no` skips starting the loop at all (`backend/app.py` lines 157 to 170).

### It stays out of the way of database migrations

`flask db upgrade` imports the app too. Starting the loop there would have it query tables that a migration is still altering, so `start` returns immediately when the `FLASK_RUN_FROM_CLI` variable is set (`backend/utils/slideshow.py` lines 100 to 104).

## The loop

The thread wakes every 30 seconds, the `TICK_SECONDS` constant, and looks at every TV that has the slideshow enabled. The tick only bounds how late a rotation can be. The per-TV interval is what paces the rotation (`backend/utils/slideshow.py` lines 27 to 29 and 161 to 176).

A TV is due when the slideshow is enabled, has an album, has a positive interval, and either has never run or its last run is at least one interval old. Any exception in a tick is logged and the loop carries on (`backend/utils/slideshow.py` lines 51 to 57 and 172 to 173).

## Not interrupting someone who is watching

Selecting an image with display turned on pulls a Frame TV into art mode. If someone is watching a programme, a rotation would cut across it. So before each rotation the loop reads the TV's art-mode state and rotates only if the TV is already showing art (`backend/utils/slideshow.py` lines 70 to 81 and 114 to 120).

Two details keep this safe and quiet:

- A TV whose state cannot be read is treated as in use. Skipping a rotation is harmless and interrupting one is not.
- A skipped rotation records nothing, so the rotation resumes on the next tick once the TV returns to art mode, rather than waiting out another full interval.

<!-- openwiki: broken internal link [/openwiki/tv/connection-and-session.md] link "/openwiki/tv/connection-and-session.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
The art-mode read is an ordinary call, so it respects the cooldown described in [TV connection layer](/openwiki/tv/connection-and-session.md), which also means a TV that just failed is treated as in use for a short while.

## When a TV no longer has an image

The database can say an image is on a TV after it has been deleted there, for instance from the TV's own menu. Selecting it then fails with error number -10. Retrying it on every tick would fill the log, so a refusal of that kind is treated differently from an unreachable TV: the record is deleted and the loop moves on. The next tick tries again with the images that remain (`backend/utils/slideshow.py` lines 84 to 95 and 144 to 150).

An unreachable TV, which may simply be switched off, is logged quietly and retried on the next tick with nothing recorded (`backend/utils/slideshow.py` lines 151 to 154).

Only a successful rotation records the content id and the time and commits them (`backend/utils/slideshow.py` lines 156 to 159).

## Related pages

<!-- openwiki: broken internal link [/openwiki/tv/uploading-and-display.md] link "/openwiki/tv/uploading-and-display.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [Sending art to a TV](/openwiki/tv/uploading-and-display.md)
<!-- openwiki: broken internal link [/openwiki/architecture/data-model-and-migrations.md] link "/openwiki/architecture/data-model-and-migrations.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [Data model and migrations](/openwiki/architecture/data-model-and-migrations.md)
