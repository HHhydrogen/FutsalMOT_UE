"""v6 crop纯CPU契约检查；不加载模型/媒体/GT。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'python/src'))
from grf_ue_bridge import fixed_detection_crop_pose_v6 as C
from grf_ue_bridge.pose_association_contract_v2 import pose_pair_cost_candidate

def frame(boxes):
    key='SNMOT-151:000001'
    return dict(schema='futsalmot_fixed_detection_frame_v1',sequence_id='SNMOT-151',camera_id='broadcast',frame_index=0,frame_number=1,frame_key=key,width=1920,height=1080,coordinate_space='image_pixels',
        detections=[dict(source_index=i,detection_id=f'{key}:{i:06d}',class_id=0,bbox_xywh_px=list(box),score=.8) for i,box in enumerate(boxes)])
def prediction(box):
    x,y,w,h=box;return dict(bbox_xywh_px=list(box),score=.9,xy_px=[[x+w*(.3+.02*(j%5)),y+h*(.1+.04*j)] for j in range(17)])
def attach(f,values):return C.attach_frame(f,values,model_sha256='a'*64,fixed_detection_set_sha256='b'*64,config=C.configuration())
class CropTests(unittest.TestCase):
    def test_transform_roundtrip_and_edges(self):
        for box in ([0.,0.,10.,20.],[1870.,1000.,50.,80.],[100.5,200.5,30.,60.]):
            g=C.crop_geometry(box,(1920,1080));x,y,w,h=box;r=g['scale'];left,top,_,_=g['crop_xywh'];px=g['left'];py=g['top']
            def forward(x,y):return [(x-left)*r+px,(y-top)*r+py]
            a=forward(x,y);b=forward(x+w,y+h);point=forward(x+w/2,y+h/2)
            row=a+b+[.9,0.]+point*17;out=C.inverse_prediction(row,g)
            for actual,expected in zip(out['bbox_xywh_px'],box):self.assertAlmostEqual(actual,expected,places=9)
            self.assertAlmostEqual(out['xy_px'][0][0],x+w/2,places=9)
            self.assertGreater(g['crop_xywh'][2],0);self.assertGreaterEqual(g['crop_xywh'][0],0)
    def test_empty_output_and_empty_frame_keep_UIDs(self):
        f=frame([[100,100,100,200]]);out=attach(f,{f['detections'][0]['detection_id']:[]});self.assertFalse(out['attachments'][0]['prediction_valid']);self.assertFalse(any(out['attachments'][0]['geometry_valid']))
        empty=frame([]);self.assertEqual(attach(empty,{})['attachments'],[])
    def test_cross_crop_duplicate_is_ambiguity_fallback(self):
        f=frame([[100,100,100,200],[100,100,100,200]]);values={d['detection_id']:[prediction(d['bbox_xywh_px'])] for d in f['detections']};out=attach(f,values)
        self.assertTrue(all(not row['prediction_valid'] and row['prediction_rejection']=='cross_crop_same_person_component_ambiguous' for row in out['attachments']))
    def test_distinct_people_one_to_one_tracker_bridge(self):
        f=frame([[100,100,100,200],[500,100,100,200]]);out=attach(f,{d['detection_id']:[prediction(d['bbox_xywh_px'])] for d in f['detections']})
        records=C.tracker_records(f,out,model_sha256='a'*64,fixed_detection_set_sha256='b'*64,config=C.configuration());self.assertEqual(list(records),[d['detection_id'] for d in f['detections']])
        first=next(iter(records.values()));second=deepcopy(first);second['frame_index']=1
        self.assertAlmostEqual(pose_pair_cost_candidate(first,second,[0.,0.])['pose_cost'],0.)
        self.assertEqual(first['schema'],C.VERSION);self.assertEqual(first['transform']['strategy'],C.STRATEGY)
    def test_most_relevant_target_chosen_before_dedup(self):
        f=frame([[100,100,100,200]]);uid=f['detections'][0]['detection_id'];out=attach(f,{uid:[prediction([100,100,100,200]),prediction([100,100,40,200])]})
        self.assertTrue(out['attachments'][0]['prediction_valid']);self.assertEqual(out['attachments'][0]['model_prediction_index'],0)
    def test_equal_rank_ambiguity_fallback(self):
        f=frame([[100,100,100,200]]);p=prediction([100,100,100,200]);uid=f['detections'][0]['detection_id'];out=attach(f,{uid:[p,deepcopy(p)]})
        self.assertEqual(out['attachments'][0]['prediction_rejection'],'own_crop_equal_rank_ambiguity')
    def test_too_few_limbs_never_forced_valid(self):
        f=frame([[100,100,100,200]]);p=prediction([100,100,100,200]);p['xy_px']=[[-50.,-50.] if j>=10 else point for j,point in enumerate(p['xy_px'])]
        out=attach(f,{f['detections'][0]['detection_id']:[p]});self.assertEqual(out['attachments'][0]['prediction_rejection'],'too_few_geometry_valid_limbs')
    def test_frozen_box_score_uid_and_unknown(self):
        f=frame([[100,100,100,200]]);original=deepcopy(f);uid=f['detections'][0]['detection_id'];out=attach(f,{uid:[prediction([100,100,100,200])]});self.assertEqual(f,original)
        for key in ('bbox_xywh_px','detection_id','class_id'):self.assertEqual(out['attachments'][0][key],f['detections'][0][key])
        self.assertEqual(out['attachments'][0]['visibility_state'],['unknown']*17)
        with self.assertRaises(ValueError):attach(f,{})
    def test_forged_geometry_rejected(self):
        f=frame([[100,100,100,200]]);uid=f['detections'][0]['detection_id'];out=attach(f,{uid:[prediction([100,100,100,200])]});out['attachments'][0]['xy_px'][5]=[-1.,-1.]
        with self.assertRaises(ValueError):C.validate_frame(f,out,model_sha256='a'*64,fixed_detection_set_sha256='b'*64,config=C.configuration())
if __name__=='__main__':unittest.main()
