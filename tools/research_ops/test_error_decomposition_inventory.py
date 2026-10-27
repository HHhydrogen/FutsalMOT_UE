"""27/63只读来源清单的最小CPU合同，不打开真实研究数据。"""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import error_decomposition_inventory as inventory


class Inventory(unittest.TestCase):
    def fixture_units(self):
        traces=[];missing=[]
        for i,(sequence,fold,seed) in enumerate(sorted(inventory.expected_old_cells())):
            traces.append(dict(unit_id='trace'+str(i),sequence=sequence,fold=fold,seed=seed,
                expected_stage_rows=320752 if i==0 else 0, expected_stage_calls=24863 if i==0 else 0,
                stage_assignment_reference={'events':'ref'} if seed==inventory.FIRST_SEED else None))
        for sequence in ['N'+str(i) for i in range(7)]:
            for fold in inventory.FOLDS:
                for seed in inventory.SEEDS:missing.append(dict(sequence=sequence,fold=fold,seed=seed))
        return traces+missing,traces,missing

    def reference(self,path):
        return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    def test_exact27_balanced_and63_unknown_with9_first_seed(self):
        strong,traces,missing=self.fixture_units();inventory.validate_coverage(strong,traces,missing)
        for bad in (traces[:-1], traces+[deepcopy(traces[0])]):
            with self.assertRaises(ValueError):inventory.validate_coverage(strong,bad,missing)
        wrong=deepcopy(traces);wrong[0]['seed']=999
        with self.assertRaises(ValueError):inventory.validate_coverage(strong,wrong,missing)
        wrong=deepcopy(traces);wrong[0]['expected_stage_rows']-=1
        with self.assertRaises(ValueError):inventory.validate_coverage(strong,wrong,missing)

    def test_data_references_not_rehashed_or_opened(self):
        with TemporaryDirectory() as directory,patch.object(inventory,'R',Path(directory)):
            path=Path(directory)/'cache.jsonl';path.write_text('do not read',encoding='utf-8')
            reference=dict(path=str(path),sha256='a'*64)
            with patch.object(Path,'open',side_effect=AssertionError('不得读取数据')):
                inventory.assert_data_ref(reference)
            with self.assertRaises(ValueError):inventory.read_metadata(reference)

    def test_metadata_rejects_GT_label_and_endpoint_reads(self):
        with TemporaryDirectory() as directory,patch.object(inventory,'R',Path(directory)):
            for filename in ('posthoc_GT_labels.json','gap_registry.json'):
                path=Path(directory)/filename;path.write_text('{}',encoding='utf-8')
                with self.assertRaises(ValueError):inventory.read_metadata(self.reference(path))

    def test_metadata_SHA_and_test_scope_strict(self):
        with TemporaryDirectory() as directory,patch.object(inventory,'R',Path(directory)):
            path=Path(directory)/'receipt.json';path.write_text('{"status":"complete"}',encoding='utf-8')
            reference=self.reference(path);self.assertEqual(inventory.read_metadata(reference)['status'],'complete')
            with self.assertRaises(ValueError):inventory.read_metadata(dict(reference,sha256='b'*64))
            with self.assertRaises(ValueError):inventory.safe(Path(directory)/'test/a.json')
            with self.assertRaises(ValueError):inventory.safe(Path(directory)/'SNMOT-116/a.json')

    def test_trace_header_nonempty_actual_cost_and_endframe_UID_differentiated(self):
        event=dict(frame_number=2,stage=0,track_ids=[1],history_UIDs=[['old']],candidate_UIDs=['candidate'],
            bbox_cost=[[.2]],reference_cost=[[.3]],motion_gate=[[False]],enabled=[[False]],active_rows=[False],
            enough_history=[False],lost_gap=[False],scored_locations=[],logits={},quality=[],quality_gates={},
            chosen_raw_UID=['endframe_not_explicit_stage_assignment'],GT_read=False)
        with TemporaryDirectory() as directory,patch.object(inventory,'R',Path(directory)):
            path=Path(directory)/'common_state_trace.jsonl.gz'
            with gzip.open(path,'wt',encoding='utf-8') as stream:stream.write(json.dumps(event)+'\n')
            header=inventory.trace_header(self.reference(path))
            self.assertFalse(header['complete_trace_rehashed'])
            self.assertIn('not_explicit_stage_assignment',header['chosen_raw_UID'])
            event['reference_cost']=[]
            with gzip.open(path,'wt',encoding='utf-8') as stream:stream.write(json.dumps(event)+'\n')
            with self.assertRaises(ValueError):inventory.trace_header(self.reference(path))

    def test_no_hidden_ledger_path_or_new_execution_in_API(self):
        import inspect
        self.assertEqual(list(inspect.signature(inventory.build_inventory).parameters),
            ['policy_inventory_ref','information_report_ref','decision_report_ref','ledger_complete_ref'])
        self.assertNotIn('torch', inventory.__dict__)

    def test_nine_assignment_refs_never_parse_events_with_posthoc_labels(self):
        with TemporaryDirectory() as directory,patch.object(inventory,'R',Path(directory)):
            root=Path(directory);details={};refs=[];first_path=None
            events=root/'events.jsonl.gz';events.write_bytes(b'not_opened_or_decoded_in_inventory')
            event_ref=dict(path=str(events),sha256='a'*64)
            for index in range(9):
                key='source'+str(index);trace=dict(path='trace'+str(index),sha256='trace')
                receipt=dict(path='receipt'+str(index),sha256='receipt')
                details[key]=dict(job={'original':{'seed':inventory.FIRST_SEED}},trace=trace,receipt=receipt,
                    counts={'stage_calls':1,'all_stage_rows':2})
                for group in ('T_RS','T_shuffle_RS'):
                    summary=dict(status='complete_new_T_fixed_state_probe_unit_not_free_tracking',
                        job=dict(source_job_id=key,pool='balanced',seed=inventory.FIRST_SEED,group=group),
                        new_optimizer_updates=0,new_free_tracking=False,trace=trace,source_receipt=receipt,
                        diagnostic_event_limit=None,counts={'stage_events':1,'stage_rows':2},events=event_ref)
                    path=root/f'{index}_{group}.json';path.write_text(json.dumps(summary),encoding='utf-8')
                    if first_path is None:first_path=path
                    refs.append(self.reference(path))
            report=dict(status='complete18_new_T_fixed_state_decision_probe_zero_updates_not_free_tracking',
                source_trace_units=9,scoring_units=18,new_optimizer_updates=0,new_free_tracking=False,units=refs)
            with patch.object(inventory,'first_gzip_record',side_effect=AssertionError('不得解析后验标签事件')):
                values=inventory.decision_references(report,details)
            self.assertEqual(len(values),9)
            self.assertTrue(all(value['checked_header_records']==0 and value['record_path']=='new_T.reference.assignment'
                and value['record_path_is_numeric_gate_obligation'] for value in values.values()))
            content=json.loads(first_path.read_text());content['counts']['stage_events']=0
            first_path.write_text(json.dumps(content),encoding='utf-8');report['units'][0]=self.reference(first_path)
            with self.assertRaises(ValueError):inventory.decision_references(report,details)


if __name__=='__main__':unittest.main()
