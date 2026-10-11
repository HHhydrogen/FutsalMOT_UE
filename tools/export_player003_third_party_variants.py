import bpy
from pathlib import Path
from mathutils import Matrix

ROOT = Path(r"D:\projects\FutsalMOT_blender\characters\Player_003\third_party_export")
FBX_DIR = ROOT / "Variants"
FBX_DIR.mkdir(parents=True, exist_ok=True)

groups = [
    ("01", "Human.001", "Human.futsalmot_jersey_male_flare_v1.001", "Human.futsalmot_shorts_male_v1.001"),
    ("02", "Human.002", "Human.futsalmot_jersey_male_flare_v1.002", "Human.futsalmot_shorts_male_v1.002"),
    ("03", "Human.003", "Human.futsalmot_jersey_male_flare_v1.003", "Human.futsalmot_shorts_male_v1.003"),
    ("04", "Human.004", "Human.futsalmot_jersey_male_flare_v1.004", "Human.futsalmot_shorts_male_v1.004"),
]
source_armature = bpy.data.objects.get("Human.rig")
if source_armature is None:
    raise RuntimeError("Source MPFB rig is missing")

reports = []
for suffix, human_name, jersey_name, shorts_name in groups:
    arm = source_armature.copy()
    arm.data = source_armature.data.copy()
    arm.name = "Human_rig"
    coll = bpy.data.collections.new("Player003_Variant_" + suffix)
    bpy.context.scene.collection.children.link(coll)
    coll.objects.link(arm)
    exports = [arm]

    for name in (human_name, jersey_name, shorts_name):
        src = bpy.data.objects.get(name)
        if src is None:
            raise RuntimeError("Missing variant object: " + name)
        obj = src.copy()
        obj.data = src.data.copy()
        for old_coll in list(obj.users_collection):
            old_coll.objects.unlink(obj)
        coll.objects.link(obj)
        for mod in obj.modifiers:
            if mod.type == "ARMATURE":
                mod.object = arm
        obj.data.transform(Matrix.Scale(100.0, 4))
        if obj.data.shape_keys:
            for key in obj.data.shape_keys.key_blocks:
                for point in key.data:
                    point.co *= 100.0
        exports.append(obj)

    bpy.ops.object.select_all(action="DESELECT")
    for obj in exports:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = arm
    out = FBX_DIR / ("MPFB_Player_003_KitVariant_" + suffix + ".fbx")
    bpy.ops.export_scene.fbx(
        filepath=str(out), use_selection=True, object_types={'ARMATURE', 'MESH'},
        global_scale=1.0, apply_unit_scale=False, apply_scale_options='FBX_SCALE_NONE',
        add_leaf_bones=False, bake_anim=False, path_mode='COPY', embed_textures=True,
        use_mesh_modifiers=False, axis_forward='-Z', axis_up='Y')
    reports.append({"variant": suffix, "fbx": str(out), "exists": out.exists(), "objects": [x.name for x in exports]})

    for obj in exports:
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(coll)

print({"variants": reports})
