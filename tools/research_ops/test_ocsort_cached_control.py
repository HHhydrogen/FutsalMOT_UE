"""官方core控制器的真实收据schema与进程/GT边界CPU合同；不启动worker。"""
import ast
import hashlib
from copy import deepcopy
import inspect
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ocsort_cached_control as control
from ocsort_cached_admission import PARAMETERS as ADMISSION_PARAMETERS
from ocsort_cached_runtime import PARAMETERS as CORE_PARAMETERS


def reference(path, key): return dict(path=str(path), sha256=key)


def admission_fixture():
    formal = Path('D:/projects/FutsalMOT_Research/pose/ocsort_cached12_a01/frozen/config.json')
    receipt_path = formal.parent/'admission/receipt.json'; admission_path = formal.parent/'admission_config.json'
    formal_ref = reference(formal, 'formal_sha'); admission_ref = reference(admission_path, 'admission_sha')
    runtime_ref = reference(control.ROOT/'tools/research_ops/ocsort_cached_runtime.py', 'runtime_sha')
    sources = {'SNMOT-060': {'cache': reference('/cache/A', 'A')},
               'v_2QhNRucNC7E_c017': {'cache': reference('/cache/B', 'B')}}
    cfg = dict(admission_receipt_path=str(receipt_path), official_manifest=reference('/official', 'official'),
        dependency_manifest=reference('/dependencies', 'dependencies'), parameters=deepcopy(CORE_PARAMETERS),
        sources=sources, protected_GT_paths=['/private/gt', '/private/registry'])
    admission = dict(formal_protocol=formal_ref, official_manifest=cfg['official_manifest'],
        dependency_manifest=cfg['dependency_manifest'], parameters=cfg['parameters'], sources=sources,
        runtime=runtime_ref, admission_parameters=deepcopy(ADMISSION_PARAMETERS),
        protected_GT_paths=cfg['protected_GT_paths'])
    comparison = dict(original_ID_MOT_equal=True, all_frame_counts_equal=True, per_frame_raw_outputs_exact=True,
                      frames=48, tracked_rows=10, mot_sha256='mot', raw_outputs_sha256='raw')
    guard = dict(GT_Python_open_guard=True, self_test_blocked_opens=2, algorithm_blocked_GT_opens=0,
                 algorithm_GT_read=False, protected_paths=2)
    def closure(pid):
        return dict(kind='closed', pid=pid, jobs=['fixture'], GT_guard=deepcopy(guard), active_trackers=0,
                    exitcode=0, joined=True, actual_PID_absent_after_join=True)
    proof = dict(schema='official_ocsort_cached_admission_receipt_v1',
        status='complete_official_literal96_frames_ABA_two_spawn_exact_GT_guard_and_exit_verified', config=admission_ref,
        parameters=deepcopy(ADMISSION_PARAMETERS), official_backend={'manifest':cfg['official_manifest']},
        literal_vs_adapter={k:deepcopy(comparison) for k in ('A','B')},
        persistent_ABA=[dict(job=j, comparison=deepcopy(comparison), source_input_unchanged=True) for j in ('0A','1B','2A')],
        persistent_worker=closure(101), independent_spawn_A=[dict(comparison=deepcopy(comparison), closure=closure(pid),
            source_input_unchanged=True) for pid in (201,202)], parent_GT_guard=guard,
        source_prefixes={'A':sources['SNMOT-060']['cache'],'B':sources['v_2QhNRucNC7E_c017']['cache']},
        literal_internal_Kalman_dtypes={'A':['float64'],'B':['float64']},
        parent_source_input_unchanged=True, all_workers_joined_exited=True, unique_source_frames=96,
        TrackEval_runs=0, optimizer_updates=0, performance_speedup_claim=False, test_read=False)
    # 实际文件逐次JSON读取没有跨文件对象别名；夹具也必须隔离预期ref与待测载荷。
    admission=deepcopy(admission);proof=deepcopy(proof)
    documents = {str(receipt_path):proof, str(admission_path):admission}
    def fake_ref(path):
        if Path(path)==formal:return formal_ref
        if Path(path)==Path(runtime_ref['path']):return runtime_ref
        if Path(path)==receipt_path:return reference(receipt_path,'receipt_sha')
        raise AssertionError('未预期ref:'+str(path))
    return formal,cfg,admission,proof,documents,fake_ref


