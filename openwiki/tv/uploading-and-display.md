---
type: workflow
title: Sending art to a TV
description: What happens when an image is sent to a Frame TV — path checks, optional fetch from a photo provider, matte selection, display and brightness, the delete-others and one-slot modes, record keeping — plus playing an uploaded image, deleting from a TV, and art mode and power.
tags: [tv, upload, matte, one-slot-mode, delete, art-mode, workflow]
sources:
  - id: openwiki-source-7872be2c059c5659d94804ea
    resource: repo://backend/app.py
  - id: openwiki-source-ba30ebcb023436412b51c6d9
    resource: repo://backend/utils/frame_tv.py
  - id: openwiki-source-52fa25a8462b90d08dafa6be
    resource: repo://frontend/app/components/imageCard.tsx
  - id: openwiki-source-38e7d6bcf2d3f744920ea643
    resource: repo://frontend/app/routes/albumPage.tsx
  - id: openwiki-source-c1cd5dfce419b6b44db275e7
    resource: repo://frontend/app/utils/matte.ts
generated: { by: "claude-code", at: "2026-10-28T14:34:25.443Z" }
verified:
  - by: openwiki/0.7.2
    at: 2026-10-28T14:34:25.443Z
---

# Sending art to a TV

Sending an image is the main thing the app does. It is one request that turns a file in the local library into art on a TV, and then keeps the app's own records of what is on which TV in step with reality.

## The request

The image card in the gallery calls `sendToTV`, which posts to `POST /api/tv/send` (`frontend/app/utils/tvApi.ts` lines 186 to 207). The body names the TV address and the filename, and may carry a brightness, a `display` flag that defaults to true, a matte, and a `provider_id` when the file is not yet local. The handler is `api_send_to_tv` (`backend/app.py` lines 1016 to 1140).

The handler works in this order.

### 1. Validate the filename

Both address and filename are required. The filename goes through `_normalized_upload_path`, which strips it to a safe name, requires that it has no directory part, requires an allowed extension (`png`, `jpg`, `jpeg`), and confirms the resolved path sits directly inside the uploads folder. Anything else is a `ValueError`, so a name cannot point outside the library (`backend/app.py` lines 211 to 235).

### 2. Fetch the file if it is missing

If the file is not in the library but the request names a provider image by `provider_id`, the handler downloads it into the uploads folder first, through the media provider built from the saved settings at the time of the request (`get_media_provider()`). A missing provider (400) or a failed download (500) ends the request with an error (`backend/app.py` lines 1038 to 1046).

An image is named by its id, never by a URL. A request that carries `provider_url` is refused with 400 before anything else happens. That field used to make the server download whatever address it was given with the provider's API key attached, so any client that could reach the API could send the key elsewhere, and the app has no login. The download method behind it was removed, not merely disabled (`backend/app.py` lines 1027 to 1031).

The `provider_id` path is how an image from Immich is sent without first being imported. See [Local image library](../workflows/image-library.md).

### 3. Choose the matte

A matte is the border the TV draws around the artwork. Its precedence is:

1. A matte named in the request.
2. Otherwise the TV's stored default matte.
3. Otherwise no matte argument is sent at all, so `upload_artwork`'s own default of `none` applies.

Leaving the argument out when nothing was chosen keeps behaviour exactly as it was before per-TV defaults existed (`backend/app.py` lines 1056 to 1064).

The frontend agrees with this. It pre-fills the picker from the TV's default but only puts a matte in the request if the person touched the picker, so an untouched send falls through to the TV default (`frontend/app/components/imageCard.tsx` lines 64 to 68, 93 to 100 and 114).

A matte is a single token of the form `style_colour`, for example `modernthin_polar`, with `none` standing alone. `matte.ts` holds the lists of styles and colours and the functions that combine and split the token. The spelling `burgandy` is what the API expects (`frontend/app/utils/matte.ts` lines 1 to 49). The image dialog also draws a live `MattePreview` of the chosen style and colour; it is only an approximation from fixed swatch and padding tables, because the TV renders its own matte (`frontend/app/utils/matte.ts` lines 17 to 38, `frontend/app/components/MattePreview.tsx`). On the TV side, `_matte_kwargs` sends the same value as both the landscape and portrait matte, and only logs a warning if the requested matte is not in the list the TV reports, without blocking the send (`backend/utils/frame_tv.py` lines 127 to 137).

### When a send fails

A failed send comes back with a `code` (`tv_busy`, `tv_timeout` or `tv_unreachable`) and a readable message, so the person sees why instead of a generic error; see [Diagnostics and failure modes](../operations/diagnostics-and-failure-modes.md) (`backend/app.py` lines 1119 to 1140).

Sending a whole album from its page shows a progress bar and keeps the images that failed, with the message for each, in a list. After three failures in a row it stops, on the assumption that the TV is not coming back mid-album (`frontend/app/routes/albumPage.tsx` lines 30 to 31, 70 to 93 and 207 to 221).

### 4. Upload and display

