"""诊断来源/曝光/GT边界的针对性合同，不冒充真实模型准入。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parent))
import state_gap_runtime as rt

def fixture():
    models=[dict(model_id=r+f,regime=r,fold=f,seed=20261024) for r in ('R','RS') for f in rt.OLD.values()]
    sources={seq:dict(frames=750,game=game) for seq,game in rt.OLD.items()}
    folds={f:dict(allowed_sequences=[seq for seq,g in rt.OLD.items() if g!=f]) for f in rt.OLD.values()}
    inventory=dict(models=models,sources=sources,folds=folds)
    jobs=[dict(job_id=s['model_id']+seq,sequence=seq,**s) for s in models for seq in folds[s['fold']]['allowed_sequences']]
    cfg=dict(jobs=jobs,sources=sources,tracker_parameters=deepcopy(rt.FIXED_ARGS),optimizer_updates=0,new_image_predictions=0)
    return cfg,inventory

class Contracts(unittest.TestCase):
    def test_rollout_schema_is_retained_without_receipt_schema_collision(self):
        result=rt.compose_observe_receipt(dict(schema='train_free_state_rollout_v1',frames=96),dict(inputs_unchanged=True),dict(status='complete'))
        self.assertEqual(result['schema'],'state_gap_observe_receipt_v1');self.assertEqual(result['rollout_schema'],'train_free_state_rollout_v1')
        with self.assertRaises(ValueError):rt.compose_observe_receipt(dict(frames=96),dict(frames=1),{})
    def test_resource_sampler_is_not_GT_guard(self):
        with self.assertRaises(ValueError):rt.require_guard_api(SimpleNamespace(resource_snapshot=lambda:None,enough_memory=lambda:True))
        rt.require_guard_api(SimpleNamespace(GTReadGuard=lambda:None,BoundedLRU=lambda:None,deep_bytes=lambda:0))
    def test_twelve_exact_train_cells(self):
        cfg,inv=fixture();self.assertEqual(len(rt.validate_matrix(cfg,inv)),6)
    def test_heldout_cannot_replace_allowed(self):
        cfg,inv=fixture();cfg['jobs'][0]['sequence']='SNMOT-060'
        with self.assertRaises(ValueError):rt.validate_matrix(cfg,inv)
    def test_duplicate_regime_inventory_rejected(self):
        cfg,inv=fixture();inv['models'][3]['regime']='R'
        with self.assertRaises(ValueError):rt.validate_matrix(cfg,inv)
    def test_no_source_or_count_growth(self):
        cfg,inv=fixture();cfg['sources']['SNMOT-060']['frames']=751
        with self.assertRaises(ValueError):rt.validate_matrix(cfg,inv)
    def test_no_numeric_or_training_factor_change(self):
        for key in ('optimizer_updates','new_image_predictions'):
            cfg,inv=fixture();cfg[key]=1
            with self.assertRaises(ValueError):rt.validate_matrix(cfg,inv)
        cfg,inv=fixture();cfg['tracker_parameters']['match_thresh']=.7
        with self.assertRaises(ValueError):rt.validate_matrix(cfg,inv)
    def test_test_and_outside_write_rejected(self):
        for path in ('D:/projects/FutsalMOT_Research/public/test/x','D:/projects/FutsalMOT_Research/public/train/SNMOT-116/x'):
            with self.assertRaises(ValueError):rt.safe(path)
        with self.assertRaises(ValueError):rt.safe('D:/projects/FutsalMOT_Research/pose/other/result.json',rt.EXP)

if __name__=='__main__':unittest.main()
