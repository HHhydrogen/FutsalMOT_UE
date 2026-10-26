"""额外R独立输入的完成、来源、索引和无GT模型帧边界。"""
from copy import deepcopy
import unittest
import extra_real_prediction_inputs as inputs


def fixture():
    sequences=[]
    for seq,game in inputs.SEQUENCES.items():
        names=[f'img1/{i:06d}.jpg' for i in range(1,751)]+['gt/gt.txt','gameinfo.ini','seqinfo.ini']
        files=[dict(official_member=f'train/{seq}/{p}',path=str(inputs.ROOT/seq/p),bytes=1,sha256='0'*64) for p in names]
        sequences.append(dict(sequence=seq,game_id=game[4:],frames=750,fps=25,width=1920,height=1080,
            files=files,game_time_start='1 - 00:00',game_time_stop='1 - 00:30'))
    return dict(schema='extra_real_train_input_manifest_v1',status=inputs.STATUS,images=2250,optimizer_updates=0,
        training_authorized=False,models_inferred=False,test_requested=False,det_file_extracted_or_used=False,sequences=sequences)


class Tests(unittest.TestCase):
    def test_three_real_sources_and_explicit_frame_mapping(self):
        result=inputs.sources(fixture(),inputs.ROOT);self.assertEqual(sum(len(s['frames']) for s in result),2250)
        s=result[0];first=inputs.inference_frame(s,s['frames'][0]);last=inputs.inference_frame(s,s['frames'][-1])
        self.assertEqual((first['frame_index'],first['frame_number']),(0,1));self.assertTrue(first['image_file'].endswith('000001.jpg'))
        self.assertEqual((last['frame_index'],last['frame_number'],last['timestamp_sec']),(749,750,29.96))

    def test_incomplete_acquisition_is_not_admission(self):
        m=fixture();m['status']='started'
        with self.assertRaises(ValueError):inputs.sources(m,inputs.ROOT)

    def test_GT_and_accidental_prediction_fields_never_pass_to_model(self):
        s=inputs.sources(fixture(),inputs.ROOT)[0];f=deepcopy(s['frames'][0]);f.update(gt_id=99,bbox=[1,2,3,4],xy_px=[0,0],GT={'secret':1})
        d=inputs.inference_frame(s,f)
        for key in ('gt_id','bbox','xy_px','GT','gt_reference'):self.assertNotIn(key,d)

    def test_missing_duplicate_or_det_member_rejected(self):
        for kind in ('missing','duplicate','det'):
            m=fixture();files=m['sequences'][0]['files']
            if kind=='missing':files.pop()
            elif kind=='duplicate':files[-1]=deepcopy(files[0])
            else:files[-1]['official_member']='train/SNMOT-061/det/det.txt'
            with self.assertRaises(ValueError):inputs.sources(m,inputs.ROOT)

    def test_wrong_game_test_sequence_and_off_by_one_rejected(self):
        for field,value in (('game_id','9'),('sequence','SNMOT-116')):
            m=fixture();m['sequences'][0][field]=value
            with self.assertRaises(ValueError):inputs.sources(m,inputs.ROOT)
        s=inputs.sources(fixture(),inputs.ROOT)[0];f=deepcopy(s['frames'][0]);f['frame_number']=0
        with self.assertRaises(ValueError):inputs.inference_frame(s,f)


if __name__=='__main__':unittest.main()
