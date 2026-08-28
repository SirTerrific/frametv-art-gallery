"""Downscaled copies of the uploaded images, cached on disk.

The gallery grid asks for one tile per image. Serving the original for that means
downloading a full-resolution artwork — often several megabytes — to fill a couple of
hundred pixels. These are generated once, on first request, and reused afterwards.

Nothing here is required for the app to work: every failure falls back to the original
file, so a missing Pillow or an unreadable image degrades to the previous behaviour.
"""

import logging
import os
from pathlib import Path
from typing import Optional

try:
    from PIL import Image as PILImage
except ImportError:  # pragma: no cover - Pillow is a declared dependency
    PILImage = None

logger = logging.getLogger(__name__)

# Only these are generated, so a crafted query string cannot fill the disk with
# one cache entry per pixel width.
THUMBNAIL_WIDTHS = (160, 400, 800)


def parse_width(raw: Optional[str]) -> Optional[int]:
    """Return the requested width when it is one we generate, else None."""
    if not raw:
        return None
    try:
        width = int(raw)
    except (TypeError, ValueError):
        return None
    return width if width in THUMBNAIL_WIDTHS else None


def _cache_path(cache_dir: Path, width: int, filename: str) -> Path:
    return cache_dir.joinpath(str(width), filename)


def get_or_create(
    cache_dir: Path, source_path: str, filename: str, width: int
) -> Optional[str]:
    """Path to a copy of `source_path` no wider than `width`, generating it if needed.

    Returns None when the caller should just serve the original: Pillow missing, image
    already small enough, or anything going wrong on the way.
    """
    if PILImage is None or width not in THUMBNAIL_WIDTHS:
        return None

    target = _cache_path(cache_dir, width, filename)
    try:
        source_mtime = os.path.getmtime(source_path)
    except OSError:
        return None

    # Re-crop and re-upload both rewrite the original in place, so a stale copy has to
    # lose to it rather than be served forever.
    if target.is_file() and os.path.getmtime(target) >= source_mtime:
        return str(target)

    try:
        with PILImage.open(source_path) as img:
            if img.width <= width:
                return None
            img = img.convert("RGB") if img.mode in ("P", "RGBA", "LA") else img
            height = max(1, round(img.height * width / img.width))
            img = img.resize((width, height), PILImage.LANCZOS)
            target.parent.mkdir(parents=True, exist_ok=True)
            # Write beside the target first: a reader must never find a half-written file.
            staging = target.with_name(f".{target.name}.{os.getpid()}")
            img.save(staging, format="JPEG", quality=82, optimize=True)
            os.replace(staging, target)
    except Exception:
        logger.warning("Could not build a %spx thumbnail for %s", width, filename, exc_info=True)
        return None

    return str(target)
