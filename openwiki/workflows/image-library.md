---
type: workflow
title: Local image library
description: How images are stored and tracked — upload, content hashing and duplicate detection, listing and search, downscaled copies, albums, cropping, deleting, reconcile, backup — and how images are imported from Immich and Reframed Gallery.
tags: [images, uploads, albums, duplicates, crop, backup, immich, reframed, workflow]
sources:
  - id: openwiki-source-7872be2c059c5659d94804ea
    resource: repo://backend/app.py
  - id: openwiki-source-e4a635ea27709b0335115c6f
    resource: repo://backend/media_provider_routes.py
  - id: openwiki-source-33cbfc7e7a71efa3be86a374
    resource: repo://backend/models.py
  - id: openwiki-source-532c076376dca909f588a9db
    resource: repo://backend/utils/crop_image.py
  - id: openwiki-source-6f692cd6120b32764242a4be
    resource: repo://backend/utils/immich_provider.py
  - id: openwiki-source-9d921f777fdc2cd3b015a600
    resource: repo://backend/utils/reframed_gallery.py
  - id: openwiki-source-0301c2d7fdc4636928505978
    resource: repo://backend/utils/thumbnails.py
generated: { by: "claude-code", at: "2026-10-27T18:55:06.371Z" }
verified:
  - by: openwiki/0.5.1
    at: 2026-09-21T12:08:00.549Z
---

# Local image library

The library is the set of images the app can send to TVs. Its central design choice is that the uploads folder is the source of truth for which images exist, and the database only adds information about them.

## Files first, rows second

<!-- openwiki: broken internal link [/openwiki/architecture/data-model-and-migrations.md] link "/openwiki/architecture/data-model-and-migrations.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
The folder `uploads/` under the data directory holds the image files. The database holds an `Image` row per file with its album, the time it was added and a content hash (see [Data model and migrations](/openwiki/architecture/data-model-and-migrations.md)).

The listing endpoint reflects that. It reads the folder, not the table, so a file dropped into the folder by hand appears immediately, with or without a row. For each file it uses the row's added time when there is one and the file's modification time otherwise (`backend/app.py` lines 398 to 437).

The consequence is that the two can drift apart, and `reconcile` exists to bring them back in line.

## Uploading

<!-- openwiki: broken internal link [/openwiki/tv/uploading-and-display.md] link "/openwiki/tv/uploading-and-display.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
`POST /api/upload` accepts one file and an optional album. The file must have an allowed extension: `png`, `jpg` or `jpeg`. The filename goes through the same safe-name checks used everywhere else (see [Sending art to a TV](/openwiki/tv/uploading-and-display.md)), and an unknown album id is a 404 (`backend/app.py` lines 732 to 788).

After saving, the app hashes the file with SHA-256, reading it in one megabyte chunks, and finds or creates its row. Uploading a file with the same name overwrites the file, so the existing row is reused rather than leaving a second row that points at the same image (`backend/app.py` lines 264 to 274 and 762 to 766).

### Duplicate detection

If another row has the same hash under a different name, and that file still exists, the response includes `duplicate_of` naming it. The upload still succeeds. Silently discarding a file the person asked for would be worse than keeping a copy, so the app saves it and tells the caller, which can then say so (`backend/app.py` lines 768 to 783).

## Listing, searching and sorting

`GET /api/images` returns filenames, newest first. Two query parameters change that: `q` keeps only names containing the text, case-insensitively, and `sort` selects `oldest` or `name`. Any other sort value falls back to newest first. The response is a plain list of filenames (`backend/app.py` lines 398 to 437).

## Serving images and downscaled copies

`GET /uploads/<filename>` serves the original file. With `?w=` it can serve a smaller copy instead, so the gallery grid does not download a multi-megabyte original to draw a tile a couple of hundred pixels wide (`backend/app.py` lines 879 to 900).

Only three widths are generated: 160, 400 and 800 pixels. Any other value is ignored and the original is served, so a crafted query string cannot fill the disk with one cache entry per pixel width (`backend/utils/thumbnails.py` lines 23 to 36).

A copy is made the first time it is asked for, as a JPEG at quality 82, and stored under `instance/thumbnails/<width>/`. It is rebuilt whenever the original is newer, because cropping and re-uploading both rewrite the original in place. It is written beside its final name first and then moved into place, so a reader never finds a half-written file. Every failure, including a missing Pillow library, an unreadable image, or an image already narrower than the width, falls back to serving the original, so this feature can only make things faster, never break them (`backend/utils/thumbnails.py` lines 1 to 81).

Everything under `instance/thumbnails/` can be deleted safely; it is rebuilt on demand.

## Albums

An album is a named group. Endpoints create, list, fetch and delete albums, add one or several images to an album by name, and remove an image from an album (`backend/app.py` lines 638 to 731).

Adding an image to an album updates its row, and creates a row if the filename had none. It does not check that the file exists.

Deleting an album deletes the rows of the images in it, because the relationship cascades. It does not delete the files. The images stay in the folder and in the listing, and lose their album and their recorded added time until reconcile recreates the rows.

The album delete also reaches the records of images sent to a TV. `UploadedImage.image` declares its backref with `cascade='all, delete-orphan'`, so when the cascade deletes an image row, the upload records that point at it go too. Before that was added, SQLAlchemy tried to clear the not-null `image_id` of those records and the delete failed with an integrity error, so an album holding an image already sent to a TV could not be deleted. The album handler itself stays a plain `db.session.delete(album)`; the image delete endpoint still removes the upload records by hand, which is now redundant but harmless (`backend/models.py` lines 58 to 70 and `backend/app.py` lines 560 to 583 and 721 to 728).

