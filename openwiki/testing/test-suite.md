---
type: testing
title: Test suite
description: How the backend tests are organised, how they avoid touching a real TV or the working tree, what each group protects, and how to run them locally and in CI.
tags: [testing, pytest, backend, fixtures, ci]
sources:
  - id: openwiki-source-070c6307b3860e1806baf566
    resource: repo://backend/pyproject.toml
  - id: openwiki-source-539ff1e55b1e385204a4bb93
    resource: repo://backend/tests/conftest.py
  - id: openwiki-source-31da078a7907297ef877dbe6
    resource: repo://backend/tests/test_frame_tv_timeouts.py
  - id: openwiki-source-64ed2c6018b0eae34dd77457
    resource: repo://backend/tests/test_migrations.py
  - id: openwiki-source-d281b6895c2bb7d8c2cf09ed
    resource: repo://backend/tests/test_provider_settings.py
  - id: openwiki-source-40a9426dfd988cde0852abee
    resource: repo://backend/tests/test_reframed_import.py
  - id: openwiki-source-409ba6a0a4bc479b5339335a
    resource: repo://backend/tests/test_tv_diagnostics.py
generated: { by: "claude-code", at: "2026-10-28T14:34:25.443Z" }
verified:
  - by: openwiki/0.7.2
    at: 2026-10-28T14:34:25.443Z
---

# Test suite

The tests are pytest tests for the backend only, in `backend/tests/`. There is no frontend test runner; the frontend is checked by its typecheck and build (see [Frontend structure](../frontend/spa-structure.md)). The directory holds 19 test files with 150 test functions, and pytest reports more than that because some tests are parametrised.

## Running them

From `backend/`, install the package with its test extra and run pytest:

```
pip install -e ".[test]"
pytest -q
```

The `test` extra contains pytest and nothing else (`backend/pyproject.toml` line 35). CI runs exactly this on Python 3.13, so a local pass is what CI will check (see [Deployment and release](../operations/deployment-and-release.md)).

Each file carries a docstring that names the command to run just that file, for example `pytest tests/test_frame_tv_timeouts.py`.

## No real TV, no writes to the working tree

Two mechanisms keep the suite safe to run anywhere.

`conftest.py` points `FRAME_TV_DATA` at a folder under the system temp directory before anything is imported. It has to run first because both `app` and the TV modules read that variable at import time, and without it the tests would write uploads, the database and thumbnails into the repository (`backend/tests/conftest.py` lines 5 to 11). It also puts `backend/` on `sys.path` so the tests can import `app` and `utils` directly.

The tests are written so that nothing reaches a real network address. TV behaviour is replaced with fakes and monkeypatching: a fake art channel, a fake websocket module and socket, and patched HTTP calls. TV addresses in the tests come from the `192.0.2.x` documentation range, which is reserved and never routable. The two other literal addresses that appear, `10.0.0.13` and `169.254.169.254`, are inputs the Reframed import must refuse, and the tests patch the HTTP layer so that a request to them would fail the test.

## The shared `client` fixture

Most API tests define the same fixture in their own file: it turns on Flask's testing mode, drops and recreates every table with `create_all`, and returns a test client. Each test therefore starts from an empty database. Some also clear the uploads folder. Because the fixture is repeated rather than shared, a change to how the app creates its schema means editing several files.

The consequence to know about is that these fixtures never run alembic. That gap is the reason for the migrations tests below.

## What each group protects

