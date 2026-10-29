"""五个必选与独立随机局部相机的配置/运行入口检查。"""
import json
import random
from copy import deepcopy
from pathlib import Path

import pytest

from grf_ue_bridge.camera_rig import build_camera_plan,project_point,MANDATORY,PARTIAL
from grf_ue_bridge.seeded_episode import prepare_episode_recipe,build_episode_recipe
from test_seeded_episode import inputs

RIG=Path(__file__).resolve().parents[1]/'configs/camera_rig_v2.json'


def catalog():
    return json.loads(RIG.read_text(encoding='utf-8'))


def test_every_seed_keeps_five_and_selects_one_or_two_unique_partial_views_without_rng():
    rig=catalog();before=random.getstate();counts=set();seen=set()
    for seed in (0,1,2,42,1048,1102,2026102901,2147483647):
        plan=build_camera_plan(seed,rig)
        assert plan['selected_ids'][:5]==list(MANDATORY)
        chosen=plan['selected_ids'][5:]
        assert 1<=len(chosen)<=2 and len(set(chosen))==len(chosen)
        assert set(chosen)<=set(PARTIAL)
        assert len(plan['entries']) in (6,7)
        assert build_camera_plan(seed,rig)==plan
        counts.add(len(plan['entries']));seen.update(chosen)
    assert counts=={6,7} and seen==set(PARTIAL)
    assert random.getstate()==before


def test_adjusting_camera_poses_does_not_reselect_cameras_or_other_random_parts(tmp_path):
    meta,frames,profile=inputs(tmp_path)
    before=build_episode_recipe(meta,frames,profile)
    profile['seeded_episode']['camera_rig']=catalog()
    after=build_episode_recipe(meta,frames,profile)
    assert all(after['components'][k]==v for k,v in before['components'].items())
    changed=deepcopy(catalog());changed['profiles']['C1']['position_m'][0]+=1
    assert build_camera_plan(1048,changed)['selected_ids']==build_camera_plan(1048,catalog())['selected_ids']
    assert build_camera_plan(1048,changed)['catalog_sha256']!=build_camera_plan(1048,catalog())['catalog_sha256']


def test_runtime_consumes_frozen_selection_and_rejects_partial_override(tmp_path):
    from camera_distribution import resolve_runtime_camera_selection
    _,_,profile=inputs(tmp_path)
    profile['seeded_episode']['camera_rig']=catalog()
    recipe=prepare_episode_recipe(tmp_path,profile)
    resolved={'trajectory_output':str(tmp_path),'ue_profile':profile}
    result=resolve_runtime_camera_selection(resolved,legacy_sequences=[],legacy_cameras=[])
    assert [e['camera_id'] for e in result['entries']]==recipe['components']['cameras']['selected_ids']
    assert result['canonical'] is True
    assert len(result['sequences']) in (6,7)
    with pytest.raises(ValueError,match='全部6'):
        resolve_runtime_camera_selection(resolved,legacy_sequences=[],legacy_cameras=[],camera_ids=['C5'])


def test_main_covers_pitch_corners_and_partial_views_have_smaller_footprints():
    rig=catalog()
    width,height=rig['resolution']
    assert (width,height)==(3840,2160)
    for point in [(-20,-10,0),(20,-10,0),(-20,10,0),(20,10,0),(-21,0,1),(21,0,1)]:
        p=project_point(rig,'C5',point)
        assert p is not None and 16<=p[0]<width-16 and 16<=p[1]<height-16
    for cid in PARTIAL:
        inside=0
        for x in range(-20,21):
            for y in range(-10,11):
                p=project_point(rig,cid,(x,y,0))
                inside+=bool(p is not None and 0<=p[0]<width and 0<=p[1]<height)
        assert 0.2<inside/(41*21)<0.85
