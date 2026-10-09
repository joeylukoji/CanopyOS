from io import BytesIO

import pytest
from PIL import Image

from app.services.metrics import SceneRejected
from app.services.vision import check_quality, decode_image


def test_exif_orientation_corrected_and_metadata_removed():
    image = Image.new("RGB", (256, 128), "green")
    exif = Image.Exif()
    exif[274] = 6
    exif[315] = "Private author"
    content = BytesIO()
    image.save(content, "JPEG", exif=exif)
    result = decode_image(content.getvalue())
    assert result.size == (128, 256)
    assert not result.getexif()
    assert not result.info


def test_truncated_file_rejected():
    image = Image.new("RGB", (256, 256), "green")
    content = BytesIO()
    image.save(content, "JPEG")
    with pytest.raises(ValueError):
        decode_image(content.getvalue()[:60])


def test_blank_scene_rejected():
    with pytest.raises(SceneRejected):
        check_quality(Image.new("RGB", (256, 256), "gray"))
