"""v8完整矩阵分析/缺臂拒绝定向夹具；不读真实媒体、不训练。"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/research_ops'))
from v8_analyze import analyze,GAMES,SEEDS,ARMS
from v8_train import sha
def dump(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value),encoding='utf-8')
class AnalysisTests(unittest.TestCase):
    def test_complete_cross_game_matrix_budget_and_negative_baseline(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'Saved/ResearchPlanning') as temp:
            p=Path(temp);config=p/'config.json';dump(config,dict(bundle=str(ROOT)));control=p/'control';protocol=sha(config)
            dump(control/'driver_state.json',dict(protocol_sha256=protocol,completed_train=[{}]*36,completed_tracking=[{}]*42))
            def result(directory,game,value):
                sequence={'game4':'SNMOT-060','game6':'SNMOT-097','game9':'SNMOT-151'}[game]
                metrics={key:value for key in ('AssA','HOTA','IDF1','DetA','MOTA')}
                dump(directory/'metric/report.json',dict(status='complete',protocol_sha256=protocol,DO_PREPROC=False,test_read=False,sequence=sequence,summary={sequence:dict(metrics_percent=metrics)}))
                dump(directory/'recovery.json',dict(sequences={sequence:dict(overall=dict(total_events=2,same_prediction_ID_recovered=1))}))
            for game in GAMES:
                for mode in ('PT_bbox','PT_static_pose'):result(control/'baselines'/game/mode,game,80)
                for seed in SEEDS:
                    for arm in ARMS:
                        directory=control/'runs'/game/str(seed)/arm
                        receipt=dict(status='complete',completed_updates=1000,real_window_exposures=3000,synthetic_window_exposures=1000 if arm.endswith('_RS') else 0,binding=dict(initialization_sha256=str(seed),R_window_UID_chain_sha256=game),wall_seconds_including_validation_and_checkpoint=1,prefetch=dict(closed=True))
                        dump(directory/'training/run_receipt.json',receipt);dump(directory/'tracking/receipt.json',dict(audit=dict(learned_pairs=1)))
                        result(directory,game,71 if arm=='pose_RS' else 70)
            value=analyze(config,control,p/'analysis');self.assertTrue(value['primary_progress_passed'])
            self.assertEqual(value['formal_updates'],36000);self.assertEqual(value['real_window_exposures'],108000);self.assertEqual(value['synthetic_window_exposures'],18000)
            self.assertEqual(value['mixed_minus_pretrained']['pose_RS']['PT_static_pose']['macro_mean_pp']['AssA'],-9)
            self.assertEqual(value['Pose_difference_in_differences_pp']['AssA'],1)
            self.assertEqual(value['gap_proxy_recovery']['per_arm_per_seed']['pose_RS']['20261024']['registered_events'],6)
            self.assertEqual(len(value['all_rows']),36);self.assertFalse(value['test116187_read'])
    def test_missing_arm_refuses_final_claim(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'Saved/ResearchPlanning') as temp:
            p=Path(temp);config=p/'config.json';dump(config,dict(bundle=str(ROOT)))
            dump(p/'control/driver_state.json',dict(protocol_sha256=sha(config),completed_train=[{}]*35,completed_tracking=[{}]*42))
            with self.assertRaisesRegex(ValueError,'完整36'):analyze(config,p/'control',p/'analysis')
            self.assertFalse((p/'analysis').exists())
if __name__=='__main__':unittest.main()
