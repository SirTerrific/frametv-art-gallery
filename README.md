<p align="center">
    <picture>
      <img alt="Header" width="500" src="https://raw.githubusercontent.com/SirTerrific/frametv-art-gallery/refs/heads/main/docs/header_dark.png" >
      <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/SirTerrific/frametv-art-gallery/refs/heads/main/docs/header_light.png">
    </picture>
</p>


# frametv-art-gallery

> A fork of [mrtncode/frametv-art-gallery](https://github.com/mrtncode/frametv-art-gallery).
> The badges, images and container below refer to this fork; upstream keeps its own.

[![Release](https://img.shields.io/github/v/release/SirTerrific/frametv-art-gallery)](https://github.com/SirTerrific/frametv-art-gallery/releases/latest) 
[![Build](https://github.com/SirTerrific/frametv-art-gallery/actions/workflows/build_image.yaml/badge.svg)](https://github.com/SirTerrific/frametv-art-gallery/actions/workflows/build_image.yaml) 
[![License](https://img.shields.io/github/license/SirTerrific/frametv-art-gallery)](https://github.com/SirTerrific/frametv-art-gallery/blob/main/LICENSE) 
[![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue)](https://www.python.org/) 
[![Stars](https://img.shields.io/github/stars/SirTerrific/frametv-art-gallery?style=social)](https://github.com/SirTerrific/frametv-art-gallery/stargazers)

frametv-art-gallery is an independent, open-source, self-hosted gallery manager for Samsung Frame TVs. Not affiliated with Samsung. It lets you create and manage a personal gallery of images, photos, or artworks locally on your TV.


## Disclaimer

frametv-art-gallery is an unofficial, fun, open-source project and is **not affiliated with, endorsed by, or sponsored by Samsung** (or any other company). It is provided "as is" and use is entirely at your own risk. 

This project uses local websocket APIs provided by the TVs.

> ⚠️ **Security Warning:** This application does **not** implement authentication, authorization, or other hardening controls. It is intended for **private, local network use only**.
>
> - Do **not** expose this service to the public internet.
> - Do **not** run it on a publicly reachable IP/host without adding your own security layer (VPN, reverse proxy auth, firewall rules, etc.).
> - If you want to access it remotely, put it behind a secure tunnel or VPN and ensure only trusted devices can reach it.

> ⚠️ **No Warranty and Liability:** The author assumes **no liability** for any damages, data loss, device malfunction, or any other issues that may arise from using this application. You use frametv-art-gallery **entirely at your own risk**. The software is provided without any warranties, express or implied. 
>
> **Always create backups of your data before updating** to a new version. While we strive to maintain compatibility, updates may introduce breaking changes or require data migrations. You are responsible for ensuring you have a complete backup of your uploads and database before proceeding with any update.


## Features

- **Upload straight into an album.** The upload form and drag-and-drop both ask where the
  images should land, and can create the album on the spot.
- **Work on several images at once.** Tick the boxes in the gallery, or shift-click a range,
  then move the selection to an album or delete it in one go.
- **Send a whole album to a TV.** One button uploads every image in the album, in order,
  showing progress and stopping early if the TV goes quiet.
- **Light and dark mode.** Follows the system preference, with a toggle in the header.
- **Slideshow.** Rotate through an album on a TV at a chosen interval. It only moves art
  that is already on screen, so it never pulls the TV into art mode while you are watching
  something — it picks back up on its own once the TV returns to art mode.
- **Wake the TV.** Wake-on-LAN, using the MAC address stored with the TV.
- **Search and sort** the gallery, newest first by default.
- **Duplicate warning.** The same artwork uploaded under another name is flagged.
- **Backup.** Download a zip of your uploads and the database in one click.
- **Immich import.** Browse your Immich albums and push any photo to the TV.

## Images
You can use any kind of image! Either upload your own personal photos or import them from Immich. Or download copyright-free artwork from the internet and import it into Frame TV Gallery.

### Screenshots
<p align="center">
  <img alt="Screenshot 1" src="docs/Screenshot1.png" width="300" />
  <img alt="Screenshot 2" src="docs/Screenshot2.png" width="300" />
  <img alt="Screenshot 3" src="docs/Screenshot3.png" width="300" />
</p>
Example images from https://pixabay.com/

# Installation

## Docker
docker volume create frametv_uploads
docker volume create frametv_db

docker run -d \
  --name frametv \
  -v frametv_uploads:/app/uploads \
  -v frametv_db:/app/instance \
  -p 8000:8000 \
  frametvartgallery:latest

Or use the docker-compose.yml file: https://github.com/SirTerrific/frametv-art-gallery/blob/main/docker-compose.yml

# Update
## Docker (docker run)
Pull the latest image and restart the container while keeping your data (persists in volumes)

Docker Compose (recommended):
1. `docker compose pull`
2. `docker compose up -d`

# Configuration

All optional, with sensible defaults. Set them as environment variables on the container.

| Variable | Default | What it does |
| --- | --- | --- |
| `GUNICORN_WORKERS` | `4` | Worker processes. More than one keeps a slow TV from blocking the whole app. |
| `GUNICORN_TIMEOUT` | `180` | Seconds before gunicorn kills a worker. Keep it above `FRAME_TV_UPLOAD_DEADLINE`. |
| `FRAME_TV_SOCKET_TIMEOUT` | `8` | Socket timeout for a single read from the TV. |
| `FRAME_TV_CALL_DEADLINE` | `20` | Seconds a normal TV request may take before it is given up on. |
| `FRAME_TV_UPLOAD_DEADLINE` | `120` | Same, for image uploads, which push the whole file to the TV. |
| `FRAME_TV_PAIRING_TIMEOUT` | `45` | How long adding a TV waits for the pairing prompt to be accepted. |
| `FRAME_TV_DOWN_COOLDOWN` | `30` | Seconds a TV is skipped after it failed to answer. |
| `FRAME_TV_BUSY_WAIT` | `90` | How long a deliberate action queues behind another operation on the same TV. |
| `FRAME_TV_THUMBNAIL_BATCH` | `8` | Thumbnails asked for per request. Lower it if a TV drops long transfers. |
| `FRAME_TV_THUMBNAIL_DEADLINE` | `120` | Seconds a page of thumbnails may take in total. |
| `FRAME_TV_MAX_PARALLEL_CALLS` | `8` | Concurrent TV requests per worker. |
| `FRAME_TV_SLIDESHOW` | `1` | Set to `0` to stop the slideshow loop from running at all. |

# Tests

```
pip install -e ".[test]"
pytest
```

# Troubleshooting

## The TV gallery shows placeholders instead of thumbnails

The TV stopped answering. Every request to a TV is given a deadline, and a TV that misses
it is skipped for `FRAME_TV_DOWN_COOLDOWN` seconds so one silent set cannot tie up the
whole app — the page then falls back to whatever thumbnails are already cached on disk.

A Frame TV serves a single art channel, so requests to one TV are serialised: opening a
second connection while another is still being established makes the set reject both.

Thumbnails are fetched `FRAME_TV_THUMBNAIL_BATCH` at a time. The TV streams a whole
request down one socket before answering, so asking for a large gallery at once is a
single long transfer that is lost entirely if it does not finish — which is what leaves
every row blank on a set holding dozens of 4K images. Each batch is cached as it lands,
so a gallery fills in over a few visits even on a set that keeps giving up. If yours
still stops early, lower the batch size and look for
`TV … stopped answering after N of M thumbnails` in the logs.

Deliberate actions (playing an image, deleting one, uploading) ignore that cooldown and
still try, so the TV waking up is noticed immediately. If it persists, check that the TV is
on and reachable, then look for a single `Timeout after …` line in the logs: the skipped
requests that follow are deliberately silent.

## "The TV is busy with another request"

Something else was talking to that TV — most often a page of thumbnails still loading,
which holds the set for far longer than a single request. A deliberate action queues for
`FRAME_TV_BUSY_WAIT` seconds before giving up; nothing was changed on the TV, so retrying
once the other operation has finished is all it needs.

## Errors when uploading images to the TV:

-> Check that the TV is on and has enough free storage space. When the storage space for art images is full, the upload fails. 

-> Try uploading an image with the SmartThings App. There will appear a more specific error message.


## The TV keeps asking for permission when uploading an image

Some TVs are asking for permission every time, to avoid this, go to:

Device Connection Manager > Access Notification Settings > First Time Only


# Techstack
Frontend:
- React.js
- TailwindCSS
- Shadcn/ui
- Lottie Animation 

https://lottiefiles.com/free-animation/image-VXYNYReCmq -> Thanks!

Backend:
- Flask (Python)

# Credits
Speical thanks to https://github.com/xchwarze/samsung-tv-ws-api and https://github.com/billyfw/frame-art-shuffler  
