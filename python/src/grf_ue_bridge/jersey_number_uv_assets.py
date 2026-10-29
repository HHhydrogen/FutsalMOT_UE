"""构建号码 UV 印花原型所需的确定性 1..99 alpha 图集。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from PIL import Image, ImageDraw, ImageFont, __version__ as pillow_version

# src/grf_ue_bridge -> 仓库根目录需要向上两级。
_UE_DIR = Path(__file__).resolve().parents[2] / "ue"
if str(_UE_DIR) not in sys.path:
    sys.path.insert(0, str(_UE_DIR))
from jersey_number_uv_contract import ATLAS_GRID, UV_NUMBER_POLICY, atlas_cell, canonical_fingerprint


def build_atlas(output: Path, font_path: Path, *, cell_px: int = 128, padding_px: int = 12,
                font_axes: Optional[Sequence[float]] = None) -> dict:
    """创建新输出目录并写 PNG/JSON；字体文件只读取，不复制或重分发。"""
    if type(cell_px) is not int or not 32 <= cell_px <= 1024:
        raise ValueError("cell_px 必须为 32..1024 整数")
    if type(padding_px) is not int or not 2 <= padding_px < cell_px // 3:
        raise ValueError("padding_px 必须保留足够的空白边界")
    output = Path(output)
    font_path = Path(font_path)
    font_bytes = font_path.read_bytes()
    variations = None
    if font_axes is not None:
        probe = ImageFont.truetype(str(font_path), cell_px)
        axes = probe.get_variation_axes()
        if len(font_axes) != len(axes) or any(type(v) not in (int,float) or not a['minimum']<=v<=a['maximum']
                                             for v,a in zip(font_axes,axes)):
            raise ValueError('字体可变轴数量或范围不符')
        variations = [{'name':a['name'].decode('utf-8'),'value':v} for a,v in zip(axes,font_axes)]
    if output.exists():
        raise FileExistsError("拒绝覆盖已有号码图集目录: {}".format(output))
    font_size = cell_px
    available = cell_px - 2 * padding_px
    while font_size > 1:
        font = ImageFont.truetype(str(font_path), font_size)
        if font_axes is not None:
            font.set_variation_by_axes(list(font_axes))
        boxes = [font.getbbox(str(number)) for number in range(1, 100)]
        if max(box[2] - box[0] for box in boxes) <= available and max(box[3] - box[1] for box in boxes) <= available:
            break
        font_size -= 1
    atlas = Image.new("RGBA", (ATLAS_GRID[0] * cell_px, ATLAS_GRID[1] * cell_px), (255, 255, 255, 0))
    draw = ImageDraw.Draw(atlas)
    cells = []
    for number, box in zip(range(1, 100), boxes):
        column, row = atlas_cell(number)
        width, height = box[2] - box[0], box[3] - box[1]
        x = column * cell_px + (cell_px - width) // 2 - box[0]
        y = row * cell_px + (cell_px - height) // 2 - box[1]
        draw.text((x, y), str(number), font=font, fill=(255, 255, 255, 255))
        alpha = atlas.getchannel("A").crop((column * cell_px, row * cell_px, (column + 1) * cell_px, (row + 1) * cell_px))
        bbox = alpha.getbbox()
        if bbox is None or not (padding_px <= bbox[0] < bbox[2] <= cell_px - padding_px and padding_px <= bbox[1] < bbox[3] <= cell_px - padding_px):
            raise RuntimeError("号码 {} 超出安全图集边界".format(number))
        cells.append({"value": number, "column": column, "row": row, "alpha_bbox_in_cell": list(bbox)})
    output.mkdir(parents=True)
    png = output / "jersey_numbers_01_99.png"
    atlas.save(png, compress_level=9)
    record = {
        "schema": "futsalmot_jersey_number_uv_atlas", "version": 1, "policy": UV_NUMBER_POLICY,
        "grid": list(ATLAS_GRID), "cell_px": cell_px, "padding_px": padding_px,
        "resolution": list(atlas.size), "number_range": [1, 99], "index_formula": "value - 1",
        "font_sha256": hashlib.sha256(font_bytes).hexdigest(), "font_size_px": font_size,
        "font_file_distributed": False, "pillow_version": pillow_version,
        "png_sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
        "rgba_pixel_sha256": hashlib.sha256(atlas.tobytes()).hexdigest(), "cells": cells,
        "ue_import": {"srgb": False, "compression": "Masks", "address_x": "Clamp", "address_y": "Clamp"},
        "acceptance": "CPU_ATLAS_ONLY_NOT_UE_VERIFIED",
    }
    if variations is not None:
        record['font_variation_axes'] = variations
    record["fingerprint"] = canonical_fingerprint(record)
    (output / "atlas.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--cell-px", type=int, default=128)
    parser.add_argument("--padding-px", type=int, default=12)
    parser.add_argument("--font-axes", type=float, nargs='+', default=None)
    args = parser.parse_args(argv)
    result = build_atlas(args.output, args.font, cell_px=args.cell_px, padding_px=args.padding_px,font_axes=args.font_axes)
    print("JERSEY_UV_ATLAS_WRITTEN " + json.dumps({key: result[key] for key in ("resolution", "png_sha256", "acceptance")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
