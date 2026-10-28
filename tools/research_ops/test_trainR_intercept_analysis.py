"""截距分析的纯CPU夹具；不运行真实拟合/追踪，不读取原数据或GT坐标。"""
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import trainR_intercept_analysis as analysis


def panels():
    return dict(original_heldout=list(analysis.OLD), old_external=['external1', 'external2'],
        seven_observed=['seven'+str(i) for i in range(7)])


def records(zero_events=False):
    p = panels(); target, baseline = [], []
    for regime, sequence, fold, seed in sorted(analysis.expected_cells(p)):
        number = list(analysis.panels_map(p)).index(sequence)
        base = 30.+number+(.1 if regime == 'RS' else 0.)
        # 所有正、零、负差均保留；交互按同fold/seed计算，不挑seed。
        change = (-1. if regime == 'R' else .25)*(number-5)+(seed-20261024)*.1
        total = 0 if zero_events and sequence == 'external2' else 100
        success = 60 if regime == 'R' else 55
        for destination, condition, value, recovered in ((target, 'new', base+change, success+1), (baseline, 'old', base, success)):
            destination.append(dict(regime=regime, sequence=sequence, fold=fold, seed=seed,
                model_id=regime+fold+str(seed), metrics={key:value for key in analysis.METRICS},
                gap=dict(total_events=total, same_prediction_ID_recovered=recovered if total else 0,
                    recovery_rate=recovered/total if total else None),
                condition='calibrated_beta32' if condition=='new' else 'historical_beta_zero_reference',
                frames=750, source_origin=condition, alias_used=False,
                report=dict(path=condition+'/'+sequence+fold+str(seed)+regime+'.json',sha256='a'*64),
                tracking_receipt=dict(path='receipt.json',sha256='b'*64)))
    return target, baseline


def describe_fixture(values):
    return dict(n_independent_matches=len(values), mean_delta_pp=mean(values.values()), match_deltas_pp=values,
        Student_t_95CI=['fixture_only', 'fixture_only'], percentile_match_bootstrap_95CI=['fixture_only','fixture_only'],
        leave_one_match_out_mean={key:mean(value for other,value in values.items() if other!=key) for key in values},
        formal_equivalence_or_noninferiority_test=False, margin=None)


