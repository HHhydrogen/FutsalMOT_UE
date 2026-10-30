"""原随机外观下比较新旧背号；复用已验原生同帧RGB/号码mask近景接口。"""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'python/ue'))
sys.path.insert(0,str(ROOT/'python/src'))
OUT=ROOT/'Saved/CameraRigV2/number_typography_v2_a01'
MEDIA=Path('G:/FutsalMOT_Dataset/test/number_typography_v2_a01/raw')


def start(output_dir=None,media_dir=None):
    global OUT,MEDIA
    import importlib
    import episode_number_uv
    import grf_ue_bridge.number_uv_plan as plans
    import grf_ue_bridge.seeded_episode as recipes
    import grf_ue_bridge.number_typography as typography
    import grf_ue_bridge.appearance as appearance_plan
    import episode_appearance as appearance_runtime
    assert episode_number_uv._ACTIVE is None
    if output_dir is not None:OUT=Path(output_dir)
    if media_dir is not None:MEDIA=Path(media_dir)
    # 仅刷新无UClass的Python计划/事务模块；不刷新MCP Toolset。
    importlib.reload(appearance_plan);importlib.reload(appearance_runtime)
    importlib.reload(typography);importlib.reload(plans);importlib.reload(recipes);importlib.reload(episode_number_uv)
    import camera_rig_preview
    camera_rig_preview.start(OUT,MEDIA)
    import unreal
    from jersey_number_uv_build_catalog import DESTINATION
    # 先加载五套已有母材质，让下一次独立调用的近景捕获使用已加载资产。
    for item in camera_rig_preview._ACTIVE['profile']['appearance']['kits']:
        kit=item['set_id']
        parent=unreal.load_asset(DESTINATION+'/M_Jersey_Set_'+kit+'_NumberUV_v1')
        assert parent is not None
        unreal.MaterialEditingLibrary.get_statistics(parent)
    from jersey_number_uv_build_mask_preview import POST_PROCESS_PATH
    unreal.MaterialEditingLibrary.get_statistics(unreal.load_asset(POST_PROCESS_PATH))


