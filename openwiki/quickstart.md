---
type: guide
title: Quickstart and task map
description: What the project is, how to run and change it locally, the handful of facts that explain most of its design, and which wiki page to read for each kind of task.
tags: [quickstart, overview, onboarding, task-map]
verified:
  - by: openwiki/0.5.1
    at: 2026-09-21T02:31:07.302Z
sources:
  - id: openwiki-source-7872be2c059c5659d94804ea
    resource: repo://backend/app.py
  - id: openwiki-source-f317ee207e1653d2033c81a4
    resource: repo://CONTRIBUTING.md
  - id: openwiki-source-1047363cf615000e4c9bb694
    resource: repo://frontend/package.json
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
generated: { by: "claude-code", at: "2026-10-27T18:55:06.371Z" }
---

# Quickstart and task map

This wiki describes a self-hosted gallery manager for Samsung Frame TVs. You keep a library of images and send them to one or more TVs, where they show as art. It is a Flask backend, a React single-page frontend, and an optional Electron desktop shell (`README.md` line 21).

## The five facts that explain most of it

1. **A Frame TV serves one art channel at a time.** Almost every design decision in the TV code comes from this. A slow or long request holds the channel, and everything else aimed at that TV waits and then fails.
2. **The library is the uploads folder.** The folder is the source of truth for which images exist, and the database only adds an album, an added time and a hash to each one.
3. **Every TV call is bounded from outside.** The underlying library can wait forever on a read, so each call runs on a worker thread with a deadline, a per-TV lock and a cooldown after a failure.
4. **There is no authentication.** The API is open to anyone who can reach the port, and CORS allows any origin. It is meant for a private network.
5. **The container uses the host network by default.** Wake-on-LAN needs it, and so does automatic discovery in practice, because on Docker's bridge the scan covers Docker's subnet instead of the LAN.

## Layout

| Path | What is in it |
| --- | --- |
| `backend/app.py` | The Flask app: every route, database start-up, and the slideshow start. |
| `backend/models.py`, `backend/migrations/` | The SQLite schema and the alembic history. |
| `backend/utils/tv_connection.py` | How a TV call is made safely. |
| `backend/utils/frame_tv.py` | What to ask a TV: gallery, thumbnails, upload, delete, art mode, wake. |
| `backend/utils/` (the rest) | Slideshow, cropping, downscaled copies, discovery, Immich and Reframed import. |
| `backend/tests/` | The pytest suite. |
| `frontend/app/` | The React app: routes, components and the API client modules. |
| `frontend/main.js` | The Electron main process. |
| `.github/workflows/` | CI, the release flow, the image build and the desktop build. |

## Running it locally

**Backend.** From `backend/`, install with `pip install -e ".[test]"` and run `python app.py`. It listens on port 5000, or whatever `BACKEND_PORT` says, on all interfaces (`backend/app.py` lines 87 and 1502). Set `FRAME_TV_DATA` to choose where the data goes.

**Frontend.** From `frontend/`, run `pnpm install` and then `pnpm run dev`, which starts the Vite dev server (`frontend/package.json` line 11, and `CONTRIBUTING.md` lines 13 to 16). Because the dev server is a different origin from the backend, point it at the backend with the `VITE_API_URL` variable. Without it the pages call their own origin.

<!-- openwiki: broken internal link [/openwiki/testing/test-suite.md] link "/openwiki/testing/test-suite.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
**Tests.** From `backend/`, run `pytest -q`. See [Test suite](/openwiki/testing/test-suite.md).

<!-- openwiki: broken internal link [/openwiki/operations/deployment-and-release.md] link "/openwiki/operations/deployment-and-release.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
**The container.** Build from the repository root, not from `backend/`. See [Deployment and release](/openwiki/operations/deployment-and-release.md).

The project asks for Conventional Commit messages and `feature/` or `fix/` branch prefixes (`CONTRIBUTING.md` lines 33 to 35).

## Which page to read

