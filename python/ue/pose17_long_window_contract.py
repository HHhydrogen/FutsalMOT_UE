"""独立300帧长窗口候选契约；不放宽旧120帧或普通诊断门禁。"""
from copy import deepcopy
import math
import re

from pose17_calibration_assets import JOINT_VISUAL_IDS,production_visual_mesh

BATCH_ID='long_interaction_floor_30s_a01'
WINDOWS={1048:(0,300,'train'),1102:(20,320,'synthetic_dev')}
FLOORS=('sport_blue_v1','sport_terracotta_v1')
CAMERAS=tuple('CineCam_%02d'%i for i in range(1,5))
PACKAGE='/Game/FutsalMOT/Development/Pose17/'+BATCH_ID
SCOPE='pose17_gpu_render_cpu_lbs_joint_diagnostic'
SOURCE_SCOPE='real_GRF_motion_long_window_diagnostic_fixed_roster_two_floor_location_only_not_original_weather_or_appearance'
ORIGINAL_SHA={
    1048:('cebe1bf84ff16e94ca18a6bca883ecfb8cc1847bca3041262b1f9d82a2e3ce8b',
          '9ea713988046680a9fce1d0b21b6539e7e539bcc943d091289d69b8b543330a7'),
    1102:('e2201ef682a2fe6e137c0e4b11faf8f68a398298af12673c34eeb36cc11e88f5',
          '1a59f11f7aac73c93162db0142fbe45b9aa376340bc711a3773c68792ef994b6')}


def require(ok,message):
    if not ok:raise ValueError(message)


