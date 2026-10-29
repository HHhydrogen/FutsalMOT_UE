"""为库存06–15增加号码派生材质；不改原球衣、短裤及旧五套派生资产。"""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'python/ue'))


def main():
    import unreal
    import importlib,jersey_number_uv_build_catalog
    importlib.reload(jersey_number_uv_build_catalog)
    from jersey_number_uv_build_catalog import build_catalog,DESTINATION
    rows=[];missing=[]
    for i in range(1,16):
        kit='%02d'%i
        for kind in ('Jersey','Shorts'):
            p='/Game/FutsalMOT/Characters/MPFB/Materials/M_MPFB_'+kind+'_Set_'+kit
            mat=unreal.load_asset(p)
            assert mat and mat.get_class().get_name()=='Material',p
            textures=[t.get_path_name().split('.')[0] for t in unreal.MaterialEditingLibrary.get_material_used_textures(mat)]
            expected='/Game/FutsalMOT/Characters/MPFB/Textures/T_MPFB_'+kind+'_Set_'+kit
            assert expected in textures,(p,textures)
            rows.append({'set_id':kit,'kind':kind,'material':p,'texture':expected})
        if not unreal.EditorAssetLibrary.does_asset_exist(DESTINATION+'/M_Jersey_Set_'+kit+'_NumberUV_v1'):
            missing.append(kit)
    assert missing==['%02d'%i for i in range(6,16)],missing
    out=ROOT/'Saved/AppearanceCatalogExpansion/a01'
    (out/'asset_build_intent.json').write_text(json.dumps({'source_readback':rows,'missing_number_materials':missing},ensure_ascii=False,indent=2),encoding='utf-8')
    result=build_catalog(unreal,kit_ids=missing,report_name='catalog_expanded_06_15.json')
    for kit in missing:
        mat=unreal.load_asset(DESTINATION+'/M_Jersey_Set_'+kit+'_NumberUV_v1')
        assert mat and mat.get_class().get_name()=='Material'
        assert mat.get_editor_property('used_with_skeletal_mesh') and mat.get_editor_property('used_with_morph_targets')
        unreal.MaterialEditingLibrary.get_statistics(mat)
    assert not list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    report={'status':'fifteen_source_kits_readback_ten_number_materials_created','created_ids':missing,'source_materials_checked':30,'result':result,'dirty_after':[]}
    (out/'assets_complete.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':report['status'],'created_ids':missing},ensure_ascii=False))


if __name__=='__main__':main()
