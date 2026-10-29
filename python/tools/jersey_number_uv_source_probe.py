"""用 Blender 后台只读提取源网格 UV 证据，不保存或导出角色。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def _uv_islands(mesh, layer):
    """按 UV 连续的公共边收集面岛，避免把重叠但不连通的面合并。"""
    parent = list(range(len(mesh.polygons)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    edges = {}
    for poly in mesh.polygons:
        loops = list(poly.loop_indices)
        for left, right in zip(loops, loops[1:] + loops[:1]):
            vertices = (mesh.loops[left].vertex_index, mesh.loops[right].vertex_index)
            uv = (tuple(round(float(x), 6) for x in layer.data[left].uv),
                  tuple(round(float(x), 6) for x in layer.data[right].uv))
            if vertices[0] > vertices[1]:
                vertices = vertices[::-1]
                uv = uv[::-1]
            key = vertices, uv
            other = edges.get(key)
            if other is None:
                edges[key] = poly.index
            else:
                parent[find(poly.index)] = find(other)
    islands = {}
    for poly in mesh.polygons:
        islands.setdefault(find(poly.index), []).append(poly)
    result = []
    for faces in islands.values():
        coords = [tuple(float(x) for x in layer.data[loop].uv)
                  for poly in faces for loop in poly.loop_indices]
        result.append({
            "face_count": len(faces),
            "uv_bounds": [min(p[0] for p in coords), min(p[1] for p in coords),
                          max(p[0] for p in coords), max(p[1] for p in coords)],
            "polygon_indices": [poly.index for poly in faces],
        })
    return sorted(result, key=lambda item: (-item["face_count"], item["uv_bounds"]))


def main():
    import bpy

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    reports = []
    for player_id in range(3, 10):
        sources = list(args.sources_root.glob("[Pp]layer_{:03d}/*.blend".format(player_id)))
        sources = [path for path in sources if path.stem == "MPFB_Player_{:03d}".format(player_id)]
        if len(sources) != 1:
            raise RuntimeError("Player_{:03d} 源文件必须唯一: {}".format(player_id, sources))
        source = sources[0]
        bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
        meshes = []
        for mesh in bpy.data.meshes:
            if not mesh.uv_layers or not mesh.polygons:
                continue
            layer = mesh.uv_layers.active or mesh.uv_layers[0]
            payload = {
                "polygons": [[int(mesh.loops[index].vertex_index),
                              round(float(layer.data[index].uv.x), 6),
                              round(float(layer.data[index].uv.y), 6)]
                             for poly in mesh.polygons for index in poly.loop_indices],
                "face_sizes": [len(poly.loop_indices) for poly in mesh.polygons],
            }
            digest = hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()
            record = {"mesh": mesh.name, "vertices": len(mesh.vertices),
                      "polygons": len(mesh.polygons), "uv_layer": layer.name,
                      "uv_layer_count": len(mesh.uv_layers), "uv_topology_sha256": digest,
                      "materials": [material.name if material else None for material in mesh.materials]}
            # 原人工资料球衣有 1034 个面；同时保留所有 Mesh 元数据供匹配。
            if len(mesh.polygons) == 1034 or any("jersey" in (name or "").lower() for name in record["materials"]):
                record["islands"] = _uv_islands(mesh, layer)
                record["uv_polygons"] = [
                    {"polygon_index": poly.index,
                     "uv": [[float(x) for x in layer.data[index].uv] for index in poly.loop_indices],
                     "positions_m": [[float(x) for x in mesh.vertices[mesh.loops[index].vertex_index].co]
                                     for index in poly.loop_indices],
                     "normal": [float(x) for x in poly.normal]}
                    for poly in mesh.polygons]
            meshes.append(record)
        reports.append({"player_id": player_id, "source": str(source),
                        "scene_unit_system": bpy.context.scene.unit_settings.system,
                        "scene_scale_length": bpy.context.scene.unit_settings.scale_length,
                        "meshes": meshes})
        print("JERSEY_UV_SOURCE_READ", player_id, len(meshes), flush=True)
    result = {"schema": "futsalmot_jersey_uv_source_probe", "version": 1,
              "blender_version": bpy.app.version_string, "source_files_modified": False,
              "players": reports}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("JERSEY_UV_SOURCE_PROBE_WRITTEN", str(args.output), flush=True)


if __name__ == "__main__":
    main()
