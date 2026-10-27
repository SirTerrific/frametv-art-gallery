---
type: workflow
title: TV gallery and thumbnails
description: How the list of images on a Frame TV is fetched and briefly cached, how thumbnails are collected in batches and cached in memory and on disk, when a TV is written off or an image is remembered as having no preview, and how the frontend paces the requests.
tags: [tv, gallery, thumbnails, caching, batching, art-channel]
verified:
  - by: openwiki/0.5.1
    at: 2026-09-21T02:31:07.302Z
sources:
  - id: openwiki-source-7872be2c059c5659d94804ea
    resource: repo://backend/app.py
  - id: openwiki-source-ba30ebcb023436412b51c6d9
    resource: repo://backend/utils/frame_tv.py
  - id: openwiki-source-912a1ff2967d1aceca07a022
    resource: repo://frontend/app/routes/tvGallery.tsx
generated: { by: "claude-code", at: "2026-10-27T18:55:06.371Z" }
---

# TV gallery and thumbnails

The TV gallery page shows what is stored on a Frame TV. Two things have to be fetched from the set: the list of images, which is small and quick, and a thumbnail for each, which is large and slow. The design keeps the list fast, fetches thumbnails in small batches, and remembers as much as it can so a reload does not go back to the TV.

<!-- openwiki: broken internal link [/openwiki/tv/connection-and-session.md] link "/openwiki/tv/connection-and-session.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
The single fact behind the design is that a Frame TV serves one art channel at a time. Anything that holds the channel for a long time makes every other request to that TV wait and then fail (see [TV connection layer](/openwiki/tv/connection-and-session.md)).

## The page flow

`frontend/app/routes/tvGallery.tsx` does this when a TV is selected (`frontend/app/routes/tvGallery.tsx` lines 59 to 95):

1. Ask the backend for the list of images and show it immediately.
2. Work out which images have no thumbnail yet.
3. Request thumbnails in slices of `THUMBNAIL_BATCH` (8), one slice after another, and merge each answer into the page as it lands so the rows fill in.

The slices are sequential on purpose. Sending them in parallel would have them fight over the one channel, and the set would answer none of them. The page also stops walking as soon as one slice comes back empty, on the reasoning that the TV has stopped answering. It carries a comment explaining why the constant exists (`frontend/app/routes/tvGallery.tsx` lines 17 to 20).

One consequence to be aware of: because an empty slice ends the walk, a run of eight images that all lack previews at the start of the missing list can end the walk before later images are tried. The backend remembers previewless images, so a later visit skips them.

## The list of images

`get_tv_gallery_images` returns each image's content id, filename, date, dimensions, matte and any cached thumbnail. It builds the list from the TV's content list and attaches only thumbnails that are already cached, without asking the TV for missing ones, so the list can come back quickly (`backend/utils/frame_tv.py` lines 721 to 778).

The result is cached in memory per TV for a few seconds, `FRAME_TV_GALLERY_TTL` (default 15). The reason is practical: reloading the page while a thumbnail walk still held the TV used to queue the list behind the walk and then fail, reporting a set that was answering fine. The cache is dropped straight away when anything changes the TV's contents, because an upload or delete has to show at once, not a TTL later (`backend/utils/frame_tv.py` lines 69 to 89, 178, 234, 799 and 847).

The list call runs with the stall watchdog on, so a TV that starts to answer and then goes quiet is cut off (`backend/utils/frame_tv.py` line 777).

## The thumbnail endpoint

The page asks for a slice with one POST to `/api/tv/<ip>/gallery/thumbnails` carrying a list of content ids, and gets back a map of content id to base64 image. The handler returns 404 for an unknown TV, 400 for a malformed list or more than 500 ids, and 503 or 504 with `tv_unavailable: true` when the TV cannot be reached. It exists as one round trip for a batch, replacing one request per image that used to reject each other (`backend/app.py` lines 1295 to 1335).

A single-image endpoint also exists, `GET /api/tv/<ip>/gallery/<content_id>/thumbnail`, which the page no longer uses for the walk.

## How thumbnails are collected

`_collect_thumbnails` is the core (`backend/utils/frame_tv.py` lines 504 to 675). It works in stages.

### 1. Serve what is already known

For each requested id it first looks for a cached copy: memory first, then disk. Memory entries expire after 60 seconds. The disk cache under `instance/tv_thumbnails/<ip>/` has no expiry, and a disk hit refills memory (`backend/utils/frame_tv.py` lines 33 to 49, 92 to 112 and 438 to 445). Serving the cache means a TV that has gone quiet cannot blank a gallery it has already answered for once.

Ids that start with `SAM` are the TV's own built-in art. The TV refuses to serve thumbnails for it, so those ids are never requested, only recorded as previewless (`backend/utils/frame_tv.py` lines 527 to 531).

