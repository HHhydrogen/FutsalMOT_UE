"""绿色地板单槽事务；仅改当前自有组件，保存前置状态并严格读回/恢复。"""
import json
from pathlib import Path
from pose17_green_kit_contract import expected_material
from pose17_seeded_kit_contract import require,digest


def main(plan,action):
    import unreal
    from grf_ue_bridge.green_floor import ORIGINAL_MATERIAL
    world=unreal.EditorLevelLibrary.get_editor_world()
    require(world.get_path_name().split('.')[0]=='/Game/FutsalMOT/Maps/L_FutsalCourt','非规范地图')
    require(not unreal.EditorLevelLibrary.get_pie_worlds(False)
        and not unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering(),'活动PIE/MRQ不改地板')
    actors=unreal.EditorLevelLibrary.get_all_level_actors()
    floors=[a for a in actors if a.get_actor_label()=='SM_FutsalCourt_Floor']
    require(len(floors)==1,'地板不唯一')
    components=[c for c in floors[0].get_components_by_class(unreal.StaticMeshComponent) if c.get_name()=='StaticMeshComponent0']
    require(len(components)==1 and components[0].get_num_materials()==1,'地板槽不同')
    component=components[0];recipe=plan['seeded_kit_pair']['green_floor']
    target=unreal.load_asset(expected_material(recipe['id']))
    require(target and target.get_class().get_name()=='MaterialInstanceConstant','绿色材质class不符')
    lib=unreal.MaterialEditingLibrary;gain=None
    if recipe['id']!='grass_original_v1':
        require(target.get_editor_property('parent').get_path_name()=='/Game/FutsalMOT/Environment/Floors/GreenV1/M_GrassGain_v1.M_GrassGain_v1','绿色父材质不同')
        c=lib.get_material_instance_vector_parameter_value(target,'GreenAlbedoGain');gain=[float(c.r),float(c.g),float(c.b)]
        require(all(abs(a-b)<1e-6 for a,b in zip(gain,recipe['albedo_gain_linear'])),'绿色gain真实读回不同')
    require(abs(float(lib.get_material_instance_scalar_parameter_value(target,'Param'))-.08)<1e-6,'原标量未保持')
    dirty=lambda:[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
    require(not dirty(),'地板动作前有未知dirty')
    context=[]
    for actor in actors:
        p,r,s=actor.get_actor_location(),actor.get_actor_rotation(),actor.get_actor_scale3d()
        row=dict(actor=actor.get_path_name(),location=[p.x,p.y,p.z],rotation=[r.pitch,r.yaw,r.roll],scale=[s.x,s.y,s.z],materials=[],lights=[])
        for mesh in actor.get_components_by_class(unreal.MeshComponent):
            for index in range(mesh.get_num_materials()):
                if mesh==component and index==0:continue
                material=mesh.get_material(index)
                row['materials'].append([mesh.get_path_name(),index,material.get_path_name() if material else None])
        for light in actor.get_components_by_class(unreal.LightComponent):
            color=light.get_editor_property('light_color')
            row['lights'].append([light.get_path_name(),float(light.get_editor_property('intensity')),[color.r,color.g,color.b,color.a]])
        context.append(row)
    context_sha=digest(sorted(context,key=lambda r:r['actor']))
    root=Path(unreal.Paths.project_dir())/'Saved/FloorDiversity/green_v1/transactions'
    path=root/(plan['attempt']+'.json');state=json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    current=component.get_material(0).get_path_name()
    result=dict(action=action,current_material=current,expected_target=target.get_path_name(),gain_readback=gain,
        context_sha256=context_sha,dirty_packages=[],PIE=False,MRQ=False,state=state)
    if action in ('preflight','status'):return result
    require(action in ('apply','restore'),'未知地板动作')
    if state is None:
        require(action=='apply' and current==ORIGINAL_MATERIAL,'首次应用必须是原绿绑定')
        state=dict(attempt=plan['attempt'],status='initialized',original_material=current,target_material=target.get_path_name(),
            component=component.get_path_name(),initial_context_sha256=context_sha,step=0,expected_current_material=current)
    require(current==state['expected_current_material'] and component.get_path_name()==state['component'],'自有地板被未知操作改变')
    if action=='apply':require(context_sha==state['initial_context_sha256'],'应用前相机/角色/光照改变')
    output=target if action=='apply' else unreal.load_asset(state['original_material'])
    require(output is not None,'原材质不可恢复')
    root.mkdir(parents=True,exist_ok=True);state.update(status=action+'_intent_persisted',step=state['step']+1)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
    component.set_material(0,output)
    require(component.get_material(0)==output,'实际地板槽读回失败')
    require(not dirty(),'地板动作意外dirty，保留现场')
    state.update(status='preview_active' if action=='apply' else 'original_floor_slot_restored_not_saved',
        expected_current_material=output.get_path_name(),gain_readback=gain,
        non_floor_context_unchanged=context_sha==state['initial_context_sha256'])
    temp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
    return state
