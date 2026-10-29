"""统一清单的兼容性、独立性、输入绑定及共同生命周期检查。"""
import json
import random
from copy import deepcopy

import pytest

from grf_ue_bridge.appearance import build_appearance_manifest
from grf_ue_bridge.environment import build_environment_manifest
from grf_ue_bridge.grass_detail import grass_recipe
from grf_ue_bridge.number_uv_plan import build_plan
from grf_ue_bridge.seeded_episode import build_episode_recipe, prepare_episode_recipe, load_episode_recipe
from test_appearance import appearance_catalog, appearance_meta, write_frames
from test_environment import _environment_profile


def inputs(tmp_path):
    meta = appearance_meta()
    (tmp_path/'meta.json').write_text(json.dumps(meta),encoding='utf-8')
    frames = write_frames(tmp_path)
    profile = {'seeded_episode':{'enabled':True},'appearance':appearance_catalog(),
               'environment_profile':_environment_profile(),'uv_numbering':{'enabled':True}}
    return meta, frames, profile


def test_unified_results_exactly_match_existing_builders_and_do_not_consume_rng(tmp_path):
    meta, frames, profile = inputs(tmp_path)
    before = random.getstate()
    result = build_episode_recipe(meta,frames,profile)
    app = build_appearance_manifest(meta,frames,profile['appearance'])
    assert result['components'] == {
        'appearance':app,'weather':build_environment_manifest(meta,frames,profile['environment_profile']),
        'numbers':build_plan(app,profile['uv_numbering']),'floor':grass_recipe(meta['randomness']['root_seed'])}
    assert build_episode_recipe(meta,frames,profile) == result
    assert random.getstate() == before


def test_changing_weather_or_floor_and_disabling_numbers_keeps_other_components(tmp_path):
    meta, frames, profile = inputs(tmp_path)
    original = build_episode_recipe(meta,frames,profile)['components']
    changed = deepcopy(profile)
    changed['environment_profile'] = _environment_profile(preset='night_floodlit_v1')
    changed['seeded_episode']['floor_id'] = 'grass_dark_v2'
    changed['uv_numbering']['enabled'] = False
    actual = build_episode_recipe(meta,frames,changed)['components']
    assert actual['appearance'] == original['appearance']
    assert actual['weather'] != original['weather']
    assert 'numbers' not in actual
    weather_only = deepcopy(profile)
    weather_only['environment_profile'] = changed['environment_profile']
    assert build_episode_recipe(meta,frames,weather_only)['components']['numbers'] == original['numbers']
    assert build_episode_recipe(meta,frames,weather_only)['components']['floor'] == original['floor']


def test_prepare_sidecars_are_bound_and_tampering_is_rejected(tmp_path):
    _, _, profile = inputs(tmp_path)
    recipe = prepare_episode_recipe(tmp_path,profile)
    assert load_episode_recipe(tmp_path,profile) == recipe
    assert prepare_episode_recipe(tmp_path,profile) == recipe
    (tmp_path/'provenance/floor.json').write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError,match='sidecar'):
        load_episode_recipe(tmp_path,profile)


def test_changed_trajectory_and_unknown_configuration_are_rejected(tmp_path):
    _, frames, profile = inputs(tmp_path)
    prepare_episode_recipe(tmp_path,profile)
    frames.write_text('{"step":1}\n',encoding='utf-8')
    with pytest.raises(ValueError,match='当前输入'):
        load_episode_recipe(tmp_path,profile)
    profile['seeded_episode']['typo'] = True
    with pytest.raises(ValueError,match='未知'):
        build_episode_recipe(appearance_meta(),frames,profile)


def test_task_model_checks_opt_in_and_legacy_dump_does_not_gain_new_fields():
    from grf_ue_bridge.config.models import UeProfile
    original=UeProfile().model_dump()
    assert 'seeded_episode' not in original
    assert UeProfile(seeded_episode={'enabled':True}).model_dump()['seeded_episode']=={'enabled':True}
    with pytest.raises(ValueError):
        UeProfile(seeded_episode={'enabled':'yes'})


def test_floor_failure_restores_weather_and_combined_callback_restores_in_reverse(monkeypatch):
    from ue import run_task
    from test_run_task_environment import _FakeTransaction
    events=[]
    weather=_FakeTransaction('weather',events)
    floor=_FakeTransaction('floor',events)
    monkeypatch.setattr(run_task,'_apply_prepared_environment',lambda _:weather)

    def fail():
        raise RuntimeError('floor failure')

    floor.apply=fail
    with pytest.raises(RuntimeError,match='floor failure'):
        run_task._SeededEnvironmentPrepared({},floor).apply()
    assert events==[('weather','restore','floor_apply_failed',None)]
    events.clear()
    weather.restore_result=None
    floor.apply=lambda:floor
    environment=run_task._SeededEnvironmentPrepared({},floor).apply()
    combined=run_task._combine_environment_appearance_transactions(environment,_FakeTransaction('appearance',events))
    captured={}
    def submit(*,on_complete):
        captured['done']=on_complete
        return {'callback_ownership_transferred':True}
    run_task._submit_render_with_appearance(submit,combined)
    captured['done']({'status':'success','appearance_restore_ready':True,'environment_restore_ready':True})
    assert [r[0] for r in events if r[1]=='restore']==['appearance','floor','weather']
    assert combined.restore_result['ok'] is True
