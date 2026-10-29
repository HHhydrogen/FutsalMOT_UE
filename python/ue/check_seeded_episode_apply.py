"""真实UE统一清单联合应用及恢复检查，不启动MRQ、不改相机。"""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'python/ue'))
sys.path.insert(0,str(ROOT/'python/src'))


def main():
    import unreal
    import run_task as runner
    from grf_ue_bridge.seeded_episode import load_episode_recipe
    out=ROOT/'Saved/SeededEpisode/seeded_episode_s1048_apply_a01'
    assert not (out/'application_check.json').exists()
    task=json.loads((out/'resolved.json').read_text(encoding='utf-8'))
    profile=task['ue_profile']
    mapping=json.loads(Path(task['actor_mapping']).read_text(encoding='utf-8'))
    recipe=load_episode_recipe(out,profile)
    weather=runner._prepare_episode_environment(profile,'sequence',out,task['repo_root'],task['task_id'])
    appearance=runner._prepare_episode_appearance(profile,'sequence',out,mapping,task['repo_root'],task['task_id'])
    prepared=runner._prepare_seeded_environment(profile,'sequence',out,weather)
    transaction=None
    result={'recipe_fingerprint':recipe['fingerprint'],'rendered_frames':0}
    try:
        transaction=runner._apply_prepared_environment_and_appearance(prepared,appearance)
        floor=next(a for a in unreal.EditorLevelLibrary.get_all_level_actors() if a.get_actor_label()=='SM_FutsalCourt_Floor')
        actual=floor.get_component_by_class(unreal.StaticMeshComponent).get_material(0).get_path_name()
        assert actual==recipe['components']['floor']['material']
        assert appearance['uv_session'].plan==recipe['components']['numbers']
        assert len(appearance['uv_session'].items)==10
        result.update(status='applied',floor_material=actual,number_actors=10,
            weather_preset=recipe['components']['weather']['preset'],numbers_match_plan=True)
    finally:
        if transaction is not None:
            restored=transaction.restore('no_render')
            result['restore']=restored
            assert restored.get('ok'), restored
    dirty=[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+
           list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
    assert not dirty,dirty
    assert not unreal.EditorLevelLibrary.get_pie_worlds(False)
    assert not unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering()
    result.update(status='joint_apply_readback_and_restore_passed',dirty_after=[],PIE=False,MRQ=False)
    (out/'application_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    main()
