---
type: architecture
title: Data model and migrations
description: The SQLite schema behind the gallery, how a fresh database is created and stamped, how alembic migrations run at container start, and what happens when an older image meets a newer database.
tags: [database, sqlite, alembic, migrations, models, deployment]
verified:
  - by: openwiki/0.7.2
    at: 2026-10-28T14:34:25.443Z
sources:
  - id: openwiki-source-7872be2c059c5659d94804ea
    resource: repo://backend/app.py
  - id: openwiki-source-ef4ce636329fef9dc0ef0aa3
    resource: repo://backend/entrypoint.sh
  - id: openwiki-source-dfa1ba520fe6fcf5cf433623
    resource: repo://backend/migrations/env.py
  - id: openwiki-source-750309369407abbad10cdb1d
    resource: repo://backend/migrations/versions/ce4757b9dde8_add_app_settings_table_for_github_cache.py
  - id: openwiki-source-7ecdfb277fd674b9f54b82fb
    resource: repo://backend/migrations/versions/d3f1a7c25b90_add_image_content_hash.py
  - id: openwiki-source-33cbfc7e7a71efa3be86a374
    resource: repo://backend/models.py
  - id: openwiki-source-64ed2c6018b0eae34dd77457
    resource: repo://backend/tests/test_migrations.py
generated: { by: "claude-code", at: "2026-10-28T14:34:25.443Z" }
---

# Data model and migrations

The app keeps all of its state in one SQLite file, `instance/frametv.db` under the data directory. Six SQLAlchemy models describe it, and a linear chain of alembic revisions evolves it.

## The models

All models live in `backend/models.py`.

| Model | Holds |
| --- | --- |
| `Album` | A named group of images. |
| `Image` | One uploaded file, by filename, with an optional album and a content hash. |
| `TV` | One Frame TV: address, name, MAC, pairing token, and per-TV behaviour switches. |
| `UploadedImage` | The record that an `Image` was sent to a `TV`, with the content id the TV assigned. |
| `ProviderConfig` | Connection settings for an external photo source such as Immich. |
| `AppSetting` | Key/value rows, used to cache the latest-release lookup. |

An album owns its images. Deleting an `Album` deletes its `Image` rows because the relationship cascades with delete-orphan, and `Image.album_id` is nullable so an image can also live outside any album (`backend/models.py` lines 15 to 23).

`Image.sha256` is a nullable, indexed content hash. It exists to spot the same artwork uploaded twice under different names, and it stays null for rows that predate the column until they are touched again (`backend/models.py` lines 25 to 27).

A `TV` row carries behaviour that belongs to one set rather than to the app:

- `delete_other_images_on_upload` and `one_slot_mode` control what happens to other art when something is sent.
- `default_matte` is the matte applied when an upload does not choose one. Null means the app default, which is also "none".
- The slideshow lives entirely on the row: enabled flag, album, interval in minutes, last run time and last content id (`backend/models.py` lines 35 to 49).

`UploadedImage` links an image to a TV. Its `tv_id` foreign key has `ondelete='CASCADE'`, and the relationship on `TV` also cascades, so removing a TV removes its upload history at both the ORM and the database level (`backend/models.py` lines 51 to 62).

The link to `Image` cascades too. The `image` relationship declares its backref with `cascade='all, delete-orphan'`, so deleting an `Image` deletes the `UploadedImage` rows that point at it. Without that, SQLAlchemy tried to null the non-nullable `image_id` and the delete failed with an `IntegrityError`, which is what broke deleting an album that held an image already sent to a TV. Deleting an album now reaches its images and, through them, their upload records (`backend/models.py` lines 58 to 70).

`ProviderConfig.as_dict()` never returns the API key. It exposes `has_api_key`, a boolean that only says whether a key is stored. The key is write-only: the app has no login, so sending it back would hand it to anyone who can reach the API (`backend/models.py` lines 69 to 88).

## How a database comes into being