| If you want to... | Read |
| --- | --- |
<!-- openwiki: broken internal link [/openwiki/architecture/overview.md] link "/openwiki/architecture/overview.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
| Understand how the parts fit together | [System architecture](/openwiki/architecture/overview.md) |
<!-- openwiki: broken internal link [/openwiki/architecture/data-model-and-migrations.md] link "/openwiki/architecture/data-model-and-migrations.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
| Change the schema or add a migration | [Data model and migrations](/openwiki/architecture/data-model-and-migrations.md) |
<!-- openwiki: broken internal link [/openwiki/frontend/spa-structure.md] link "/openwiki/frontend/spa-structure.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
| Work on a page, component or API client | [Frontend structure](/openwiki/frontend/spa-structure.md) |
<!-- openwiki: broken internal link [/openwiki/tv/connection-and-session.md] link "/openwiki/tv/connection-and-session.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
| Understand why a TV call timed out, or change a timeout | [TV connection layer](/openwiki/tv/connection-and-session.md) |
<!-- openwiki: broken internal link [/openwiki/tv/gallery-and-thumbnails.md] link "/openwiki/tv/gallery-and-thumbnails.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
| Fix or change how a TV's images and thumbnails load | [TV gallery and thumbnails](/openwiki/tv/gallery-and-thumbnails.md) |
<!-- openwiki: broken internal link [/openwiki/tv/uploading-and-display.md] link "/openwiki/tv/uploading-and-display.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
| Change what happens when an image is sent, or a matte, or deletion | [Sending art to a TV](/openwiki/tv/uploading-and-display.md) |
<!-- openwiki: broken internal link [/openwiki/tv/pairing-tokens-and-wake.md] link "/openwiki/tv/pairing-tokens-and-wake.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
| Work on adding a TV, tokens, discovery or Wake-on-LAN | [Pairing, tokens, discovery and wake](/openwiki/tv/pairing-tokens-and-wake.md) |
<!-- openwiki: broken internal link [/openwiki/workflows/slideshow.md] link "/openwiki/workflows/slideshow.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
| Work on the rotation timer | [Slideshow rotation](/openwiki/workflows/slideshow.md) |
<!-- openwiki: broken internal link [/openwiki/workflows/image-library.md] link "/openwiki/workflows/image-library.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
| Change uploads, albums, cropping, backup or the importers | [Local image library](/openwiki/workflows/image-library.md) |
<!-- openwiki: broken internal link [/openwiki/operations/diagnostics-and-failure-modes.md] link "/openwiki/operations/diagnostics-and-failure-modes.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
| Read a failure log, or turn logging up | [Diagnostics and failure modes](/openwiki/operations/diagnostics-and-failure-modes.md) |
<!-- openwiki: broken internal link [/openwiki/operations/deployment-and-release.md] link "/openwiki/operations/deployment-and-release.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
| Ship a change, or understand the image and release flow | [Deployment and release](/openwiki/operations/deployment-and-release.md) |
<!-- openwiki: broken internal link [/openwiki/testing/test-suite.md] link "/openwiki/testing/test-suite.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
| Add or run tests | [Test suite](/openwiki/testing/test-suite.md) |

## When something is wrong with a TV

<!-- openwiki: broken internal link [/openwiki/operations/diagnostics-and-failure-modes.md] link "/openwiki/operations/diagnostics-and-failure-modes.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
Start with [Diagnostics and failure modes](/openwiki/operations/diagnostics-and-failure-modes.md). Set `FRAME_TV_LOG_LEVEL=INFO`, reproduce the problem once, and read the last INFO line and the timeout warning. Then look at the TV itself: a Frame TV can wedge its art channel in a way software cannot clear, and switching it off at the wall is the known way out.

## Known gaps worth knowing before you change things

These are described in detail on the pages linked and are listed here so they are not a surprise:

<!-- openwiki: broken internal link [/openwiki/workflows/image-library.md] link "/openwiki/workflows/image-library.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- Deleting an album whose image was sent to a TV fails ([Local image library](/openwiki/workflows/image-library.md)).
<!-- openwiki: broken internal link [/openwiki/workflows/image-library.md] link "/openwiki/workflows/image-library.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- The deprecated `provider_url` field sends the Immich API key to any address it is given ([Local image library](/openwiki/workflows/image-library.md)).
<!-- openwiki: broken internal link [/openwiki/tv/pairing-tokens-and-wake.md] link "/openwiki/tv/pairing-tokens-and-wake.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- A malformed MAC in a wake request is not handled by the endpoint ([Pairing, tokens, discovery and wake](/openwiki/tv/pairing-tokens-and-wake.md)).
<!-- openwiki: broken internal link [/openwiki/operations/diagnostics-and-failure-modes.md] link "/openwiki/operations/diagnostics-and-failure-modes.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- The traffic figure in the timeout log line is unreliable after a timeout ([Diagnostics and failure modes](/openwiki/operations/diagnostics-and-failure-modes.md)).