An id remembered as previewless is skipped for `FRAME_TV_NO_THUMBNAIL_TTL` seconds (default 3600), long enough to stop paying a round trip for the same nothing on every page load, short enough that firmware that starts answering is picked up (`backend/utils/frame_tv.py` lines 448 to 467).

### 2. Ask in batches

Whatever is left is requested `FRAME_TV_THUMBNAIL_BATCH` at a time (default 8) with the library's batch call. The reason is that the TV streams every thumbnail of a request down one socket before the call returns. Asking for a whole gallery at once is a single transfer that finishes or is lost entirely, and a set with forty 4K images never finished. In batches, each batch is saved as it lands, so a gallery fills in across a few visits (`backend/utils/frame_tv.py` lines 504 to 523 and 571 to 589).

Each thumbnail received is written to disk and memory at once. The batch answer is keyed by `fileID.fileType`, for example `MY_F0440.jpg`, so the key is trimmed back to the content id before it is filed. Filing it under the raw key once left every thumbnail under a name nothing looked up, and the gallery stayed blank while the bytes were arriving (`backend/utils/frame_tv.py` lines 470 to 481).

### 3. When a batch fails

A batch that raises is handled in one of two ways, and the difference is the important part (`backend/utils/frame_tv.py` lines 586 to 616):

- If frames arrived during the call and it ran for nearly the whole stall timeout, the TV answered and then stopped. Its transfer started and never finished, so the images in that batch are treated as previewless and remembered, otherwise every page load would pay the same stall again.
- Otherwise the batch was refused quickly, or the TV said nothing at all. It is logged at INFO and the images are retried one at a time.

<!-- openwiki: broken internal link [/openwiki/operations/diagnostics-and-failure-modes.md] link "/openwiki/operations/diagnostics-and-failure-modes.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
The stall test uses the frame counter the connection layer keeps. See the note in [Diagnostics and failure modes](/openwiki/operations/diagnostics-and-failure-modes.md) about how reliable that counter is after a timeout.

### 4. One at a time, and when to give up

A batch that returned less than was asked for has its remaining images fetched individually. One unservable image takes its whole batch down with it, because the TV closes the socket rather than skipping it, so fetching singly isolates the offender and saves the rest (`backend/utils/frame_tv.py` lines 520 to 522 and 628 to 659).

A single fetch reports whether the TV is still talking. A connection-level failure is a dead call, and a refusal that arrives normally is not. The walk stops in three cases:

- Nothing at all has arrived after `FRAME_TV_THUMBNAIL_FIRST_ANSWER` seconds (default 25).
- `FRAME_TV_THUMBNAIL_GIVE_UP` dead calls happen in a row (default 3). A handful of unservable images is normal, but a wall of dead calls means the TV stopped talking, and walking the rest at a socket timeout each once held a page for two minutes.
- A whole batch and then every image of it singly produced no answer, which means the set is away.

The whole call also has an overall deadline, `FRAME_TV_THUMBNAIL_DEADLINE` (default 120 seconds) (`backend/utils/frame_tv.py` lines 567 to 577, 631 to 636, 648 to 666, and 699 to 710).

### 5. Judging refusals at the end

A refusal only says something about an image if the TV goes on to answer for another one afterwards. Judging immediately would write off every image left in the list when a set stops mid-gallery. So refusals are recorded with how many answers had arrived, and judged after the walk: an image refused when the TV then kept answering is remembered as previewless (`backend/utils/frame_tv.py` lines 554 to 562 and 668 to 675).

### If the TV call fails outright

`get_tv_gallery_thumbnails` wraps the whole thing. If the call raises a TV error, it logs one warning and returns whatever was cached, rather than blanking a page because one image was missing (`backend/utils/frame_tv.py` lines 698 to 718).

## Log noise from previewless images

The line `TV <ip> has no preview for SAM-...` for the built-in art is written with `print`, not through the logger, so `FRAME_TV_LOG_LEVEL` does not affect it and it repeats on each request that includes those ids (`backend/utils/frame_tv.py` line 530). It is harmless.

## Related pages

<!-- openwiki: broken internal link [/openwiki/tv/connection-and-session.md] link "/openwiki/tv/connection-and-session.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [TV connection layer](/openwiki/tv/connection-and-session.md)
<!-- openwiki: broken internal link [/openwiki/operations/diagnostics-and-failure-modes.md] link "/openwiki/operations/diagnostics-and-failure-modes.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [Diagnostics and failure modes](/openwiki/operations/diagnostics-and-failure-modes.md)
<!-- openwiki: broken internal link [/openwiki/frontend/spa-structure.md] link "/openwiki/frontend/spa-structure.md" is root-absolute, which no real consumer resolves against the repository root (not a coding agent reading the page, not GitHub's Markdown renderer, not a local viewer); use a path relative to this file instead. Fix the href or restore the target, then delete this comment. -->
- [Frontend structure](/openwiki/frontend/spa-structure.md)
