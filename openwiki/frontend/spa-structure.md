---
type: "Reference"
title: "Frontend structure"
openwiki_generated: true
sources:
  - id: openwiki-source-e560413277439079b0684419
    resource: repo://.github/workflows/ci.yaml
  - id: openwiki-source-56ca95b8e1048a07b3fdb36a
    resource: repo://frontend/app/components/header.tsx
  - id: openwiki-source-427e8c597a595dd1f44d9900
    resource: repo://frontend/app/root.tsx
  - id: openwiki-source-32fe0e52149d8d81623146b8
    resource: repo://frontend/app/routes.ts
  - id: openwiki-source-6e56504fba18671215540393
    resource: repo://frontend/app/routes/_layout.tsx
  - id: openwiki-source-d6ac8081471b25d06d9e5077
    resource: repo://frontend/app/routes/gallery.tsx
  - id: openwiki-source-463c99d2c8ebb24e2bc02214
    resource: repo://frontend/app/routes/settings.tsx
  - id: openwiki-source-2b1512f45a6dd66527495ba1
    resource: repo://frontend/app/utils/appApi.ts
  - id: openwiki-source-c1cd5dfce419b6b44db275e7
    resource: repo://frontend/app/utils/matte.ts
  - id: openwiki-source-e4d4449f468c3757fa1188b5
    resource: repo://frontend/app/utils/providerApi.ts
  - id: openwiki-source-f938d694130f9cef91cfe20f
    resource: repo://frontend/app/utils/tvApi.ts
generated: { by: "claude-code", at: "2026-10-28T14:34:25.443Z" }
verified:
  - by: openwiki/0.7.2
    at: 2026-10-28T14:34:25.443Z
---


# Frontend structure

The frontend is a React Router single-page app under `frontend/`. It has no server of its own: the build is static files that Flask or Electron serves (see [System architecture](../architecture/overview.md)). Its source lives in `frontend/app/`.

## Routes and layout

`frontend/app/routes.ts` declares five pages, all nested in one shared layout (`frontend/app/routes.ts` lines 3 to 11):

| Path | File | Purpose |
| --- | --- | --- |
| `/` | `routes/home.tsx` | Landing page. It also renders the update notice. |
| `/gallery` | `routes/gallery.tsx` | The local image library: search, sort, multi-select, upload, import, albums. |
| `/tv-gallery` | `routes/tvGallery.tsx` | The images currently on a chosen TV. |
| `/settings` | `routes/settings.tsx` | TVs, slideshow, mattes, providers, backup and maintenance. |
| `/album/:albumId` | `routes/albumPage.tsx` | One album's images. |

The layout, `routes/_layout.tsx`, renders a `Header`, the routed page in `<main>`, and a `BottomTabs` bar (`frontend/app/routes/_layout.tsx` lines 5 to 17). The header also carries one connection light per TV (`frontend/app/components/header.tsx`). `root.tsx` wraps everything in a `next-themes` theme provider that follows the system theme, mounts the toast container, and shows a loading screen while the app hydrates (`frontend/app/root.tsx` lines 30 to 58).

One quirk to know when editing routes: the album route's file path is written with a doubled slash, `"routes//albumPage.tsx"`, and works as is.

## API client modules

Every backend call goes through one of four modules in `frontend/app/utils/`. Pages do not call `fetch` directly.

| Module | Backend area | Notable functions |
| --- | --- | --- |
| `galleryApi.ts` | Local images, albums, Immich, backup | `fetchImages`, `uploadImage`, `cropImage`, `reconcileImages`, `importReframedGallery`, album helpers |
| `tvApi.ts` | TV management and everything sent to a TV | `getTvs`, `addTv`, `updateTv`, `getTvGalleryImages`, `fetchTvGalleryThumbnails`, `sendToTV`, power and art mode |
| `providerApi.ts` | External photo-source configuration | `getProviders`, `setProvider`, `deleteProvider` |
| `appApi.ts` | App status and update check | `fetchAppStatus` |

`matte.ts` is not an API client. It holds the list of matte styles and colours and the two functions that combine and split the `style_colour` token the backend stores (`frontend/app/utils/matte.ts` lines 5 to 49). It also holds the padding and swatch tables that the matte preview uses to draw an approximate border.

`tvApi.ts` defines a `TVError` class that carries the HTTP status with the message, so a caller can tell an unreachable TV from a rejected request (`frontend/app/utils/tvApi.ts` lines 44 to 54). The module also exposes `tvReachability` and `tvDiagnostics`, and `TV_ART_ERROR_HELP`, which maps each art-channel failure to a plain-language explanation.

### The Immich key is write-only

In `providerApi.ts`, `ProviderConfig` carries `api_key` (send only) and `has_api_key` (response). The server never sends the key back. On the Settings page the key field is a password input; when a key is already stored its placeholder says so, and leaving it empty keeps the stored key on save (`frontend/app/routes/settings.tsx`, `frontend/app/utils/providerApi.ts`). Saving the Immich settings takes effect at once, with no Frame Gallery restart.

### The status check is cached in the browser

`fetchAppStatus` reads `/api/status`, which reports the running version and whether a newer release exists. It keeps the last answer in `localStorage` for six hours and returns that instead of calling the backend, unless a refresh is forced. A missing or corrupt cache entry, or a storage failure, is silently ignored and the network call is made (`frontend/app/utils/appApi.ts` lines 12 to 64).

## How pages load data

The library page loads images and albums together with `Promise.all`, and reloads whenever the search text or sort order changes. The reload is debounced by 250 ms when a search term is present, so typing does not send a request per keystroke, and runs immediately otherwise (`frontend/app/routes/gallery.tsx` lines 61 to 98).

The TV page is different because a TV is slow and serves one request at a time. It first loads the image list, shows it at once, and then fetches missing thumbnails in the background in fixed-size batches, in order. See [TV gallery and thumbnails](../tv/gallery-and-thumbnails.md).

## Components

The components in `frontend/app/components/` group as follows:

- Gallery cards and grid: `imageCard`, `imageGrid`, `AlbumCard`, `TVGalleryImageCard`.
- Dialogs: `imageModal` (with the live `MattePreview`), `imageUploadModal`, `CropImageModal`, `ReframedGalleryImportModal`.
- TV health: `TvStatusIndicator` (the header lights) and `TvDiagnosticsPanel` (the test-connection button in Settings).
- Upload input: `ImageDropZone`.
- Shell: `header`, `bottomTabs`, `loading-screen`, `update-status`.
- `ui/`: small design-system pieces (`button`, `card`, `input`, `badge`, `skeleton`, and the `sonner` toast wrapper).

The gallery page shows two floating action buttons, one to import from Reframed Gallery and one to upload from the device, and each opens its own modal and calls back into the page to reload the library. See [Local image library](../workflows/image-library.md).

## Working on the frontend

From `frontend/`, `pnpm run typecheck` runs route type generation and `tsc`, and `pnpm run build` produces the static output the backend serves. The package manager is pnpm; the CI frontend job uses the same commands.

## Related pages

- [System architecture](../architecture/overview.md)
- [TV gallery and thumbnails](../tv/gallery-and-thumbnails.md)
- [Local image library](../workflows/image-library.md)