def capture(entity_id):
    import unreal
    import episode_number_uv as numbers
    from jersey_number_uv_build_preview import TEXTURE_PATH
    from jersey_number_uv_build_catalog import DESTINATION
    from jersey_number_uv_build_mask_preview import MASKED_PATH,EMPTY_PATH,POST_PROCESS_PATH
    from number_preview_result import _result,_bool_result,_capture_result
    from grf_ue_bridge.number_uv_contract import DEFAULT_UV_RECT
    session=numbers._ACTIVE
    assert session is not None and session.report['state']=='applied'
    assert entity_id in ('L1','R2','R4')
    idx=next(i for i,e in enumerate(session.plan['entities']) if e['entity_id']==entity_id)
    entity=session.plan['entities'][idx];item=session.items[idx];source=item['visual']
    library=unreal.JerseyNumberUVLibrary
    parent=unreal.load_asset(DESTINATION+'/M_Jersey_Set_'+entity['kit_set_id']+'_NumberUV_v1')
    old_atlas=unreal.load_asset(TEXTURE_PATH)
    old_atlas.set_force_mip_levels_to_be_resident(300.0,0)
    outer=unreal.find_package('/Engine/Transient')
    source_transform=unreal.Transform(location=source.get_world_location(),rotation=source.get_world_rotation(),scale=source.get_world_scale())
    transform=unreal.Transform(location=source.get_world_location()+unreal.Vector(0,0,3000),rotation=source.get_world_rotation(),scale=source.get_world_scale())
    target=unreal.MathLibrary.transform_location(transform,unreal.Vector(0,0,130))
    back=unreal.MathLibrary.transform_direction(source_transform,unreal.Vector(0,-1,0))
    camera=target+back*180.0
    camera_transform=unreal.Transform(location=camera,rotation=unreal.MathLibrary.find_look_at_rotation(camera,target),scale=unreal.Vector(1,1,1))
    rows=[]
    try:
        for variant,atlas,rect in [('before',old_atlas,DEFAULT_UV_RECT),('after',session.atlas,session.plan['uv_rect'])]:
            params=unreal.JerseyNumberUVParameters()
            for k,v in {'number':entity['jersey_number'],'entity_mask_id':entity['number_mask_id'],
                        'uv_rect':unreal.LinearColor(*rect),'ink_color':unreal.LinearColor(*(entity['ink_color']+[1.0])),
                        'flip_u':True,'flip_v':True}.items():params.set_editor_property(k,v)
            beauty=_result(library.create_number_material(parent,atlas,outer,params),'近景球衣MID')
            masked=_result(library.create_number_material(unreal.load_asset(MASKED_PATH),atlas,outer,params),'近景mask MID')
            preview=follower=None
            try:
                preview=_result(library.create_number_preview_mesh(source,beauty,transform),'近景球员克隆')
                follower=_result(library.create_number_mask_follower(preview,masked,unreal.load_asset(EMPTY_PATH),entity['number_mask_id']),'近景号码代理')
                name=entity_id+'_'+variant
                frame=_capture_result(library.capture_number_preview_pair(preview,unreal.load_asset(POST_PROCESS_PATH),camera_transform,768,768,35.0,str(MEDIA),name))
                rows.append({'entity_id':entity_id,'number':entity['jersey_number'],'mask_id':entity['number_mask_id'],
                    'variant':variant,'engine_frame':frame,'rgb':name+'_rgb.png','mask':name+'_mask.png','media_directory':str(MEDIA),
                    'uv_rect':list(rect),'kit_set_id':entity['kit_set_id'],'player_id':entity['player_id'],
                    'resolution':[768,768],'horizontal_fov':35.0,'distance_cm':180.0})
            finally:
                if follower is not None:_bool_result(library.destroy_number_mask_follower(follower,preview),'销毁近景号码代理')
                if preview is not None:_bool_result(library.destroy_number_preview_mesh(preview),'销毁近景球员')
    finally:
        old_atlas.set_force_mip_levels_to_be_resident(0.0,0)
    assert len(rows)==2 and rows[0]['engine_frame']==rows[1]['engine_frame']
    (OUT/(entity_id+'_closeup.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print('NUMBER_TYPOGRAPHY_PAIR',entity_id,entity['jersey_number'])


def finish():
    import camera_rig_preview
    camera_rig_preview.finish()


def capture_kit(kit):
    """同一随机角色克隆，仅更换球衣套装做墨色展示，不改实际roster。"""
    import unreal
    import episode_number_uv as numbers
    from grf_ue_bridge.number_typography import ink_for_kit
    from jersey_number_uv_build_catalog import DESTINATION
    from jersey_number_uv_build_mask_preview import MASKED_PATH,EMPTY_PATH,POST_PROCESS_PATH
    from number_preview_result import _result,_bool_result,_capture_result
    session=numbers._ACTIVE
    assert session is not None
    ink_for_kit(kit)
    idx=next(i for i,e in enumerate(session.plan['entities']) if e['entity_id']=='L1')
    entity=session.plan['entities'][idx];source=session.items[idx]['visual']
    params=unreal.JerseyNumberUVParameters();ink=ink_for_kit(kit)
    for k,v in {'number':entity['jersey_number'],'entity_mask_id':entity['number_mask_id'],
                'uv_rect':unreal.LinearColor(*session.plan['uv_rect']),
                'ink_color':unreal.LinearColor(*(ink+[1.0])),'flip_u':True,'flip_v':True}.items():params.set_editor_property(k,v)
    library=unreal.JerseyNumberUVLibrary;outer=unreal.find_package('/Engine/Transient')
    beauty=_result(library.create_number_material(unreal.load_asset(DESTINATION+'/M_Jersey_Set_'+kit+'_NumberUV_v1'),session.atlas,outer,params),'配色球衣MID')
    actual=beauty.get_vector_parameter_value('NumberInkColor')
    assert all(abs(a-b)<1e-6 for a,b in zip([actual.r,actual.g,actual.b],ink))
    masked=_result(library.create_number_material(unreal.load_asset(MASKED_PATH),session.atlas,outer,params),'配色号码mask')
    transform=unreal.Transform(location=source.get_world_location()+unreal.Vector(0,0,3000),rotation=source.get_world_rotation(),scale=source.get_world_scale())
    target=unreal.MathLibrary.transform_location(transform,unreal.Vector(0,0,130))
    back=unreal.MathLibrary.transform_direction(transform,unreal.Vector(0,-1,0))
    camera=target+back*180.0
    camera_transform=unreal.Transform(location=camera,rotation=unreal.MathLibrary.find_look_at_rotation(camera,target),scale=unreal.Vector(1,1,1))
    preview=follower=None
    try:
        preview=_result(library.create_number_preview_mesh(source,beauty,transform),'配色角色克隆')
        follower=_result(library.create_number_mask_follower(preview,masked,unreal.load_asset(EMPTY_PATH),entity['number_mask_id']),'配色号码代理')
        name='kit_'+kit
        frame=_capture_result(library.capture_number_preview_pair(preview,unreal.load_asset(POST_PROCESS_PATH),camera_transform,768,768,35.0,str(MEDIA),name))
        row={'kit_set_id':kit,'diagnostic_kit_override':True,'source_entity_id':'L1','source_roster_kit_id':entity['kit_set_id'],
             'number':entity['jersey_number'],'mask_id':entity['number_mask_id'],'ink_color':ink,
             'uv_rect':session.plan['uv_rect'],'engine_frame':frame,'same_game_frame':True,
             'rgb':name+'_rgb.png','mask':name+'_mask.png','resolution':[768,768],'horizontal_fov':35,'distance_cm':180}
        (OUT/(name+'.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
    finally:
        if follower is not None:_bool_result(library.destroy_number_mask_follower(follower,preview),'销毁配色号码代理')
        if preview is not None:_bool_result(library.destroy_number_preview_mesh(preview),'销毁配色角色克隆')
    print('NUMBER_KIT_COLOR_CAPTURED',kit,ink)
