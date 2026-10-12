"""Import Player_004-009 and normalize MPFB shared/private asset ownership."""

import json
import os
import unreal


ROOT = "/Game/FutsalMOT/Characters/MPFB"
SHARED_TEXTURE_DIR = ROOT + "/Textures"
SHARED_MATERIAL_DIR = ROOT + "/Materials"
PLAYER_ROOT = ROOT + "/Players"
SKELETON_PATH = ROOT + "/Core/Skeleton/SKEL_MPFB_Base"

PLAYER_SOURCE = {
    3: ("D:/projects/FutsalMOT_blender/characters/Player_003/export/MPFB_Player_003_SOP.fbx", "afro_diffuse.png"),
    4: ("D:/projects/FutsalMOT_blender/characters/Player_004/export/MPFB_Player_004_SOP.fbx", "short01_diffuse.png"),
    5: ("D:/projects/FutsalMOT_blender/characters/player_005/export/MPFB_Player_005_SOP.fbx", "short02_diffuse.png"),
    6: ("D:/projects/FutsalMOT_blender/characters/Player_006/export/MPFB_Player_006_SOP.fbx", "short03_diffuse.png"),
    7: ("D:/projects/FutsalMOT_blender/characters/Player_007/export/MPFB_Player_007_SOP.fbx", "short04_diffuse.png"),
    8: ("D:/projects/FutsalMOT_blender/characters/Player_008/export/MPFB_Player_008_SOP.fbx", "hairtex.png"),
    9: ("D:/projects/FutsalMOT_blender/characters/Player_009/export/MPFB_Player_009_SOP.fbx", "short_messy_diff.png"),
}

PRIVATE_HAIR_MATERIAL = {
    3: "M_Player003_Hair",
    4: "M_Player004_Hair",
    5: "M_Player005_Hair",
    6: "M_Player006_Hair",
    7: "M_Player007_Hair",
    8: "M_Player008_Hair",
    9: "M_Player009_Hair",
}

PRIVATE_HAIR_TEXTURE = {
    3: "T_Player003_Hair_BaseColor",
    4: "T_Player004_Hair_BaseColor",
    5: "T_Player005_Hair_BaseColor",
    6: "T_Player006_Hair_BaseColor",
    7: "T_Player007_Hair_BaseColor",
    8: "T_Player008_Hair_BaseColor",
    9: "T_Player009_Hair_BaseColor",
}

PRIVATE_HAIR_NORMAL = {
    9: "T_Player009_Hair_ObjectNormal",
}

SHARED_MATERIALS = {
    "body": ROOT + "/Materials/M_MPFB_Body",
    "eyebrow": ROOT + "/Materials/M_MPFB_Eyebrows",
    "eyes": ROOT + "/Materials/M_MPFB_Eyes",
    "shoes": ROOT + "/Materials/M_MPFB_Shoes",
    "jersey": ROOT + "/Materials/M_MPFB_Jersey_Set_01",
    "shorts": ROOT + "/Materials/M_MPFB_Shorts_Set_01",
}

SHARED_TEXTURES = {
    "body": ROOT + "/Textures/T_MPFB_Skin_BaseColor",
    "eyebrow": ROOT + "/Textures/T_MPFB_Eyebrow_BaseColor",
    "eyes": ROOT + "/Textures/T_MPFB_Eyes_BaseColor",
    "shoes": ROOT + "/Textures/T_MPFB_Shoes_BaseColor",
    "jersey": ROOT + "/Textures/T_MPFB_Jersey_Set_01",
    "shorts": ROOT + "/Textures/T_MPFB_Shorts_Set_01",
}

SHARED_VARIANT_MATERIALS = {
    "jersey": [ROOT + f"/Materials/M_MPFB_Jersey_Set_{i:02d}" for i in range(1, 6)],
    "shorts": [ROOT + f"/Materials/M_MPFB_Shorts_Set_{i:02d}" for i in range(1, 6)],
}

SHARED_VARIANT_TEXTURES = {
    "jersey": [ROOT + f"/Textures/T_MPFB_Jersey_Set_{i:02d}" for i in range(1, 6)],
    "shorts": [ROOT + f"/Textures/T_MPFB_Shorts_Set_{i:02d}" for i in range(1, 6)],
}

SHARED_VARIANT_OLD_NAMES = {
    "jersey": [f"jersey_{i:03d}" for i in range(1, 6)],
    "shorts": [f"short_{i:03d}" for i in range(1, 6)],
}

