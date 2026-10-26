"""绿色草地候选目录：复用既有地板独立seed，不修改旧目录或运行准入。"""

from copy import deepcopy
from typing import Optional

from .floor_diversity import NAMESPACE, _hash, _sha, select_floor_id

ORIGINAL_MATERIAL = (
    "/Game/FutsalMOT/Materials/MI_Futsal_Field_Grass_Matte_v1."
    "MI_Futsal_Field_Grass_Matte_v1"
)
GREEN_CATALOG = (
    {"id": "grass_original_v1", "albedo_gain_linear": [1.0, 1.0, 1.0]},
    {"id": "grass_light_v1", "albedo_gain_linear": [1.10, 1.10, 1.10]},
    {"id": "grass_dark_v1", "albedo_gain_linear": [0.90, 0.90, 0.90]},
    {"id": "grass_warm_v1", "albedo_gain_linear": [1.06, 1.0, 0.96]},
    {"id": "grass_cool_v1", "albedo_gain_linear": [0.96, 1.0, 1.06]},
)


def build_green_floor_candidate(
    seed: int, *, trajectory_sha256: str, frozen_context_sha256: str,
    original_material_sha256: str, inspection_sha256: str,
    floor_id: Optional[str] = None,
) -> dict:
    """冻结序列级候选；真实材质创建、短样验收与正式采集准入另行记录。

    gain乘在线性BaseColor上，不是屏幕RGB/HSV百分比；不改几何、UV、纹理、
    法线、粗糙度或光照。original直接使用原实例，其他ID需要独立派生材质。
    """
    selected = select_floor_id(seed, catalog=GREEN_CATALOG)
    for value, name in ((trajectory_sha256, "trajectory_sha256"),
                        (frozen_context_sha256, "frozen_context_sha256"),
                        (original_material_sha256, "original_material_sha256"),
                        (inspection_sha256, "inspection_sha256")):
        _sha(value, name)
    if floor_id is not None:
        selected = floor_id
    matches = [item for item in GREEN_CATALOG if item["id"] == selected]
    if len(matches) != 1:
        raise ValueError("不是本轮绿色草地候选：" + str(selected))
    record = {
        "schema": "futsalmot_green_floor_candidate_v1",
        "catalog_id": "original_grass_bounded_gain_v1",
        "catalog_sha256": _hash(GREEN_CATALOG), "seed": seed,
        "selection_namespace": NAMESPACE,
        "selection_sha256": _hash({"namespace": NAMESPACE, "seed": seed,
                                    "catalog_sha256": _hash(GREEN_CATALOG)}),
        "selection_mode": "paired_override" if floor_id is not None else "seeded",
        "sequence_constant": True, "variant": deepcopy(matches[0]),
        "original_material": ORIGINAL_MATERIAL,
        "original_material_sha256": original_material_sha256,
        "inspection_sha256": inspection_sha256,
        "trajectory_sha256": trajectory_sha256,
        "frozen_context_sha256": frozen_context_sha256,
        "pairing_key": _hash({"seed": seed, "trajectory": trajectory_sha256,
                              "context": frozen_context_sha256}),
        "fixed_factors": ["geometry", "UV", "textures", "normal", "roughness",
                          "lighting", "motion", "camera", "roster"],
        "runtime_authorized": False, "visual_acceptance": False,
        "application_status": "candidate_not_applied",
        "visibility": "unknown",
    }
    record["fingerprint"] = _hash(record)
    return record