## Deleting an image

<!-- openwiki: broken internal link [/openwiki/tv/uploading-and-display.md] link "/openwiki/tv/uploading-and-display.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
`DELETE /api/images/<filename>` removes the file, the records that it was sent to any TV, and its row. A failure to remove the file is logged and does not stop the rest (`backend/app.py` lines 560 to 583). It does not remove the image from a TV; that is a separate action (see [Sending art to a TV](/openwiki/tv/uploading-and-display.md)).

## Cropping

`POST /api/images/<filename>/crop` crops an image, and it does so in place: the original file is overwritten, so the crop cannot be undone from the app. It takes either explicit `x`, `y`, `width` and `height`, or a `preset` name, in which case a centred crop box of that shape is computed from the image's own size (`backend/app.py` lines 584 to 626 and `backend/utils/crop_image.py` lines 31 to 76).

The presets, listed by `GET /api/crop-presets`, run from small 4:3 sizes up to 1920 by 1080 and 3840 by 2160. The last is labelled as the Frame TV size, since a Frame TV reports an ultra-high-definition panel and an image of that size fills it without the set having to rescale (`backend/utils/crop_image.py` lines 18 to 28).

## Reconcile

`POST /api/images/reconcile` realigns the database with the folder, and it is safe to run at any time. It does three things and reports the counts:

- Adds a row, with its hash, for every allowed file in the folder that has none.
- Removes the row, and the records of it being sent to TVs, for every row whose file is gone.
- Fills in the hash on rows that predate the hash column.

Album membership is never touched. Afterwards it groups rows by hash and returns the groups of two or more filenames as `duplicate_groups`, so the whole library's duplicates can be reviewed in one place (`backend/app.py` lines 501 to 549). The Settings page has a button for it.

## Backup

`GET /api/backup` returns a zip of the database and every file in `uploads/`. The database is copied through SQLite's own backup interface, so the archive holds a consistent snapshot even while the app is in use. The zip is built in a temporary directory that is deleted when the download finishes: a file wrapper removes the directory when the server closes the file, because deleting earlier would fail while the archive is still open, and Windows in particular refuses to delete an open file (`backend/app.py` lines 438 to 499).

The thumbnail caches are not included, since they can be rebuilt. This is the file to take before updating, as the README advises.

## Importing from other sources

### Immich

If an Immich server is configured in Settings and enabled, the app loads an Immich provider at start-up from the stored provider settings (`backend/app.py` lines 292 to 309, and `backend/models.py` lines 69 to 86). Its routes, under `/api/provider/`, list albums, list an album's images, stream an image at a chosen size, and read metadata. Each returns 404 with a message when no provider is configured. Streamed images are kept in a simple in-memory cache for the life of the process (`backend/media_provider_routes.py` lines 11 to 63).

<!-- openwiki: broken internal link [/openwiki/tv/uploading-and-display.md] link "/openwiki/tv/uploading-and-display.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
A provider image is normally imported by sending it straight to a TV: the send request names the image by `provider_id`, and the file is downloaded into the folder on the way (see [Sending art to a TV](/openwiki/tv/uploading-and-display.md)).

### `provider_url` is refused

<!-- openwiki: broken internal link [/openwiki/architecture/overview.md] link "/openwiki/architecture/overview.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
The send endpoint no longer accepts a `provider_url`. A request that carries one gets a 400 telling the caller to send `provider_id` instead (`backend/app.py` lines 1054 to 1058). The field used to make the provider download that URL with the Immich API key attached as a request header, whatever host it named, so any client that could reach the API could make the server request an arbitrary address and send the key along. The app has no authentication (see [System architecture](/openwiki/architecture/overview.md)), so the download method was deleted from the Immich provider rather than left behind a check.

### Reframed Gallery

`POST /api/import/reframed` takes the address of an artwork page on Reframed Gallery, plus an optional album, and adds the artwork to the library. It reads the page only to find the full-size file on Reframed's own CDN, downloads it into the folder, then records it exactly as an upload would, including its hash and duplicate check (`backend/app.py` lines 789 to 846).

Two restrictions apply because the address is typed in by hand and the app has no login. The page is only fetched when its host is `reframed.gallery` or one of its subdomains and its scheme is http or https, so the server cannot be pointed at its own network. The download is limited to `MAX_UPLOAD_SIZE_BYTES`, the same ceiling as an upload, and a download that fails or exceeds it removes its partial file rather than leaving a broken image in the library (`backend/utils/reframed_gallery.py`).

## Related pages

<!-- openwiki: broken internal link [/openwiki/architecture/data-model-and-migrations.md] link "/openwiki/architecture/data-model-and-migrations.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [Data model and migrations](/openwiki/architecture/data-model-and-migrations.md)
<!-- openwiki: broken internal link [/openwiki/frontend/spa-structure.md] link "/openwiki/frontend/spa-structure.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [Frontend structure](/openwiki/frontend/spa-structure.md)
<!-- openwiki: broken internal link [/openwiki/tv/uploading-and-display.md] link "/openwiki/tv/uploading-and-display.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [Sending art to a TV](/openwiki/tv/uploading-and-display.md)
