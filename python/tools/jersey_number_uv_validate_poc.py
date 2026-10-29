"""P1 读取近景 RGB/mask 实际像素，生成 tight bbox；不授予正式号码验收。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ue"))
from jersey_number_uv_poc_contract import CASES, evaluate_poc_pixels


def pixel_statistics(mask_path, mask_id):
    """只接收原始整数 ID，不容忍色调映射、边缘混色或最近邻 ID 猜测。"""
    with Image.open(mask_path) as image:
        rgb = image.convert("RGB")
    minimum_x, minimum_y = rgb.width, rgb.height
    maximum_x = maximum_y = -1
    count = unexpected = 0
    colors = {}
    for index, pixel in enumerate(rgb.getdata()):
        colors[pixel] = colors.get(pixel, 0) + 1
        if pixel == (mask_id, mask_id, mask_id):
            x, y = index % rgb.width, index // rgb.width
            minimum_x, minimum_y = min(minimum_x, x), min(minimum_y, y)
            maximum_x, maximum_y = max(maximum_x, x), max(maximum_y, y)
            count += 1
        elif pixel != (0, 0, 0):
            unexpected += 1
    return {
        "mask_dimensions": [rgb.width, rgb.height], "number_pixels": count,
        "unexpected_color_pixels": unexpected,
        "bbox_xyxy": [minimum_x, minimum_y, maximum_x + 1, maximum_y + 1] if count else None,
        "bbox_source": "visible_number_mask", "bbox_convention": "xyxy_half_open",
        "most_common_colors": [{"rgb": list(color), "pixels": pixels}
                               for color, pixels in sorted(colors.items(), key=lambda item: (-item[1], item[0]))[:12]],
    }


def validate_capture(path):
    """校验独立证据文件，不把 CPU 结构检查提升为 UE 视觉通过。"""
    path = Path(path).resolve()
    record = json.loads(path.read_text(encoding="utf-8"))
    mask_id = record["mask_id"]
    if type(mask_id) is not int or not 32 <= mask_id <= 41:
        raise ValueError("PoC mask_id 必须为 32..41 整数")
    root = path.parent
    cases = record.get("cases", {})
    file_errors = []
    for name in CASES:
        case = cases.setdefault(name, {})
        try:
            paths = {}
            for key in ("rgb", "mask"):
                file_path = (root / case[key]).resolve()
                if file_path.parent != root or file_path.suffix != ".png":
                    raise ValueError("证据 PNG 必须直接位于本次捕获目录")
                if file_path.name != name + "_" + key + ".png":
                    raise ValueError("文件名与 case 身份不一致")
                paths[key] = file_path
                case[key + "_sha256"] = hashlib.sha256(file_path.read_bytes()).hexdigest()
            with Image.open(paths["rgb"]) as rgb:
                case["rgb_dimensions"] = list(rgb.size)
            case.update(pixel_statistics(paths["mask"], mask_id))
            expected = [case.get("width"), case.get("height")]
            if case["rgb_dimensions"] != expected or case["mask_dimensions"] != expected:
                raise ValueError("文件尺寸与捕获设置不一致")
        except (KeyError, OSError, ValueError) as exc:
            file_errors.append(name + ": " + str(exc))
    errors = file_errors + evaluate_poc_pixels(record)
    if record.get("error"):
        errors.append("UE 捕获报告含错误")
    record["pixel_gate_passed"] = not errors
    record["pixel_gate_errors"] = errors
    record["visual_acceptance"] = False
    record["sequence_mrq_synchronization_verified"] = False
    record["production_enabled"] = False
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_report", type=Path)
    args = parser.parse_args()
    result = validate_capture(args.capture_report)
    output = args.capture_report.with_name("pixel_report.json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(output), "pixel_gate_passed": result["pixel_gate_passed"],
                      "errors": result["pixel_gate_errors"]}, ensure_ascii=False))
    return 0 if result["pixel_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
