---
type: architecture
title: System architecture
description: How the Flask backend, the React single-page frontend, the on-disk data directory and the optional Electron desktop shell fit together, and how a request travels from the browser to a Samsung Frame TV.
tags: [architecture, flask, react, electron, overview]
verified:
  - by: openwiki/0.7.2
    at: 2026-10-27T18:55:06.371Z
sources:
  - id: openwiki-source-3fe14ba9156cad65ad4a9425
    resource: repo://.github/workflows/build_desktop_app.yaml
  - id: openwiki-source-7872be2c059c5659d94804ea
    resource: repo://backend/app.py
  - id: openwiki-source-ba30ebcb023436412b51c6d9
    resource: repo://backend/utils/frame_tv.py
  - id: openwiki-source-8dd9baa7e93ddd33930c601f
    resource: repo://frontend/app/utils/galleryApi.ts
  - id: openwiki-source-bf839e4efab0717d06e8c988
    resource: repo://frontend/main.js
  - id: openwiki-source-b18e9242e8b5eda6fb47c473
    resource: repo://frontend/react-router.config.ts
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
generated: { by: "claude-code", at: "2026-10-27T18:55:06.371Z" }
---

# System architecture

The project is a self-hosted manager for the art on Samsung Frame TVs. It has three parts that ship together: a Python Flask backend, a React single-page frontend, and an optional Electron shell that packages both as a desktop app.

```
browser / Electron window
        │  fetch /api/...
        ▼
Flask app  (backend/app.py, 42 routes)
   ├─ SQLite + uploads on disk   (data directory)
   ├─ utils/frame_tv.py          (what to ask a TV)
   │     └─ utils/tv_connection.py   (how to ask it: locks, deadlines, cleanup)
   │           └─ samsungtvws websocket ──► Frame TV
   └─ serves the built frontend  (frontend/build/client)
```

## The frontend is a static single-page app

The frontend is built with server-side rendering switched off and prerendering off, so the build output is plain static files (`frontend/react-router.config.ts` lines 5 to 7). Flask points its static folder at `../frontend/build/client` (`backend/app.py` line 100).

Flask serves that build through a catch-all route registered last so that it has the lowest priority. If the requested path is a real file it sends the file, and for any other path it sends `index.html`, which is what lets client-side routing handle URLs such as `/tv-gallery` on a page reload (`backend/app.py` lines 1476 to 1487).

Uploaded images are served separately from `/uploads/<filename>` (`backend/app.py` lines 879 to 880).

## The API surface

Everything the frontend needs is under `/api/`. `backend/app.py` declares 42 route decorators covering images, albums, upload, TV management, sending art, power and art mode, backup, reconcile and the status check. Two blueprints add the external photo-source routes: `media_provider_routes` and `provider_config_routes` (`backend/app.py` lines 132 to 133).

A few older TV routes exist without the `/api` prefix, for example `/tv/<ip>/on`, `/tv/<ip>/off`, `/tv/<ip>/artmode` and `/tv/<ip>/status`, alongside their `/api/tv/...` equivalents.

### There is no authentication, and CORS is open

The README states that the app implements no authentication or authorisation and is meant for private networks only (`README.md` lines 30 to 34). The code matches: cross-origin access is allowed from any origin on `/api/*`, and an `after_request` hook also sets `Access-Control-Allow-Origin: *` on every response. The same hook adds `X-Content-Type-Options`, `X-Frame-Options: DENY` and a referrer policy (`backend/app.py` lines 105 to 123).

Treat the service as reachable by anyone who can reach its port. Do not publish it without adding your own protection in front.

## Where the frontend finds the backend

Each API client module builds its base URL from `VITE_API_URL` and falls back to the page's own origin, or to a relative path, when it is not set (`frontend/app/utils/galleryApi.ts` lines 3 to 4, and the same pattern in `tvApi.ts`, `providerApi.ts` and `appApi.ts`). When Flask serves the frontend the two share an origin, so no setting is needed. The desktop build sets `VITE_API_URL` at build time because there the frontend and backend are different origins (`.github/workflows/build_desktop_app.yaml` line 76).

## The data directory

