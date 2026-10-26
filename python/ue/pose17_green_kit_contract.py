"""新绿色球衣契约；原蓝地板schema保持不变，不升级历史诊断资格。"""
from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from grf_ue_bridge.green_floor import GREEN_CATALOG,ORIGINAL_MATERIAL
from grf_ue_bridge.floor_diversity import select_floor_id
from pose17_seeded_kit_contract import require,digest,context_payload

SCHEMA='futsalmot_pose17_green_seeded_kit_pair_v1'
SCOPE='same_real_GRF_motion_fixed_roster_green_seeded_kit_pair_not_original_weather'
DEST='/Game/FutsalMOT/Environment/Floors/GreenV1/'


def expected_material(floor_id):
    require(floor_id in {v['id'] for v in GREEN_CATALOG},'不是绿色目录候选')
    if floor_id=='grass_original_v1':return ORIGINAL_MATERIAL
    name='MI_'+floor_id
    return DEST+name+'.'+name


def validate_green_kit_contract(plan):
    import pose17_seeded_kit_contract as old
    kit=plan.get('seeded_kit_pair',{})
    require(plan.get('green_seeded_kit_contract') is True and kit.get('schema')==SCHEMA
        and plan.get('source_scope')==SCOPE,'绿色独立opt-in/schema错误')
    recipe=kit.get('green_floor',{})
    floor_id=kit.get('floor_id');choices=[v for v in GREEN_CATALOG if v['id']==floor_id]
    require(len(choices)==1 and recipe.get('schema')=='futsalmot_green_floor_runtime_recipe_v1'
        and recipe.get('id')==floor_id and recipe.get('albedo_gain_linear')==choices[0]['albedo_gain_linear']
        and recipe.get('material')==expected_material(floor_id) and recipe.get('sequence_constant') is True,
        '绿色材质/gain/序列内固定约束改变')
    proof=recipe.get('creation_proof',{})
    require(isinstance(proof.get('path'),str) and len(proof.get('sha256',''))==64,'缺真实材质创建来源')
    purpose=recipe.get('purpose')
    if purpose=='seeded_kit_pair':
        require(floor_id==select_floor_id(kit.get('seed'),catalog=GREEN_CATALOG),'主配对不复用原floor独立seed流')
    else:
        require(purpose=='palette_check' and kit.get('seed')==1048 and kit.get('variant')=='B'
            and kit.get('stage')=='short','颜色边界只在事前train1048短样检查，不用dev选色')
    require(kit.get('paired_context_sha256')==digest(context_payload(plan)),'绿色配对上下文改变')
    # 归一化副本仅复用已验运动/roster/服装/源范围检查，原计划及来源字节不修改。
    normalized=deepcopy(plan);normalized.pop('green_seeded_kit_contract')
    normalized['source_scope']=old.SCOPE
    normalized['seeded_kit_pair'].pop('green_floor')
    normalized['seeded_kit_pair'].update(schema=old.SCHEMA,floor_id='sport_blue_v1')
    normalized['seeded_kit_pair']['paired_context_sha256']=digest(context_payload(normalized))
    return old.validate_seeded_kit_contract(normalized)
