"""MPFB episode 外观 manifest 的纯 Python 生成与校验。"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple


APPEARANCE_POLICY = "futsalmot_appearance_v1"
APPEARANCE_POLICY_V2 = "futsalmot_appearance_v2"
APPEARANCE_SCHEMA = "futsalmot_episode_appearance"
APPEARANCE_VERSION = 1
APPEARANCE_VERSION_V2 = 2
ENTITY_IDS = ("L0", "L1", "L2", "L3", "L4", "R0", "R1", "R2", "R3", "R4")
KIT_CLASSES = (
    "left_outfield",
    "right_outfield",
    "left_goalkeeper",
    "right_goalkeeper",
)
MODEL_IDS = tuple(range(3, 10))
SKIN_COUNT = 9
KIT_IDS = tuple(f"{index:02d}" for index in range(1, 6))
_MAX_SEED = 0x7FFFFFFF
_RANK_NAMESPACE = "rank"


def _canonical_json(value: Any) -> bytes:
    """按数据契约编码 JSON，供 fingerprint 使用。"""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_hex(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _require_game_path(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.startswith("/Game/") or value == "/Game/":
        raise ValueError(f"{field} 必须是非空的 /Game/ 路径")
    return value


def _require_integer_seed(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field} 必须是非 bool 整数")
    return value


def _require_visual_seed(value: Any, field: str) -> int:
    seed = _require_integer_seed(value, field)
    if (
        not 0 <= seed <= _MAX_SEED
    ):
        raise ValueError(f"{field} 必须是 0 至 {_MAX_SEED} 之间的整数")
    return seed


def _normalize_catalog(catalog: Mapping[str, Any]) -> Dict[str, Any]:
    """复制并验证完整资产候选目录。"""
    if not isinstance(catalog, Mapping):
        raise ValueError("appearance catalog 必须是对象")

    normalized = deepcopy(dict(catalog))
    if normalized.get("mode") != "seeded":
        raise ValueError("appearance mode 必须为 seeded")
    policy = normalized.get("policy")
    if policy not in (APPEARANCE_POLICY, APPEARANCE_POLICY_V2):
        raise ValueError(
            "appearance policy 必须为 "
            f"{APPEARANCE_POLICY} 或 {APPEARANCE_POLICY_V2}"
        )
    if not isinstance(normalized.get("catalog_id"), str) or not normalized["catalog_id"]:
        raise ValueError("appearance catalog_id 不能为空")
    if (
        policy == APPEARANCE_POLICY_V2
        and normalized["catalog_id"] != "mpfb_players_003_009_v2"
    ):
        raise ValueError(
            "futsalmot_appearance_v2 catalog_id 必须为 "
            "mpfb_players_003_009_v2"
        )
    if not isinstance(normalized.get("body_texture_parameter"), str) or not normalized[
        "body_texture_parameter"
    ].strip():
        raise ValueError("body_texture_parameter 不能为空")

    numbering = normalized.get("numbering")
    if policy == APPEARANCE_POLICY:
        if "numbering" in normalized:
            raise ValueError("appearance v1 不允许 numbering 配置")
    else:
        _validate_numbering(numbering)

    models = normalized.get("models")
    if not isinstance(models, list) or len(models) != len(MODEL_IDS):
        raise ValueError("appearance models 必须包含 7 个候选")
    model_ids: List[int] = []
    for index, model in enumerate(models):
        if not isinstance(model, Mapping):
            raise ValueError(f"models[{index}] 必须是对象")
        player_id = model.get("player_id")
        if isinstance(player_id, bool) or not isinstance(player_id, int):
            raise ValueError(f"models[{index}].player_id 必须是整数")
        if player_id in model_ids:
            raise ValueError(f"models 存在重复 player_id: {player_id}")
        model_ids.append(player_id)
        if player_id not in MODEL_IDS:
            raise ValueError(f"models.player_id 必须覆盖 3-9，发现 {player_id}")
        _require_game_path(model.get("mesh"), f"models[{index}].mesh")
        _require_game_path(model.get("anim_class"), f"models[{index}].anim_class")
        _require_game_path(model.get("skeleton"), f"models[{index}].skeleton")
    if tuple(sorted(model_ids)) != MODEL_IDS:
        raise ValueError("models 必须完整覆盖 player_id 3-9")

    skins = normalized.get("skins")
    if not isinstance(skins, list) or len(skins) != SKIN_COUNT:
        raise ValueError("appearance skins 必须包含 9 个候选")
    skin_ids = []
    for index, skin in enumerate(skins):
        if not isinstance(skin, Mapping):
            raise ValueError(f"skins[{index}] 必须是对象")
        skin_id = skin.get("skin_id")
        if not isinstance(skin_id, str) or not skin_id:
            raise ValueError(f"skins[{index}].skin_id 不能为空")
        if skin_id in skin_ids:
            raise ValueError(f"skins 存在重复 skin_id: {skin_id}")
        skin_ids.append(skin_id)
        _require_game_path(skin.get("texture"), f"skins[{index}].texture")

    kits = normalized.get("kits")
    if not isinstance(kits, list) or len(kits) != len(KIT_IDS):
        raise ValueError("appearance kits 必须包含 5 个候选")
    kit_ids = []
    for index, kit in enumerate(kits):
        if not isinstance(kit, Mapping):
            raise ValueError(f"kits[{index}] 必须是对象")
        set_id = kit.get("set_id")
        if not isinstance(set_id, str) or not set_id:
            raise ValueError(f"kits[{index}].set_id 不能为空")
        if set_id in kit_ids:
            raise ValueError(f"kits 存在重复 Set ID: {set_id}")
        kit_ids.append(set_id)
        _require_game_path(kit.get("jersey_material"), f"kits[{index}].jersey_material")
        _require_game_path(kit.get("shorts_material"), f"kits[{index}].shorts_material")
    if tuple(sorted(kit_ids)) != KIT_IDS:
        raise ValueError("kits 必须完整覆盖 set_id 01-05")

    return normalized


def _validate_numbering(numbering: Any) -> Dict[str, Any]:
    """验证 v2 号码配置及其 UE 资产路径。"""
    if not isinstance(numbering, Mapping):
        raise ValueError("appearance v2 numbering 必须是对象")
    required = {
        "min",
        "max",
        "unique",
        "placement",
        "bone",
        "atlas",
        "decal_material",
        "parameter",
        "mask_proxy_mesh",
        "mask_proxy_material",
        "mask_post_process_material",
        "mask_stencil_start",
    }
    if set(numbering) != required:
        missing = sorted(required - set(numbering))
        extra = sorted(set(numbering) - required)
        details = []
        if missing:
            details.append("缺少 " + ",".join(missing))
        if extra:
            details.append("包含未知 " + ",".join(extra))
        raise ValueError("appearance v2 numbering 配置非法: " + "；".join(details))
    if (
        type(numbering["min"]) is not int
        or type(numbering["max"]) is not int
        or numbering["min"] != 1
        or numbering["max"] != 99
    ):
        raise ValueError("appearance v2 numbering 范围必须为 1..99")
    if numbering["unique"] is not True:
        raise ValueError("appearance v2 numbering.unique 必须为 true")
    if numbering["placement"] != "back":
        raise ValueError("appearance v2 numbering.placement 必须为 back")
    if numbering["bone"] != "spine_03":
        raise ValueError("appearance v2 numbering.bone 必须为 spine_03")
    if numbering["parameter"] != "NumberIndex":
        raise ValueError("appearance v2 numbering.parameter 必须为 NumberIndex")
    if (
        type(numbering["mask_stencil_start"]) is not int
        or numbering["mask_stencil_start"] != 32
    ):
        raise ValueError("appearance v2 numbering.mask_stencil_start 必须为 32")
    for field in (
        "atlas",
        "decal_material",
        "mask_proxy_mesh",
        "mask_proxy_material",
        "mask_post_process_material",
    ):
        path = _require_game_path(numbering[field], f"numbering.{field}")
        segments = path[len("/Game/"):].split("/")
        if any(not segment.strip() for segment in segments):
            raise ValueError(f"numbering.{field} 必须是完整 /Game/ 资产路径")
        package_leaf, has_object_name, object_name = segments[-1].partition(".")
        if not package_leaf.strip() or (has_object_name and not object_name.strip()):
            raise ValueError(f"numbering.{field} 必须包含有效资产叶段")
    return dict(numbering)


def derive_appearance_seeds(ue_visual_seed: int) -> Dict[str, int]:
    """从既有 ue_visual_seed 派生互相独立的外观命名空间 seed。"""
    seed = _require_visual_seed(ue_visual_seed, "ue_visual_seed")
    result: Dict[str, int] = {}
    for namespace in ("model", "skin", "kit"):
        payload = f"{APPEARANCE_POLICY}:{seed}:{namespace}".encode("utf-8")
        result[namespace] = int.from_bytes(hashlib.sha256(payload).digest()[:4], "big") & _MAX_SEED
    return result


def derive_jersey_number_seed(ue_visual_seed: int) -> int:
    """按 v2 独立字节协议派生球衣号码命名空间 seed。"""
    seed = _require_visual_seed(ue_visual_seed, "ue_visual_seed")
    payload = f"{APPEARANCE_POLICY_V2}:{seed}:jersey_number".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big") & _MAX_SEED


def catalog_fingerprint(catalog: Mapping[str, Any]) -> str:
    """返回完整、去副作用的资产目录 fingerprint。"""
    return _sha256_hex(_normalize_catalog(catalog))


def _rank_candidate(
    namespace: str,
    namespace_seed: int,
    entity_id: str,
    candidate_id: Any,
    *,
    policy: str = APPEARANCE_POLICY,
) -> Tuple[bytes, str]:
    candidate_text = str(candidate_id)
    payload = (
        f"{policy}:{_RANK_NAMESPACE}:{namespace}:{namespace_seed}:"
        f"{entity_id}:{candidate_text}"
    ).encode("utf-8")
    return hashlib.sha256(payload).digest(), candidate_text


def _select_candidate(
    candidates: Iterable[Mapping[str, Any]],
    *,
    namespace: str,
    namespace_seed: int,
    entity_id: str,
    candidate_key: str,
    policy: str = APPEARANCE_POLICY,
) -> Mapping[str, Any]:
    return min(
        candidates,
        key=lambda candidate: _rank_candidate(
            namespace,
            namespace_seed,
            entity_id,
            candidate[candidate_key],
            policy=policy,
        ),
    )


def _assign_jersey_numbers(namespace_seed: int) -> Dict[str, int]:
    """按固定实体顺序贪心分配未使用的 1..99 号码。"""
    assigned: Dict[str, int] = {}
    used = set()
    for entity_id in ENTITY_IDS:
        ranked_numbers = sorted(
            range(1, 100),
            key=lambda number: _rank_candidate(
                "jersey_number",
                namespace_seed,
                entity_id,
                number,
                policy=APPEARANCE_POLICY_V2,
            ),
        )
        number = next(number for number in ranked_numbers if number not in used)
        assigned[entity_id] = number
        used.add(number)
    return assigned


def _meta_entities(meta: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    entities = meta.get("entities")
    if not isinstance(entities, list):
        raise ValueError("meta.entities 必须是列表")
    ball_count = sum(
        1
        for entity in entities
        if isinstance(entity, Mapping) and entity.get("id") == "BALL"
    )
    if ball_count > 1:
        raise ValueError("meta.entities 中 BALL 不能重复")
    if len(entities) not in (len(ENTITY_IDS), len(ENTITY_IDS) + 1):
        raise ValueError("meta.entities 必须包含 10 名球员和可选的 BALL")

    by_id: Dict[str, Dict[str, Any]] = {}
    for index, entity in enumerate(entities):
        if not isinstance(entity, Mapping):
            raise ValueError(f"meta.entities[{index}] 必须是对象")
        entity_id = entity.get("id")
        if entity_id == "BALL":
            if "team" not in entity or entity["team"] is not None:
                raise ValueError("BALL 的 team 必须为 null")
            if entity.get("is_goalkeeper") is not False:
                raise ValueError("BALL.is_goalkeeper 必须为 false")
            continue
        if entity_id in by_id:
            raise ValueError(f"meta.entities 存在重复 entity id: {entity_id}")
        if entity_id not in ENTITY_IDS:
            raise ValueError(f"meta.entities 出现非法 entity id: {entity_id}")
        expected_team = "left" if entity_id.startswith("L") else "right"
        if entity.get("team") != expected_team:
            raise ValueError(f"{entity_id} 的 team 必须为 {expected_team}")
        if not isinstance(entity.get("is_goalkeeper"), bool):
            raise ValueError(f"{entity_id}.is_goalkeeper 必须明确为 bool")
        by_id[entity_id] = dict(entity)

    if set(by_id) != set(ENTITY_IDS):
        raise ValueError("meta.entities 必须完整覆盖 L0-L4 和 R0-R4")
    for team in ("left", "right"):
        goalkeepers = [
            entity_id
            for entity_id, entity in by_id.items()
            if entity["team"] == team and entity["is_goalkeeper"]
        ]
        if len(goalkeepers) != 1:
            raise ValueError(f"{team} 队必须恰好有一名 goalkeeper")
    return by_id


def _ue_visual_seed(meta: Mapping[str, Any]) -> int:
    randomness = meta.get("randomness")
    if not isinstance(randomness, Mapping):
        raise ValueError("meta.randomness.ue_visual_seed 缺失或非法")
    try:
        return _require_visual_seed(
            randomness["ue_visual_seed"], "meta.randomness.ue_visual_seed"
        )
    except (KeyError, ValueError) as exc:
        raise ValueError("meta.randomness.ue_visual_seed 缺失或非法") from exc


def _root_seed(meta: Mapping[str, Any]) -> int:
    randomness = meta.get("randomness")
    if isinstance(randomness, Mapping) and randomness.get("root_seed") is not None:
        return _require_integer_seed(
            randomness["root_seed"], "meta.randomness.root_seed"
        )
    source = meta.get("source")
    if isinstance(source, Mapping) and source.get("seed") is not None:
        return _require_integer_seed(source["seed"], "meta.source.seed")
    raise ValueError("meta 缺少 root seed")


def _kit_class(entity: Mapping[str, Any]) -> str:
    if entity["is_goalkeeper"]:
        return "left_goalkeeper" if entity["team"] == "left" else "right_goalkeeper"
    return "left_outfield" if entity["team"] == "left" else "right_outfield"


def _manifest_without_fingerprint(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(dict(manifest))
    payload.pop("fingerprint", None)
    return payload


def _manifest_fingerprint(manifest: Mapping[str, Any]) -> str:
    return _sha256_hex(_manifest_without_fingerprint(manifest))


def build_appearance_manifest(
    meta: Mapping[str, Any],
    frames_path: Path,
    catalog: Mapping[str, Any],
) -> Dict[str, Any]:
    """根据 episode 元数据和轨迹原始字节生成确定性的外观 manifest。"""
    normalized_catalog = _normalize_catalog(catalog)
    entities = _meta_entities(meta)
    if not frames_path.is_file():
        raise ValueError(f"frames.jsonl 不存在: {frames_path}")

    visual_seed = _ue_visual_seed(meta)
    namespace_seeds = derive_appearance_seeds(visual_seed)
    is_v2 = normalized_catalog["policy"] == APPEARANCE_POLICY_V2
    if is_v2:
        namespace_seeds["jersey_number"] = derive_jersey_number_seed(visual_seed)
    models = normalized_catalog["models"]
    skins = normalized_catalog["skins"]
    kits = normalized_catalog["kits"]
    selected_kits = sorted(
        kits,
        key=lambda kit: _rank_candidate(
            "kit", namespace_seeds["kit"], "kit", kit["set_id"]
        ),
    )[:4]
    kit_classes = {
        kit_class: selected_kit["set_id"]
        for kit_class, selected_kit in zip(KIT_CLASSES, selected_kits)
    }
    models_by_id = {model["player_id"]: model for model in models}
    skins_by_id = {skin["skin_id"]: skin for skin in skins}
    kits_by_id = {kit["set_id"]: kit for kit in kits}
    jersey_numbers = (
        _assign_jersey_numbers(namespace_seeds["jersey_number"])
        if is_v2
        else {}
    )

    manifest_entities = []
    for entity_id in ENTITY_IDS:
        meta_entity = entities[entity_id]
        model = _select_candidate(
            models,
            namespace="model",
            namespace_seed=namespace_seeds["model"],
            entity_id=entity_id,
            candidate_key="player_id",
            policy=APPEARANCE_POLICY,
        )
        skin = _select_candidate(
            skins,
            namespace="skin",
            namespace_seed=namespace_seeds["skin"],
            entity_id=entity_id,
            candidate_key="skin_id",
            policy=APPEARANCE_POLICY,
        )
        kit_class = _kit_class(meta_entity)
        kit = kits_by_id[kit_classes[kit_class]]
        entity_manifest = {
            "entity_id": entity_id,
            "team": meta_entity["team"],
            "is_goalkeeper": meta_entity["is_goalkeeper"],
            "kit_class": kit_class,
            "player_id": model["player_id"],
            "mesh": model["mesh"],
            "anim_class": model["anim_class"],
            "skeleton": model["skeleton"],
            "skin_id": skin["skin_id"],
            "skin_texture": skin["texture"],
            "kit_set_id": kit["set_id"],
            "jersey_material": kit["jersey_material"],
            "shorts_material": kit["shorts_material"],
        }
        if is_v2:
            entity_manifest["jersey_number"] = jersey_numbers[entity_id]
        manifest_entities.append(entity_manifest)

    manifest: Dict[str, Any] = {
        "schema": APPEARANCE_SCHEMA,
        "version": APPEARANCE_VERSION_V2 if is_v2 else APPEARANCE_VERSION,
        "episode_id": meta.get("episode_id", ""),
        "root_seed": _root_seed(meta),
        "ue_visual_seed": visual_seed,
        "policy": normalized_catalog["policy"],
        "namespace_seeds": namespace_seeds,
        "trajectory_sha256": hashlib.sha256(frames_path.read_bytes()).hexdigest(),
        "catalog_id": normalized_catalog["catalog_id"],
        "catalog_fingerprint": catalog_fingerprint(normalized_catalog),
        "body_texture_parameter": normalized_catalog["body_texture_parameter"],
        "kit_classes": kit_classes,
        "entities": manifest_entities,
    }
    if is_v2:
        manifest["numbering"] = deepcopy(normalized_catalog["numbering"])
    manifest["fingerprint"] = _manifest_fingerprint(manifest)
    return manifest


def validate_appearance_manifest(
    manifest: Mapping[str, Any],
    *,
    meta: Mapping[str, Any],
    frames_path: Path,
    catalog: Mapping[str, Any],
) -> List[str]:
    """返回 manifest 与当前 episode 输入之间的全部不一致项。"""
    errors: List[str] = []
    if not isinstance(manifest, Mapping):
        return ["appearance manifest 必须是对象"]
    try:
        expected = build_appearance_manifest(meta, frames_path, catalog)
    except (OSError, TypeError, ValueError, KeyError, OverflowError) as exc:
        return [f"appearance 输入无效: {exc}"]

    expected_policy = expected["policy"]
    expected_version = expected["version"]
    for key, expected_value in expected.items():
        if manifest.get(key) != expected_value:
            if key == "trajectory_sha256":
                errors.append("trajectory_sha256 与当前 frames.jsonl 不一致")
            elif key == "catalog_fingerprint":
                errors.append("catalog_fingerprint 与当前 catalog 不一致")
            elif key == "fingerprint":
                errors.append("manifest fingerprint 无效")
            elif key == "entities" and expected_policy == APPEARANCE_POLICY_V2:
                actual_entities = manifest.get("entities")
                if isinstance(actual_entities, list):
                    expected_by_id = {
                        entity["entity_id"]: entity["jersey_number"]
                        for entity in expected_value
                    }
                    for entity in actual_entities:
                        if not isinstance(entity, Mapping):
                            continue
                        entity_id = entity.get("entity_id")
                        if (
                            isinstance(entity_id, str)
                            and entity_id in expected_by_id
                            and entity.get("jersey_number")
                            != expected_by_id[entity_id]
                        ):
                            errors.append(
                                f"manifest {entity_id}.jersey_number 与当前输入不一致"
                            )
                            break
                errors.append("manifest 字段 entities 与当前输入不一致")
            else:
                errors.append(f"manifest 字段 {key} 与当前输入不一致")
    if manifest.get("schema") != APPEARANCE_SCHEMA:
        errors.append("manifest schema 无效")
    if (
        type(manifest.get("version")) is not int
        or manifest.get("version") != expected_version
    ):
        errors.append("manifest version 无效")
    if manifest.get("policy") != expected_policy:
        errors.append("manifest policy 与当前 catalog 不一致")
    if expected_policy == APPEARANCE_POLICY:
        if "numbering" in manifest:
            errors.append("appearance v1 manifest 不允许 numbering 字段")
        entities = manifest.get("entities")
        if isinstance(entities, list) and any(
            isinstance(entity, Mapping) and "jersey_number" in entity
            for entity in entities
        ):
            errors.append("appearance v1 manifest 不允许 jersey_number 字段")
    else:
        _validate_manifest_jersey_numbers(manifest, errors)
    try:
        actual_fingerprint = _manifest_fingerprint(manifest)
        if manifest.get("fingerprint") != actual_fingerprint:
            errors.append("manifest fingerprint 无效")
    except (TypeError, ValueError):
        errors.append("manifest fingerprint 无法计算")
    return list(dict.fromkeys(errors))


def _validate_manifest_jersey_numbers(
    manifest: Mapping[str, Any], errors: List[str]
) -> None:
    """对 v2 manifest 的号码字段做结构级 fail-closed 检查。"""
    numbering = manifest.get("numbering")
    try:
        _validate_numbering(numbering)
    except (TypeError, ValueError) as exc:
        errors.append(f"manifest numbering 无效: {exc}")

    entities = manifest.get("entities")
    if not isinstance(entities, list):
        errors.append("manifest entities 必须是列表")
        return
    if len(entities) != len(ENTITY_IDS):
        errors.append(
            "manifest entities 必须完整包含十名球员; "
            f"actual entity IDs={[entity.get('entity_id') if isinstance(entity, Mapping) else entity for entity in entities]}"
        )
        return

    entity_ids = []
    numbers = []
    for index, entity in enumerate(entities):
        if not isinstance(entity, Mapping):
            errors.append(f"manifest entities[{index}] 必须是对象")
            continue
        entity_id = entity.get("entity_id")
        jersey_number = entity.get("jersey_number")
        entity_ids.append(entity_id)
        if type(jersey_number) is not int or not 1 <= jersey_number <= 99:
            errors.append(
                f"manifest entities[{index}].jersey_number 必须是 1..99 整数"
            )
        else:
            numbers.append(jersey_number)
    actual_ids = list(entity_ids)
    duplicate_ids = []
    for index, entity_id in enumerate(actual_ids):
        if any(entity_id == other for other in actual_ids[index + 1:]):
            if not any(entity_id == previous for previous in duplicate_ids):
                duplicate_ids.append(entity_id)
    extra_ids = [
        entity_id
        for entity_id in actual_ids
        if not isinstance(entity_id, str) or entity_id not in ENTITY_IDS
    ]
    missing_ids = [entity_id for entity_id in ENTITY_IDS if entity_id not in actual_ids]
    if duplicate_ids:
        errors.append(
            f"manifest entities 存在重复 entity_id; actual entity IDs={actual_ids}; "
            f"duplicate IDs={duplicate_ids}"
        )
    if extra_ids:
        errors.append(
            f"manifest entities 存在额外 entity_id; actual entity IDs={actual_ids}; "
            f"extra IDs={extra_ids}"
        )
    if missing_ids:
        errors.append(
            f"manifest entities 缺少 entity_id; actual entity IDs={actual_ids}; "
            f"missing IDs={missing_ids}"
        )
    if actual_ids != list(ENTITY_IDS):
        errors.append(
            "manifest entities 必须按固定 L0..L4,R0..R4 顺序排列; "
            f"actual entity IDs={actual_ids}"
        )
    if len(numbers) != len(ENTITY_IDS) or len(set(numbers)) != len(ENTITY_IDS):
        errors.append("manifest jersey_number 必须覆盖十人且互不重复")


def write_appearance_manifest(episode_dir: Path, manifest: Mapping[str, Any]) -> Path:
    """原子写入 episode provenance/appearance.json。"""
    output_dir = episode_dir / "provenance"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "appearance.json"
    payload = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ).encode("utf-8") + b"\n"

    file_descriptor, temp_name = tempfile.mkstemp(
        prefix=".appearance.", suffix=".tmp", dir=str(output_dir)
    )
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temp_name).replace(output_path)
    except Exception:
        try:
            Path(temp_name).unlink()
        except FileNotFoundError:
            pass
        raise
    return output_path