def is_sha(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None


def v1_annotation_to_source(clip,frame_index):
    """v1 annotation为一基；偏移来自原clip，绝不假定local0就是GRF0。"""
    selected=clip['source_selection']['source_step_range'];start,end=selected
    require(type(clip.get('frame_count')) is int and type(frame_index) is int and 1<=frame_index<=clip['frame_count']
        and type(start) is int and type(end) is int and end-start==clip['frame_count'],
        'v1注释index/原clip范围不合法')
    return start+frame_index-1


def source_prefix(meta,frames,seed):
    """保留0..end运动历史及原step/time；不是把所选300帧重基后导入。"""
    require(type(seed) is int and seed in WINDOWS,'只允许本轮两seed')
    start,end,_=WINDOWS[seed]
    require(meta.get('schema')=='grf_ue_episode' and meta.get('source',{}).get('seed')==seed
        and meta['source'].get('environment')=='google_research_football'
        and meta['source'].get('scenario')=='5_vs_5','GRF源身份不符')
    require(meta.get('timing')==dict(source_step_seconds=.1,playback_fps=10,num_steps=1800)
        and len(frames)==1800,'原始源必须是1800步/10FPS')
    for index,row in enumerate(frames[:end]):
        require(type(row.get('step')) is int and row['step']==index
            and type(row.get('time_seconds')) in (int,float) and math.isfinite(row['time_seconds'])
            and abs(row['time_seconds']-index*.1)<=1e-12,'源前缀不连续或time/step被重基')
        players=row.get('players',[])
        require(len(players)==10 and {p['id'] for p in players}==set(JOINT_VISUAL_IDS),'每帧十实体不完整/重复')
        positions=[p.get('position_m') for p in players]+[row.get('ball',{}).get('position_m')]
        require(all(isinstance(p,list) and len(p)==3 and all(type(v) in (int,float) and math.isfinite(v) for v in p)
            for p in positions),'源位置必须是有限三维，不裁剪或补造')
    result=deepcopy(meta);result['timing']['num_steps']=end
    return result,deepcopy(frames[:end])


def mapping_rows(clip,seed):
    start,end,_=WINDOWS[seed];original_start,original_end=clip['source_selection']['source_step_range']
    require(original_start<=start<end<=original_end,'新窗口不在原冻结活动窗内')
    rows=[]
    for local,source in enumerate(range(start,end)):
        v1_index=source-original_start+1
        require(v1_annotation_to_source(clip,v1_index)==source,'v1/GRF映射不一致')
        rows.append(dict(capture_local_index=local,sequence_frame=source,grf_source_step=source,
            capture_time_seconds=local*.1,source_time_seconds=source*.1,
            v1_local_index_zero_based=source-original_start,v1_annotation_index_one_based=v1_index))
    return rows


def validate_roster(targets):
    require(isinstance(targets,list) and [t.get('entity_id') for t in targets]==list(JOINT_VISUAL_IDS),
            '只允许固定十实体及顺序')
    require(len({t.get('actor_object_name') for t in targets})==10,'Actor必须各自唯一')
    for target in targets:
        entity=target['entity_id'];player=JOINT_VISUAL_IDS[entity]
        require(type(target.get('calibration_player_id')) is int and target['calibration_player_id']==player
            and target.get('component_object_name')=='MPFBVisual'
            and target.get('sequence_binding_name')=='Player_'+entity
            and isinstance(target.get('landmark_manifest'),str)
            and isinstance(target.get('actor_object_name'),str) and target['actor_object_name'],
            '真实mesh/绑定/manifest路径缺失')
        require(target.get('diagnostic_visual_mesh_override')==(None if player==3 else production_visual_mesh(player)),
                '必须固定已验七模型roster，不能按prefix猜mesh')


def validate_long_window_contract(plan):
    """没有新字段返回false；有任一新字段就严格验证，不能借旧bool放行。"""
    if 'long_window_contract' not in plan and 'long_window' not in plan:return False
    require(plan.get('long_window_contract') is True and isinstance(plan.get('long_window'),dict),
            '长窗需要独立显式opt-in')
    require('location_pilot_contract' not in plan and 'location_pilot' not in plan,'不能携带或伪装旧120帧契约')
    long=plan['long_window'];seed=long.get('seed')
    require(type(seed) is int and seed in WINDOWS,'长窗只允许1048/1102')
    start,end,split=WINDOWS[seed];floor=long.get('floor_variant_id')
    expected=dict(schema='futsalmot_pose17_long_window_v1',batch_id=BATCH_ID,seed=seed,split=split,
        source_frame_range=[start,end],frame_count=300,floor_variant_id=floor,
        location_supervision=True,visibility_supervision=False,formal_pose_release=False)
    require(long==expected and floor in FLOORS
        and type(long.get('frame_count')) is int and all(type(i) is int for i in long['source_frame_range'])
        and all(type(long.get(k)) is bool for k in ('location_supervision','visibility_supervision','formal_pose_release')),
        '长窗seed/split/时段/地板/监督边界变化')
    require(plan.get('schema')=='futsalmot_pose17_smoke_plan_v1' and plan.get('diagnostic_scope')==SCOPE
        and plan.get('source_scope')==SOURCE_SCOPE and plan.get('pose_sampling_path')=='gpu_render_cpu_lbs'
        and type(plan.get('start_frame')) is int and plan['start_frame']==start
        and type(plan.get('frame_count')) is int and plan['frame_count']==300
        and plan.get('review_frame_indices')==[150] and type(plan['review_frame_indices'][0]) is int
        and plan.get('capture_dimensions')==[3840,2160] and all(type(i) is int for i in plan['capture_dimensions']),
        '长窗必须精确300帧/四机位4K，不放宽普通短诊断')
    for key,value in dict(allow_joint_pose17_diagnostic=True,allow_gpu_render_cpu_lbs_diagnostic=True,
        allow_pie_visual_mesh_override=True,allow_pie_cpu_preparation=False,allow_pie_driver_hide=True,
        allow_unaccepted_landmarks_for_diagnostic=True).items():
        require(plan.get(key) is value,'原native显式诊断门禁变化: '+key)
    require(type(plan.get('gpu_lbs_warmup_frames')) is int and 8<=plan['gpu_lbs_warmup_frames']<=120
        and plan.get('override_warmup_frames')==plan['gpu_lbs_warmup_frames'],'保留原实际GPU/override预热')
    motion=plan.get('source_motion',{})
    require(motion.get('root_seed')==seed and type(motion.get('root_seed')) is int
        and motion.get('fps')==10 and type(motion.get('fps')) is int
        and motion.get('source_frames_sha256')==ORIGINAL_SHA[seed][0]
        and motion.get('source_meta_sha256')==ORIGINAL_SHA[seed][1]
        and motion.get('selected_source_frame_range')==[start,end]
        and motion.get('context_source_frame_range')==[0,end]
        and motion.get('sequence_frame_equals_source_step') is True
        and type(motion.get('capture_local_zero_source_step')) is int and motion['capture_local_zero_source_step']==start
        and is_sha(motion.get('source_input',{}).get('sha256'))
        and isinstance(motion['source_input'].get('path'),str),'来源/前缀/绝对帧映射不完整')
    validate_roster(plan.get('targets'))
    cameras=plan.get('cameras',[]);package=PACKAGE+f'/seed_{seed:08d}'
    require([c.get('camera_id') for c in cameras]==list(CAMERAS)
        and len({c.get('camera_actor_object_name') for c in cameras})==4
        and all(c.get('source_sequence')==package+'/LS_Cam_'+c['camera_id'][-2:] for c in cameras),
        '四个原camera或新独立源Sequence路径不符')
    pair=plan.get('floor_pair',{})
    require(pair.get('pair_id')==BATCH_ID+f'_s{seed:08d}' and pair.get('floor_id')==floor
        and pair.get('application_status')=='planned_not_applied'
        and pair.get('requires_fresh_P2_context_and_material_transaction') is True,'地板配对不能冒称已应用/动态验证')
    return True


def validate_floor_pair(plans):
    require(len(plans)==2 and {p.get('long_window',{}).get('floor_variant_id') for p in plans}==set(FLOORS),
            '每运动窗口必须蓝/红棕恰一份')
    normalized=[]
    for plan in plans:
        validate_long_window_contract(plan);copy=deepcopy(plan)
        copy.pop('attempt');copy['long_window'].pop('floor_variant_id');copy['floor_pair'].pop('floor_id')
        normalized.append(copy)
    require(normalized[0]==normalized[1],'配对地板以外运动/相机/roster/split/context计划变化')
    return True
