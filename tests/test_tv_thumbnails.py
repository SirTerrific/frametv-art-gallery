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
    frame_tv._NO_THUMBNAIL.clear()
    shutil.rmtree(frame_tv.TV_THUMB_DIR, ignore_errors=True)
    frame_tv.TV_THUMB_DIR.mkdir(parents=True, exist_ok=True)
    yield
    frame_tv._CACHE.clear()
    shutil.rmtree(frame_tv.TV_THUMB_DIR, ignore_errors=True)
    frame_tv.TV_THUMB_DIR.mkdir(parents=True, exist_ok=True)


class FakeArt:
    """Answers like samsungtvws does: keyed `fileID.fileType`, not by content id.

    Optionally stops after a while, like a set that gives up mid-gallery.
    """

    def __init__(self, fail_after=None, suffix=".jpg"):
        self.fail_after = fail_after
        self.suffix = suffix
        self.requests = []
        self.singles = []
        self.served = 0

    def __repr__(self):
        return f"FakeArt(requests={self.requests})"

    def get_thumbnail_list(self, content_ids):
        self.requests.append(list(content_ids))
        if self.fail_after is not None and self.served >= self.fail_after:
            raise OSError("the TV stopped answering")
        self.served += len(content_ids)
        # Art store content is skipped by the batch endpoint on my own set.
        return {
            f"{cid}{self.suffix}": bytearray(b"jpeg-" + cid.encode())
            for cid in content_ids
            if not cid.startswith("SAM-")
        }

    def get_thumbnail(self, content_id):
        self.singles.append(content_id)
        return bytearray(b"single-" + content_id.encode())


def test_a_thumbnail_is_filed_under_its_content_id():
    """The TV labels each file `fileID.fileType`; the gallery looks up the bare id."""
    art = FakeArt()

    found = frame_tv._collect_thumbnails(art, "192.0.2.33", ["MY_F0440", "MY_F0469"])

    assert set(found) == {"MY_F0440", "MY_F0469"}, "keys must be content ids, not filenames"
    assert frame_tv._cached_thumbnail("192.0.2.33", "MY_F0440") == b"jpeg-MY_F0440"


def test_an_answer_that_matches_nothing_asked_for_is_dropped():
    art = FakeArt(suffix="")
    art.get_thumbnail_list = lambda ids: {"SOMETHING_ELSE.jpg": bytearray(b"x")}
    art.get_thumbnail = lambda cid: None

    assert frame_tv._collect_thumbnails(art, "192.0.2.34", ["MY_F0440"]) == {}


def test_content_the_batch_skips_is_asked_for_on_its_own():
    """The batch endpoint returns nothing for art store items; the single call does."""
    art = FakeArt()

    found = frame_tv._collect_thumbnails(art, "192.0.2.35", ["MY_F0473", "SAM-S5714"])

    assert set(found) == {"MY_F0473", "SAM-S5714"}
    assert art.singles == ["SAM-S5714"], "only what the batch left out"
    assert found["SAM-S5714"] == b"single-SAM-S5714"


def test_a_thumbnail_the_tv_simply_does_not_have_is_left_out():
    art = FakeArt()
    art.get_thumbnail = lambda cid: None

    found = frame_tv._collect_thumbnails(art, "192.0.2.36", ["MY_F0473", "SAM-S5714"])

    assert set(found) == {"MY_F0473"}, "a missing thumbnail must not break the page"


def test_content_with_no_preview_is_not_asked_for_again():
    """Otherwise every page load pays a round trip to be told the same nothing."""
    asked = []

    art = FakeArt()
    art.get_thumbnail = lambda cid: asked.append(cid)  # returns None

    for _ in range(3):
        frame_tv._collect_thumbnails(art, "192.0.2.37", ["SAM-S5714"])

    assert asked == ["SAM-S5714"], f"asked {len(asked)} times instead of once"


def test_the_tv_is_asked_again_once_the_answer_has_aged():
    """A firmware that starts answering should be picked up without a restart."""
    art = FakeArt()
    art.get_thumbnail = lambda cid: None
    frame_tv._collect_thumbnails(art, "192.0.2.38", ["SAM-S5714"])
    assert frame_tv._known_to_have_no_thumbnail("192.0.2.38", "SAM-S5714")

    frame_tv._NO_THUMBNAIL[("192.0.2.38", "SAM-S5714")] -= frame_tv._NO_THUMBNAIL_TTL + 1
    assert not frame_tv._known_to_have_no_thumbnail("192.0.2.38", "SAM-S5714")


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
