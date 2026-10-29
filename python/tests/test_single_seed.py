"""单seed新增契约的轻量检查；实际同步由本轮MRQ短样验证。"""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from grf_ue_bridge.single_seed import projection,bounds_state,frame_annotation,POINT_NAMES,ENTITY_IDS
from grf_ue_bridge.config.models import ExportConfig


def native():
    return {'camera_position_m':[0,0,0],'camera_rotation_deg':[0,0,0],
            'horizontal_fov_deg':90,'focal_length_mm':12,'width':100,'height':100}


def test_projection_and_truncation():
    frame=native();project=projection(frame)
    assert project([10,0,0])==pytest.approx([49.5,49.5])
    assert project([10,1,1])==pytest.approx([54.5,44.5])
    assert project([-1,0,0]) is None
    assert bounds_state({'bounds_center_m':[10,10,0],'bounds_extent_m':[1,2,2]},frame)==(False,True)
    assert bounds_state({'bounds_center_m':[10,40,0],'bounds_extent_m':[1,2,2]},frame)==(True,False)


def test_ten_players_include_invisible_and_flat_number():
    frame=native();entities=[];players=[]
    for i,entity in enumerate(ENTITY_IDS):
        entities.append({'entity_id':entity,'track_id':i+1,'team':entity[0],'role':'goalkeeper' if entity.endswith('0') else 'player',
            'jersey_number':i+1,'instance_mask_id':i+1,'number_mask_id':32+i})
        players.append({'entity_id':entity,'world_m':[[10,0,0]]*12,'bounds_center_m':[10,0,0],
            'bounds_extent_m':[.5,.5,1],'back_normal_world':[-1,0,0]})
    frame['players']=players
    instance=np.zeros((100,100),dtype=np.uint8);number=instance.copy()
    instance[40:50,40:50]=1;number[42:45,42:45]=32
    protocol={'request':{'number_instance_pixel_mismatch_max':0,'fps':10,'dataset_id':'test','dataset_version':'v1_test'},'seed_id':'seed_00000418'}
    result=frame_annotation(protocol,'C5',1,frame,instance,number,entities)
    assert len(result['objects'])==10
    assert result['objects'][0]['bbox_xyxy']==[40,40,50,50]
    assert result['objects'][0]['jersey_number_bbox_xyxy']==[42,42,45,45]
    assert result['objects'][0]['jersey_number_visible'] is True
    assert result['objects'][1]['bbox_xyxy'] is None
    assert result['objects'][1]['visibility']=='unknown'
    assert [p['name'] for p in result['objects'][0]['keypoints']]==list(POINT_NAMES)
    assert all(p['visibility']==0 for p in result['objects'][0]['keypoints'])
    from pathlib import Path
    from grf_ue_bridge.single_seed import SCHEMA_NAMES,sha
    from grf_ue_bridge.single_seed_export import schema_validators
    project=Path(__file__).resolve().parents[2]
    validators=schema_validators(project,{'schemas':{n:sha(project/'python/schemas/single_seed_v1'/n) for n in SCHEMA_NAMES}})
    validators['frame_annotation.schema.json'].validate(result)
    result['extra']=True
    with pytest.raises(Exception,match='Additional properties'):
        validators['frame_annotation.schema.json'].validate(result)
    result.pop('extra')
    number[5,5]=32
    with pytest.raises(ValueError,match='号码像素'):
        frame_annotation(protocol,'C5',1,frame,instance,number,entities)


def test_complete_episode_does_not_reset_after_terminal(monkeypatch):
    from grf_ue_bridge import grf_runner as runner
    class Environment:
        def __init__(self):
            self.calls=0;self.resets=0;self.closed=False
            self.unwrapped=SimpleNamespace(observation=lambda:[{'score':[1,0]}])
        def reset(self):
            self.resets+=1
            return [{}]
        def step(self,actions):
            self.calls+=1
            return [{'score':[1,0],'steps_left':2-self.calls}],0,self.calls==2,{}
        def close(self):
            self.closed=True
    env=Environment()
    monkeypatch.setattr(runner,'create_env',lambda *a,**k:env)
    monkeypatch.setattr(runner,'_apply_scenario_overrides',lambda *a,**k:None)
    monkeypatch.setattr(runner,'_extract_observation',lambda ob:ob)
    result=runner.run_episode(seed=1048,num_steps=10,stop_on_done=True)
    assert result.num_steps==2 and result.snapshots[-1].done and env.calls==2
    assert env.resets==1 and env.closed
    assert ExportConfig(scenario='5_vs_5').stop_on_done is False
