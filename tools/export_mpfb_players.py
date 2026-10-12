"""Export MPFB Player_N source files using the verified Player_003 contract."""

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mpfb_player_asset_manifest import (
    EXPORT_ARMATURE_OBJECT_SCALE,
    EXPORT_DATA_SCALE,
    export_directory,
    export_fbx_path,
    player_hair_object,
    source_blend_path,
    source_directory,
)


EXPECTED_PELVIS_HEAD_Z = 93.8267822
HEIGHT_TOLERANCE = 0.01


def _ensure_object_mode():
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def _source_objects():
    source_armature = bpy.data.objects.get("Human.rig")
    source_body = bpy.data.objects.get("Human")
    if source_armature is None or source_body is None:
        raise RuntimeError("MPFB source must contain Human and Human.rig")
    objects = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type in {"MESH", "ARMATURE"}
        and (
            obj.name in {"Human", "Human.rig"}
            or obj.parent is source_armature
        )
    ]
    return source_armature, source_body, objects


def _copy_objects(source_objects, collection):
    copies = []
    copy_by_source = {}
    copy_armature = None
    for source in source_objects:
        copy = source.copy()
        if source.data:
            copy.data = source.data.copy()
        copy.name = "Human_rig" if source.type == "ARMATURE" else source.name
        for source_collection in list(copy.users_collection):
            source_collection.objects.unlink(copy)
        collection.objects.link(copy)
        copies.append(copy)
        copy_by_source[source] = copy
        if source.type == "ARMATURE":
            copy_armature = copy

    if copy_armature is None:
        raise RuntimeError("MPFB source armature is missing")

    source_armature = next(obj for obj in source_objects if obj.type == "ARMATURE")
    for source in source_objects:
        copy = copy_by_source[source]
        if source.parent in source_objects:
            copy.parent = copy_by_source[source.parent]
            copy.matrix_parent_inverse = source.matrix_parent_inverse.copy()
        if source.type == "MESH" and source.parent is source_armature:
            # Preserve child offsets when the export armature object is scaled.
            copy.location = tuple(
                float(value) / EXPORT_ARMATURE_OBJECT_SCALE
                for value in source.location
            )

    return copies, copy_by_source, copy_armature


def _copy_private_hair_images(player_id, hair_source_objects):
    export = export_directory(player_id)
    texture_dir = export / "Textures"
    texture_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    hair_name = player_hair_object(player_id)
    for obj in hair_source_objects:
        if obj.name != hair_name or obj.type != "MESH":
            continue
        for material in obj.data.materials:
            if not material or not material.node_tree:
                continue
            for node in material.node_tree.nodes:
                if node.type != "TEX_IMAGE" or not node.image:
                    continue
                source_path = Path(bpy.path.abspath(node.image.filepath))
                if not source_path.is_file():
                    raise RuntimeError(f"Hair texture is missing: {source_path}")
                target = texture_dir / source_path.name
                target.write_bytes(source_path.read_bytes())
                copied.append(str(target))
    if not copied:
        raise RuntimeError(f"No usable hair texture found for {hair_name}")
    return sorted(set(copied))


