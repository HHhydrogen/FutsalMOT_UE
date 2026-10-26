"""单机位生命周期的显式子集契约；源计划仍保留完整四机位，不伪造整组完成。"""
import re
from pose17_seeded_kit_contract import validate_seeded_kit_contract,require

SCHEMA='futsalmot_seeded_kit_single_camera_capture_v1'


def select_capture_cameras(plan,camera_id=None):
    if camera_id is None:return list(plan['cameras'])
    require(validate_seeded_kit_contract(plan) and plan['seeded_kit_pair']['stage']=='full'
        and plan['frame_count']==300,'单机位分区只准入明确seed球衣300帧契约')
    selected=[c for c in plan['cameras'] if c['camera_id']==camera_id]
    require(len(plan['cameras'])==4 and len(selected)==1,'分区须来自原四机位的精确一个camera_id')
    return selected


def make_capture_scope(plan,camera_id,plan_sha256):
    require(isinstance(plan_sha256,str) and re.fullmatch('[0-9a-f]{64}',plan_sha256),'缺完整计划SHA')
    selected=select_capture_cameras(plan,camera_id)
    require(len(selected)==1 and camera_id is not None,'分区不得隐式变成整组')
    return dict(schema=SCHEMA,camera_ids=[camera_id],canonical_camera_ids=[c['camera_id'] for c in plan['cameras']],
        plan_sha256=plan_sha256,paired_context_sha256=plan['seeded_kit_pair']['paired_context_sha256'],
        source_frame_range=plan['seeded_kit_pair']['source_frame_range'],frames=300,
        full_four_camera_group_complete=False)


def validate_capture_scope(plan,scope,plan_sha256):
    require(isinstance(scope,dict) and isinstance(scope.get('camera_ids'),list) and len(scope['camera_ids'])==1,'缺实际单机位范围')
    expected=make_capture_scope(plan,scope['camera_ids'][0],plan_sha256)
    require(scope==expected,'分区范围/源时间/整组完成标记与原计划不同')
    return select_capture_cameras(plan,scope['camera_ids'][0])


def session_cameras(session):
    cameras=session.get('capture_cameras',session['plan']['cameras'])
    scope=session['state'].get('capture_scope')
    if scope is not None:
        require(cameras==validate_capture_scope(session['plan'],scope,session['state']['plan_sha256']),
            '内存Queue实际机位与持久范围不匹配')
    else:require(cameras==session['plan']['cameras'],'没有独立分区契约不得缩减机位')
    return cameras