`FRAME_TV_DATA` names the data directory and defaults to `data`. Under it the backend creates two folders on startup:

- `uploads/` holds the image files.
- `instance/` holds `frametv.db`, the SQLite database, plus the derived thumbnail directories (`backend/app.py` lines 77 to 96).

<!-- openwiki: broken internal link [/openwiki/architecture/data-model-and-migrations.md] link "/openwiki/architecture/data-model-and-migrations.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
TV preview thumbnails are cached under `instance/tv_thumbnails` (`backend/utils/frame_tv.py` lines 52 to 57). Everything in `instance/thumbnails` and `instance/tv_thumbnails` can be rebuilt, so only the database and `uploads/` need backing up. See [Data model and migrations](/openwiki/architecture/data-model-and-migrations.md) for the schema.

## How a request reaches a TV

A request that touches a TV goes through two layers, and keeping them apart is the main design rule:

<!-- openwiki: broken internal link [/openwiki/operations/diagnostics-and-failure-modes.md] link "/openwiki/operations/diagnostics-and-failure-modes.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
1. `backend/utils/frame_tv.py` decides what to ask: list the gallery, upload an image, delete, select, switch art mode. The route handlers in `app.py` import these functions (`backend/app.py` lines 46 to 69). Two of them, `probe_tv` and `diagnose_tv`, serve the read-only `GET /api/tv/<ip>/diagnostics` route (`backend/app.py` line 1460), which the Settings page uses for its test-connection button; see [Diagnostics and failure modes](/openwiki/operations/diagnostics-and-failure-modes.md).
2. `backend/utils/tv_connection.py` decides how to ask it safely: one caller per TV at a time, a hard deadline, a watchdog for silence, and cleanup of connections the TV left half-open.

<!-- openwiki: broken internal link [/openwiki/tv/connection-and-session.md] link "/openwiki/tv/connection-and-session.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
See [TV connection layer](/openwiki/tv/connection-and-session.md) for the second layer, which is where most reliability problems live.

## Background work

<!-- openwiki: broken internal link [/openwiki/workflows/slideshow.md] link "/openwiki/workflows/slideshow.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
On import the app also starts the slideshow loop unless `FRAME_TV_SLIDESHOW` is set to `0`, `false` or `no`. Only one worker process runs it (`backend/app.py` lines 157 to 170). See [Slideshow rotation](/openwiki/workflows/slideshow.md).

## The desktop shell

The Electron main process, `frontend/main.js`, runs three things when the app is packaged:

- A frozen copy of the Flask backend, started as a child process with the `--upgrade-db` flag so the database is migrated first. It listens on port 5543 and keeps its data in Electron's per-user `userData/data` directory, passed through the `FRAME_TV_DATA` and `BACKEND_PORT` environment variables (`frontend/main.js` lines 64 to 91).
- A small static HTTP server on `127.0.0.1:5174` that serves the built frontend files (`frontend/main.js` lines 13 to 14 and 147 onward).
- A browser window that loads that local address. In development it loads the Vite dev server at `http://localhost:5173` instead (`frontend/main.js` lines 254 to 283).

If the backend exits with a non-zero code while the app is not quitting, the shell shows the captured error to the user (`frontend/main.js` lines 115 to 130).

<!-- openwiki: broken internal link [/openwiki/operations/deployment-and-release.md] link "/openwiki/operations/deployment-and-release.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
In the container image none of this applies: gunicorn runs the Flask app directly and Flask serves the frontend build. See [Deployment and release](/openwiki/operations/deployment-and-release.md).

## Related pages

<!-- openwiki: broken internal link [/openwiki/architecture/data-model-and-migrations.md] link "/openwiki/architecture/data-model-and-migrations.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [Data model and migrations](/openwiki/architecture/data-model-and-migrations.md)
<!-- openwiki: broken internal link [/openwiki/frontend/spa-structure.md] link "/openwiki/frontend/spa-structure.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [Frontend structure](/openwiki/frontend/spa-structure.md)
<!-- openwiki: broken internal link [/openwiki/operations/deployment-and-release.md] link "/openwiki/operations/deployment-and-release.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [Deployment and release](/openwiki/operations/deployment-and-release.md)