SHARED_MATERIAL_OLD_NAMES = {
    "body": "middleage_lightskinned_male_diffuse2_Mat",
    "eyebrow": "eyebrow001_Mat",
    "eyes": "blue_eye_Mat",
    "shoes": "shoes06_diffuse_Mat",
}

SHARED_TEXTURE_OLD_NAMES = {
    "body": "middleage_lightskinned_male_diffuse2",
    "eyebrow": "eyebrow001",
    "eyes": "blue_eye",
    "shoes": "shoes06_diffuse",
}


def _old_player003_path(folder, name):
    return f"{ROOT}/Players/Player_003/{folder}/{name}"


def _asset_tools():
    return unreal.AssetToolsHelpers.get_asset_tools()


def _editor_assets():
    return unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)


def _ensure_folder(path):
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        if not unreal.EditorAssetLibrary.make_directory(path):
            raise RuntimeError("Could not create UE content folder: " + path)


def _load(path):
    asset = unreal.load_asset(path)
    if not asset:
        raise RuntimeError("Missing UE asset: " + path)
    return asset


def _move_loaded_asset(asset_path, new_path):
    if asset_path == new_path or not unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        return new_path
    if unreal.EditorAssetLibrary.does_asset_exist(new_path):
        return new_path
    asset = _load(asset_path)
    rename = unreal.AssetRenameData()
    rename.set_editor_property("asset", asset)
    rename.set_editor_property("new_name", new_path.rsplit("/", 1)[-1])
    rename.set_editor_property("new_package_path", new_path.rsplit("/", 1)[0])
    if not _asset_tools().rename_assets([rename]):
        raise RuntimeError(f"Could not move asset: {asset_path} -> {new_path}")
    return new_path


def _move_player003_assets():
    _ensure_folder(SHARED_TEXTURE_DIR)
    _ensure_folder(SHARED_MATERIAL_DIR)
    # Existing Player_003 assets are the established, verified material sources.
    for category, old_name in SHARED_TEXTURE_OLD_NAMES.items():
        _move_loaded_asset(
            _old_player003_path("texture", old_name), SHARED_TEXTURES[category]
        )
    for category, old_name in SHARED_MATERIAL_OLD_NAMES.items():
        _move_loaded_asset(
            _old_player003_path("material", old_name), SHARED_MATERIALS[category]
        )
    for category in ("jersey", "shorts"):
        for old_name, new_texture, new_material in zip(
            SHARED_VARIANT_OLD_NAMES[category],
            SHARED_VARIANT_TEXTURES[category],
            SHARED_VARIANT_MATERIALS[category],
        ):
            _move_loaded_asset(_old_player003_path("texture", old_name), new_texture)
            _move_loaded_asset(
                _old_player003_path("material", old_name + "_Mat"), new_material
            )

    # The hair pair remains private to Player_003.
    _ensure_folder(PLAYER_ROOT + "/Player_003/Textures")
    _ensure_folder(PLAYER_ROOT + "/Player_003/Materials")
    _move_loaded_asset(
        _old_player003_path("texture", "hair_001"),
        PLAYER_ROOT + "/Player_003/Textures/T_Player003_Hair_BaseColor",
    )
    _move_loaded_asset(
        _old_player003_path("material", "hair_001_Mat"),
        PLAYER_ROOT + "/Player_003/Materials/M_Player003_Hair",
    )

    mesh = _load(ROOT + "/Players/Player_003/MPFB_Player_003")
    materials = list(mesh.get_editor_property("materials"))
    slot_names = [str(slot.material_slot_name) for slot in materials]
    replacements = {
        "Human_body": SHARED_MATERIALS["body"],
        "Human_eyebrow001": SHARED_MATERIALS["eyebrow"],
        "材质": SHARED_VARIANT_MATERIALS["jersey"][0],
        "Human_futsalmot_shorts_male_v2_005": SHARED_VARIANT_MATERIALS["shorts"][0],
        "Human_low-poly": SHARED_MATERIALS["eyes"],
        "Human_shoes06": SHARED_MATERIALS["shoes"],
    }
    for index, slot_name in enumerate(slot_names):
        if slot_name in replacements:
            materials[index].material_interface = _load(replacements[slot_name])
    mesh.set_editor_property("materials", materials)
    _editor_assets().save_loaded_asset(mesh)

    for old_folder in [
        PLAYER_ROOT + "/Player_003/texture",
        PLAYER_ROOT + "/Player_003/material",
    ]:
        if not _editor_assets().does_directory_contain_assets(old_folder, True):
            _editor_assets().delete_directory(old_folder)


