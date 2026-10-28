---
type: guide
title: Quickstart and task map
description: What the project is, how to run and change it locally, the handful of facts that explain most of its design, and which wiki page to read for each kind of task.
tags: [quickstart, overview, onboarding, task-map]
sources:
  - id: openwiki-source-7872be2c059c5659d94804ea
    resource: repo://backend/app.py
  - id: openwiki-source-f317ee207e1653d2033c81a4
    resource: repo://CONTRIBUTING.md
  - id: openwiki-source-1047363cf615000e4c9bb694
    resource: repo://frontend/package.json
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
generated: { by: "claude-code", at: "2026-10-28T14:34:25.443Z" }
verified:
  - by: openwiki/0.7.2
    at: 2026-10-28T14:34:25.443Z
---

# Quickstart and task map

This wiki describes a self-hosted gallery manager for Samsung Frame TVs. You keep a library of images and send them to one or more TVs, where they show as art. It is a Flask backend, a React single-page frontend, and an optional Electron desktop shell (`README.md` line 21).

## The five facts that explain most of it

1. **A Frame TV serves one art channel at a time.** Almost every design decision in the TV code comes from this. A slow or long request holds the channel, and everything else aimed at that TV waits and then fails.
2. **The library is the uploads folder.** The folder is the source of truth for which images exist, and the database only adds an album, an added time and a hash to each one.
3. **Every TV call is bounded from outside.** The underlying library can wait forever on a read, so each call runs on a worker thread with a deadline, a per-TV lock and a cooldown after a failure.
4. **There is no authentication.** The API is open to anyone who can reach the port. It is meant for a private network. CORS is closed by default (`CORS_ORIGINS` to develop the frontend on another port), and the Immich API key is write-only.
5. **The container uses the host network by default.** Wake-on-LAN needs it, and so does automatic discovery in practice, because on Docker's bridge the scan covers Docker's subnet instead of the LAN.

## Layout

| Path | What is in it |
| --- | --- |
| `backend/app.py` | The Flask app: every route, database start-up, and the slideshow start. |
| `backend/models.py`, `backend/migrations/` | The SQLite schema and the alembic history. |
| `backend/media_provider_routes.py`, `backend/provider_config_routes.py` | The Immich provider routes and their settings. |
| `backend/utils/tv_connection.py` | How a TV call is made safely. |
| `backend/utils/frame_tv.py` | What to ask a TV: gallery, thumbnails, upload, delete, art mode, wake. |
| `backend/utils/` (the rest) | Slideshow, cropping, downscaled copies, discovery, Immich and Reframed import. |
| `backend/tests/` | The pytest suite. |
| `frontend/app/` | The React app: routes, components and the API client modules. |
| `frontend/main.js` | The Electron main process. |
| `.github/workflows/` | CI, the release flow, the image build and the desktop build. |

## Running it locally

**Backend.** From `backend/`, install with `pip install -e ".[test]"` and run `python app.py`. It listens on port 5000, or whatever `BACKEND_PORT` says, on all interfaces (`backend/app.py` lines 83 and 1484). Set `FRAME_TV_DATA` to choose where the data goes.

**Frontend.** From `frontend/`, run `pnpm install` and then `pnpm run dev`, which starts the Vite dev server (`frontend/package.json` line 11, and `CONTRIBUTING.md` lines 13 to 16). Because the dev server is a different origin from the backend, point it at the backend with the `VITE_API_URL` variable, and allow that origin on the backend with `CORS_ORIGINS=http://localhost:5173`. Without `VITE_API_URL` the pages call their own origin.

**Tests.** From `backend/`, run `pytest -q`. See [Test suite](testing/test-suite.md).

**The container.** Build from the repository root, not from `backend/`. See [Deployment and release](operations/deployment-and-release.md).

The project asks for Conventional Commit messages and `feature/` or `fix/` branch prefixes (`CONTRIBUTING.md` lines 33 to 35).

## Which page to read

| If you want to... | Read |
| --- | --- |
| Understand how the parts fit together | [System architecture](architecture/overview.md) |
| Change the schema or add a migration | [Data model and migrations](architecture/data-model-and-migrations.md) |
| Work on a page, component or API client | [Frontend structure](frontend/spa-structure.md) |
| Understand why a TV call timed out, or change a timeout | [TV connection layer](tv/connection-and-session.md) |
| Fix or change how a TV's images and thumbnails load | [TV gallery and thumbnails](tv/gallery-and-thumbnails.md) |
| Change what happens when an image is sent, or a matte, or deletion | [Sending art to a TV](tv/uploading-and-display.md) |
| Work on adding a TV, tokens, discovery or Wake-on-LAN | [Pairing, tokens, discovery and wake](tv/pairing-tokens-and-wake.md) |
| Work on the rotation timer | [Slideshow rotation](workflows/slideshow.md) |
| Change uploads, albums, cropping, backup or the importers | [Local image library](workflows/image-library.md) |
| Read a failure log, or turn logging up | [Diagnostics and failure modes](operations/diagnostics-and-failure-modes.md) |
| Ship a change, or understand the image and release flow | [Deployment and release](operations/deployment-and-release.md) |
| Add or run tests | [Test suite](testing/test-suite.md) |

## When something is wrong with a TV

Start with [Diagnostics and failure modes](operations/diagnostics-and-failure-modes.md). Set `FRAME_TV_LOG_LEVEL=INFO`, reproduce the problem once, and read the last INFO line and the timeout warning. Then look at the TV itself: a Frame TV can wedge its art channel in a way software cannot clear, and switching it off at the wall is the known way out. The Test connection button on the Settings page and the light in the header give a first diagnosis without reading logs.

## Points to know before you change things

The known defects that used to be listed here have been fixed: deleting an album whose image was sent to a TV works, `provider_url` is refused, a malformed MAC gives a clear 400, and the traffic figure in the timeout log line is reliable (see [Local image library](workflows/image-library.md), [Pairing, tokens, discovery and wake](tv/pairing-tokens-and-wake.md) and [Diagnostics and failure modes](operations/diagnostics-and-failure-modes.md)).

What remains: the API still has no login, a frontend served on another port needs `CORS_ORIGINS`, and a third-party TV client, such as a phone app, can take the art channel away from the app.
