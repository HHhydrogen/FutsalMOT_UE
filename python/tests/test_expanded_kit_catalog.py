"""十五套入口可达、P1/P2一致，旧五套与其他独立随机分配保留。"""
import json
from copy import deepcopy
from pathlib import Path

import pytest
from grf_ue_bridge.appearance import build_appearance_manifest
from grf_ue_bridge.config.models import AppearanceCatalog,DatasetTaskConfig
from grf_ue_bridge.kit_catalog import EXPANDED_CATALOG_ID,EXPANDED_KIT_IDS
from grf_ue_bridge.number_uv_plan import build_plan
from test_appearance import appearance_catalog,appearance_meta,write_frames
import episode_appearance


def expanded(old):
    c=deepcopy(old);c['catalog_id']=EXPANDED_CATALOG_ID
    template=c['kits'][0]
    c['kits']=[{'set_id':kit,'jersey_material':template['jersey_material'].replace('_01','_'+kit),
                'shorts_material':template['shorts_material'].replace('_01','_'+kit)} for kit in EXPANDED_KIT_IDS]
    return c


def test_all_fifteen_reachable_and_only_kit_selection_changes(tmp_path):
    meta=appearance_meta();frames=write_frames(tmp_path);old=appearance_catalog();new=expanded(old)
    AppearanceCatalog.model_validate(new)
    seen=set()
    for seed in range(64):
        meta['randomness']['ue_visual_seed']=seed
        a=build_appearance_manifest(meta,frames,old);b=build_appearance_manifest(meta,frames,new)
        assert len(set(b['kit_classes'].values()))==4
        assert not episode_appearance._manifest_errors(b,new)
        seen.update(b['kit_classes'].values())
        for x,y in zip(a['entities'],b['entities']):
            for key in ('entity_id','player_id','mesh','skin_id','skin_texture'):
                assert x[key]==y[key]
        assert build_appearance_manifest(meta,frames,new)==b
    assert seen==set(EXPANDED_KIT_IDS)
    invalid=deepcopy(new);invalid['catalog_id']=old['catalog_id']
    with pytest.raises(ValueError):AppearanceCatalog.model_validate(invalid)


def test_real_catalog_task_and_number_material_paths():
    root=Path(__file__).resolve().parents[1]
    c=json.loads((root/'configs/player_appearance_catalog_15kits.json').read_text(encoding='utf-8'))
    assert len(AppearanceCatalog.model_validate(c).kits)==15
    task=json.loads((root/'configs/player_appearance_15kits_smoke_10frames_1cam.json').read_text(encoding='utf-8'))
    DatasetTaskConfig.model_validate(task)
    assert task['ue']['appearance']==c
