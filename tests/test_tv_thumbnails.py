"""Covers how a page of TV thumbnails is fetched.

The TV streams every thumbnail of one request down a single D2D socket before the
call returns, so asking for a whole gallery at once is one long transfer that is lost
in full if it does not finish. These tests pin the batching that replaced it.

Run with: pytest tests/test_tv_thumbnails.py
"""

import shutil

import pytest

from utils import frame_tv


@pytest.fixture(autouse=True)
def clean_caches():
    frame_tv._CACHE.clear()
    shutil.rmtree(frame_tv.TV_THUMB_DIR, ignore_errors=True)
    frame_tv.TV_THUMB_DIR.mkdir(parents=True, exist_ok=True)
    yield
    frame_tv._CACHE.clear()
    shutil.rmtree(frame_tv.TV_THUMB_DIR, ignore_errors=True)
    frame_tv.TV_THUMB_DIR.mkdir(parents=True, exist_ok=True)


class FakeArt:
    """Answers a bounded number of thumbnails, then stops — like a set that gives up."""

    def __init__(self, answers=None, fail_after=None):
        self.answers = answers or {}
        self.fail_after = fail_after
        self.requests = []
        self.served = 0

    def get_thumbnail_list(self, content_ids):
        self.requests.append(list(content_ids))
        if self.fail_after is not None and self.served >= self.fail_after:
            raise OSError("the TV stopped answering")
        self.served += len(content_ids)
        return {cid: bytearray(b"jpeg-" + cid.encode()) for cid in content_ids}


def test_thumbnails_are_asked_for_in_batches():
    art = FakeArt()
    wanted = [f"C{n}" for n in range(20)]

    found = frame_tv._collect_thumbnails(art, "192.0.2.30", wanted)

    assert set(found) == set(wanted)
    assert len(art.requests) > 1, "a whole gallery should not go in one request"
    assert max(len(batch) for batch in art.requests) <= frame_tv.TV_THUMBNAIL_BATCH


def test_what_arrived_before_the_tv_gave_up_is_kept():
    """The point of batching: a set that stops halfway still fills part of the page."""
    art = FakeArt(fail_after=frame_tv.TV_THUMBNAIL_BATCH)
    wanted = [f"C{n}" for n in range(20)]

    found = frame_tv._collect_thumbnails(art, "192.0.2.31", wanted)

    assert 0 < len(found) < len(wanted), "some thumbnails, not all and not none"

    # ...and they are cached, so the next visit resumes rather than starting over.
    for content_id in found:
        assert frame_tv._cached_thumbnail("192.0.2.31", content_id) is not None


def test_the_listing_serves_the_cache_without_calling_the_tv():
    """The gallery listing must come back quickly; the page fetches the rest itself."""
    art = FakeArt()
    frame_tv._thumb_disk_set("192.0.2.32", "CACHED", b"jpeg-cached")

    found = frame_tv._collect_thumbnails(
        art, "192.0.2.32", ["CACHED", "MISSING"], fetch_missing=False
    )

    assert set(found) == {"CACHED"}
    assert art.requests == [], "the listing should not wait on the TV for thumbnails"
