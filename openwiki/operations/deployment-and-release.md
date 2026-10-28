---
type: operations
title: Deployment and release
description: How the Docker image is built and run, what the entrypoint and gunicorn settings do, which environment variables matter, and how a merge to main turns into a published release, a container image and desktop builds.
tags: [docker, gunicorn, release-please, ci, electron, deployment]
sources:
  - id: openwiki-source-3fe14ba9156cad65ad4a9425
    resource: repo://.github/workflows/build_desktop_app.yaml
  - id: openwiki-source-da115a4df5fbdc71468c5265
    resource: repo://.github/workflows/build_image.yaml
  - id: openwiki-source-e560413277439079b0684419
    resource: repo://.github/workflows/ci.yaml
  - id: openwiki-source-f8b7b48444f96e08372841e6
    resource: repo://.github/workflows/release.yaml
  - id: openwiki-source-3641e44aef067384d4965781
    resource: repo://backend/docker-compose.yml
  - id: openwiki-source-600e7dce49b27b22f5486b40
    resource: repo://backend/Dockerfile
  - id: openwiki-source-3a0919f050c14e57b5495c9e
    resource: repo://backend/flask_backend.spec
  - id: openwiki-source-1047363cf615000e4c9bb694
    resource: repo://frontend/package.json
generated: { by: "claude-code", at: "2026-10-28T14:34:25.443Z" }
verified:
  - by: openwiki/0.7.2
    at: 2026-10-28T14:34:25.443Z
---

# Deployment and release

There are two ways to run the app: as a container image, which is the main path, and as an Electron desktop application. Both are produced by GitHub Actions when a release is cut.

## The container image

`backend/Dockerfile` is a two-stage build, and it must be built from the repository root rather than from `backend/`. The app serves the frontend build from one level above itself, and `pyproject.toml` reads the `README.md` that sits at the root, so neither is reachable from a build context narrowed to `backend/` (`backend/Dockerfile` lines 1 to 3).

- The builder stage installs the backend package into a private prefix (`backend/Dockerfile` lines 6 to 20).
- The runtime stage copies that prefix, the `backend/` code, and the prebuilt `frontend/build` directory to `/frontend/build`, which is where `app.py` expects it (`backend/Dockerfile` lines 24 to 35).

The frontend is therefore built before the image is, by the workflow, not inside the Dockerfile. An image built without `frontend/build` present would fail at the copy step.

The image sets `PORT=8000`, exposes it, and records its version in `FRAME_TV_VERSION` from the `APP_VERSION` build argument, which is what the update check compares against (`backend/Dockerfile` lines 39 to 45).

### Start-up sequence

The entrypoint runs first and applies database migrations. If they fail it refuses to start, printing why (`backend/Dockerfile` line 51 and `backend/entrypoint.sh`). See [Data model and migrations](../architecture/data-model-and-migrations.md). It then runs gunicorn:

```
gunicorn app:app --bind 0.0.0.0:${PORT:-8000} --workers ${GUNICORN_WORKERS:-4} --timeout ${GUNICORN_TIMEOUT:-180}
```

Two choices in that line are deliberate. Several workers, four by default, mean that one TV that stops answering cannot freeze the whole app. The timeout of 180 seconds sits above `FRAME_TV_UPLOAD_DEADLINE`, so a legitimately slow upload is not killed by gunicorn first. Keep that ordering if you change either value (`backend/Dockerfile` lines 53 to 56).

Because there are several worker processes, anything that must happen once per app, such as the slideshow loop, has to be coordinated across processes. See [Slideshow rotation](../workflows/slideshow.md).

## The compose file

`backend/docker-compose.yml` runs the published image with one named volume mounted at `/data` and `FRAME_TV_DATA=/data`, so uploads, the database and caches survive an image update (`backend/docker-compose.yml` lines 6 to 7 and 21).

It uses the host network by default, for two separate reasons. Wake-on-LAN is a UDP broadcast, and a broadcast never leaves Docker's bridge network. Automatic TV discovery does not broadcast at all: it probes the addresses `.1` to `.254` of the /24 that the container itself uses, over HTTP. On the host network that is your LAN. On the bridge it is Docker's own subnet, so the scan finds nothing. On the bridge you replace `network_mode: host` with a `ports` mapping and add each TV by typing its address; everything else keeps working (`backend/docker-compose.yml` lines 9 to 18). On the host network there is no port mapping to move the app with, so `PORT` is how you avoid a clash (`backend/docker-compose.yml` lines 22 to 24).