class Pipe:
    def __init__(self, message, ready=True): self.message=message;self.ready=ready;self.sent=[];self.closed=False
    def poll(self, timeout): return self.ready
    def recv(self): return self.message
    def send(self, value): self.sent.append(value)
    def close(self): self.closed=True


class Process:
    pid=701
    def __init__(self, alive=False, exitcode=0):self.alive=alive;self.exitcode=exitcode;self.joined=False
    def join(self, timeout):self.joined=True
    def is_alive(self):return self.alive


def service(evidence=None, ready_pid=701, alive=False, exitcode=0):
    value=object.__new__(control.Service);value.kind='track';value.busy=None;value.closed=False
    value.ready=dict(worker_pid=ready_pid);value.process=Process(alive,exitcode)
    value.parent=Pipe(dict(status='closed', evidence=evidence or dict(status='closed',worker_pid=701)))
    return value


class OCControlTests(unittest.TestCase):
    def call_admission(self, mutate=None):
        path,cfg,admission,proof,documents,fake_ref=admission_fixture()
        if mutate:mutate(cfg,admission,proof)
        with patch.object(control,'physical',side_effect=lambda p:Path(p)), \
             patch.object(control,'checked',side_effect=lambda r:Path(r['path'])), \
             patch.object(control,'read',side_effect=lambda p:documents[str(p)]), \
             patch.object(control,'ref',side_effect=fake_ref):
            return control.check_admission(path,cfg)

    def test_actual_admission_schema_prospective_formal_binding_accepted(self):
        result=self.call_admission()
        self.assertEqual(result['sha256'],'receipt_sha')

    def test_admission_wrong_formal_runtime_dependency_or_legacy_status_rejected(self):
        mutations=(lambda c,a,p:a['formal_protocol'].update(sha256='other'),
            lambda c,a,p:a.update(runtime=reference('/other_runtime','other')),
            lambda c,a,p:a.update(dependency_manifest=reference('/other_dependencies','other')),
            lambda c,a,p:p.update(status='complete_fixture_only'),
            lambda c,a,p:p.update(all_workers_joined_exited=False))
        for mutate in mutations:
            with self.assertRaises(ValueError):self.call_admission(mutate)

    def test_actual_admission_evidence_failure_cannot_hide_behind_complete_status(self):
        mutations=(lambda c,a,p:p['literal_vs_adapter']['A'].update(per_frame_raw_outputs_exact=False),
            lambda c,a,p:p['independent_spawn_A'][0]['closure'].update(joined=False),
            lambda c,a,p:p['independent_spawn_A'][1]['closure'].update(pid=201),
            lambda c,a,p:p['parent_GT_guard'].update(algorithm_blocked_GT_opens=1),
            lambda c,a,p:p['parent_GT_guard'].update(self_test_blocked_opens=0),
            lambda c,a,p:p.update(literal_internal_Kalman_dtypes={'A':['float32'],'B':['float64']}),
            lambda c,a,p:p.update(unique_source_frames=95))
        for mutate in mutations:
            with self.assertRaises(ValueError):self.call_admission(mutate)

    def test_protected_paths_cover_actual_GT_gameinfo_seqinfo_and_private_registries(self):
        sources={'A':dict(cache=reference('/public/pred','p'),gt=reference('/private/gt','g'),
            gameinfo=reference('/private/gameinfo','i'),seqinfo=reference('/private/seqinfo','s')),
            'B':dict(gt_reference=reference('/private/other_gt','g2'))}
        registries={key:dict(registry=reference('/private/'+key,'r'),receipt=reference('/public/'+key,'u'))
                    for key in ('old_five','seven')}
        result=control.protected_paths(sources,registries)
        self.assertEqual(set(result),{'/private/gt','/private/gameinfo','/private/seqinfo','/private/other_gt',
                                    '/private/old_five','/private/seven'})
        self.assertNotIn('/public/pred',result);self.assertNotIn('/public/seven',result)

    def test_track_class_has_guard_before_official_and_never_calls_V_validation_or_GT_loader(self):
        tree=ast.parse(inspect.getsource(control.TrackWorker))
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)]
        attrs=[n.func.attr for n in calls if isinstance(n.func,ast.Attribute)]
        self.assertNotIn('validate_config',attrs);self.assertNotIn('load_gt',attrs)
        init=next(n for n in tree.body[0].body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
        initcalls=[n for n in ast.walk(init) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        installed=next(n.lineno for n in initcalls if n.func.attr=='install')
        official=next(n.lineno for n in initcalls if n.func.attr=='load_official')
        self.assertLess(installed,official)

    def test_Service_requires_PID_and_inner_close_evidence_then_join_exit0(self):
        value=service();proof=value.close()
        self.assertTrue(value.process.joined);self.assertTrue(proof['process_exited'])
        self.assertEqual(value.parent.sent,[dict(op='close')]);self.assertTrue(value.parent.closed)
        for value in (service(dict(status='failed',worker_pid=701)),service(dict(status='closed',worker_pid=999)),
                      service(ready_pid=999),service(alive=True),service(exitcode=7)):
            with self.assertRaises(ValueError):value.close()

    def test_Service_does_not_report_close_for_busy_or_failed_or_timed_out_worker(self):
        value=service();value.busy='active_sequence'
        with self.assertRaises(ValueError):value.close()
        self.assertEqual(value.parent.sent,[])
        value=service();value.parent=Pipe(dict(status='failed',traceback='actual_child_failed'))
        with self.assertRaisesRegex(ValueError,'actual_child_failed'):value.receive()
        value=service();value.parent=Pipe({},ready=False)
        with self.assertRaises(ValueError):value.receive()


class DependencyReadBoundaryTests(unittest.TestCase):
    ENTRIES=tuple(Path('D:/projects/FutsalMOT/.venv/Lib/site-packages')/name/'__init__.py'
                  for name in ('numpy','scipy'))

    def test_actual_two_dependency_entries_allow_read_only_SHA_checks(self):
        references=[]
        for path in self.ENTRIES:
            self.assertTrue(path.is_file(), '当前真实环境已固定的入口不存在')
            references.append(reference(path,hashlib.sha256(path.read_bytes()).hexdigest()))
        original=Path.open;opened=[]
        def readonly(path,mode='r',*args,**kwargs):
            self.assertIn(mode,('r','rb'),'依赖核验不能通过任何写模式打开环境')
            opened.append((path,mode));return original(path,mode,*args,**kwargs)
        with patch.object(Path,'open',new=readonly):
            for value in references:
                self.assertEqual(control.checked_dependency(value),Path(value['path']))
        self.assertEqual({p for p,_ in opened},set(self.ENTRIES))
        self.assertTrue(all(mode=='rb' for _,mode in opened))

    def test_other_venv_files_and_external_GT_rejected_before_open(self):
        denied=(self.ENTRIES[0].with_name('_globals.py'),self.ENTRIES[1].with_name('gt.txt'),
                Path('D:/private/SNMOT-060/gt/gt.txt'))
        with patch.object(Path,'read_bytes',side_effect=AssertionError('不得打开非白名单依赖或GT')):
            for path in denied:
                with self.assertRaises(ValueError):control.checked_dependency(reference(path,'0'*64))

    def test_general_physical_and_write_roots_remain_research_only(self):
        with patch.object(Path,'open',side_effect=AssertionError('不能写入或普通读取venv')):
            for path in self.ENTRIES:
                with self.assertRaises(ValueError):control.physical(path)
                with self.assertRaises(ValueError):control.write_new(path,{'never_written':True})
                with self.assertRaises(ValueError):control.checked(reference(path,'0'*64))

    def test_changed_expected_SHA_rejected_without_modifying_dependency(self):
        for path in self.ENTRIES:
            before=hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):control.checked_dependency(reference(path,'0'*64))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)


if __name__=='__main__':unittest.main()
