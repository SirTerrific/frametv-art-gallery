"""Covers the crop presets offered for a Frame TV panel.

Run with: pytest tests/test_crop_presets.py
"""

import pytest
from PIL import Image as PILImage

from utils.crop_image import CROP_PRESETS, CropImageError, get_preset_crop_box


@pytest.fixture
def image(tmp_path):
    def make(width, height):
        path = tmp_path / f"{width}x{height}.png"
        PILImage.new("RGB", (width, height), "red").save(path)
        return str(path)
    return make


def test_the_frame_tv_panel_size_is_offered_as_a_preset():
    assert CROP_PRESETS["3840x2160"]["width"] == 3840
    assert CROP_PRESETS["3840x2160"]["height"] == 2160


def test_the_4k_preset_takes_a_centred_panel_sized_crop(image):
    x, y, width, height = get_preset_crop_box(image(4200, 2400), "3840x2160")

    assert (width, height) == (3840, 2160), "exactly the panel, no rescaling on the TV"
    assert x == (4200 - 3840) // 2 and y == (2400 - 2160) // 2, "centred"


def test_a_source_smaller_than_the_panel_is_not_asked_for_more_than_it_has(image):
    x, y, width, height = get_preset_crop_box(image(1600, 900), "3840x2160")

    assert (x, y) == (0, 0)
    assert (width, height) == (1600, 900), "the whole image, not a box past its edge"


def test_an_unknown_preset_is_refused(image):
    with pytest.raises(CropImageError):
        get_preset_crop_box(image(4200, 2400), "not-a-preset")
