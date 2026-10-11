import bpy
from pathlib import Path

OUT = Path(r"D:\projects\FutsalMOT_blender\characters\Player_003\third_party_export\Textures")
OUT.mkdir(parents=True, exist_ok=True)

keep = [
    "uv1.psd", "uv2.psd", "uv3.psd", "uv4.psd", "uv5.psd",
    "uv1-1.psd", "uv2-1.psd", "uv3-1.psd", "uv4-1.psd", "uv5-1.psd",
    "M03-D_Wool (Kintted)_Displace.jpg", "M04-B_Denim.jpg",
    "TOP_456_Albedo.png", "TOP_457_Albedo.png",
]

reports = []
for image in bpy.data.images:
    if image.name not in keep or image.packed_file is None:
        continue
    stem = image.name.replace(".psd", ".png")
    target = OUT / stem
    image.save_render(str(target))
    reports.append({"source": image.name, "output": str(target), "size": list(image.size)})

print({"output": str(OUT), "images": reports})
