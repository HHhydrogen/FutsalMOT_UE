"""新权重身份/无截距路由/常驻原生输出与GT隔离的CPU夹具。"""
from copy import deepcopy
from pathlib import Path
import sys,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import state_aligned_tracking_workers as w
import test_trainR_intercept_tracking as fixtures
import trainR_intercept_tracking as framework

def worker_fixture(root):
    worker,job,loaded,frames=fixtures.worker_fixture(root)
    worker.__class__=w.TrackWorker;worker.framework=framework
    job['baseline_model_id']='old_different_id'
    worker.cfg.update(learning_protocol=dict(path='new_training',sha256='new'),training_budget=dict(path='new_budget',sha256='budget'))
    worker.binding.spec=lambda value:job if value==job else (_ for _ in ()).throw(ValueError('unknown'))
    loaded.pop('shifted');loaded.pop('zero');loaded.pop('beta32');loaded.pop('fit')
    return worker,job,loaded,frames

class Contracts(unittest.TestCase):
    def test_direct_new_model_forward_no_beta_wrapper_and_full_state_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            worker,job,loaded,frames=worker_fixture(Path(tmp));before=deepcopy(frames)
            a=worker.payload(job,prefix_frames=2);b=worker.payload(job,prefix_frames=2)
            self.assertEqual(len(loaded['base'].calls),4);self.assertEqual(a['raw_frames'][0][0][4],1)
            self.assertTrue(w.compare_payloads(a,b)['original_ID_MOT_exact']);self.assertEqual(frames,before)
            self.assertFalse(a['intercept_applied']);self.assertFalse(a['calibration_metadata_read'])
            self.assertTrue(a['original_base_forward_without_intercept_wrapper'])
            self.assertEqual(a['baseline_model_id'],'old_different_id')
            self.assertFalse(any(k in a for k in ('fit','beta32','calibrated_beta32','diagnostic_beta0')))
            with self.assertRaises(TypeError):worker.payload(job,diagnostic_beta0=True)
    def test_numeric_prefix_requires_own_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            worker,job,_,_=worker_fixture(Path(tmp));worker.cfg['numeric_authorized']=False
            with self.assertRaises(ValueError):worker.payload(job,prefix_frames=2)
            worker.payload(job)
    def test_compare_cannot_hide_GT_read_beta_alias_or_raw_native_difference(self):
        with tempfile.TemporaryDirectory() as tmp:
            worker,job,_,_=worker_fixture(Path(tmp));a=worker.payload(job)
            for key,value in (('intercept_applied',True),('calibration_metadata_read',True),('alias_used',True),
                    ('raw_frames',[]),('audit',{}),('evaluation_GT_coordinate_files_opened',True)):
                b=deepcopy(a);b[key]=value
                with self.assertRaises(ValueError,msg=key):w.compare_payloads(a,b)
    def test_new_tracking_receipt_preserves_sources_native_sha_and_no_calibration_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);worker,job,_,_=worker_fixture(root)
            with patch.object(w,'safe',side_effect=lambda path,root=None:Path(path)),patch.object(w,'ref',side_effect=framework.ref),patch.object(w.rt,'sha',side_effect=framework.sha):
                value=worker.run(job,root/'new/tracking');r=framework.read_ref(value['receipt'])
                self.assertEqual(r['schema'],w.TRACK_SCHEMA);self.assertEqual(r['job'],job)
                self.assertFalse(r['intercept_applied']);self.assertEqual(r['learning_protocol'],worker.cfg['learning_protocol'])
                self.assertEqual(r['training_budget'],worker.cfg['training_budget'])
                self.assertNotIn('raw_frames',r);self.assertNotIn('fit',r);self.assertNotIn('beta32',r)
                with self.assertRaises(ValueError):worker.run(job,root/'new/tracking')
                close=worker.close();self.assertFalse(close['calibration_metadata_read']);self.assertNotIn('calibration_trainR_metadata_parsed',close)
                self.assertTrue(close['source_closure_verified'])
    def test_metric_rejects_old_intercept_receipt_before_GT_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);worker,job,_,_=worker_fixture(root)
            metric=w.MetricWorker.__new__(w.MetricWorker);metric.cfg=dict(worker.cfg,control_root=str(root),sources={job['sequence']:dict(cache={},frames=2)})
            metric.binding=worker.binding;metric.closed=False
            receipt=dict(schema='trainR_intercept_tracking_receipt_v1',status='complete',job=job)
            with patch.object(w,'safe',side_effect=lambda path,root=None:Path(path)),patch.object(w,'ref',return_value={}),patch.object(w,'read_ref',return_value=receipt):
                with self.assertRaises(ValueError):metric.run(job,root/'metric')
    def test_original_metric_AST_functions_reused_and_all_unmatched_kept(self):
        source=Path(__file__).parent/'v10_metric.py';binding=SimpleNamespace(old={},old_rt=SimpleNamespace(require=w.require),source=lambda cfg,path:framework.ref(source))
        numeric,proof=framework.metric_functions(binding)
        # 原tracker预测ID从1开始；SportsMOT合法GT ID0不等于预测ID0。
        text='1,1,0,0,10,10,.9,-1,-1,-1\n1,2,90,90,5,5,.1,-1,-1,-1\n'
        values,count=numeric.prediction_rows(text,2)
        self.assertEqual(count,2);self.assertEqual([x['uid'] for x in values[1]],['1','2'])
        self.assertTrue(proof['numerical_function_AST_unchanged'])
    def test_metric_new_identity_keeps_all_predictions_and_full_gap_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);worker,job,_,_=worker_fixture(root);seq=job['sequence'];cache=dict(path='cache',sha256='cache')
            output=root/'metric';tracking=root/'runs'/job['job_id']/'tracking';tracking.mkdir(parents=True);mot=tracking/'data.txt'
            mot.write_text('1,1,0,0,10,10,.9,-1,-1,-1\n1,2,90,90,5,5,.1,-1,-1,-1\n',encoding='utf-8')
            receipt=dict(schema=w.TRACK_SCHEMA,status='complete',job=job,protocol_sha256='protocol_fixture',source_cache=cache,
                frames=2,learning_protocol=worker.cfg['learning_protocol'],training_budget=worker.cfg['training_budget'],baseline_model_id=job['baseline_model_id'],
                intercept_applied=False,calibration_metadata_read=False,GT_used_for_tracking=False,evaluation_GT_coordinate_files_opened=False,
                test_read=False,alias_used=False,mot=framework.ref(mot),tracked_rows=2,frame_counts=[2,0])
            framework.write_new(tracking/'receipt.json',receipt)
            source=dict(cache=cache,frames=2);registry=dict(sources={seq:source},sequences={seq:dict(cache=cache,endpoint_GT=[])},events=[dict(sequence=seq)])
            regref=dict(path='registry',sha256='registry')
            cfg=dict(worker.cfg,control_root=str(root),sources={seq:source},panels=dict(seven_observed=[]),expected_GT_rows={seq:1},registries=dict(old_five=dict(registry=regref)))
            numeric,proof=framework.metric_functions(SimpleNamespace(old={},old_rt=SimpleNamespace(require=w.require),source=lambda c,p:framework.ref(Path(__file__).parent/'v10_metric.py')))
            count=dict(Dets=2,GT_Dets=1,Frames=2);raw={seq:{'pedestrian':dict(Count=count,HOTA=dict(HOTA=[.2],AssA=[.3],DetA=[.4]),Identity=dict(IDF1=.5),CLEAR=dict(MOTA=.6,IDSW=0))}}
            numeric.trackeval_numeric=lambda *args:(raw,'numeric')
            metric=w.MetricWorker.__new__(w.MetricWorker);metric.cfg=cfg;metric.binding=worker.binding;metric.jobs=0;metric.closed=False
            metric.metric=numeric;metric.numeric_evidence=proof;metric.GT={seq:({},['1,0,0,0,10,10,1,1,1'])};metric.registries={'registry':registry}
            metric.gap=SimpleNamespace(evaluate_events=lambda events,gt,pred:dict(overall=dict(total_events=len(events),recovered=0),fixture_all_predictions=sum(map(len,pred.values()))))
            with patch.object(w,'safe',side_effect=lambda path,root=None:Path(path)),patch.object(w,'ref',side_effect=framework.ref), \
                    patch.object(w,'read_ref',return_value=receipt),patch.object(w,'checked',side_effect=lambda value:Path(value['path'])):
                answer=metric.run(job,output)
            report=framework.read_ref(answer['report']);self.assertEqual(report['schema'],w.METRIC_SCHEMA)
            self.assertEqual(report['tracked_rows'],2);self.assertEqual(report['gap']['overall']['total_events'],1)
            self.assertEqual(report['gap']['fixture_all_predictions'],2);self.assertFalse(report['DO_PREPROC']);self.assertFalse(report['predictions_GT_filtered'])
            self.assertTrue(report['GT_ID0_original']);self.assertEqual(report['metrics'],dict(AssA=30.,HOTA=20.,IDF1=50.,DetA=40.,MOTA=60.))
            self.assertNotIn('beta32',report);self.assertNotIn('fit',report)

if __name__=='__main__':unittest.main()
