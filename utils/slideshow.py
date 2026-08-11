"""Rotate through an album on a TV, one image at a time.

Runs as a background thread inside the web app rather than as a separate service, so
there is nothing extra to deploy. gunicorn runs several workers, though, and every one
of them imports this module: a naive thread would fire the rotation once per worker.
A lock file decides which single process owns the loop, and the others do nothing.

The loop only ever moves to an image that is already on the TV, so a rotation is one
short `select_image` call rather than an upload.
"""

import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import fcntl  # POSIX only; the published image runs Linux
except ImportError:  # pragma: no cover - Windows development
    fcntl = None

# How often the loop looks for TVs that are due. The per-TV interval is what actually
# paces the rotation; this only bounds how late a rotation can be.
TICK_SECONDS = 30


def _claim_runner_slot(lock_path: Path) -> Optional[object]:
    """Take the single runner slot, or return None when another worker holds it.

    The handle is returned so it stays referenced: closing the file drops the lock,
    which is exactly what should happen if this process dies.
    """
    if fcntl is None:
        # Without flock there is no cross-process arbitration; a single-process
        # development server is the only place this happens.
        return object()
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(lock_path, "w")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return handle
    except OSError:
        return None


def _due(tv, now: datetime) -> bool:
    interval = tv.slideshow_interval_minutes
    if not tv.slideshow_enabled or not tv.slideshow_album_id or not interval or interval <= 0:
        return False
    if tv.slideshow_last_run is None:
        return True
    return (now - tv.slideshow_last_run).total_seconds() >= interval * 60


def _next_content_id(uploaded, last_content_id: Optional[str]) -> Optional[str]:
    """The entry after `last_content_id`, wrapping around."""
    content_ids = [u.content_id for u in uploaded if u.content_id]
    if not content_ids:
        return None
    if last_content_id in content_ids:
        return content_ids[(content_ids.index(last_content_id) + 1) % len(content_ids)]
    return content_ids[0]


def _is_showing_art(tv, is_art_mode_on, frame_tv_errors) -> bool:
    """Whether the TV is on art mode and can be rotated without interrupting anyone.

    Selecting an image with show=True pulls a Frame TV into art mode, so a rotation
    would cut across whatever someone is watching. A TV that cannot be read is treated
    as in use: skipping a rotation is harmless, interrupting one is not.
    """
    try:
        return bool(is_art_mode_on(tv.ip, token=tv.token))
    except frame_tv_errors as err:
        logger.info("Slideshow could not read art mode on TV %s: %s", tv.ip, err)
        return False


def _forget_content(db, UploadedImage, tv_id, content_id) -> int:
    """Drop the record that an image sits on a TV, once the TV says otherwise.

    A refused content id left in place is requested again on every tick, which is how
    one deleted image fills the log with `select_image request failed with error
    number -10`.
    """
    removed = UploadedImage.query.filter_by(tv_id=tv_id, content_id=content_id).delete(
        synchronize_session=False
    )
    db.session.commit()
    return removed


def start(app, db, models, play_uploaded_content, is_art_mode_on, frame_tv_errors, content_gone_errors) -> None:
    """Start the rotation loop in this process if no other worker owns it."""
    # `flask db upgrade` imports the app too. Starting there would have the loop query
    # tables the migration is still in the middle of altering.
    if os.environ.get("FLASK_RUN_FROM_CLI"):
        logger.debug("Running a CLI command; the slideshow stays out of the way")
        return

    lock_path = Path(app.config['SLIDESHOW_LOCK_PATH'])
    slot = _claim_runner_slot(lock_path)
    if slot is None:
        logger.info("Another worker runs the slideshow; this one will not")
        return

    TV, Image, UploadedImage = models

    def rotate_one(tv) -> None:
        # The rotation only ever moves art that is already on screen. Nothing is
        # recorded when skipping, so it resumes on the next tick rather than waiting
        # out another full interval once the TV goes back to art mode.
        if not _is_showing_art(tv, is_art_mode_on, frame_tv_errors):
            logger.debug("TV %s is in use; leaving the slideshow paused", tv.ip)
            return

        uploaded = (
            UploadedImage.query
            .join(Image, UploadedImage.image_id == Image.id)
            .filter(
                UploadedImage.tv_id == tv.id,
                Image.album_id == tv.slideshow_album_id,
            )
            .order_by(UploadedImage.id)
            .all()
        )
        content_id = _next_content_id(uploaded, tv.slideshow_last_content_id)
        if not content_id:
            logger.info(
                "Slideshow for TV %s has nothing to show: send the album to the TV first", tv.ip
            )
            # Recorded anyway, so an empty album does not retry every tick.
            tv.slideshow_last_run = datetime.now()
            db.session.commit()
            return

        try:
            play_uploaded_content(tv.ip, content_id, token=tv.token)
        except content_gone_errors as err:
            # The TV refused the image rather than failing to answer — it no longer
            # holds that content id, whatever this database still says. Forgetting it
            # is what stops the loop retrying the same dead entry every tick.
            logger.info("TV %s no longer holds %s, forgetting it: %s", tv.ip, content_id, err)
            _forget_content(db, UploadedImage, tv.id, content_id)
            return
        except frame_tv_errors as err:
            # An unreachable TV is expected — it may simply be off. Try again next tick.
            logger.info("Slideshow could not reach TV %s: %s", tv.ip, err)
            return

        tv.slideshow_last_content_id = content_id
        tv.slideshow_last_run = datetime.now()
        db.session.commit()
        logger.info("Slideshow moved TV %s to %s", tv.ip, content_id)

    def loop() -> None:
        # Keeps the lock handle alive for as long as the loop runs.
        _ = slot
        time.sleep(TICK_SECONDS)
        while True:
            try:
                with app.app_context():
                    now = datetime.now()
                    for tv in TV.query.filter_by(slideshow_enabled=True).all():
                        if _due(tv, now):
                            rotate_one(tv)
            except Exception:
                logger.exception("Slideshow tick failed")
            time.sleep(TICK_SECONDS)

    threading.Thread(target=loop, name="frametv-slideshow", daemon=True).start()
    logger.info("Slideshow runner started in this worker")
