"""Import the CC0 male skin diffuse texture set into the MPFB shared library."""

import hashlib
import json
import os
import zipfile

import unreal


ARCHIVE_PATH = "D:/projects/FutsalMOT_blender/asset_sources/makehuman_system_assets_cc0.zip"
SOURCE_SKIN_DIR = "D:/projects/FutsalMOT_blender/asset_library/MPFB/skins"
DESTINATION_DIR = "/Game/FutsalMOT/Characters/MPFB/Textures/Skins/Male"
TEXTURES = [
    (
        "skins/young_african_male/young_darkskinned_male_diffuse.png",
        "T_MPFB_Skin_Young_African_Dark",
    ),
    (
        "skins/middleage_asian_male/middleage_lightskinned_male_diffuse2.png",
        "T_MPFB_Skin_MiddleAge_Asian_Light",
    ),
    (
        "skins/young_caucasian_male/young_lightskinned_male_diffuse.png",
        "T_MPFB_Skin_Young_Caucasian_Light",
    ),
    (
        "skins/old_asian_male/old_lightskinned_male_diffuse2.png",
        "T_MPFB_Skin_Old_Asian_Light",
    ),
    (
        "skins/middleage_caucasian_male/middleage_lightskinned_male_diffuse.png",
        "T_MPFB_Skin_MiddleAge_Caucasian_Light",
    ),
    (
        "skins/middleage_african_male/middleage_darkskinned_male_diffuse.png",
        "T_MPFB_Skin_MiddleAge_African_Dark",
    ),
    (
        "skins/young_asian_male/young_lightskinned_male_diffuse3.png",
        "T_MPFB_Skin_Young_Asian_Light",
    ),
    (
        "skins/old_african_male/old_darkskinned_male_diffuse.png",
        "T_MPFB_Skin_Old_African_Dark",
    ),
    (
        "skins/old_caucasian_male/old_lightskinned_male_diffuse.png",
        "T_MPFB_Skin_Old_Caucasian_Light",
    ),
]


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _ensure_source_textures():
    if not os.path.isfile(ARCHIVE_PATH):
        raise RuntimeError("Missing MPFB source archive: " + ARCHIVE_PATH)
    if not os.path.isdir(SOURCE_SKIN_DIR):
        raise RuntimeError("Missing MPFB skin library directory: " + SOURCE_SKIN_DIR)

    with zipfile.ZipFile(ARCHIVE_PATH) as archive:
        members = set(archive.namelist())
        for member, _ in TEXTURES:
            if member not in members:
                raise RuntimeError("Missing skin texture in source archive: " + member)

        sources = []
        for member, asset_name in TEXTURES:
            source_file = os.path.join(SOURCE_SKIN_DIR, member[len("skins/"):])
            archive_data = archive.read(member)
            if os.path.isfile(source_file):
                with open(source_file, "rb") as source:
                    existing_data = source.read()
                if _sha256(existing_data) != _sha256(archive_data):
                    raise RuntimeError("Existing MPFB skin source differs from CC0 archive: " + source_file)
            else:
                os.makedirs(os.path.dirname(source_file), exist_ok=True)
                with open(source_file, "wb") as source:
                    source.write(archive_data)
            sources.append((source_file, asset_name, _sha256(archive_data)))
    return sources


def _ensure_destination():
    if not unreal.EditorAssetLibrary.does_directory_exist(DESTINATION_DIR):
        if not unreal.EditorAssetLibrary.make_directory(DESTINATION_DIR):
            raise RuntimeError("Could not create UE folder: " + DESTINATION_DIR)


def _import_texture(source_file, asset_name):
    asset_path = DESTINATION_DIR + "/" + asset_name
    existing = unreal.load_asset(asset_path)
    if existing:
        import_data = existing.get_editor_property("asset_import_data")
        existing_source = str(import_data.get_first_filename()).replace("\\", "/")
        if existing_source != source_file.replace("\\", "/"):
            raise RuntimeError("Refusing to replace unrelated UE texture: " + asset_path)
        texture = existing
    else:
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", source_file)
        task.set_editor_property("destination_path", DESTINATION_DIR)
        task.set_editor_property("destination_name", asset_name)
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)
        task.set_editor_property("replace_existing", False)
        task.set_editor_property("factory", unreal.TextureFactory())
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        texture = unreal.load_asset(asset_path)
        if not texture:
            raise RuntimeError("UE failed to import texture: " + asset_path)

    texture.set_editor_property("srgb", True)
    if not unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).save_loaded_asset(texture):
        raise RuntimeError("Could not save UE texture: " + asset_path)
    return texture


def main():
    sources = _ensure_source_textures()
    _ensure_destination()
    results = []
    for source_file, asset_name, source_hash in sources:
        texture = _import_texture(source_file, asset_name)
        results.append(
            {
                "asset": texture.get_path_name(),
                "source": source_file,
                "sha256": source_hash,
                "srgb": texture.get_editor_property("srgb"),
                "class": texture.get_class().get_name(),
            }
        )
    return {"destination": DESTINATION_DIR, "count": len(results), "textures": results}


print(json.dumps(main(), ensure_ascii=False))