| Group | Files | What breaks if it fails |
| --- | --- | --- |
| Call deadlines and failure handling | `test_frame_tv_timeouts.py` | A stuck TV blocks a request forever, a cooldown is not applied or not shared, two calls talk to one TV at once, or a half-open connection is left behind. |
| Thumbnails and gallery cache | `test_tv_thumbnails.py`, `test_thumbnails.py`, `test_tv_content.py` | Thumbnails are misfiled, a TV is asked again for previews it refused, a stalled batch is retried forever, or the listing cache serves stale data. |
| Pairing and tokens | `test_tv_token.py` | A new token the TV hands back is lost so the TV asks to authorise again, or pairing runs without a deadline. |
| Sending and deleting | `test_matte_and_one_slot_mode.py`, `test_tv_delete.py`, `test_frame_tv_delete_fallback.py` | A matte is sent when none was chosen, one-slot mode prunes the wrong images, or deleting from the TV leaves stale records here. |
| Slideshow | `test_slideshow.py` | A TV is rotated too early, while in use, or with a half-configured slideshow. |
| Library | `test_album_api.py`, `test_duplicate_uploads.py`, `test_gallery_listing.py`, `test_crop_presets.py`, `test_backup.py`, `test_reframed_import.py` | Albums, duplicate detection, listing and sort, cropping, backup or Reframed import misbehave. |
| Immich provider and settings | `test_provider_settings.py` | The API returns the API key, a partial save erases the stored key, the provider does not follow the saved settings, an unreachable Immich crashes instead of answering 502, the image cache grows without bound, other sites get CORS permission, the old `/tv/<ip>/...` routes come back, or a failed GitHub version check is not cached. |
| Diagnostics and send errors | `test_tv_diagnostics.py` | The TV probe reads the wrong endpoint or opens the art channel, an unreachable TV still triggers an art session, a failure is reported under the wrong `art_error`, or a failed send loses its `code` and readable message. |
| Wake-on-LAN | `test_wake_on_lan.py` | The magic packet is malformed, or a TV with no saved address is not explained. |
| Migrations | `test_migrations.py` | A database is not usable however it was created. |

### The timeout tests

`test_frame_tv_timeouts.py` is the largest file. It exercises the TV call wrapper without a network by passing `open_remote=False`, which skips the remote-control handshake, and by using an action that sleeps in place of a stuck read. A module constant, `STUCK`, sets how long that sleep lasts: long enough to outlive the deadlines under test, short enough that the worker threads are gone before the interpreter shuts down (`backend/tests/test_frame_tv_timeouts.py` lines 1 to 25).

A second autouse fixture stubs `describe_tv_state`, because a timed-out call asks the TV for its state over HTTP on a background thread and no test may reach the network. The real function is saved in `_REAL_DESCRIBE_TV_STATE` for the two tests that exercise the probe, which patch it again with their own stub and wait for the `frametv-state-probe` thread (`backend/tests/test_frame_tv_timeouts.py` lines 29 to 41). The tests capture log output through a handler attached directly to the module's logger rather than through the root logger, so they do not depend on how another test module configured logging.

An autouse fixture deletes the cooldown marker directory before and after every test, so one test's failed TV cannot put the next test's TV into cooldown (`backend/tests/test_frame_tv_timeouts.py` lines 44 to 48). Any new test file that fails a TV call needs the same fixture; the token tests carry their own copy.

One test proves the ordering fix in the timeout branch: it fails if the traffic figure is read after the session is closed.

### The migration tests

`test_migrations.py` runs `flask db upgrade` in a separate process against a throwaway data directory, because that is what the container entrypoint does and the failure it guards against only appears there. It asserts that a fresh install ends at the single head revision, that a fresh install is stamped rather than replayed, that upgrading twice changes nothing, and that an existing database still migrates (`backend/tests/test_migrations.py` lines 1 to 8 and 70 to 100).

It also finds the head by reading the revision files, and fails with a clear message if there is more than one head. That protects against two branches adding a migration at the same time (`backend/tests/test_migrations.py` lines 24 to 37).

`test_running_alembic_leaves_the_app_loggers_alone` guards a fault that only shows on a fresh data directory: alembic's logging setup used to switch off every logger already created, so a first start lost the `utils.*` diagnostics. It is also why a test can pass on a developer machine with an old database and fail on a clean CI runner. When that happens, suspect a fresh-data-directory side effect first (`backend/tests/test_migrations.py` line 126).

### Regression tests for fork fixes

Four more tests each fail without the change they cover. Album deletion with an image already sent to a TV lives in `test_album_api.py`. `test_a_provider_url_is_refused_and_nothing_is_requested` in `test_reframed_import.py` checks that `provider_url` gets a 400 and that no outbound request is made. `test_a_malformed_mac_is_a_clear_400_not_a_server_error` in `test_wake_on_lan.py` covers a bad MAC. The traffic-before-close test is in the timeout file.

## Writing a new test

- Put the docstring first and say what behaviour the file protects, and how to run it.
- Use the `192.0.2.x` range for any TV address.
- Patch `requests.get`, the websocket layer or the TV functions rather than reaching out.
- If the test touches the database, use the `client` fixture pattern so it starts empty. If it depends on alembic behaviour, follow `test_migrations.py` and use a subprocess.
- If the test fails a TV call, clear the cooldown directory around it.

## Related pages

- [TV connection layer](../tv/connection-and-session.md)
- [Local image library](../workflows/image-library.md)
