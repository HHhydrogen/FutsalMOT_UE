import bpy
from mathutils import Matrix
from pathlib import Path

ROOT = Path(r"D:\projects\FutsalMOT_blender\characters\Player_003")
EXPORT = ROOT / "export"
EXPORT.mkdir(parents=True, exist_ok=True)
TEXTURES = EXPORT / "Textures"
TEXTURES.mkdir(parents=True, exist_ok=True)
fbx_path = EXPORT / "MPFB_Player_003_SOP.fbx"
EXPORT_DATA_SCALE = 100.0
EXPORT_ARMATURE_OBJECT_SCALE = 0.01

bpy.ops.object.mode_set(mode="OBJECT") if bpy.context.object and bpy.context.object.mode != "OBJECT" else None

source_objects = [
    obj for obj in bpy.context.scene.objects
    if obj.type in {"MESH", "ARMATURE"}
    and (
        obj.name == "Human"
        or obj.name == "Human.rig"
        or obj.parent is bpy.data.objects.get("Human.rig")
    )
]
source_armature = bpy.data.objects.get("Human.rig")
if source_armature is None or bpy.data.objects.get("Human") is None:
    raise RuntimeError("Player_003 source objects are incomplete")

collection = bpy.data.collections.new("Player003_ExportCopy")
bpy.context.scene.collection.children.link(collection)
copies = []
copy_by_source = {}
copy_armature = None
for src in source_objects:
    obj = src.copy()
    if src.data:
        obj.data = src.data.copy()
    obj.name = "Human_rig" if src.type == "ARMATURE" else src.name
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    collection.objects.link(obj)
    copies.append(obj)
    copy_by_source[src] = obj
    if src.type == "ARMATURE":
        copy_armature = obj

if copy_armature is None:
    raise RuntimeError("Export armature missing")

# Keep the duplicate hierarchy self-contained and preserve the source world
# transforms when assigning copied mesh objects to the copied armature.
for src in source_objects:
    obj = copy_by_source[src]
    if src.parent in source_objects:
        parent_copy = copy_by_source[src.parent]
        obj.parent = parent_copy
        obj.matrix_parent_inverse = src.matrix_parent_inverse.copy()
    # The verified Player_002 FBX carries a 0.01 armature object scale.
    # Preserve each child mesh's source world offset by compensating its local
    # translation before export. This is critical for the shorts' -6.7 cm
    # source offset; without it the pants move upward after import.
    if src.type == "MESH" and src.parent is source_armature:
        obj.location = src.location / EXPORT_ARMATURE_OBJECT_SCALE

# Export image files actually used by materials into a sidecar directory.
used_images = {}
for obj in source_objects:
    if obj.type != "MESH":
        continue
    for material in obj.data.materials:
        if material and material.use_nodes and material.node_tree:
            for node in material.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image:
                    used_images[node.image.name] = node.image
for image in used_images.values():
    filename = Path(bpy.path.abspath(image.filepath)).name if image.filepath else image.name
    if not Path(filename).suffix:
        filename += ".png"
    target = TEXTURES / filename
    if image.packed_file or image.has_data:
        image.save_render(str(target))

for obj in copies:
    if obj.type == "MESH":
        for mod in obj.modifiers:
            if mod.type == "ARMATURE":
                mod.object = copy_armature
        obj.data.transform(Matrix.Scale(EXPORT_DATA_SCALE, 4), shape_keys=False)
        if obj.data.shape_keys:
            for key in obj.data.shape_keys.key_blocks:
                for co in key.data:
                    co.co *= EXPORT_DATA_SCALE

# Convert the copied armature data once, after all mesh copies are prepared.
copy_armature.data.transform(Matrix.Scale(EXPORT_DATA_SCALE, 4))

# Match the verified Player_002 FBX contract: centimeter-valued armature data
# carried by a 0.01 armature object transform. UE's Legacy FBX importer then
# produces centimeter mesh bounds and a unit runtime retarget scale.
copy_armature.scale = (EXPORT_ARMATURE_OBJECT_SCALE,) * 3

body_copy = next(obj for obj in copies if obj.type == "MESH" and obj.name.startswith("Human"))
body_z = [float((body_copy.matrix_world @ vertex.co).z) for vertex in body_copy.data.vertices]
body_height = max(body_z) - min(body_z)
pelvis_head_z = float(copy_armature.data.bones["pelvis"].head_local.z)
if abs(body_height - 169.4550395) > 0.01:
    raise RuntimeError(f"Export Copy BODY height invalid: {body_height}")
if abs(pelvis_head_z - 93.8267822) > 0.01:
    raise RuntimeError(f"Export Copy pelvis height invalid: {pelvis_head_z}")
if any(abs(float(value) - EXPORT_ARMATURE_OBJECT_SCALE) > 1e-6 for value in copy_armature.scale):
    raise RuntimeError(f"Export Copy armature object scale invalid: {tuple(copy_armature.scale)}")

bpy.ops.object.select_all(action="DESELECT")
for obj in copies:
    obj.select_set(True)
bpy.context.view_layer.objects.active = copy_armature

bpy.ops.export_scene.fbx(
    filepath=str(fbx_path),
    use_selection=True,
    object_types={'ARMATURE', 'MESH'},
    global_scale=1.0,
    apply_unit_scale=False,
    apply_scale_options='FBX_SCALE_NONE',
    add_leaf_bones=False,
    bake_anim=False,
    path_mode='COPY',
    embed_textures=True,
    # Player_003 Human relies on Mask modifiers to remove hidden clothing/helper
    # geometry. The manually imported legacy FBX contains the evaluated result.
    use_mesh_modifiers=True,
    use_mesh_modifiers_render=True,
    axis_forward='-Z',
    axis_up='Y',
)

# Remove the temporary export copy after FBX is written; source Human/rig remain.
copy_names = [obj.name for obj in copies]
bpy.ops.object.select_all(action="DESELECT")
for obj in list(collection.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
bpy.data.collections.remove(collection)

print({
    "fbx": str(fbx_path),
    "exists": fbx_path.exists(),
    "objects": copy_names,
    "temporary_collection_removed": bpy.data.collections.get("Player003_ExportCopy") is None,
})
