"""号码计划的共享纯Python入口；复用既有分配协议。"""
from .number_uv_contract import ENTITY_IDS, DEFAULT_UV_RECT, assign_numbers, canonical_fingerprint, material_parameters

PLAN_SCHEMA = "futsalmot_episode_uv_numbers_v1"
RENDER_POLICY = "futsalmot_appearance_v1_uv_numbers"


def build_plan(manifest, config):
    """从已绑定的完整随机外观清单派生号码，保留所有原分配。"""
    if manifest.get("policy") != "futsalmot_appearance_v1":
        raise ValueError("UV叠加入口要求原 appearance v1 完整随机清单")
    entities = manifest.get("entities", [])
    if [e.get("entity_id") for e in entities] != list(ENTITY_IDS):
        raise ValueError("外观清单必须包含固定身份顺序的十人")
    numbers = assign_numbers(manifest["ue_visual_seed"])
    rect = config.get("uv_rect", list(DEFAULT_UV_RECT))
    result = {"schema": PLAN_SCHEMA, "version": 1,
              "appearance_fingerprint": manifest["fingerprint"],
              "trajectory_sha256": manifest["trajectory_sha256"],
              "episode_id": manifest["episode_id"], "ue_visual_seed": manifest["ue_visual_seed"],
              "uv_rect": rect, "flip_u": config.get("flip_u", True),
              "flip_v": config.get("flip_v", True), "entities": []}
    if 'atlas_id' in config:
        from .number_typography import atlas_profile
        result['atlas'] = atlas_profile(config['atlas_id'])
        result['print_profile'] = config.get('print_profile','custom')
    if config.get('ink_profile') is not None:
        from .number_typography import INK_PROFILE
        if config['ink_profile'] != INK_PROFILE:raise ValueError('未知号码墨色规则')
        result['ink_profile']=INK_PROFILE
    for i, entity in enumerate(entities):
        material_parameters(numbers[entity["entity_id"]], entity["entity_id"], rect,
                            flip_u=result["flip_u"], flip_v=result["flip_v"])
        # 原Set_02为白球衣，使用黑色数字；其余保持已验白色印花。
        ink = [0.0, 0.0, 0.0] if entity["kit_set_id"] == "02" else [1.0, 1.0, 1.0]
        if result.get('ink_profile') is not None:
            from .number_typography import ink_for_kit
            ink=ink_for_kit(entity['kit_set_id'])
        result["entities"].append(dict(entity, jersey_number=numbers[entity["entity_id"]],
                                       instance_mask_id=i + 1, number_mask_id=32 + i, ink_color=ink))
    result["fingerprint"] = canonical_fingerprint(result)
    return result
