import bpy
import json

out = {
    "filepath": bpy.data.filepath,
    "units": {
        "system": bpy.context.scene.unit_settings.system,
        "length": bpy.context.scene.unit_settings.length_unit,
        "scale": bpy.context.scene.unit_settings.scale_length,
    },
    "objects": [],
}
for obj in bpy.context.scene.objects:
    item = {"name": obj.name, "type": obj.type, "scale": tuple(obj.scale)}
    if obj.type == "MESH":
        item.update({
            "verts": len(obj.data.vertices),
            "faces": len(obj.data.polygons),
            "materials": [mat.name if mat else None for mat in obj.data.materials],
            "armature_modifiers": [
                mod.object.name if mod.object else None
                for mod in obj.modifiers if mod.type == "ARMATURE"
            ],
        })
    if obj.type == "ARMATURE":
        item["bones"] = len(obj.data.bones)
    out["objects"].append(item)
print("PLAYER003_SOURCE_SCAN=" + json.dumps(out, ensure_ascii=False))