class Analysis(unittest.TestCase):
    def test180_each270_pairs36_matches_correct_interaction_no_seed_as_match(self):
        target, baseline = records()
        cells=analysis.paired_cells(target,baseline,panels());matches=analysis.paired_matches(cells,panels())
        self.assertEqual([len(cells[name]) for name in analysis.COMPARISONS],[90]*3)
        self.assertEqual(len(matches),36)
        values={name:{(r['sequence'],r['fold'],r['seed']):r for r in rows} for name,rows in cells.items()}
        for key,row in values[analysis.COMPARISONS[2]].items():
            self.assertEqual(row['delta_pp']['AssA'],values[analysis.COMPARISONS[1]][key]['delta_pp']['AssA']-
                values[analysis.COMPARISONS[0]][key]['delta_pp']['AssA'])
            self.assertEqual(len(row['source_terms']),4)
        metrics,gaps=analysis.describe(matches,panels(),describe_fixture)
        self.assertEqual(sum(len(metrics[c][p]) for c in metrics for p in metrics[c]),45)
        self.assertEqual(sum(len(gaps[c]) for c in gaps),9)
        for c in analysis.COMPARISONS:
            self.assertEqual([metrics[c][p]['AssA']['n_independent_matches'] for p in analysis.PANELS],[3,2,7])
        self.assertTrue(any(r['delta_pp']['AssA']<0 for rows in cells.values() for r in rows))

    def test_zero_event_match_kept_null_not_imputed_no_interval_if_one_match(self):
        target,baseline=records(zero_events=True)
        cells=analysis.paired_cells(target,baseline,panels());matches=analysis.paired_matches(cells,panels())
        metrics,gaps=analysis.describe(matches,panels(),describe_fixture)
        for name in analysis.COMPARISONS:
            summary=gaps[name]['old_external']
            self.assertEqual(summary['zero_event_matches_retained_null'],['external2'])
            self.assertEqual(summary['n_independent_matches'],1)
            self.assertIsNone(summary['Student_t_95CI'])
            self.assertEqual(metrics[name]['old_external']['AssA']['n_independent_matches'],2)
            self.assertTrue(all(row['gap']['delta_recovery_rate_pp'] is None for row in cells[name] if row['sequence']=='external2'))

    def test_missing_duplicate_nonfinite_wrong_model_or_gap_rejected(self):
        target,baseline=records()
        for changed in (target[:-1],target+[target[0]]):
            with self.assertRaises(ValueError):analysis.paired_cells(changed,baseline,panels())
        for key,value in [('metrics',{'AssA':float('nan')}),('model_id','different_model'),
            ('gap',dict(total_events=101,same_prediction_ID_recovered=61,recovery_rate=61/101))]:
            changed=deepcopy(target);changed[0][key]=value
            with self.assertRaises(ValueError):analysis.paired_cells(changed,baseline,panels())
        invalid=deepcopy(panels());invalid['old_external'][0]=invalid['seven_observed'][0]
        with self.assertRaises(ValueError):analysis.panels_map(invalid)

    def test_analysis_metadata_guard_no_weights_cache_MOT_GT_or_test(self):
        with TemporaryDirectory() as directory,patch.object(analysis,'R',Path(directory)):
            for name in ('last.pt','pool.jsonl','MOT.txt','gap_registry.json','posthoc_GT_labels.json'):
                path=Path(directory)/name;path.write_text('{}',encoding='utf-8')
                with self.assertRaises(ValueError):analysis.read(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            path=Path(directory)/'metric.json';path.write_text('{}',encoding='utf-8')
            with self.assertRaises(ValueError):analysis.read(dict(path=str(path),sha256='b'*64))
            with self.assertRaises(ValueError):analysis.physical(Path(directory)/'SNMOT-116/report.json')
            with self.assertRaises(ValueError):analysis.interval_module(dict(path=str(path),sha256='a'*64))

    def test_literal_statistics_source_fixed_without_local_fallback(self):
        import inspect
        text=inspect.getsource(analysis.interval_module)
        self.assertIn('INTERVAL_SHA',text)
        self.assertNotIn('scipy',text)
        self.assertNotIn('numpy',text)
        self.assertEqual(analysis.INTERVAL_SHA,'7458aa01dc5396124ac40d51ac3a3ff9851ce2a8cb4e61e64f4e7d9b6b695e7e')

    def test_actual_manifest_binding_alias_and_GT_boundary_rejected(self):
        target,baseline=records();p=panels()
        with TemporaryDirectory() as directory,patch.object(analysis,'R',Path(directory)):
            control=Path(directory)/'control';control.mkdir()
            cfgref=dict(path='configuration',sha256='f'*64)
            cfg=dict(jobs=[],calibrations={},sources={seq:dict(frames=750,cache=dict(path='unread_cache',sha256='a'*64)) for seq in analysis.panels_map(p)},panels=p)
            cfg['expected_GT_rows']={seq:1000 for seq in analysis.panels_map(p)}
            manifest=dict(schema='trainR_intercept_tracking_manifest_v1',status='complete180_trainR_intercept_tracking_and_evaluation',
                config_sha256='f'*64,reports=[])
            metadata={};models={};fits=[]
            for number,row in enumerate(target):
                job={key:row[key] for key in ('model_id','regime','sequence','fold','seed')};job['job_id']=str(number)
                cfg['jobs'].append(job)
                models[row['model_id']]={'binding':{'model':row['model_id']}}
                fitref=dict(path='fit/'+row['model_id'],sha256='b'*64);cfg['calibrations'][row['model_id']]=fitref
                reportref=dict(path=str(control/str(number)/'metric.json'),sha256='c'*64)
                receiptref=dict(path=str(control/str(number)/'tracking.json'),sha256='d'*64)
                manifest['reports'].append(dict(job=job,report=reportref))
                metadata[reportref['path']]=dict(schema='trainR_intercept_tracking_metric_v1',status='complete',job=job,
                    protocol_sha256='f'*64,DO_PREPROC=False,predictions_GT_filtered=False,test_read=False,
                    frames=750,GT_rows=1000,tracked_rows=100,metrics=row['metrics'],gap={'overall':row['gap']},
                    source_cache=cfg['sources'][row['sequence']]['cache'],fit=fitref,beta32=0.,
                    summary={row['sequence']:{'metrics_percent':row['metrics']}},tracking_receipt=receiptref)
                metadata[receiptref['path']]=dict(schema='trainR_intercept_tracking_receipt_v1',status='complete',job=job,
                    protocol_sha256='f'*64,fit=fitref,beta32=0.,GT_used_for_tracking=False,test_read=False,
                    model_id=row['model_id'],binding=models[row['model_id']]['binding'],evaluation_GT_coordinate_files_opened=False,
                    alias_used=False,diagnostic_beta0=False,prefix_frames=None,source_inputs_unchanged=True,
                    original_model_state_unchanged=True,original_normalizer_unchanged=True,native_ordered_batch_forward_preserved=True,
                    GPU_used=False,new_optimizer_updates=0,frame_counts=[1]*100+[0]*650,
                    source_cache=cfg['sources'][row['sequence']]['cache'],frames=750,tracked_rows=100)
            fits=[dict(model_id=mid,apply_beta32=0.) for mid in models]
            def fake_read(reference):
                return manifest if Path(reference['path']).name=='manifest.json' else metadata[reference['path']]
            with patch.object(analysis,'ref',side_effect=lambda path:dict(path=str(path),sha256='e'*64)),\
                    patch.object(analysis,'read',side_effect=fake_read):
                actual,_=analysis.target_records(cfgref,cfg,control,models,fits,baseline)
                self.assertEqual(len(actual),180)
                self.assertTrue(all(not row['alias_used'] for row in actual))
                path=manifest['reports'][0]['report']['path']
                metadata[path]['predictions_GT_filtered']=True
                with self.assertRaises(ValueError):analysis.target_records(cfgref,cfg,control,models,fits,baseline)
                metadata[path]['predictions_GT_filtered']=False
                manifest['reports'][0]['report']['path']=baseline[0]['report']['path']
                metadata[baseline[0]['report']['path']]=metadata[path]
                with self.assertRaises(ValueError):analysis.target_records(cfgref,cfg,control,models,fits,baseline)

    def test_full_output_keeps360_sources270_pair_and_gap18_fit_no_NLL_gate(self):
        target,baseline=records(zero_events=True)
        fits=[]
        for regime in analysis.REGIMES:
            for fold in analysis.FOLDS:
                for seed in analysis.SEEDS:
                    fits.append(dict(model_id=regime+fold+str(seed),regime=regime,fold=fold,seed=seed,
                        fit=dict(path='fit.json',sha256='c'*64),beta64=-.1,apply_beta32=-.10000000149,
                        windows=1000,all_pair_count=10,known_pair_count=8,unknown_pair_count=2,optimizer_updates=0,
                        before_NLL=.6,after_fit64_NLL=.7,after_apply32_NLL=.71,
                        NLL_fit_is_independent_tracking_effectiveness_evidence=False))
        with TemporaryDirectory() as directory:
            root=Path(directory);exp=root/'pose/trainR_intercept_calibration_a01';control=exp/'control';control.mkdir(parents=True)
            output=control/'analysis';cfg_ref=dict(path=str(exp/'cfg.json'),sha256='d'*64)
            cfg=dict(panels=panels(),inventory={'ref':'inventory'},fit_complete={'ref':'fit'},interval_source={'sha256':analysis.INTERVAL_SHA})
            with patch.object(analysis,'R',root),patch.object(analysis,'EXP',exp),\
                patch.object(analysis,'validate_config',return_value=(cfg_ref,cfg,{},{})),\
                patch.object(analysis,'fit_records',return_value=fits),patch.object(analysis,'baseline_records',return_value=baseline),\
                patch.object(analysis,'target_records',return_value=(target,{'path':'manifest','sha256':'e'*64})),\
                patch.object(analysis,'interval_module',return_value=SimpleNamespace(effect_intervals=describe_fixture)):
                result=analysis.analyze(cfg_ref['path'],control,output)
                self.assertEqual(result['status'],analysis.STATUS)
                counts={'all_results.csv':360,'all_paired_cells.csv':270,'all_paired_gaps.csv':270,'all_paired_matches.csv':36,'fit_records18.csv':18}
                for name,count in counts.items():
                    with (output/name).open(encoding='utf-8-sig',newline='') as stream:self.assertEqual(len(list(csv.DictReader(stream))),count)
                report=json.loads((output/'report.json').read_text(encoding='utf-8'))
                self.assertFalse(report['formal_equivalence_or_noninferiority'])
                self.assertFalse(report['fitting_NLL_improvement_is_tracking_effectiveness_evidence'])
                self.assertEqual(report['extra_clean_R_model_window_evaluations'],18000)
                with self.assertRaises(ValueError):analysis.analyze(cfg_ref['path'],control,output)


if __name__ == '__main__':
    unittest.main()
