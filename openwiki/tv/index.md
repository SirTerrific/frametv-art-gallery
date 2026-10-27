# Files

- [TV connection layer](connection-and-session.md) - How every call to a Samsung Frame TV is made and bounded — the per-TV lock, thread-pool deadline, stall watchdog, cooldown, half-open connection cleanup, token capture and error types — and which settings tune it.
- [TV gallery and thumbnails](gallery-and-thumbnails.md) - How the list of images on a Frame TV is fetched and briefly cached, how thumbnails are collected in batches and cached in memory and on disk, when a TV is written off or an image is remembered as having no preview, and how the frontend paces the requests.
- [Pairing, tokens, discovery and wake](pairing-tokens-and-wake.md) - How a TV is added and paired, how the token a TV hands back is kept, how network discovery actually finds TVs and why it fails in Docker's bridge network, and how Wake-on-LAN is sent.
- [Sending art to a TV](uploading-and-display.md) - What happens when an image is sent to a Frame TV — path checks, optional fetch from a photo provider, matte selection, display and brightness, the delete-others and one-slot modes, record keeping — plus playing an uploaded image, deleting from a TV, and art mode and power.