def _import_fbx(player_id):
    player_dir = f"{PLAYER_ROOT}/Player_{player_id:03d}"
    mesh_dir = player_dir + "/Mesh"
    texture_dir = player_dir + "/Textures"
    material_dir = player_dir + "/Materials"
    for path in [player_dir, mesh_dir, texture_dir, material_dir]:
        _ensure_folder(path)

    filename, _ = PLAYER_SOURCE[player_id]
    if not os.path.isfile(filename):
        raise RuntimeError("Missing FBX source: " + filename)
    existing_mesh_path = mesh_dir + f"/MPFB_Player_{player_id:03d}"
    existing_mesh = unreal.load_asset(existing_mesh_path)
    if existing_mesh:
        existing_import_data = existing_mesh.get_editor_property("asset_import_data")
        if (
            existing_import_data.get_class().get_name() == "FbxSkeletalMeshImportData"
            and str(existing_import_data.get_first_filename()).replace("\\", "/")
            == filename
        ):
            return existing_mesh
    options = unreal.FbxImportUI()
    options.set_editor_property("automated_import_should_detect_type", False)
    options.set_editor_property("original_import_type", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    options.set_editor_property("import_as_skeletal", True)
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_animations", False)
    options.set_editor_property("import_materials", False)
    options.set_editor_property("import_textures", False)
    options.set_editor_property("skeleton", _load(SKELETON_PATH))
    skeletal_data = options.get_editor_property("skeletal_mesh_import_data")
    # Copy the verified Player_003 FBX import transform contract from its data.
    reference_mesh = _load(ROOT + "/Players/Player_003/MPFB_Player_003")
    reference_data = reference_mesh.get_editor_property("asset_import_data")
    for property_name in [
        "convert_scene",
        "convert_scene_unit",
        "force_front_x_axis",
        "import_uniform_scale",
        "import_rotation",
        "import_translation",
        "normal_import_method",
        "normal_generation_method",
        "transform_vertex_to_absolute",
        "preserve_smoothing_groups",
        "update_skeleton_reference_pose",
        "use_t0_as_ref_pose",
    ]:
        try:
            skeletal_data.set_editor_property(
                property_name, reference_data.get_editor_property(property_name)
            )
        except Exception:
            pass
    skeletal_data.set_editor_property("import_content_type", unreal.FBXImportContentType.FBXICT_ALL)
    skeletal_data.set_editor_property("import_meshes_in_bone_hierarchy", True)
    skeletal_data.set_editor_property("import_morph_targets", False)
    skeletal_data.set_editor_property("import_mesh_lods", False)

    task = unreal.AssetImportTask()
    task.set_editor_property("filename", filename)
    task.set_editor_property("destination_path", mesh_dir)
    task.set_editor_property("destination_name", f"MPFB_Player_{player_id:03d}")
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("replace_existing_settings", True)
    task.set_editor_property("options", options)
    factory = unreal.FbxFactory()
    factory.set_editor_property("asset_import_task", task)
    task.set_editor_property("factory", factory)
    _asset_tools().import_asset_tasks([task])
    mesh_path = existing_mesh_path
    mesh = _load(mesh_path)
    import_data = mesh.get_editor_property("asset_import_data")
    if import_data.get_class().get_name() != "FbxSkeletalMeshImportData":
        raise RuntimeError(
            f"Player_{player_id:03d} did not use the Legacy FBX importer: "
            f"{import_data.get_class().get_name()}"
        )
    return mesh


def _import_texture(source_file, folder, asset_name):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", source_file)
    task.set_editor_property("destination_path", folder)
    task.set_editor_property("destination_name", asset_name)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("factory", unreal.TextureFactory())
    _asset_tools().import_asset_tasks([task])
    return _load(folder + "/" + asset_name)


def _create_texture_material(name, texture, folder, hair=False, normal_texture=None):
    material_path = folder + "/" + name
    material = unreal.load_asset(material_path)
    if not material:
        material = _asset_tools().create_asset(
            name, folder, unreal.Material, unreal.MaterialFactoryNew()
        )
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
    diffuse = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSample, -420, 0
    )
    diffuse.set_editor_property("texture", texture)
    unreal.MaterialEditingLibrary.connect_material_property(
        diffuse, "RGB", unreal.MaterialProperty.MP_BASE_COLOR
    )
    if hair:
        material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
        material.set_editor_property("opacity_mask_clip_value", 0.3333)
        unreal.MaterialEditingLibrary.connect_material_property(
            diffuse, "A", unreal.MaterialProperty.MP_OPACITY_MASK
        )
    if normal_texture:
        normal = unreal.MaterialEditingLibrary.create_material_expression(
            material, unreal.MaterialExpressionTextureSample, -420, 220
        )
        normal.set_editor_property("texture", normal_texture)
        normal.set_editor_property(
            "sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
        )
        unreal.MaterialEditingLibrary.connect_material_property(
            normal, "RGB", unreal.MaterialProperty.MP_NORMAL
        )
    unreal.MaterialEditingLibrary.recompile_material(material)
    _editor_assets().save_loaded_asset(material)
    return material


