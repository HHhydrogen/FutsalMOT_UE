"""原seed服装A/B的独立短样/300帧契约，不放宽历史诊断准入。"""
import hashlib
import json
from copy import deepcopy
from pose17_long_window_contract import WINDOWS, ORIGINAL_SHA, PACKAGE, CAMERAS, validate_roster

SCHEMA = 'futsalmot_pose17_seeded_kit_pair_v1'
SCOPE = 'same_real_GRF_motion_fixed_roster_seeded_kit_pair_not_original_weather'


def require(ok, text):
    if not ok: raise ValueError(text)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def context_payload(plan):
    result=deepcopy(plan)
    result.pop('attempt',None)
    kit=result['seeded_kit_pair']
    for key in ('variant','apply_original_seeded_kits','paired_context_sha256'):kit.pop(key,None)
    return result


def validate_seeded_kit_contract(plan):
    if 'v10_multiseed_contract' in plan:
        from pose17_multiseed_v10_contract import validate_v10_contract
        return validate_v10_contract(plan)
    if plan.get('green_seeded_kit_contract') is True:
        from pose17_green_kit_contract import validate_green_kit_contract
        return validate_green_kit_contract(plan)
    if 'seeded_kit_pair_contract' not in plan and 'seeded_kit_pair' not in plan:return False
    return validate_kit_core(plan,windows=WINDOWS,original_sha=ORIGINAL_SHA,package=PACKAGE,
        schema=SCHEMA,scope=SCOPE,floor_id='sport_blue_v1')


def validate_kit_core(plan,*,windows,original_sha,package,schema,scope,floor_id):
    """复用原数值/服装门禁；新scope必须提供独立固定身份，绝不改旧常量。"""
    require(plan.get('seeded_kit_pair_contract') is True and isinstance(plan.get('seeded_kit_pair'),dict),'服装配对需要独立明确opt-in')
    require(not any(k in plan for k in ('long_window_contract','long_window','location_pilot_contract','location_pilot')),'不能混用历史长窗/120帧准入')
    kit=plan['seeded_kit_pair'];seed=kit.get('seed');variant=kit.get('variant');stage=kit.get('stage')
    require(type(seed) is int and seed in windows and variant in ('A','B') and stage in ('short','full'),'服装seed/版本/阶段错误')
    start,end,split=windows[seed];count=3 if stage=='short' else 300
    require(kit.get('schema')==schema and kit.get('split')==split and kit.get('source_frame_range')==[start,start+count]
        and kit.get('floor_id')==floor_id and kit.get('apply_original_seeded_kits') is (variant=='B'),'配对split/源帧/地板/服装开关变化')
    require(plan.get('schema')=='futsalmot_pose17_smoke_plan_v1' and plan.get('source_scope')==scope
        and plan.get('diagnostic_scope')=='pose17_gpu_render_cpu_lbs_joint_diagnostic'
        and type(plan.get('start_frame')) is int and plan['start_frame']==start
        and type(plan.get('frame_count')) is int and plan['frame_count']==count
        and plan.get('capture_dimensions')==[3840,2160] and plan.get('pose_sampling_path')=='gpu_render_cpu_lbs','服装配对原生4K/源时间/采样路径不符')
    for key,value in dict(allow_joint_pose17_diagnostic=True,allow_gpu_render_cpu_lbs_diagnostic=True,
        allow_pie_visual_mesh_override=True,allow_pie_cpu_preparation=False,allow_pie_driver_hide=True).items():
        require(plan.get(key) is value,'原native门禁变化：'+key)
    require(type(plan.get('gpu_lbs_warmup_frames')) is int and 8<=plan['gpu_lbs_warmup_frames']<=120
        and plan.get('override_warmup_frames')==plan['gpu_lbs_warmup_frames'],'不能删减native预热')
    motion=plan.get('source_motion',{})
    require(motion.get('root_seed')==seed and motion.get('fps')==10
        and motion.get('source_frames_sha256')==original_sha[seed][0]
        and motion.get('source_meta_sha256')==original_sha[seed][1]
        and motion.get('selected_source_frame_range')==[start,end]
        and motion.get('context_source_frame_range')==[0,end],'原完整运动来源/前缀变化')
    validate_roster(plan.get('targets'))
    cameras=plan.get('cameras',[])
    require([c.get('camera_id') for c in cameras]==list(CAMERAS)
        and all(c.get('source_sequence')==package+f'/seed_{seed:08d}/LS_Cam_'+c['camera_id'][-2:] for c in cameras)
        and len({c.get('camera_actor_object_name') for c in cameras})==4,'四机位源路径/身份变化')
    binding=kit.get('binding',{})
    require(binding.get('source_policy')=='futsalmot_appearance_v1' and binding.get('root_seed')==seed
        and binding.get('no_new_random_assignment') is True and binding.get('numbers_enabled') is False
        and binding.get('original_full_trajectory_sha256')==original_sha[seed][0]
        and binding.get('pose_targets_fingerprint')==digest(plan['targets']),'必须复用原无号码服装清单，固定Pose模型')
    entities=binding.get('entities',[]);targets={r['entity_id']:r for r in plan['targets']}
    require(len(entities)==10 and {r.get('entity_id') for r in entities}==set(targets),'原服装实体集合变化')
    for row in entities:
        target=targets[row['entity_id']];role=row['kit_class'];set_id=binding['kit_classes'][role]
        require(row.get('actor_object_name')==target['actor_object_name'] and row.get('component_object_name')=='MPFBVisual'
            and row.get('kit_set_id')==set_id and set_id in ('01','02','03','04','05')
            and row.get('semantic_materials')=={k:'/Game/FutsalMOT/Characters/MPFB/Materials/M_MPFB_'+k+'_Set_'+set_id for k in ('Jersey','Shorts')},'原服装绑定或材质路径变化')
    require(kit.get('paired_context_sha256')==digest(context_payload(plan)),'除服装A/B外的context不一致')
    return True


