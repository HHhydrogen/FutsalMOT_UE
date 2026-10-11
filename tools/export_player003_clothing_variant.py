import bpy
from pathlib import Path
from mathutils import Matrix

ROOT = Path(r"D:\projects\FutsalMOT_blender\characters\Player_003\third_party_export")
OUT = ROOT / "ClothingVariants"
OUT.mkdir(parents=True, exist_ok=True)

# Set 01 is the first third-party clothing pair in the supplied blend.
arm_src = bpy.data.objects.get("Human.rig")
jersey_src = bpy.data.objects.get("Human.futsalmot_jersey_male_flare_v1")
shorts_src = bpy.data.objects.get("Human.futsalmot_shorts_male_v1")
if not arm_src or not jersey_src or not shorts_src:
    raise RuntimeError("Set 01 source clothing objects are missing")

collection = bpy.data.collections.new("Player003_ClothingVariant_01")
bpy.context.scene.collection.children.link(collection)
arm = arm_src.copy()
arm.data = arm_src.data.copy()
arm.name = "Human_rig"
collection.objects.link(arm)
copies = [arm]

for src in (jersey_src, shorts_src):
    obj = src.copy()
    obj.data = src.data.copy()
    obj.name = src.name
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    collection.objects.link(obj)
    for mod in obj.modifiers:
        if mod.type == "ARMATURE":
            mod.object = arm
    obj.data.transform(Matrix.Scale(100.0, 4))
    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:
            for point in key.data:
                point.co *= 100.0
    copies.append(obj)

bpy.ops.object.select_all(action="DESELECT")
for obj in copies:
    obj.select_set(True)
bpy.context.view_layer.objects.active = arm
out = OUT / "MPFB_Player_003_ClothingVariant_01.fbx"
bpy.ops.export_scene.fbx(
    filepath=str(out), use_selection=True, object_types={'ARMATURE', 'MESH'},
    global_scale=1.0, apply_unit_scale=False, apply_scale_options='FBX_SCALE_NONE',
    add_leaf_bones=False, bake_anim=False, path_mode='COPY', embed_textures=True,
    use_mesh_modifiers=False, axis_forward='-Z', axis_up='Y')
print({"fbx": str(out), "exists": out.exists(), "objects": [o.name for o in copies]})
