"""v5新增候选的一次定向CPU检查，不加载模型或图像。"""
import json
from pathlib import Path
import unittest
from prepare_longpair_v5 import anchor_crop,transformed_profile,POLICY
from v5_virtual_crop import location_record

class CandidateTest(unittest.TestCase):
    def person(self):
        return dict(entity_id='L0',bbox_visible_xywh=[100,100,100,200],uv_px=[[150,150]]*17,location_valid=[True]*16+[False],visibility_state=['unknown']*17)
    def test_deterministic_crop_geometry(self):
        crop,entity=anchor_crop([self.person()],3840,2160,138.2678,'1048:camera:100')
        self.assertEqual((crop,entity),anchor_crop([self.person()],3840,2160,138.2678,'1048:camera:100'))
        self.assertEqual(crop[2],crop[3]);self.assertTrue(0<=crop[0]<=3840-crop[2])
    def test_unknown_and_invalid_preserved(self):
        record=location_record(dict(objects=[self.person()],source_frame_index=100,rgb_ref='rgb/000000.png'),Path('G:/FutsalMOT_Dataset/fake'),[100,100,256,256],'key')
        obj=record['instances'][0]
        self.assertEqual(obj['bbox_xywh_px'],[0.,0.,100.,200.])
        self.assertEqual(obj['xy_normalized'][0],[50/256,50/256]);self.assertFalse(obj['location_valid'][-1])
        self.assertEqual(obj['visibility_state'],['unknown']*17)
    def test_outside_crop_invalid_not_visible(self):
        obj=self.person();obj['uv_px'][0]=[50,50]
        record=location_record(dict(objects=[obj],source_frame_index=100,rgb_ref='rgb/0.png'),Path('G:/FutsalMOT_Dataset/fake'),[100,100,256,256],'key')
        self.assertFalse(record['instances'][0]['location_valid'][0]);self.assertEqual(record['instances'][0]['visibility_state'][0],'unknown')
    def test_bound_numeric_extraction_without_models(self):
        from v5_numeric_loader import numeric_helpers
        module,bindings=numeric_helpers(Path(__file__).resolve().parents[2])
        self.assertEqual(len(bindings),19)
        self.assertEqual(module.SCHEMA,'futsalmot_longpair_location_checkpoint_v5')
        self.assertEqual(module.NORMALIZATION['synthetic_alpha'],1/3)
        self.assertIn('train_loop',[item['symbol'] for item in bindings])
    def test_actual_candidate_metadata_only(self):
        root=Path(__file__).resolve().parents[2]/'Saved/ResearchPlanning/longpair_v5_a03'
        if not root.is_dir():
            self.skipTest('本机候选元数据未生成；纯几何/数值闭包检查不依赖Saved')
        protocol=json.loads((root/'protocol_candidate.json').read_text(encoding='utf-8'))
        self.assertFalse(protocol['training_authorized']);self.assertEqual(protocol['seeds'],[20261024,20261025,20261026])
        counts={}
        for line in (root/'paired_crop_table.jsonl').read_text(encoding='utf-8').splitlines():
            row=json.loads(line);counts[row['split']]=counts.get(row['split'],0)+1
            self.assertEqual(set(row['pairs']),{'sport_blue_v1','sport_terracotta_v1'})
            for pair in row['pairs'].values():self.assertTrue(Path('G:/FutsalMOT_Dataset') in Path(pair['image_file']).parents)
        self.assertEqual(counts,dict(train=1200,synthetic_dev=1200))
        for item in protocol['virtual_location_files']:
            for line in Path(item['path']).read_text(encoding='utf-8').splitlines():
                frame=json.loads(line);self.assertTrue(frame['not_training']);self.assertEqual(frame['source_wh'],[3840,2160])
                self.assertTrue(all(state=='unknown' for person in frame['instances'] for state in person['visibility_state']))

if __name__=='__main__':unittest.main()