The app no longer has a `SECRET_KEY`: the compose file does not set it and `app.py` does not read it, because nothing used it (no sessions or signatures).

CORS is closed by default. To develop the frontend on another port, set `CORS_ORIGINS`, for example `CORS_ORIGINS=http://localhost:5173` (`backend/app.py` lines 101 to 106).

## Environment variables

The full table of tunables, with defaults, is in the README (`README.md` lines 94 to 116). The ones that matter most in operation:

| Variable | Effect |
| --- | --- |
| `FRAME_TV_DATA` | Where uploads, the database and caches live. Mount it to keep them. |
| `PORT` | Listen port; only useful on the host network. |
| `GUNICORN_WORKERS`, `GUNICORN_TIMEOUT` | Process count and worker kill timeout. |
| `FRAME_TV_CALL_DEADLINE`, `FRAME_TV_UPLOAD_DEADLINE`, `FRAME_TV_STALL_TIMEOUT` | How long a TV call may take before it is cut off. |
| `FRAME_TV_LOG_LEVEL` | Set to `INFO` or `DEBUG` to see what a TV is doing. |
| `FRAME_TV_SLIDESHOW` | Set to `0` to stop the slideshow loop. |
| `CORS_ORIGINS` | Comma-separated origins allowed to call the API from a browser. Empty by default. |

The TV timeouts are explained in [TV connection layer](../tv/connection-and-session.md).

## From merge to published image

The release flow is automatic and starts on every push to `main`:

1. `release.yaml` runs release-please with the `simple` release type. On most pushes it only opens or updates a release pull request that carries the next version and changelog (`.github/workflows/release.yaml` lines 17 to 28).
2. Merging that pull request makes release-please create the release and tag. The same workflow then calls the image build, passing the tag (`.github/workflows/release.yaml` lines 30 to 37).
3. `build_image.yaml` builds the frontend, then builds and pushes a multi-architecture image, `linux/amd64` and `linux/arm64`, to GitHub Container Registry with the repository root as build context (`.github/workflows/build_image.yaml` lines 61, 100 to 105).

The build is called explicitly because a release created with the workflow's own token does not raise the `release` event, so `build_image.yaml`'s own release trigger would never fire (`.github/workflows/release.yaml` lines 30 to 31).

### Image tags

A run that has a version publishes `latest`, the version tag and a short commit tag. A manual run that names no version publishes the commit tag only, so it can never claim to be `latest` (`.github/workflows/build_image.yaml` lines 33 and 92 to 94). The version is spelled out from the workflow input or the release tag because the metadata action's release reference is rejected outright when the run was not started by a release event.

You can start the build by hand from the Actions tab and pass a version to publish that tag along with `latest` (`.github/workflows/build_image.yaml` lines 14 to 20).

## Continuous integration

`ci.yaml` runs on pushes to `main` and on pull requests. The backend job installs the package with its test extra on Python 3.13 and runs `pytest -q` from `backend/`. The frontend job installs with pnpm and a frozen lockfile, then runs the typecheck and the build (`.github/workflows/ci.yaml` lines 10 to 61). Both jobs are skipped when the pull request comes from a `release-please--` branch, because that pull request only moves the changelog and version and its commits were already tested on `main`.

## Desktop builds

`build_desktop_app.yaml` runs when a release is published, or by hand. It builds on Windows, Linux and macOS runners: it freezes the backend with PyInstaller, builds the frontend with `VITE_API_URL` pointing at `http://127.0.0.1:5543`, and packages both with `electron-builder` without publishing (`.github/workflows/build_desktop_app.yaml` lines 3 to 17, 71 to 90). A final job attaches the `.exe`, `.dmg`, `.AppImage`, `.deb` and `.zip` files to the release, and only when the run was triggered by a release (`.github/workflows/build_desktop_app.yaml` lines 104 to 127).

The Electron configuration bundles the frozen backend as an extra resource and targets an NSIS installer on Windows, a DMG on macOS and an AppImage on Linux (`frontend/package.json` lines 57 to 84). The backend spec file bundles the `migrations` folder so the desktop build can upgrade its database (`backend/flask_backend.spec` line 9). See [System architecture](../architecture/overview.md) for how the shell starts the backend.

## Related pages

- [System architecture](../architecture/overview.md)
- [Diagnostics and failure modes](diagnostics-and-failure-modes.md)
