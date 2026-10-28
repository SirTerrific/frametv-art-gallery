---
type: architecture
title: System architecture
description: How the Flask backend, the React single-page frontend, the on-disk data directory and the optional Electron desktop shell fit together, and how a request travels from the browser to a Samsung Frame TV.
tags: [architecture, flask, react, electron, overview]
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
generated: { by: "claude-code", at: "2026-10-28T14:34:25.443Z" }
verified:
  - by: openwiki/0.7.2
    at: 2026-10-28T14:34:25.443Z
---

# System architecture

The project is a self-hosted manager for the art on Samsung Frame TVs. It has three parts that ship together: a Python Flask backend, a React single-page frontend, and an optional Electron shell that packages both as a desktop app.

```
browser / Electron window
        │  fetch /api/...
        ▼
Flask app  (backend/app.py, 40 routes)
   ├─ SQLite + uploads on disk   (data directory)
   ├─ utils/frame_tv.py          (what to ask a TV)
   │     └─ utils/tv_connection.py   (how to ask it: locks, deadlines, cleanup)
   │           └─ samsungtvws websocket ──► Frame TV
   └─ serves the built frontend  (frontend/build/client)
```

## The frontend is a static single-page app

The frontend is built with server-side rendering switched off and prerendering off, so the build output is plain static files (`frontend/react-router.config.ts` lines 5 to 7). Flask points its static folder at `../frontend/build/client` (`backend/app.py` line 96).

Flask serves that build through a catch-all route registered last so that it has the lowest priority. If the requested path is a real file it sends the file, and for any other path it sends `index.html`, which is what lets client-side routing handle URLs such as `/tv-gallery` on a page reload (`backend/app.py` lines 1460 to 1469).

Uploaded images are served separately from `/uploads/<filename>` (`backend/app.py` line 852).

## The API surface

Everything the frontend needs is under `/api/`. `backend/app.py` declares 40 route decorators covering images, albums, upload, TV management, sending art, power and art mode, backup, reconcile and the status check. Two blueprints add the external photo-source routes: `media_provider_routes` and `provider_config_routes` (`backend/app.py` lines 124 and 125).

The older TV routes without the `/api` prefix, `/tv/<ip>/on`, `/off`, `/artmode` and `/status`, have been removed: they no longer worked and nothing used them. Only the `/api/tv/...` routes exist.

### There is no authentication, and CORS is closed by default

The README states that the app implements no authentication or authorisation and is meant for private networks only (`README.md` lines 30 to 34). The code matches: there is no login.

CORS is off by default, so no other website gets permission to read the API from a browser. The built frontend is served by Flask and shares the API's origin, so it does not need it. To develop the frontend on another port, list the allowed origins in `CORS_ORIGINS`, for example `CORS_ORIGINS=http://localhost:5173`. An `after_request` hook always adds `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` and a `strict-origin-when-cross-origin` referrer policy (`backend/app.py` lines 101 to 114).

The Immich API key is write-only: API responses only say whether a key is stored, never the key itself, because without a login sending it back would hand it to anyone who can reach the port.

Treat the service as reachable by anyone who can reach its port. Do not publish it without adding your own protection in front.

## Where the frontend finds the backend

Each API client module builds its base URL from `VITE_API_URL` and falls back to the page's own origin, or to a relative path, when it is not set (`frontend/app/utils/galleryApi.ts` lines 3 to 4, and the same pattern in `tvApi.ts`, `providerApi.ts` and `appApi.ts`). When Flask serves the frontend the two share an origin, so no setting is needed. The desktop build sets `VITE_API_URL` at build time because there the frontend and backend are different origins (`.github/workflows/build_desktop_app.yaml` line 76).

## The data directory

`FRAME_TV_DATA` names the data directory and defaults to `data`. Under it the backend creates two folders on startup:

- `uploads/` holds the image files.
- `instance/` holds `frametv.db`, the SQLite database, plus the derived thumbnail directories (`backend/app.py` lines 77 to 96).

TV preview thumbnails are cached under `instance/tv_thumbnails` (`backend/utils/frame_tv.py` lines 52 to 57). Everything in `instance/thumbnails` and `instance/tv_thumbnails` can be rebuilt, so only the database and `uploads/` need backing up. See [Data model and migrations](data-model-and-migrations.md) for the schema.

## How a request reaches a TV

A request that touches a TV goes through two layers, and keeping them apart is the main design rule:

1. `backend/utils/frame_tv.py` decides what to ask: list the gallery, upload an image, delete, select, switch art mode. The route handlers in `app.py` import these functions (`backend/app.py` lines 46 to 69). Two of them, `probe_tv` and `diagnose_tv`, serve the read-only `GET /api/tv/<ip>/diagnostics` route (`backend/app.py` line 1460), which the Settings page uses for its test-connection button; see [Diagnostics and failure modes](../operations/diagnostics-and-failure-modes.md).
2. `backend/utils/tv_connection.py` decides how to ask it safely: one caller per TV at a time, a hard deadline, a watchdog for silence, and cleanup of connections the TV left half-open.

See [TV connection layer](../tv/connection-and-session.md) for the second layer, which is where most reliability problems live.

## External photo provider

The Immich source is not built at start-up: `get_media_provider()` in `backend/media_provider_routes.py` reads the saved settings (`ProviderConfig`) on every call. Saving or removing the settings therefore takes effect at once in every worker, with no restart. When Immich is unreachable the API answers 502, and the cache of recently viewed images is bounded to 32 entries. See [Local image library](../workflows/image-library.md).

## Background work

On import the app also starts the slideshow loop unless `FRAME_TV_SLIDESHOW` is set to `0`, `false` or `no`. Only one worker process runs it (`backend/app.py` lines 152 to 170). See [Slideshow rotation](../workflows/slideshow.md).

## The desktop shell

The Electron main process, `frontend/main.js`, runs three things when the app is packaged:

- A frozen copy of the Flask backend, started as a child process with the `--upgrade-db` flag so the database is migrated first. It listens on port 5543 and keeps its data in Electron's per-user `userData/data` directory, passed through the `FRAME_TV_DATA` and `BACKEND_PORT` environment variables (`frontend/main.js` lines 64 to 91).
- A small static HTTP server on `127.0.0.1:5174` that serves the built frontend files (`frontend/main.js` lines 13 to 14 and 147 onward).
- A browser window that loads that local address. In development it loads the Vite dev server at `http://localhost:5173` instead (`frontend/main.js` lines 254 to 283).

If the backend exits with a non-zero code while the app is not quitting, the shell shows the captured error to the user (`frontend/main.js` lines 115 to 130).

In the container image none of this applies: gunicorn runs the Flask app directly and Flask serves the frontend build. See [Deployment and release](../operations/deployment-and-release.md).

## Related pages

- [Data model and migrations](data-model-and-migrations.md)
- [Frontend structure](../frontend/spa-structure.md)
- [Deployment and release](../operations/deployment-and-release.md)
