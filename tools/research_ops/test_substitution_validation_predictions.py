"""七比赛固定帧、GT隔离、真实进程独占和诊断继承路径门禁。"""
import importlib.util
from pathlib import Path
import unittest

def load(name,file):
    s=importlib.util.spec_from_file_location(name,Path(__file__).with_name(file));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
inp=load('seven_inputs','substitution_validation_prediction_inputs.py')
entry=load('seven_entry','substitution_validation_predictions.py')

class SevenInputs(unittest.TestCase):
    def fixture(self):
        seqs=[];registry=[];ledger=[]
        for i,(seq,n) in enumerate(inp.EXPECTED.items()):
            video='video'+str(i)
            seqs.append(dict(sequence=seq,video_id=video,original_split='train',role='external_validation_only',frames=n,
                fps=25,width=1280,height=720,match_identity='fixture',gt={'path':'never_read_GT'},seqinfo={'path':'metadata'}))
            registry.append(dict(sequence=seq,video_id=video,split='train',full_clip_frames=n))
            for j in range(1,n+1):ledger.append(dict(sequence=seq,frame_number=j,path=str(inp.R/'public/substitution_validation_a02'/seq/'img1'/('%06d.jpg'%j)),bytes=100,sha256='a'*64))
        manifest=dict(schema='seven_match_validation_inputs_v1',status=inp.STATUS,frames=4790,new_R_training_exposure=0,
            optimizer_updates=0,test_read=False,models_run=False,sequences=seqs)
        return manifest,dict(sources=registry),ledger
    def test_fixed4790_and_no_GT_in_model_frames(self):
        m,r,l=self.fixture();sources=inp.sources(m,r,l);self.assertEqual(sum(len(s['frames']) for s in sources),4790)
        s=sources[0];f=dict(s['frames'][0],GT_identity=99,GT_bbox=[0,0,1,1],GT_pose='must_not_copy')
        frame=inp.inference_frame(s,f);self.assertEqual(frame['frame_index'],0);self.assertEqual(frame['frame_number'],1)
        self.assertNotIn('GT_identity',frame);self.assertNotIn('GT_bbox',frame);self.assertNotIn('GT_pose',frame)
    def test_partial_duplicate_or_missing_images_refused(self):
        for change in ('partial','duplicate','missing'):
            m,r,l=self.fixture()
            if change=='partial':m['status']='started'
            elif change=='duplicate':l[-1]=l[0]
            else:l.pop()
            with self.assertRaises(ValueError):inp.sources(m,r,l)
    def test_no_training_role_or_frame_shift(self):
        m,r,l=self.fixture();m['sequences'][0]['role']='train'
        with self.assertRaises(ValueError):inp.sources(m,r,l)
        m,r,l=self.fixture();s=inp.sources(m,r,l)[0];f=dict(s['frames'][0],frame_number=2)
        with self.assertRaises(ValueError):inp.inference_frame(s,f)
    def test_only_exact_diagnostic_image_allowed(self):
        inp.image_boundary(inp.R/'pose/real_substitution_a01/input_diagnostic_a01/000414_response.jpg')
        with self.assertRaises(ValueError):inp.image_boundary(inp.R/'pose/real_substitution_a01/input_diagnostic_a01/other.jpg')
    def test_live_C_input_and_duplicate_prediction_blocked(self):
        script=Path('D:/candidate/substitution_validation_predictions.py');own=dict(ProcessId=2,ParentProcessId=1,Name='python.exe',CommandLine='python '+str(script)+' --config c')
        launcher=dict(own,ProcessId=1,ParentProcessId=0)
        self.assertEqual(entry.process_gate([launcher,own],2,script),[1,2])
        for filename in ('substitution_C_train.py','substitution_validation_inputs.py','substitution_validation_predictions.py'):
            other=dict(ProcessId=3,ParentProcessId=0,Name='python.exe',CommandLine='python D:/candidate/'+filename+' --config other')
            with self.assertRaises(ValueError):entry.process_gate([launcher,own,other],2,script)

if __name__=='__main__':unittest.main()
