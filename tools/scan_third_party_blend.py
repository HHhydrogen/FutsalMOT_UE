import bpy
import json

result = {"objects": [], "materials": [], "images": []}
for obj in bpy.context.scene.objects:
    materials = []
    if hasattr(obj.data, "materials"):
        materials = [mat.name if mat else None for mat in obj.data.materials]
    result["objects"].append({
        "name": obj.name,
        "type": obj.type,
        "materials": materials,
        "mesh_vertices": len(obj.data.vertices) if obj.type == "MESH" else None,
        "mesh_polygons": len(obj.data.polygons) if obj.type == "MESH" else None,
        "uv_layers": len(obj.data.uv_layers) if obj.type == "MESH" else None,
        "uv_points": len(obj.data.uv_layers.active.data) if obj.type == "MESH" and obj.data.uv_layers.active else None,
    })

for material in bpy.data.materials:
    nodes = []
    if material.use_nodes and material.node_tree:
        for node in material.node_tree.nodes:
            entry = {"type": node.type, "name": node.name}
            if hasattr(node, "image") and node.image:
                entry["image"] = node.image.name
                entry["filepath"] = node.image.filepath
            nodes.append(entry)
    result["materials"].append({"name": material.name, "nodes": nodes})

for image in bpy.data.images:
    result["images"].append({
        "name": image.name,
        "filepath": image.filepath,
        "size": list(image.size),
        "packed": bool(image.packed_file),
        "source": image.source,
    })

print("THIRD_PARTY_BLEND_SCAN=" + json.dumps(result, ensure_ascii=False))