def _import_player_hair(player_id):
    player_dir = f"{PLAYER_ROOT}/Player_{player_id:03d}"
    texture_dir = player_dir + "/Textures"
    material_dir = player_dir + "/Materials"
    source_dir = os.path.dirname(PLAYER_SOURCE[player_id][0])
    texture_filename = PLAYER_SOURCE[player_id][1]
    texture_source = os.path.join(source_dir, "Textures", texture_filename)
    texture_name = PRIVATE_HAIR_TEXTURE[player_id]
    texture = _import_texture(texture_source, texture_dir, texture_name)
    normal_texture = None
    if player_id in PRIVATE_HAIR_NORMAL:
        normal_source = os.path.join(source_dir, "Textures", "short_messy_objnorm.png")
        normal_texture = _import_texture(
            normal_source,
            texture_dir,
            PRIVATE_HAIR_NORMAL[player_id],
        )
        normal_texture.set_editor_property("srgb", False)
        normal_texture.set_editor_property(
            "compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP
        )
        _editor_assets().save_loaded_asset(normal_texture)
    return _create_texture_material(
        PRIVATE_HAIR_MATERIAL[player_id],
        texture,
        material_dir,
        hair=True,
        normal_texture=normal_texture,
    )


def _move_player003_hair_material_to_masked():
    material = _load(PLAYER_ROOT + "/Player_003/Materials/M_Player003_Hair")
    texture = _load(PLAYER_ROOT + "/Player_003/Textures/T_Player003_Hair_BaseColor")
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
    sample = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSample, -420, 0
    )
    sample.set_editor_property("texture", texture)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    material.set_editor_property("opacity_mask_clip_value", 0.3333)
    unreal.MaterialEditingLibrary.connect_material_property(
        sample, "RGB", unreal.MaterialProperty.MP_BASE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        sample, "A", unreal.MaterialProperty.MP_OPACITY_MASK
    )
    unreal.MaterialEditingLibrary.recompile_material(material)
    _editor_assets().save_loaded_asset(material)


def _bind_materials(player_id, mesh, hair_material):
    slot_names = [str(slot.material_slot_name) for slot in mesh.get_editor_property("materials")]
    materials = list(mesh.get_editor_property("materials"))
    replacements = {
        "Human_body": SHARED_MATERIALS["body"],
        "Human_eyebrow001": SHARED_MATERIALS["eyebrow"],
        "材质": SHARED_MATERIALS["jersey"],
        "Human_futsalmot_shorts_male_final": SHARED_MATERIALS["shorts"],
        "Human_futsalmot_shorts_male_v2_005": SHARED_MATERIALS["shorts"],
        "Human_low-poly": SHARED_MATERIALS["eyes"],
        "Human_shoes06": SHARED_MATERIALS["shoes"],
    }
    for index, slot_name in enumerate(slot_names):
        if "hair" in slot_name.casefold() or "afro01" in slot_name.casefold() or "short0" in slot_name.casefold():
            materials[index].material_interface = hair_material
        elif slot_name in replacements:
            materials[index].material_interface = _load(replacements[slot_name])
        else:
            raise RuntimeError(f"Unknown Player_{player_id:03d} material slot: {slot_name}")
    mesh.set_editor_property("materials", materials)
    _editor_assets().save_loaded_asset(mesh)
    return slot_names


def main():
    _move_player003_assets()
    _move_player003_hair_material_to_masked()
    results = []
    for player_id in range(4, 10):
        mesh = _import_fbx(player_id)
        hair_material = _import_player_hair(player_id)
        slots = _bind_materials(player_id, mesh, hair_material)
        skeleton = mesh.get_editor_property("skeleton")
        if not skeleton or skeleton.get_path_name() != SKELETON_PATH + ".SKEL_MPFB_Base":
            raise RuntimeError(f"Player_{player_id:03d} did not reuse SKEL_MPFB_Base")
        results.append(
            {
                "player": player_id,
                "mesh": mesh.get_path_name(),
                "skeleton": skeleton.get_path_name(),
                "hair_material": hair_material.get_path_name(),
                "slots": slots,
            }
        )
    return {"shared": SHARED_MATERIALS, "players": results}


print(json.dumps(main(), ensure_ascii=False))
