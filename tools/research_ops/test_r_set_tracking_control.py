"""常驻调度、数值帧预算与启动失败清理的独立CPU契约。"""
import json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).parent))
import r_set_tracking_control as c

class FakeService:
    instances=[];fail_at=None;frames=48
    def __init__(self,kind,cfg,log):
        if len(self.instances)==self.fail_at:raise RuntimeError('启动夹具失败')
        self.instances.append(self);self.closed=False;self.busy=None;self.task_failed=False
        self.kind=kind;self.process=SimpleNamespace(pid=len(self.instances));self.task=None
        self.parent=SimpleNamespace(send=lambda v:setattr(self,'task',v))
    def receive(self):return dict(status='complete',worker_pid=self.process.pid,result=dict(frames=self.frames))
    def close(self):
        self.closed=True;return dict(joined=True,exit_code=0,process_exited=True)
    def join_failed(self):self.closed=True;return dict(process_exited=True)

class Contracts(unittest.TestCase):
    def setUp(self):FakeService.instances=[];FakeService.fail_at=None;FakeService.frames=48
    def numeric(self,tmp):
        cfg=dict(numeric_output=str(Path(tmp)/'numeric'),worker_support={},gate_job_ids=['a','b'],
            jobs=[dict(job_id='a'),dict(job_id='b')],source_numeric_validation={})
        support=SimpleNamespace(resource_snapshot=lambda:{},enough_memory=lambda *a:True)
        helpers=SimpleNamespace(compare_payloads=lambda a,b:dict(original_ID_MOT_exact=True,raw_native_frames_exact=True,audit_exact=True))
        with patch.object(c,'Service',FakeService),patch.object(c,'producers_absent'),patch.object(c.rt,'safe',side_effect=Path),\
             patch.object(c.rt,'module',return_value=support),patch.object(c,'load',return_value=helpers),\
             patch.object(c,'write_new'),patch.object(c,'ref',return_value={}):
            return c.numeric('fixture',cfg)
    def test_actual_seven_payloads_336_frames_and_five_comparisons(self):
        with tempfile.TemporaryDirectory() as tmp:r=self.numeric(tmp)
        self.assertEqual(r['diagnostic_frame_consumptions'],336);self.assertEqual(r['unique_source_frames'],96)
        self.assertEqual(len(r['comparisons']),5);self.assertEqual(len(r['exits']),5)
        self.assertTrue(all(s.closed for s in FakeService.instances))
    def test_short_payload_cannot_claim_336(self):
        FakeService.frames=47
        with tempfile.TemporaryDirectory() as tmp,self.assertRaises(ValueError):self.numeric(tmp)
        self.assertTrue(all(s.closed for s in FakeService.instances))
    def test_second_spawn_startup_failure_closes_first_spawn(self):
        FakeService.fail_at=4
        with tempfile.TemporaryDirectory() as tmp,self.assertRaises(RuntimeError):self.numeric(tmp)
        self.assertEqual(len(FakeService.instances),4);self.assertTrue(all(s.closed for s in FakeService.instances))
    def test_message_requires_complete_and_actual_pid(self):
        s=SimpleNamespace(process=SimpleNamespace(pid=7),receive=lambda:dict(status='ready',worker_pid=7,result={}))
        with self.assertRaises(ValueError):c.completed(s)
        s.receive=lambda:dict(status='complete',worker_pid=8,result={})
        with self.assertRaises(ValueError):c.completed(s)
    def test_startup_failure_joins_and_preserves_receipt(self):
        parent=Mock();child=Mock();proc=Mock(pid=9,exitcode=1);proc.is_alive.return_value=False
        ctx=Mock();ctx.Pipe.return_value=(parent,child);ctx.Process.return_value=proc
        with tempfile.TemporaryDirectory() as tmp,patch.object(c.mp,'get_context',return_value=ctx),\
             patch.object(c.Service,'receive',side_effect=EOFError),patch.object(c.rt,'safe',side_effect=Path):
            log=Path(tmp)/'worker.log'
            with self.assertRaises(EOFError):c.Service('track',{},log)
            receipt=json.loads(log.with_suffix('.startup_failed.json').read_text(encoding='utf-8'))
        proc.join.assert_called_once_with(30);parent.close.assert_called_once()
        self.assertTrue(receipt['process_exited']);self.assertEqual(receipt['exit_code'],1)
    def test_startup_rejects_wrong_ready_pid(self):
        parent=Mock();child=Mock();proc=Mock(pid=9,exitcode=0);proc.is_alive.return_value=False
        ctx=Mock();ctx.Pipe.return_value=(parent,child);ctx.Process.return_value=proc
        with patch.object(c.mp,'get_context',return_value=ctx),patch.object(c.Service,'receive',return_value=dict(status='ready',worker_pid=10)),patch.object(c,'write_new'):
            with self.assertRaises(ValueError):c.Service('track',{},'fixture.log')
        proc.join.assert_called_once_with(30)
    def test_worker_metric_dispatch_uses_two_arguments_and_closes(self):
        conn=Mock();conn.recv.side_effect=[dict(op='metric',job={'job_id':'a'},tracking='ignored',output='metric'),dict(op='close')]
        context=Mock();context.run.return_value={'report':'fixture'};context.close.return_value={'status':'closed'}
        module=SimpleNamespace(MetricWorker=Mock(return_value=context),TrackWorker=Mock())
        with tempfile.TemporaryDirectory() as tmp,patch.object(c,'load',return_value=module):
            c.worker(conn,'metric',{},str(Path(tmp)/'metric.log'))
        context.run.assert_called_once_with({'job_id':'a'},'metric');context.close.assert_called_once()
        self.assertEqual([v.args[0]['status'] for v in conn.send.call_args_list],['ready','complete','closed'])
        module.TrackWorker.assert_not_called();conn.close.assert_called_once()
    def test_formal_queue_isolates_metric_and_finishes_gate_before_remaining_jobs(self):
        events=[];instances=[]
        class Pool(FakeService):
            def __init__(self,kind,cfg,log):
                self.closed=False;self.busy=None;self.task_failed=False;self.kind=kind;instances.append(self)
                self.process=SimpleNamespace(pid=len(instances),is_alive=lambda:True)
                self.ready=dict(status='ready',worker_pid=self.process.pid)
                self.parent=SimpleNamespace(send=self.send)
            def send(self,task):self.task=task;events.append((self.kind,task['job']['job_id']))
            def receive(self):
                job=self.task['job'];result=dict(job=job)
                if self.kind=='track':result['tracking']='tracking'
                else:result['report']={'path':'metric'}
                return dict(status='complete',worker_pid=self.process.pid,result=result)
        jobs=[dict(job_id=str(i),sequence='s') for i in range(180)]
        support=SimpleNamespace(resource_snapshot=lambda:{},enough_memory=lambda *a:True)
        analysis=SimpleNamespace(analyze=lambda *a:dict(status='complete180_R_set_tracking_all540_results450_pairs75_metric15_gap_intervals'))
        with tempfile.TemporaryDirectory() as tmp,patch.object(c,'Service',Pool),patch.object(c,'producers_absent'),\
             patch.object(c.rt,'safe',side_effect=Path),patch.object(c.rt,'module',return_value=support),\
             patch.object(c,'load',return_value=analysis),patch.object(c,'ref',return_value={}),patch.object(c.rt,'sha',return_value='sha'),\
             patch.object(c,'write_new'),patch.object(c,'wait',side_effect=lambda connections,timeout:connections),\
             patch.object(c,'read_ref',return_value=dict(status='complete',GT_rows=5,DO_PREPROC=False,predictions_GT_filtered=False,GT_ID0_original=True)):
            state=c.execute('fixture',dict(control_root=str(Path(tmp)/'control'),worker_support={},jobs=jobs,gate_job_ids=['0','1'],expected_GT_rows={'s':5}))
        self.assertEqual(state['status'],c.STATUS);self.assertEqual(len(state['completed_track']),180)
        self.assertEqual(len(state['completed_metric']),180);self.assertTrue(all(s.closed for s in instances))
        first_remaining=events.index(('track','2'))
        self.assertLess(events.index(('metric','0')),first_remaining);self.assertLess(events.index(('metric','1')),first_remaining)
        self.assertEqual(sum(k=='track' for k,j in events),180);self.assertEqual(sum(k=='metric' for k,j in events),180)

if __name__=='__main__':unittest.main()
