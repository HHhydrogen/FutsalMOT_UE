"""v8训练标签、实际观测、分层窗口与曝光的必要纯CPU检查。"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('pairs',Path(__file__).with_name('v8_pairs.py'))
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)


def det(uid,x,t):
    return dict(uid=uid,bbox_xywh_px=[x,0,20,40],score=.9,timestamp_sec=t,image_wh=[1000,600],
                xy_px=[[0.,0.] for _ in range(17)],geometry_valid=[False]*17)


class PairTests(unittest.TestCase):
    def test_zero_based_cache_joins_real_gt_by_explicit_frame_number(self):
        temp_root=Path(__file__).resolve().parents[2]/'Saved/Verification'
        temp_root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as folder:
            cache=Path(folder)/'cache.jsonl'
            prediction=det('pred0',0,0.)
            cache.write_text(json.dumps(dict(sequence='SNMOT-060',game='game4',fps=25,frame_index=0,
                frame_number=1,timestamp_sec=0.,width=1000,height=600,detections=[prediction]))+'\n',encoding='utf-8')
            source=dict(domain='real',sequence='SNMOT-060',game='game4',fps=25,first_frame=0,last_frame=0,
                        cache=dict(path=str(cache),sha256=p.sha(cache)))
            with patch.object(p,'real_gt',return_value={1:[dict(gt_id='gt_first',bbox_xywh_px=[0,0,20,40])]}):
                frames,audit=p.load_source(source)
            self.assertEqual(frames[0]['labels']['pred0']['gt_id'],'gt_first')
            self.assertEqual(audit,{'matched':1})

    def test_unique_conflict_unmatched_query_labels(self):
        gt=[dict(gt_id='a',bbox_xywh_px=[0,0,20,40]),dict(gt_id='b',bbox_xywh_px=[100,0,20,40])]
        ds=[det('a',0,0),det('b',100,0),det('u',300,0),det('low',15,0)]
        result=p.match_labels(ds,gt)
        self.assertEqual(result['a']['gt_id'],'a');self.assertEqual(result['b']['gt_id'],'b')
        self.assertEqual(result['u']['state'],'unmatched')
        self.assertEqual(result['low']['state'],'unknown_low_overlap')
        ds.append(det('duplicate',1,0));result=p.match_labels(ds,gt)
        self.assertEqual(result['a']['state'],'unknown_conflict')
        self.assertEqual(result['duplicate']['state'],'unknown_conflict')

    def test_actual_observations_gap_and_no_gt_in_prediction(self):
        source=dict(domain='synthetic',sequence='S1048cam1',game='synthetic1048',camera='cam1',fps=10)
        frames={}
        for i in range(20):
            ds=[det(f'a_{i}',0,i/10),det(f'u_{i}',30,i/10)]
            frames[i]=dict(timestamp_sec=i/10,detections=ds,labels={ds[0]['uid']:dict(state='matched',gt_id='A'),
                ds[1]['uid']:dict(state='unmatched',gt_id=None)})
        windows=list(p.enumerate_windows(source,frames,lambda h,c:dict(accepted=True)))
        w=next(w for w in windows if w['candidate_frame_index']==3 and w['gap_requested_sec']==0.)
        self.assertEqual(w['history_frame_indices'],[0,1,2]);self.assertAlmostEqual(w['gap_actual_sec'],.1)
        self.assertEqual([c['label'] for c in w['candidates']],[1,0])
        self.assertTrue(all(set(d)==set(p.PRED_FIELDS) for d in w['history']))
        self.assertTrue(w['supervision']['teacher_forced_history'])
        frames[3]['labels']['a_3']['state']='unknown_low_overlap'
        frames[3]['labels']['u_3']['state']='unknown_conflict'
        audit=p.Counter()
        filtered=list(p.enumerate_windows(source,frames,lambda h,c:dict(accepted=True),audit))
        self.assertFalse(any(x['candidate_frame_index']==3 and x['gap_requested_sec']==0. for x in filtered))
        self.assertGreaterEqual(audit['filtered_all_unknown_windows'],1)
        frames[3]['labels']['a_3']['state']='matched'
        frames[3]['labels']['u_3']['state']='unmatched'
        # 缺少实际第三观测即不造历史，也不拿GT Pose填充。
        frames[2]['labels']['a_2']['state']='unknown_conflict'
        after=list(p.enumerate_windows(source,frames,lambda h,c:dict(accepted=True)))
        self.assertFalse(any(x['candidate_frame_index']==3 and x['gap_requested_sec']==0. for x in after))

    def test_pretraining_grid_distinct_actual_frames_and_native_history_cadence(self):
        self.assertEqual(p.GAPS,(0.,.2,.4,.8,1.2))
        for fps,expected in ((25,[1,5,10,20,30]),(10,[1,2,4,8,12])):
            self.assertEqual([max(1,p.math.floor(gap*fps+.5)) for gap in p.GAPS],expected)
            source=dict(domain='synthetic',sequence='fixture',game='synthetic1048',camera='cam1',fps=fps)
            frames={}
            for i in range(50):
                ds=[det(f'a_{i}',0,i/fps),det(f'u_{i}',30,i/fps)]
                frames[i]=dict(timestamp_sec=i/fps,detections=ds,labels={ds[0]['uid']:dict(state='matched',gt_id='A'),
                    ds[1]['uid']:dict(state='unmatched',gt_id=None)})
            windows=list(p.enumerate_windows(source,frames,lambda h,c:dict(accepted=True)))
            selected=[w for w in windows if w['candidate_frame_index']==40]
            self.assertEqual(len(selected),5);self.assertEqual(len({w['window_uid'] for w in selected}),5)
            for w in selected:
                h=w['history_frame_indices'];self.assertEqual([h[1]-h[0],h[2]-h[1]],[1,1])
        r=p.BalancedPool([(game,gap) for game in ('game4','game6') for gap in p.GAPS])
        s=p.BalancedPool([(camera,gap) for camera in ('cam1','cam2','cam3','cam4') for gap in p.GAPS])
        self.assertEqual(set(r.quotas.values()),{100});self.assertEqual(set(s.quotas.values()),{50})

    def test_balanced_exact_pool_and_fixed_real_exposure(self):
        strata=[('game4',.12),('game6',.12)]
        pool=p.BalancedPool(strata)
        for group in ('game4','game6'):
            for i in range(600):
                pool.add(dict(window_uid=p.key([group,i]),stratum=[group,.12],
                    candidates=[dict(label=1),dict(label=0),dict(label=None)]))
        selected=pool.finish();self.assertEqual(len(selected),1000)
        self.assertEqual(sum(w['stratum'][0]=='game4' for w in selected),500)
        schedule=p.exposures(selected,selected,20261024)
        self.assertEqual(len(schedule['real']),3000);self.assertEqual(len(schedule['synthetic']),1000)
        self.assertEqual(schedule['accounting']['real_candidate_pair_exposures'],9000)
        self.assertEqual(schedule,p.exposures(selected,selected,20261024))
        self.assertNotEqual(schedule['real'],p.exposures(selected,selected,20261025)['real'])
        empty=p.BalancedPool(strata)
        with self.assertRaisesRegex(ValueError,'不足'):empty.finish()


if __name__=='__main__':unittest.main()
