"""诊断来源/曝光/GT边界的针对性合同，不冒充真实模型准入。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from contextlib import nullcontext
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib
import gzip
from io import StringIO

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
    def test_online_array_digest_exact_empty_unicode_float_and_repeated_finish(self):
        fixtures=[[],[None,False,1,1.0,-0.0,'中文'],[[[1.25,2],[]],{'x':'中','a':[0,1]}]]
        for values in fixtures:
            digest=rt.ArrayDigest()
            for value in values:digest.add(value)
            expected=hashlib.sha256(rt.canonical(values).encode('utf-8')).hexdigest()
            self.assertEqual(digest.hexdigest(),expected)
            self.assertEqual(digest.hexdigest(),expected)
            self.assertEqual(digest.count,len(values))

    def test_iter_rows_checks_SHA_before_open_and_rejects_wrong_full_count(self):
        with patch.object(rt,'checked',side_effect=ValueError('SHA变化')),patch.object(rt.gzip,'open') as opened:
            with self.assertRaisesRegex(ValueError,'SHA变化'):next(rt.iter_rows({}))
            opened.assert_not_called()
        with patch.object(rt,'checked',return_value=Path('unused')), \
                patch.object(rt.gzip,'open',return_value=StringIO('{"a":1}\n{"a":2}\n')):
            self.assertEqual(list(rt.iter_rows(dict(rows=2))),[{'a':1},{'a':2}])
        with patch.object(rt,'checked',return_value=Path('unused')), \
                patch.object(rt.gzip,'open',return_value=StringIO('{"a":1}\n')):
            with self.assertRaisesRegex(ValueError,'完整日志行数不同'):list(rt.iter_rows(dict(rows=2)))

    def test_posthoc_streams_full_annotation_without_read_rows(self):
        import state_gap_analysis as analysis
        import test_state_gap_analysis as examples
        job=examples.META;source=examples.source_fixture();frames=examples.rollout_fixture()
        context=rt.PosthocContext.__new__(rt.PosthocContext)
        context.analysis=analysis;context.jobs=0;context.labeled=lambda sequence:source
        original=dict(job=job,frames=750,frames_log={'path':'stream'})
        saved={};written=[]
        class Writer:
            def __init__(self,path):pass
            def write(self,row):written.append(row)
            def close(self):return dict(path='rows',rows=len(written))
        with TemporaryDirectory() as folder,patch.object(rt,'safe',side_effect=lambda value,parent=None:Path(value)), \
                patch.object(rt,'read_ref',return_value=original),patch.object(rt,'RowsWriter',Writer), \
                patch.object(rt,'iter_rows',side_effect=lambda reference:iter(frames)) as reader, \
                patch.object(rt,'read_rows',side_effect=AssertionError('正式后验不能整卷物化')), \
                patch.object(rt,'write_new',side_effect=lambda path,value:saved.update(value)), \
                patch.object(rt,'ref',side_effect=lambda path:dict(path=str(path))):
            context.annotate(job,dict(observe={}),Path(folder)/'posthoc')
        expected=analysis.annotate_rollout(frames,source,job)
        self.assertEqual(reader.call_count,2)
        self.assertEqual(written,expected.pop('rows'))
        for key,value in expected.items():self.assertEqual(saved[key],value)
        self.assertEqual(saved['events'],analysis.select_first_errors(frames,source,job))
        self.assertNotIn('rows',saved)

    def test_observe_receipt_does_not_materialize_full_trace(self):
        rows=[dict(native_output=[[1,2]],full_state_sha256='a'),dict(native_output=[],full_state_sha256='b')]
        def run(tracker,frames,**kwargs):
            for row in rows:kwargs['frame_sink'](row)
            return dict(schema='rollout',frame_states=[],native_frames=[],frames=2,frame_counts=[1,0])
        class Writer:
            def __init__(self,path):pass
            def write(self,row):pass
            def close(self):return dict(path='not_read',sha256='a'*64,rows=2)
        state=SimpleNamespace(clone=lambda:None)
        context=SimpleNamespace(cfg=dict(_protocol_ref={},sources={'s':dict(cache={})}),jobs=0,
            new_tracker=lambda job:object(),frames=lambda seq:[{},{}],checkpoint=lambda:{},
            BaseTrack=SimpleNamespace(_count=0),
            torch=SimpleNamespace(get_rng_state=lambda:state,equal=lambda a,b:True,no_grad=nullcontext))
        saved={}
        with TemporaryDirectory() as folder,patch.object(rt,'safe',side_effect=lambda value,parent=None:Path(value)), \
                patch.object(rt,'load_own',return_value=SimpleNamespace(run_rollout=run)), \
                patch.object(rt,'RowsWriter',Writer),patch.object(rt,'observer_kwargs',return_value={}), \
                patch.object(rt,'read_rows',side_effect=AssertionError('正式路径不能整卷物化')), \
                patch.object(rt,'write_new',side_effect=lambda path,value:saved.update(value)), \
                patch.object(rt,'ref',side_effect=lambda path:dict(path=str(path))):
            rt.observe_job(context,dict(sequence='s'),Path(folder)/'new')
        digest=lambda value:hashlib.sha256(rt.canonical(value).encode()).hexdigest()
        self.assertEqual(saved['native_sha256'],digest([row['native_output'] for row in rows]))
        self.assertEqual(saved['state_sequence_sha256'],digest([row['full_state_sha256'] for row in rows]))

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