def export_player(player_id):
    expected_source = source_blend_path(player_id)
    if Path(bpy.data.filepath).resolve() != expected_source.resolve():
        raise RuntimeError(
            f"Opened source does not match Player_{player_id:03d}: "
            f"{bpy.data.filepath}"
        )
    scene = bpy.context.scene
    if (
        scene.unit_settings.system != "METRIC"
        or scene.unit_settings.length_unit != "METERS"
        or abs(scene.unit_settings.scale_length - 1.0) > 1e-9
    ):
        raise RuntimeError("Source Scene Units must be METRIC / METERS / 1.0")

    _ensure_object_mode()
    source_armature, source_body, source_objects = _source_objects()
    if len(source_armature.data.bones) != 53:
        raise RuntimeError("Source Human.rig must contain 53 bones")
    if not any(b.parent is None and b.name == "Root" for b in source_armature.data.bones):
        raise RuntimeError("Source Human.rig must have Root as its root bone")

    export = export_directory(player_id)
    export.mkdir(parents=True, exist_ok=True)
    fbx_path = export_fbx_path(player_id)
    collection_name = f"Player{player_id:03d}_ExportCopy"
    collection = bpy.data.collections.new(collection_name)
    bpy.context.scene.collection.children.link(collection)

    copies = []
    try:
        copies, copy_by_source, copy_armature = _copy_objects(source_objects, collection)
        body_copy = copy_by_source[source_body]

        private_hair_images = _copy_private_hair_images(player_id, source_objects)

        for copy in copies:
            if copy.type != "MESH":
                continue
            for modifier in copy.modifiers:
                if modifier.type == "ARMATURE":
                    modifier.object = copy_armature
            copy.data.transform(Matrix.Scale(EXPORT_DATA_SCALE, 4), shape_keys=False)
            if copy.data.shape_keys:
                for key in copy.data.shape_keys.key_blocks:
                    for vertex in key.data:
                        vertex.co *= EXPORT_DATA_SCALE

        copy_armature.data.transform(Matrix.Scale(EXPORT_DATA_SCALE, 4))
        copy_armature.scale = (EXPORT_ARMATURE_OBJECT_SCALE,) * 3

        body_z = [
            float((body_copy.matrix_world @ vertex.co).z)
            for vertex in body_copy.data.vertices
        ]
        body_height = max(body_z) - min(body_z)
        source_body_z = [
            float((source_body.matrix_world @ vertex.co).z)
            for vertex in source_body.data.vertices
        ]
        source_body_height = max(source_body_z) - min(source_body_z)
        pelvis_head_z = float(copy_armature.data.bones["pelvis"].head_local.z)
        expected_body_height = source_body_height * EXPORT_DATA_SCALE
        if abs(body_height - expected_body_height) > HEIGHT_TOLERANCE:
            raise RuntimeError(
                "Export Copy BODY data height mismatch: "
                f"expected {expected_body_height}, got {body_height}"
            )
        if abs(pelvis_head_z - EXPECTED_PELVIS_HEAD_Z) > HEIGHT_TOLERANCE:
            raise RuntimeError(f"Export Copy pelvis height invalid: {pelvis_head_z}")
        if any(
            abs(float(value) - EXPORT_ARMATURE_OBJECT_SCALE) > 1e-6
            for value in copy_armature.scale
        ):
            raise RuntimeError(f"Export Copy armature scale invalid: {copy_armature.scale}")

        bpy.ops.object.select_all(action="DESELECT")
        for copy in copies:
            copy.select_set(True)
        bpy.context.view_layer.objects.active = copy_armature
        bpy.ops.export_scene.fbx(
            filepath=str(fbx_path),
            use_selection=True,
            object_types={"ARMATURE", "MESH"},
            global_scale=1.0,
            apply_unit_scale=False,
            apply_scale_options="FBX_SCALE_NONE",
            use_space_transform=True,
            bake_space_transform=False,
            add_leaf_bones=False,
            bake_anim=False,
            path_mode="COPY",
            embed_textures=True,
            use_mesh_modifiers=True,
            use_mesh_modifiers_render=True,
            axis_forward="-Z",
            axis_up="Y",
        )
        return {
            "player": player_id,
            "source": str(expected_source),
            "fbx": str(fbx_path),
            "fbx_exists": fbx_path.is_file(),
            "hair_object": player_hair_object(player_id),
            "source_body_height_m": source_body_height,
            "export_body_height_cm": body_height,
            "private_hair_images": private_hair_images,
            "source_meshes": [obj.name for obj in source_objects if obj.type == "MESH"],
            "temporary_collection_removed": True,
        }
    finally:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in list(collection.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(collection)


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--player", type=int, action="append", required=True)
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1 :]
    else:
        argv = bpy.app.driver_namespace.get("mpfb_export_argv", [])
    return parser.parse_args(argv)


def main():
    args = _parse_args()
    if len(args.player) != 1:
        raise RuntimeError(
            "Run Blender once per source file; --player must contain one player id"
        )
    return export_player(args.player[0])


print(json.dumps(main(), ensure_ascii=False))
