"""新字体只变印花，不改变原随机分配和旧计划。"""
import json
from pathlib import Path

import pytest

from grf_ue_bridge.seeded_episode import build_episode_recipe
from grf_ue_bridge.number_typography import ATLAS_PROFILE
from test_seeded_episode import inputs


def test_explicit_font_profile_keeps_roster_numbers_and_other_components(tmp_path):
    meta,frames,profile=inputs(tmp_path)
    old=build_episode_recipe(meta,frames,profile)
    assert 'atlas' not in old['components']['numbers']
    profile['uv_numbering']=json.loads((Path(__file__).resolve().parents[1]/'configs/number_typography_v2.json').read_text(encoding='utf-8'))
    new=build_episode_recipe(meta,frames,profile)
    assert new['components']['numbers']['atlas']==ATLAS_PROFILE
    for a,b in zip(new['components']['numbers']['entities'],old['components']['numbers']['entities']):
        assert {k:v for k,v in a.items() if k!='ink_color'}=={k:v for k,v in b.items() if k!='ink_color'}
        if a['kit_set_id'] in ('02','05'):assert a['ink_color']==[0.0,0.0,0.0]
        else:assert a['ink_color']==[1.0,1.0,1.0]
    assert new['components']['numbers']['uv_rect']==[0.125,0.15,0.405,0.45]
    for key in ('appearance','weather','floor'):
        assert new['components'][key]==old['components'][key]
    profile['uv_numbering']['atlas_id']='missing'
    with pytest.raises(ValueError,match='未知UV号码字体'):
        build_episode_recipe(meta,frames,profile)
