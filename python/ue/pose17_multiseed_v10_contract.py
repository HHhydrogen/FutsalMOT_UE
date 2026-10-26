"""v10三个新增运动的独立身份；不伪装旧两seed绿色A/B准入。"""
from pathlib import Path
from pose17_seeded_kit_contract import require, digest, context_payload, validate_kit_core
from pose17_green_kit_contract import expected_material, GREEN_CATALOG, select_floor_id

SCHEMA = 'futsalmot_pose17_multiseed_v10_v1'
SCOPE = 'v10_independent_motion_original_seeded_kit_green_location_diagnostic'
PACKAGE = '/Game/FutsalMOT/Development/Pose17/multiseed_v10_a01'
WINDOWS = {1042:(152,452,'train'),1044:(383,683,'train'),1131:(565,865,'train')}
ORIGINAL_SHA = {
    1042:('7d61b45ae798311fe4b0984b30fb34fb0d89e207b2e9da8018b2bf93c9101534',
          '4db65a28192ad5798992e05e96fbcf0c31ca70e81b38069a17cad75af2770271'),
    1044:('3cd73cf29e7077b28966a44444c8af6656ba7960421e356365476683358d6840',
          '42911dfa4d7db26dcb02a50ac4acda6f722a8132bc076ce25b7785365f2a1715'),
    1131:('ecad6ce77cf28c09f2857774049c024c3256f2762a4be052ab719dcf365b89a0',
          '0379e801e2db2f42753a9f9702399b375ecb3644e98e79e27d3d50e8c97cd45a')}


def validate_v10_contract(plan):
    kit = plan.get('seeded_kit_pair', {}); seed = kit.get('seed')
    require(plan.get('v10_multiseed_contract') is True and plan.get('green_seeded_kit_contract') is True
            and kit.get('variant') == 'B' and seed in WINDOWS, 'v10仅新增三运动的原seed球衣B，不接旧A/B身份')
    floor_id = select_floor_id(seed, catalog=GREEN_CATALOG)
    recipe = kit.get('green_floor', {}); choice = next(v for v in GREEN_CATALOG if v['id'] == floor_id)
    require(recipe.get('schema') == 'futsalmot_green_floor_runtime_recipe_v1'
            and recipe.get('id') == floor_id and recipe.get('material') == expected_material(floor_id)
            and recipe.get('albedo_gain_linear') == choice['albedo_gain_linear']
            and recipe.get('sequence_constant') is True and recipe.get('purpose') == 'v10_multiseed',
            '绿色原seed/材质/gain/固定时序变化')
    proof = recipe.get('creation_proof', {})
    require(isinstance(proof.get('path'),str) and len(proof.get('sha256','')) == 64, '缺绿色真实来源')
    source = kit.get('source_input', {}); motion = plan.get('source_motion', {})
    require(isinstance(source.get('path'),str) and len(source.get('sha256','')) == 64
            and motion.get('source_input') == source and motion.get('sequence_frame_equals_source_step') is True
            and motion.get('capture_local_zero_source_step') == WINDOWS[seed][0], '源输入/显式时间映射错误')
    require(Path(source['path']).as_posix().endswith(f'/v10_motion_sources_a01/seed_{seed:08d}/source_input.json')
            and Path(motion.get('source_build_receipt','')).as_posix().endswith('/multiseed_v10_a01/P2_sources_prepare.json'),
            '不得复用旧P2来源收据')
    require(kit.get('paired_context_sha256') == digest(context_payload(plan)), 'v10上下文变化')
    return validate_kit_core(plan,windows=WINDOWS,original_sha=ORIGINAL_SHA,package=PACKAGE,
        schema=SCHEMA,scope=SCOPE,floor_id=floor_id)
