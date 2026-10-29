"""从同一MRQ采样的线性EXR导出整数号码mask，避免PNG的sRGB/抖动改变ID。"""

import json
from pathlib import Path


def export_number_masks(cameras, *, source_step_seconds=0.1, playback_fps=10):
    import OpenEXR
    import Imath
    import numpy as np
    from PIL import Image

    report = {"schema": "futsalmot_number_mask_exr_export_v1", "cameras": [], "frames": 0}
    for camera in map(Path, cameras):
        metadata = json.loads((camera / "camera.json").read_text(encoding="utf-8"))
        width = metadata.get("image_width") or metadata["intrinsics"]["width"]
        height = metadata.get("image_height") or metadata["intrinsics"]["height"]
        frames = [json.loads(row) for row in (camera / "annotations.jsonl").read_text(encoding="utf-8").splitlines() if row.strip()]
        destination = camera / "number_mask"
        destination.mkdir(exist_ok=True)
        observed = set()
        for frame in frames:
            index = frame["frame_index"]
            render_index = int(round((index - 1) * source_step_seconds * playback_fps))
            source = camera / "render_mask" / ("{:06d}.exr".format(render_index))
            exr = OpenEXR.InputFile(str(source))
            try:
                header = exr.header()
                names = [name for name in header["channels"] if "NumberMask" in name and name.endswith(".R")]
                if len(names) != 1:
                    raise ValueError("EXR号码通道不唯一: " + str(source))
                prefix = names[0][:-1]
                arrays = [np.frombuffer(exr.channel(prefix + channel, Imath.PixelType(Imath.PixelType.FLOAT)), dtype=np.float32).reshape(height, width) for channel in "RGB"]
            finally:
                exr.close()
            if not all(np.isfinite(a).all() for a in arrays) or any(not np.array_equal(arrays[0], a) for a in arrays[1:]):
                raise ValueError("号码EXR RGB通道不一致或包含非有限值")
            scaled = arrays[0] * 255.0
            rounded = np.rint(scaled)
            # HALF在此值域的量化误差小于1/16 ID；不接受混合色或任意最近ID映射。
            if np.max(np.abs(scaled - rounded)) > 1.0 / 16.0:
                raise ValueError("号码EXR不是整数ID，可能存在混合采样: " + str(source))
            ids = set(np.unique(rounded).tolist())
            if not ids <= {0, *range(32, 42)}:
                raise ValueError("号码EXR含非法ID: " + str(ids))
            mask = rounded.astype(np.uint8)
            target = destination / ("{:06d}.png".format(index))
            if target.exists():
                with Image.open(target) as previous:
                    if previous.mode != "L" or not np.array_equal(np.asarray(previous), mask):
                        raise ValueError("拒绝覆盖不同号码mask: " + str(target))
            else:
                temporary = target.with_suffix(".png.tmp")
                Image.fromarray(mask, mode="L").save(temporary, format="PNG")
                temporary.replace(target)
            observed.update(int(v) for v in ids if v)
            report["frames"] += 1
        report["cameras"].append({"camera": camera.name, "frames": len(frames), "visible_ids": sorted(observed), "source": "shared_mrq_linear_exr"})
    return report
