import bpy
import hashlib
import json


def signature(obj):
    mesh = obj.data
    uv = mesh.uv_layers.active.data if mesh.uv_layers.active else None
    if uv is None:
        return {"has_uv": False}
    coords = [(round(item.uv.x, 7), round(item.uv.y, 7)) for item in uv]
    loops = [tuple(poly.loop_indices) for poly in mesh.polygons]
    vertices = [tuple(poly.vertices) for poly in mesh.polygons]
    payload = json.dumps({"coords": coords, "loops": loops, "vertices": vertices}, separators=(",", ":"))
    return {
        "has_uv": True,
        "uv_points": len(coords),
        "polygons": len(mesh.polygons),
        "vertices": len(mesh.vertices),
        "hash": hashlib.sha256(payload.encode()).hexdigest(),
        "uv_bbox": [
            min(x for x, y in coords),
            max(x for x, y in coords),
            min(y for x, y in coords),
            max(y for x, y in coords),
        ],
    }


result = {"jersey": [], "shorts": []}
for obj in bpy.context.scene.objects:
    if obj.type != "MESH":
        continue
    name = obj.name.lower()
    if "jersey" in name:
        result["jersey"].append({"name": obj.name, "signature": signature(obj)})
    elif "shorts" in name:
        result["shorts"].append({"name": obj.name, "signature": signature(obj)})

print("THIRD_PARTY_UV_COMPARE=" + json.dumps(result, ensure_ascii=False))
