"""号码图集的像素边界、可复现性和输出保护测试。"""

from pathlib import Path

import pytest
from PIL import Image

from grf_ue_bridge.jersey_number_uv_assets import build_atlas


@pytest.fixture
def font_path():
    options = [Path("C:/Windows/Fonts/arialbd.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
    for path in options:
        if path.is_file():
            return path
    pytest.skip("没有可用于实际图集像素验证的本机 TrueType 字体")


def test_atlas_reproducible_with_99_nonempty_cells_and_empty_padding_cells(tmp_path, font_path):
    first = build_atlas(tmp_path / "one", font_path, cell_px=64, padding_px=6)
    second = build_atlas(tmp_path / "two", font_path, cell_px=64, padding_px=6)
    assert first == second
    assert first["resolution"] == [1024, 512]
    assert first["font_file_distributed"] is False
    assert len(first["cells"]) == 99
    image = Image.open(tmp_path / "one" / "jersey_numbers_01_99.png")
    alpha = image.getchannel("A")
    for cell in first["cells"]:
        column, row = cell["column"], cell["row"]
        block = alpha.crop((column * 64, row * 64, (column + 1) * 64, (row + 1) * 64))
        assert list(block.getbbox()) == cell["alpha_bbox_in_cell"]
    for index in range(99, 128):
        column, row = index % 16, index // 16
        assert alpha.crop((column * 64, row * 64, (column + 1) * 64, (row + 1) * 64)).getbbox() is None


def test_existing_output_is_never_overwritten(tmp_path, font_path):
    destination = tmp_path / "existing"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("原文件", encoding="utf-8")
    with pytest.raises(FileExistsError):
        build_atlas(destination, font_path)
    assert sentinel.read_text(encoding="utf-8") == "原文件"


@pytest.mark.parametrize("cell,padding", [(True, 4), (16, 4), (64, 0), (64, 30)])
def test_invalid_atlas_resolution_or_padding_fails_before_write(tmp_path, font_path, cell, padding):
    output = tmp_path / "invalid"
    with pytest.raises(ValueError):
        build_atlas(output, font_path, cell_px=cell, padding_px=padding)
    assert not output.exists()
