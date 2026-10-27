"""只读政策清单的CPU夹具；不打开真实缓存、GT、媒体或模型。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import tracking_policy_inventory as inventory


class Inventory(unittest.TestCase):
    def make(self, root, relative, value):
        path = root/relative; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')
        return inventory.ref(path)

    def test_fixed_matrix114_and_76315_unit_frames(self):
        sources = {s: {'frames': 750} for s in inventory.OLD}
        sources.update({s: {'frames': n} for s, n in [('externalA',450),('externalB',675),('a',725),('b',775),('c',701),('d',550),('e',700),('f',888),('g',451)]})
        units = [dict(method=m, sequence=s, fold=f, seed=z, unit_id=str(i), mot={'path':str(i)}, frames=sources[s]['frames'])
                 for i,(m,s,f,z) in enumerate(inventory.expected_cells(sources))]
        inventory.validate_units(units, sources)
        wrong = deepcopy(units); wrong[0] = deepcopy(wrong[1])
        with self.assertRaises(ValueError): inventory.validate_units(wrong, sources)
        with self.assertRaises(ValueError): inventory.validate_units(units[:-1], sources)
        wrong = deepcopy(units); wrong[0]['method'] = 'T_RS'
        with self.assertRaises(ValueError): inventory.validate_units(wrong, sources)

    def test_three_panels_cannot_overlap_or_pool_matches(self):
        panels = dict(original_heldout=list(inventory.OLD), old_external=['d','e'], seven_observed=list('fghijkl'))
        self.assertEqual(len(inventory.panel_lookup(panels)),12)
        panels['seven_observed'][0] = 'd'
        with self.assertRaises(ValueError): inventory.panel_lookup(panels)

    def test_cache_ref_assertion_does_not_open_or_hash(self):
        reference = dict(path=str(inventory.R/'public/never_opened/cache.jsonl'),sha256='a'*64)
        with patch.object(Path, 'open', side_effect=AssertionError('缓存不得打开')):
            inventory.assert_unread_ref(reference)
        with self.assertRaises(ValueError): inventory.assert_unread_ref(dict(reference,sha256='short'))

    def test_exact_frozen_function_evidence_no_module_execution(self):
        with TemporaryDirectory() as directory, patch.object(inventory, 'R', Path(directory)):
            root = Path(directory); path=root/'code/runtime.py';path.parent.mkdir()
            path.write_text('raise RuntimeError("不能导入整个模块")\ndef load_gt(source):\n    return {}, []\n',encoding='utf-8')
            value = inventory.function_evidence(inventory.ref(path),'load_gt')
            self.assertEqual(value['signature'],['source'])
            self.assertFalse(value['GT_loaded_by_inventory'])

    def test_unknown_historical_schema_rejected_not_broad_fallback(self):
        report=dict(status='complete',DO_PREPROC=False,predictions_GT_filtered=False,test_read=False,
                    schema='invented_old',job={'sequence':'SNMOT-060'})
        with TemporaryDirectory() as directory, patch.object(inventory, 'R', Path(directory)):
            reference=self.make(Path(directory),'runs/actual_id/metric/report.json',report)
            with self.assertRaises(ValueError):
                inventory.tracking_from_metric(reference,report,'PT_bbox','SNMOT-060',
                    {'panels':{'seven_observed':[]}}, {}, {})

    def test_sha_only_historical_layout_binds_receipt_and_real_MOT(self):
        with TemporaryDirectory() as directory, patch.object(inventory, 'R', Path(directory)):
            root=Path(directory); base=root/'runs/not_a_guessed_job_hash';seq='SNMOT-060'
            mot=base/'tracking/data'/f'{seq}.txt';mot.parent.mkdir(parents=True)
            mot.write_text('1,17,1,2,3,4,.8,-1,-1,-1\n',encoding='utf-8')
            cache=dict(path=str(root/'cache.jsonl'),sha256='a'*64)
            job=dict(kind='PT',mode='PT_bbox',sequence=seq)
            receipt=dict(schema='v10_independent_free_tracking_v1',status='complete',test_read=False,
                GT_read=False,frames=2,tracked_rows=1,frame_counts=[1,0],cache=cache,job=job,mot_sha256=inventory.sha(mot))
            rec=self.make(root,'runs/not_a_guessed_job_hash/tracking/receipt.json',receipt)
            metric=dict(schema='v10_independent_trackeval_gap_v1',status='complete',DO_PREPROC=False,
                predictions_GT_filtered=False,test_read=False,job=job,protocol_sha256='old',
                tracking_receipt_sha256=rec['sha256'],frames=2,raw_results={seq:{'pedestrian':{'Count':{'Dets':1}}}})
            met=self.make(root,'runs/not_a_guessed_job_hash/metric/report.json',metric)
            config=dict(sources={seq:{'frames':2,'cache':cache}},panels={'seven_observed':[]},_old_protocol_sha='old')
            actual,actualmot,_,basis=inventory.tracking_from_metric(met,metric,'PT_bbox',seq,config,{}, {})
            self.assertEqual(actual,rec);self.assertEqual(actualmot['sha256'],inventory.sha(mot))
            self.assertIn('no_job_ID_guess',basis)
            metric['tracking_receipt_sha256']='b'*64
            with self.assertRaises(ValueError):inventory.tracking_from_metric(met,metric,'PT_bbox',seq,config,{}, {})

    def test_final_test_and_external_dependency_scope_rejected(self):
        for relative in ('test/cache.jsonl','pose/SNMOT-116/a.json','pose/SNMOT-187/a.json'):
            with self.assertRaises(ValueError): inventory.safe(inventory.R/relative)
        with self.assertRaises(ValueError): inventory.safe(Path('D:/other/byte_tracker.py'),dependency=True)


if __name__ == '__main__':
    unittest.main()