`init_db()` in `backend/app.py` runs when the module is imported, not on demand. It always calls `db.create_all()`, which builds any missing tables straight from the models. It then checks whether the database file existed before that call:

- A fresh file is stamped at alembic `head`, so alembic believes the schema is already current.
- An existing file is left alone and migrates normally.

The stamp matters because `create_all` produces a complete schema without ever touching `alembic_version`. Without the stamp a brand new database would replay every migration from the beginning over tables that are already finished (`backend/app.py` lines 141 to 155).

Because the call is at import time, every gunicorn worker runs it, which is why the startup log shows "Initializing database" once per worker.

## How migrations run

The container entrypoint runs `flask db upgrade` before starting the server, and refuses to continue if it fails. On failure it prints an explanation and exits with status 1, so the container does not serve traffic against a schema it could not bring up to date (`backend/entrypoint.sh` lines 4 to 31). When it succeeds it `exec`s the container command, which is gunicorn.

The revisions form one straight line with no branches:

`929a60c602a1` → `a16beaf2617d` → `500fac4679d4` → `601a7cee3cbb` → `b7c3d1e9f204` → `d3f1a7c25b90` → `e7a2c4f19b3d` → `f2a4d1c9e8b7` → `ce4757b9dde8`

The newest, `ce4757b9dde8`, adds the `app_settings` table and follows `f2a4d1c9e8b7` (`backend/migrations/versions/ce4757b9dde8_add_app_settings_table_for_github_cache.py` line 14).

`backend/migrations/env.py` takes its database engine from the running Flask app's `migrate` extension, so a migration always targets the same file the app uses (`backend/migrations/env.py` lines 22 to 28). Eight of the revision files use `batch_alter_table`, which is how alembic alters SQLite tables that cannot be changed in place.

### env.py must not silence the app's loggers

`env.py` configures Python logging from the alembic ini file, and it passes `disable_existing_loggers=False` to `fileConfig` (`backend/migrations/env.py` lines 12 to 18). The default is `True`, which switches off every logger already created, and that includes the whole `utils.*` tree that carries the TV diagnostics.

This matters because `init_db()` stamps a fresh database at import time. The stamp runs `env.py` inside the server process, so on a first start with a new data directory the default would have muted every `utils.*` log line until the next restart. An existing database skips the stamp, which is why the fault never showed on a developer machine with old data. `test_running_alembic_leaves_the_app_loggers_alone` in `backend/tests/test_migrations.py` guards it.

### Migrations are written to tolerate `create_all`

Since `create_all` can add a column before the migration that introduces it runs, at least one migration checks before acting. The content-hash revision adds `sha256` only if the column is missing, and creates its index only if the index is missing. It creates the index outside the batch block on purpose: creating an index inside a batch makes alembic rebuild the table, and that rebuild trips over the column `create_all` already added (`backend/migrations/versions/d3f1a7c25b90_add_image_content_hash.py` lines 27 to 43).

When you add a migration that adds a column or index, follow the same pattern: inspect first, then act.

## Frozen and desktop builds

When the app runs frozen (the PyInstaller desktop bundle), the migrations directory is resolved from `sys._MEIPASS` instead of next to the source. The `--upgrade-db` command line flag runs the upgrade inside an app context and then starts the server, which is how the desktop build migrates without the container entrypoint (`backend/app.py` lines 80 to 83 and 1491 to 1496).

## Going back to an older image

Going back to an older image does not roll the schema back. The database records a revision the older image has never heard of, `flask db upgrade` fails with "Can't locate revision identified by ...", and the entrypoint stops with its explanation (`backend/entrypoint.sh` lines 12 to 27).

There are two ways out:

1. Run the newer image again. Nothing was lost.
2. Stay on the older image and set `alembic_version.version_num` by hand to the newest revision that image knows, which `flask db history` lists. Columns the newer version added stay behind, unused.

## Related pages

- [System architecture](overview.md)
- [Deployment and release](../operations/deployment-and-release.md)
