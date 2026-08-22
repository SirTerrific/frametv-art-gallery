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

    `unservable` are ids the set will not preview. Asking for one takes its whole batch
    down, which is what a real Frame TV does — it closes the socket rather than leaving
    the entry out. `dies_after` stands in for a set that stops talking mid-gallery.
    """

    def __init__(self, unservable=(), dies_after=None, suffix=".jpg"):
        self.unservable = set(unservable)
        self.dies_after = dies_after
        self.suffix = suffix
        self.requests = []
        self.singles = []
        self.served = 0

    def __repr__(self):
        return f"FakeArt(requests={self.requests}, singles={self.singles})"

    def _check_alive(self):
        if self.dies_after is not None and self.served >= self.dies_after:
            raise OSError("the TV stopped answering")

    def get_thumbnail_list(self, content_ids):
        self.requests.append(list(content_ids))
        self._check_alive()
        if self.unservable.intersection(content_ids):
            raise ConnectionError({"reason": "socket closed"})
        self.served += len(content_ids)
        return {
            f"{cid}{self.suffix}": bytearray(b"jpeg-" + cid.encode()) for cid in content_ids
        }

    def get_thumbnail(self, content_id):
        self.singles.append(content_id)
        self._check_alive()
        if content_id in self.unservable:
            raise ConnectionError({"reason": "socket closed"})
        self.served += 1
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


def test_one_unservable_image_does_not_cost_the_rest_of_its_batch():
    """The TV closes the socket on the whole request, so the batch is retried singly.

    Observed on a real set: `stopped answering after 0 of 2`, both entries blank, while
    the same images answered one at a time.
    """
    art = FakeArt(unservable={"SAM-S5714"})
    wanted = ["MY_F0473", "MY_F0472", "SAM-S5714"]

    found = frame_tv._collect_thumbnails(art, "192.0.2.35", wanted)

    assert set(found) == {"MY_F0473", "MY_F0472"}, "the batch must not take its neighbours down"
    assert sorted(art.singles) == sorted(wanted), "every id of the refused batch is retried"


def test_an_image_the_tv_will_not_preview_is_not_asked_for_again():
    """It answered for the others, so the refusal is about that image. Remember it."""
    art = FakeArt(unservable={"SAM-S5714"})
    wanted = ["SAM-S5714", "MY_F0473"]

    frame_tv._collect_thumbnails(art, "192.0.2.37", wanted)
    assert frame_tv._known_to_have_no_thumbnail("192.0.2.37", "SAM-S5714")

    before = len(art.singles)
    frame_tv._collect_thumbnails(art, "192.0.2.37", wanted)
    assert art.singles[before:] == [], "asked the TV again for a preview it does not have"


def test_a_tv_that_stops_talking_is_not_mistaken_for_missing_previews():
    """Otherwise one power-off blanks the gallery for an hour."""
    art = FakeArt(dies_after=frame_tv.TV_THUMBNAIL_BATCH)
    wanted = [f"C{n}" for n in range(20)]

    frame_tv._collect_thumbnails(art, "192.0.2.39", wanted)

    unanswered = [cid for cid in wanted if frame_tv._cached_thumbnail("192.0.2.39", cid) is None]
    assert unanswered, "the set died halfway, so some are still missing"
    for cid in unanswered:
        assert not frame_tv._known_to_have_no_thumbnail("192.0.2.39", cid), (
            f"{cid} was written off because the TV went away, not because it has no preview"
        )


def test_the_tv_is_asked_again_once_the_answer_has_aged():
    """A firmware that starts answering should be picked up without a restart."""
    art = FakeArt(unservable={"SAM-S5714"})
    frame_tv._collect_thumbnails(art, "192.0.2.38", ["SAM-S5714", "MY_F0473"])
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
    art = FakeArt(dies_after=frame_tv.TV_THUMBNAIL_BATCH)
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


def test_a_wall_of_dead_images_stops_the_walk():
    """Each dead image costs a socket timeout, and the TV is locked for the whole walk.

    A page load was holding the set for two minutes working through a gallery that had
    stopped answering, which blocked every other request behind it.
    """
    wanted = [f"C{n}" for n in range(40)]
    art = FakeArt(unservable=set(wanted))

    frame_tv._collect_thumbnails(art, "192.0.2.40", wanted)

    assert len(art.singles) <= frame_tv.TV_THUMBNAIL_GIVE_UP + 1, (
        f"asked {len(art.singles)} dead images one by one instead of giving up"
    )


def test_scattered_unservable_images_do_not_stop_it():
    """Store art sits among ordinary art; a few refusals must not abandon the rest."""
    wanted = [f"C{n}" for n in range(12)]
    art = FakeArt(unservable={"C1", "C5", "C9"})

    found = frame_tv._collect_thumbnails(art, "192.0.2.41", wanted)

    assert set(found) == set(wanted) - {"C1", "C5", "C9"}
    assert len(found) == 9, "everything the TV would serve should still be here"
