"""只导入新的号码字体图集，保留旧Atlas及全部原球衣材质。"""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'python/src'))
sys.path.insert(0,str(ROOT/'python/ue'))
from grf_ue_bridge.number_typography import ATLAS_PROFILE


def main():
    import unreal
    import diagnose_episode_appearance as diagnostic
    local=ROOT/'Saved/JerseyNumberUV/number_typography_v2_a01'
    source=Path('G:/FutsalMOT_Dataset/test/number_typography_v2_a01/source_atlas/jersey_numbers_01_99.png')
    atlas=json.loads(source.with_name('atlas.json').read_text(encoding='utf-8'))
    assert atlas['font_sha256']==ATLAS_PROFILE['font_sha256']
    assert atlas['font_variation_axes']==[{'name':'Weight','value':700},{'name':'Width','value':75}]
    assert atlas['resolution']==[4096,2048] and len(atlas['cells'])==99
    assert hashlib.sha256(source.read_bytes()).hexdigest()==atlas['png_sha256']
    mapping=json.loads((ROOT/'python/ue/actor_mapping.example.json').read_text(encoding='utf-8'))
    gate=diagnostic.collect_diagnostic(unreal,mapping)
    assert gate['task7_preflight_can_start'] and not gate['dirty_package_paths'],gate['errors']
    assert not unreal.EditorLevelLibrary.get_pie_worlds(False)
    assert not unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering()
    path=ATLAS_PROFILE['texture']
    assert not unreal.EditorAssetLibrary.does_asset_exist(path),'不覆盖现有图集'
    task=unreal.AssetImportTask()
    for k,v in {'filename':str(source),'destination_path':path.rsplit('/',1)[0],
        'destination_name':path.rsplit('/',1)[1],'automated':True,'replace_existing':False,'save':False}.items():
        task.set_editor_property(k,v)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture=unreal.load_asset(path)
    assert texture and texture.get_class().get_name()=='Texture2D'
    texture.set_editor_property('srgb',False)
    texture.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_MASKS)
    texture.set_editor_property('address_x',unreal.TextureAddress.TA_CLAMP)
    texture.set_editor_property('address_y',unreal.TextureAddress.TA_CLAMP)
    assert unreal.EditorAssetLibrary.save_loaded_asset(texture)
    assert texture.get_editor_property('srgb') is False
    assert not list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    local.mkdir(parents=True,exist_ok=True)
    (local/'atlas.json').write_bytes(source.with_name('atlas.json').read_bytes())
    report={'status':'new_typography_atlas_imported_saved','texture':path,'source':str(source),
            'atlas_png_sha256':atlas['png_sha256'],'profile':ATLAS_PROFILE,'dirty_after':[]}
    (local/'import_complete.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
