import unreal
import json

BASE = "/Game/FutsalMOT/Characters/MPFB/Players/Player_003/"
MESH_PATH = BASE + "Mesh/MPFB_Player_003"
MAT_DIR = BASE + "ThirdPartyMaterials"
TEXTURE_DIR = BASE + "ThirdPartyTextures"

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
editor = unreal.EditorAssetLibrary


def texture(path):
    return unreal.load_asset(path)


def material(name, tex_path):
    path = MAT_DIR + "/" + name
    mat = unreal.load_asset(path)
    if not mat:
        mat = asset_tools.create_asset(name, MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
    unreal.MaterialEditingLibrary.delete_all_material_expressions(mat)
    sample = unreal.MaterialEditingLibrary.create_material_expression(
        mat, unreal.MaterialExpressionTextureSample, 0, 0
    )
    sample.texture = texture(tex_path)
    unreal.MaterialEditingLibrary.connect_material_property(
        sample, "RGB", unreal.MaterialProperty.MP_BASE_COLOR
    )
    unreal.MaterialEditingLibrary.recompile_material(mat)
    editor.save_asset(path, only_if_is_dirty=False)
    return mat


def main():
    if not editor.does_asset_exist(MESH_PATH):
        raise RuntimeError("Correct Player_003 mesh is missing: " + MESH_PATH)
    mesh = unreal.load_asset(MESH_PATH)
    materials = list(mesh.get_editor_property("materials"))
    slot_names = [str(x) for x in mesh.get_material_slot_names()]
    results = {"slots": slot_names, "materials": []}
    for set_id in range(1, 6):
        jersey_tex = TEXTURE_DIR + "/Set_%02d/T_Player003_Jersey_UV%02d" % (set_id, set_id)
        shorts_tex = TEXTURE_DIR + "/Set_%02d/T_Player003_Shorts_UV%02d" % (set_id, set_id)
        jersey_mat = material("M_Player003_Jersey_Set_%02d" % set_id, jersey_tex)
        shorts_mat = material("M_Player003_Shorts_Set_%02d" % set_id, shorts_tex)
        results["materials"].append({"set": set_id, "jersey": jersey_mat.get_path_name(), "shorts": shorts_mat.get_path_name()})
    # Keep the current mesh slot contract; set the first imported variant as the default test appearance.
    if "Human_futsalmot_jersey_male_flare_v1" in slot_names:
        i = slot_names.index("Human_futsalmot_jersey_male_flare_v1")
        materials[i] = unreal.load_asset(MAT_DIR + "/M_Player003_Jersey_Set_01")
    if "Human_futsalmot_shorts_male_v1" in slot_names:
        i = slot_names.index("Human_futsalmot_shorts_male_v1")
        materials[i] = unreal.load_asset(MAT_DIR + "/M_Player003_Shorts_Set_01")
    mesh.set_editor_property("materials", materials)
    editor.save_asset(MESH_PATH, only_if_is_dirty=False)
    results["mesh"] = MESH_PATH
    results["default_set"] = 1
    return results


print(json.dumps(main(), ensure_ascii=False))