`upload_artwork` reads the file and, inside one TV call, uploads it, sets the brightness if one was given, selects it for display if `display` is true and an id came back, and then removes other images if asked. The TV assigns the content id. The call has the longer upload deadline, `FRAME_TV_UPLOAD_DEADLINE` (default 120 seconds), and is a deliberate call, so it ignores the cooldown and queues behind other work on the same TV. It then drops the cached gallery list so the new image shows at once (`backend/utils/frame_tv.py` lines 140 to 179). See [TV connection layer](connection-and-session.md).

### 5. Record what was uploaded

If the image exists in the library database, the handler records that it is on this TV, in an `UploadedImage` row linking image, TV and content id. If the image was already sent to this TV, the row is updated rather than duplicated, because the TV assigns a new content id on every upload and the old one would point at something that no longer exists (`backend/app.py` lines 1067 to 1090).

## Keeping other art out: two modes

Two per-TV switches decide what happens to art already on the TV. They work differently and should not be confused.

### Delete other images on upload

When set, the upload also asks the TV to delete everything except the new image. It fetches the content list, works out every id other than the new one, and deletes them in one batch call. If the firmware rejects the batch, it falls back to deleting one by one and treats an "already missing" answer as success. If there is more than one copy of the new id, it keeps them all rather than risk deleting the active image (`backend/utils/frame_tv.py` lines 181 to 214). Because this wipes everything else off the TV, the handler then forgets every other upload record for that TV (`backend/app.py` lines 1088 to 1089).

### One-slot mode

One-slot mode is narrower. It keeps only one image that this app sent, and leaves art the app did not send alone. Before uploading, the handler collects the content ids the app has recorded for the TV. After a successful upload it deletes the older ones from the TV, and forgets the records of those it cleared (`backend/app.py` lines 1048 to 1054 and 1090 to 1117).

The pruning is careful about failure. An "already missing" answer from the TV counts as cleared, so a stale id is not retried forever. Any other TV error stops the loop and is logged, and only the ids actually cleared are forgotten. If every stale image was cleared, all other records go. A failure while pruning does not fail the send, since the new image is already on the TV.

`imageCard.tsx` carries a comment describing an `ignore_one_slot` flag that lets a send bypass pruning. The backend does not read any such field, so the comment describes something that is not implemented (`frontend/app/components/imageCard.tsx` line 104).

## Playing an image already on the TV

`POST /api/tv/play_uploaded` shows an image that was uploaded before, without uploading it again. It looks up the stored content id for this image and TV and asks the TV to select it. It answers 404 if the TV or image is unknown, or if that image was never uploaded to that TV (`backend/app.py` lines 822 to 850). The TV can answer that the content id no longer exists, which is why every path that removes art must forget its record.

## Deleting art from a TV

Every removal path forgets the matching upload records through `_forget_uploaded`, because a record left behind makes the app offer to play something the TV no longer has, and the TV answers with error number -10 (`backend/app.py` lines 238 to 255).

- **One image:** `delete_tv_image` deletes a content id and drops the cached list.
- **A selection:** `delete_tv_images` sends the whole list in one connection, since the TV accepts a list and only serves one art channel. If the firmware rejects the list, it deletes one by one and counts an already-missing item as deleted. It also drops the deleted ids from the thumbnail cache (`backend/utils/frame_tv.py` lines 802 to 848).
- **Everything:** `DELETE /api/tv/<ip>/images` deletes every content id the TV lists, and forgets all the records for that TV. If another operation held the TV for the whole wait, nothing was deleted and it answers 503 with `tv_busy` so the person can try again (`backend/utils/frame_tv.py` lines 216 to 234 and `backend/app.py` lines 1144 to 1170).

All of these are deliberate calls.

## Art mode, power and mattes

Small operations on the same pattern, each a deliberate TV call:

- `enable_art_mode` turns art mode on (`backend/utils/frame_tv.py` lines 359 to 372).
- `power_off` sends the power key through the remote channel (`backend/utils/frame_tv.py` lines 350 to 357).
- `set_brightness` sets art-mode brightness (`backend/utils/frame_tv.py` lines 252 to 266).
- `change_matte` changes the matte of art already on the TV. It logs and swallows any failure instead of raising (`backend/utils/frame_tv.py` lines 402 to 420).
- `is_art_mode_on` reads the art-mode state and is an ordinary, cooldown-respecting call, which the slideshow uses to decide whether it may rotate (`backend/utils/frame_tv.py` lines 268 to 283). See [Slideshow rotation](../workflows/slideshow.md).
- Waking a TV that is off is separate, because it cannot go through the TV's websocket. See [Pairing, tokens, discovery and wake](pairing-tokens-and-wake.md).

The older routes `/tv/<ip>/on`, `/off`, `/artmode` and `/status`, without the `/api` prefix, no longer exist: only the `/api/tv/...` routes are available.

## How failures are reported

The send handler answers a TV or HTTP API failure with a generic 500 "Failed to send artwork to TV", a rejection by the TV, meaning a `ResponseError`, with 400 "TV rejected the request", and anything else with a generic 500. The details go to the log, not to the browser (`backend/app.py` lines 1119 to 1140).

## Related pages

- [TV connection layer](connection-and-session.md)
- [Local image library](../workflows/image-library.md)
- [Slideshow rotation](../workflows/slideshow.md)
