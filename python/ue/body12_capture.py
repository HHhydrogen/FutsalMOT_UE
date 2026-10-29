"""配置原生同帧十二关节流；不使用旧BurnIn的隐藏driver Pose。"""
import json
from pathlib import Path


def configure(job, camera_actor, options):
    import unreal
    if not options or not options.get('enabled'):
        return
    directory = Path(options['output_dir']).resolve()
    root = (Path(unreal.Paths.project_saved_dir()) / 'SingleSeed').resolve()
    if root not in directory.parents:
        raise ValueError('Body12小型元数据须位于Saved/SingleSeed')
    path = directory / (camera_actor + '.jsonl')
    if path.exists() or Path(str(path)+'.complete.json').exists():
        raise ValueError('Body12不能覆盖既有采集')
    actors = unreal.EditorLevelLibrary.get_all_level_actors()
    mapping = json.loads(Path(options['actor_mapping']).read_text(encoding='utf-8'))
    targets = []
    for entity in [s+str(i) for s in 'LR' for i in range(5)]:
        matches = [a for a in actors if a.get_actor_label() == mapping[entity]]
        if len(matches) != 1:
            raise RuntimeError('Body12目标不唯一: '+entity)
        components = [c for c in matches[0].get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='MPFBVisual']
        if len(components)!=1:
            raise RuntimeError('Body12需要实际MPFBVisual: '+entity)
        mesh = components[0].get_editor_property('skeletal_mesh_asset')
        identity = unreal.FutsalPose17MeshIdentity()
        identity.set_editor_property('asset_path',mesh.get_path_name())
        target = unreal.FutsalPose17MRQTarget()
        target.entity_id = entity
        target.actor_object_name = matches[0].get_name()
        target.component_object_name = 'MPFBVisual'
        target.expected_identity = identity
        targets.append(target)
    cameras = [a for a in actors if a.get_actor_label()==camera_actor]
    if len(cameras)!=1:
        raise RuntimeError('Body12相机不唯一')
    config = job.get_configuration()
    # 使用已验FinalImage过滤输出；号码只消费同帧线性EXR，不另存伪彩PNG。
    burnin=config.find_setting_by_class(unreal.MoviePipelineBurnInSetting)
    if burnin is not None:
        config.remove_setting(burnin)
    original=config.find_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
    if original is not None:
        alpha=original.get_editor_property('write_alpha')
        config.remove_setting(original)
        filtered=config.find_or_add_setting_by_class(unreal.FutsalMoviePipelinePNGOutput)
        filtered.set_editor_property('write_alpha',alpha)
    setting = config.find_or_add_setting_by_class(unreal.FutsalBody12MRQPass)
    setting.targets = targets
    setting.camera_object_name = cameras[0].get_name()
    setting.metadata_file = str(path)
    setting.expected_frames = int(options['frame_count'])
    aa = config.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
    aa.set_editor_property('use_camera_cut_for_warm_up',False)
    aa.set_editor_property('engine_warm_up_count',8)
    aa.set_editor_property('render_warm_up_count',0)
    aa.spatial_sample_count=1
    aa.temporal_sample_count=1
    aa.set_editor_property('override_anti_aliasing',True)
    aa.set_editor_property('anti_aliasing_method',unreal.AntiAliasingMethod.AAM_NONE)