def assert_seeded_kit_receipt(plan, receipt):
    if not validate_seeded_kit_contract(plan):return
    kit=plan['seeded_kit_pair'];apply=kit['apply_original_seeded_kits']
    require(receipt.get('seeded_kit_requested') is apply,'native服装开关没有实际读回')
    rows=receipt.get('seeded_kit_bindings',[])
    if not apply:
        require(not rows and not receipt.get('seeded_appearance_fingerprint'),'A基线不得混入服装替换')
        return
    require(receipt.get('seeded_appearance_fingerprint')==kit['binding']['source_appearance_fingerprint'] and len(rows)==10,'缺少十人原服装native证据')
    expected={'.'+r['actor_object_name']+'.MPFBVisual':r for r in kit['binding']['entities']}
    require(len({r.get('component_path') for r in rows})==10,'服装native组件重复')
    for row in rows:
        matched=[r for suffix,r in expected.items() if row.get('component_path','').endswith(suffix)]
        require(len(matched)==1,'服装native未匹配精确目标组件')
        target=matched[0];materials=target['semantic_materials']
        require(row.get('kit_set_id')==target['kit_set_id'] and all(row.get(flag) is True for flag in
            ('apply_succeeded','other_materials_preserved','mesh_animation_transform_preserved','live_readback_succeeded','gpu_lbs_eligible_after_kit','restore_attempted','restore_succeeded')),'服装实际应用/保持/恢复未通过')
        require(row.get('jersey_material_path','').split('.')[0]==materials['Jersey']
            and row.get('shorts_material_path','').split('.')[0]==materials['Shorts'],'native服装路径不符')
        require(type(row.get('applied_engine_frame')) is int and 0<=row['applied_engine_frame']<=receipt['gpu_lbs_prepared_engine_frame'],'服装未在GPU预热前应用')
    require(all(r.get('seeded_kit_readback_succeeded') is True for r in receipt['records']),'实际输出帧服装读回失败')
