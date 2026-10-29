"""从已有RGB和标注生成号码人工验收图，不重渲染、不增强或补画号码。"""

import json
import math
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TEST = Path("G:/FutsalMOT_Dataset/test/number_uv_random_s1048_a02")
CAMERA = TEST / "raw/number_uv_random_s1048_a02/CineCam_01"
SELECTION = [(4, "R2"), (10, "L1"), (10, "R3"), (9, "R0")]


def font(size):
    return ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", size)


def fit_crop(image, bounds, size, nearest=False):
    crop = image.crop(bounds)
    scale = min(size[0] / crop.width, size[1] / crop.height)
    resized = crop.resize((int(crop.width * scale), int(crop.height * scale)),
                          Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS)
    return resized, scale


def draw_box(draw, box, color, width):
    x1, y1, x2, y2 = box
    draw.rectangle([x1, y1, x2 - 1, y2 - 1], outline=color, width=width)


def main():
    global TEST, CAMERA
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", default="number_uv_size115_down_s1048_a01", choices=("number_uv_random_s1048_a02", "number_uv_size115_s1048_a01", "number_uv_size115_down_s1048_a01"))
    args = parser.parse_args()
    TEST = TEST.parent / args.attempt
    CAMERA = TEST / "raw" / args.attempt / "CineCam_01"
    output = TEST / "review_number_annotations"
    output.mkdir(exist_ok=False)
    frames = {r["frame_index"]: r for r in map(json.loads, (CAMERA / "annotations.jsonl").read_text(encoding="utf-8").splitlines())}
    cards = []
    records = []
    for frame_index, entity in SELECTION:
        frame = frames[frame_index]
        obj = next(r for r in frame["objects"] if r["entity_id"] == entity)
        label = obj["jersey_number"]
        box = list(map(int, label["bbox_xyxy"]))
        player = list(map(int, obj["bbox_xyxy"]))
        rgb = Image.open(CAMERA / "img1" / f"{frame_index:06d}.png").convert("RGB")
        mask = Image.open(CAMERA / "number_mask" / f"{frame_index:06d}.png").convert("L")
        mask_id = 32 + ["L0", "L1", "L2", "L3", "L4", "R0", "R1", "R2", "R3", "R4"].index(entity)
        center = ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)
        # 同一原图区域等比例放大；号码原像素不做插值。
        radius = 24
        detail = [max(0, center[0] - radius), max(0, center[1] - radius),
                  min(rgb.width, center[0] + radius), min(rgb.height, center[1] + radius)]
        context = [max(0, player[0] - 18), max(0, player[1] - 18),
                   min(rgb.width, player[2] + 18), min(rgb.height, player[3] + 18)]
        card = Image.new("RGB", (1440, 690), "#101827")
        draw = ImageDraw.Draw(card)
        draw.text((26, 16), f"帧 {frame_index:06d}   {entity} / track {obj['track_id']}   号码 {label['value']}", font=font(28), fill="white")
        partial = "（门将局部遮挡）" if entity == "R0" else ""
        draw.text((26, 58), f"CineCam_01 · 原图 1920×1080 {partial}", font=font(19), fill="#bdc9dc")
        for x, title in [(24, "球员定位 + 号码框"), (500, "原始RGB局部 · 像素放大"), (966, "同一区域 · 号码mask叠加")]:
            draw.text((x, 101), title, font=font(21), fill="#d6e1ef")
        body, body_scale = fit_crop(rgb, context, (440, 450))
        body_draw = ImageDraw.Draw(body)
        transformed = [(box[0] - context[0]) * body_scale, (box[1] - context[1]) * body_scale,
                       (box[2] - context[0]) * body_scale, (box[3] - context[1]) * body_scale]
        draw_box(body_draw, transformed, "#38e8bb", 2)
        card.paste(body, (24 + (440 - body.width) // 2, 140))
        raw, scale = fit_crop(rgb, detail, (432, 432), nearest=True)
        card.paste(raw, (500, 140))
        # 右图只着色该实体真实mask像素，不根据bbox填充号码。
        colored = rgb.crop(detail).convert("RGBA")
        cropped_mask = mask.crop(detail)
        overlay = Image.new("RGBA", colored.size)
        op = overlay.load()
        for y in range(cropped_mask.height):
            for x in range(cropped_mask.width):
                if cropped_mask.getpixel((x, y)) == mask_id:
                    op[x, y] = (255, 55, 178, 210)
        colored = Image.alpha_composite(colored, overlay).convert("RGB").resize(raw.size, Image.Resampling.NEAREST)
        cd = ImageDraw.Draw(colored)
        transformed = [(box[0] - detail[0]) * scale, (box[1] - detail[1]) * scale,
                       (box[2] - detail[0]) * scale, (box[3] - detail[1]) * scale]
        draw_box(cd, transformed, "#38e8bb", 3)
        card.paste(colored, (966, 140))
        draw.text((26, 595), f"原图号码bbox XYXY = {box}   |   宽高 {box[2]-box[0]}×{box[3]-box[1]} px", font=font(23), fill="#38e8bb")
        draw.text((26, 635), f"号码mask ID={mask_id}   可见像素={label['visible_pixel_count']}   绿色=标注框   洋红=实际号码像素", font=font(21), fill="#d6e1ef")
        filename = f"frame_{frame_index:06d}_{entity}_number_{label['value']}.png"
        card.save(output / filename)
        record = {"frame_index": frame_index, "entity_id": entity, "track_id": obj["track_id"],
                  "jersey_number": label["value"], "number_mask_id": mask_id,
                  "bbox_xyxy": box, "visible_pixel_count": label["visible_pixel_count"],
                  "source_rgb": str(CAMERA / "img1" / f"{frame_index:06d}.png"),
                  "source_number_mask": str(CAMERA / "number_mask" / f"{frame_index:06d}.png"),
                  "detail_crop_xyxy": detail, "review_image": filename}
        records.append(record)
        cards.append(card)
    overview = Image.new("RGB", (2880, 1380), "#101827")
    for i, card in enumerate(cards):
        overview.paste(card, ((i % 2) * 1440, (i // 2) * 690))
    overview.save(output / "number_annotation_review_overview.png")
    if args.attempt != "number_uv_random_s1048_a02":
        lowered = args.attempt == "number_uv_size115_down_s1048_a01"
        baseline = "number_uv_size115_s1048_a01" if lowered else "number_uv_random_s1048_a02"
        old_camera = TEST.parent / baseline / "raw" / baseline / "CineCam_01"
        old_frames = {r["frame_index"]: r for r in map(json.loads, (old_camera / "annotations.jsonl").read_text(encoding="utf-8").splitlines())}
        comparison = Image.new("RGB", (1440, 1180), "#101827")
        compare_draw = ImageDraw.Draw(comparison)
        for row, record in enumerate(records[:2]):
            index, entity = record["frame_index"], record["entity_id"]
            previous = next(o for o in old_frames[index]["objects"] if o["entity_id"] == entity)["jersey_number"]
            old_box, new_box = previous["bbox_xyxy"], record["bbox_xyxy"]
            cx, cy = int((old_box[0]+old_box[2])/2), int((old_box[1]+old_box[3])/2)
            bounds = [cx-24, cy-24, cx+24, cy+24]
            y = row*590
            compare_draw.text((24,y+12),f"号码 {record['jersey_number']} · 帧 {index:06d} · {entity} · 相同原图裁剪区域",font=font(26),fill="white")
            before_title = "已确认的15%放大版" if lowered else "原尺寸"
            after_title = "保持尺寸，中心下移约2cm" if lowered else "印花宽高各 +15%"
            for x,title,source in [(24,before_title,old_camera),(500,after_title,CAMERA)]:
                compare_draw.text((x,y+58),title,font=font(22),fill="#d6e1ef")
                with Image.open(source / "img1" / f"{index:06d}.png") as image:
                    panel=image.convert("RGB").crop(bounds).resize((432,432),Image.Resampling.NEAREST)
                comparison.paste(panel,(x,y+98))
            compare_draw.text((966,y+58),"新版标注框 + mask",font=font(22),fill="#d6e1ef")
            with Image.open(CAMERA/"img1"/f"{index:06d}.png") as image:
                panel=image.convert("RGBA").crop(bounds)
            with Image.open(CAMERA/"number_mask"/f"{index:06d}.png") as image:
                m=image.crop(bounds)
            overlay=Image.new("RGBA",panel.size)
            for py in range(48):
                for px in range(48):
                    if m.getpixel((px,py))==record["number_mask_id"]:
                        overlay.putpixel((px,py),(255,55,178,210))
            panel=Image.alpha_composite(panel,overlay).convert("RGB").resize((432,432),Image.Resampling.NEAREST)
            pd=ImageDraw.Draw(panel)
            draw_box(pd,[(new_box[0]-bounds[0])*9,(new_box[1]-bounds[1])*9,(new_box[2]-bounds[0])*9,(new_box[3]-bounds[1])*9],"#38e8bb",3)
            comparison.paste(panel,(966,y+98))
            compare_draw.text((24,y+548),f"原bbox: {list(map(int,old_box))}  →  新bbox: {new_box}",font=font(23),fill="#38e8bb")
        comparison.save(output/("number_position_before_after.png" if lowered else "number_size115_before_after.png"))
    # 额外提供对应原尺寸全帧，便于核对放大裁剪的位置。
    for frame_index in sorted({r[0] for r in SELECTION}):
        full = Image.open(CAMERA / "img1" / f"{frame_index:06d}.png").convert("RGB")
        d = ImageDraw.Draw(full)
        for record in records:
            if record["frame_index"] != frame_index:
                continue
            box = record["bbox_xyxy"]
            draw_box(d, box, "#38e8bb", 1)
            text = f"{record['entity_id']} #{record['jersey_number']}"
            tx, ty = max(0, box[0] - 15), max(0, box[1] - 32)
            bounds = d.textbbox((tx, ty), text, font=font(17))
            d.rectangle(bounds, fill="#101827")
            d.text((tx, ty), text, fill="#38e8bb", font=font(17))
        full.save(output / f"full_frame_{frame_index:06d}_annotated.png")
    (output / "selected_number_annotations.json").write_text(json.dumps({"source": "已导出annotations.jsonl与number_mask，无新增渲染", "bbox_convention": "pixel_half_open_xyxy", "samples": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    lifecycle_path = TEST / "_test_lifecycle.json"
    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8-sig"))
    lifecycle.update(expires_at_utc=(datetime.now(timezone.utc)+timedelta(hours=24)).isoformat(),
                     purpose="号码人工验收：已有RGB局部与真实mask叠加，生成验收图后保留24小时")
    lifecycle_path.write_text(json.dumps(lifecycle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "samples": len(records), "overview": str(output / "number_annotation_review_overview.png")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
