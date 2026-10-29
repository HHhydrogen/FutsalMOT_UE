"""既有窗口复用的纯metadata夹具；不打开真实记录、模型或GT。"""
from collections import Counter
from copy import deepcopy
import unittest
import record_reuse_windows as m

def fixture():
    units=[];data={};global_index=0;unknown_remaining=7225
    for fold in m.FOLDS:
        for sequence,heldout in m.SOURCES.items():
            if fold==heldout:continue
            job=dict(fold=fold,sequence=sequence,regime='R',seed=20261024,job_id=fold+sequence,model_id='model_'+fold)
            windows=[];candidates=[]
            for i in range(500):
                uid=job['job_id']+':'+str(i);n=14+int(global_index<465);pairs=[]
                for j in range(n):
                    if j==0 and global_index<1115:label=1
                    elif unknown_remaining:label=None;unknown_remaining-=1
                    else:label=0
                    eligible=(j%3!=2);status=('not_applicable' if not eligible else
                        'probability_rejected' if label==1 and i%2==0 else 'strict_cost_feasible')
                    pairs.append(dict(window_uid=uid,job_id=job['job_id'],candidate_index=j,uid=uid+'c'+str(j),
                        label=label,label_group=m.label_group(label),enabled=eligible,motion_gate=eligible,
                        motion_gate_missing_reason=None,scoring_eligible=eligible,probability_status=status,
                        reference_cost=1. if status=='probability_rejected' else .4))
                counts=Counter(p['label_group'] for p in pairs);scoring={g:dict(eligible=0,ineligible=0,unknown=0) for g in m.LABELS}
                probability={g:{s:0 for s in m.STATUSES} for g in m.LABELS}
                for p in pairs:
                    scoring[p['label_group']]['eligible' if p['scoring_eligible'] else 'ineligible']+=1
                    probability[p['label_group']][p['probability_status']]+=1
                windows.append(dict(schema='state_label_alignment_window_v1',is_selected_R_window=True,job_id=job['job_id'],fold=fold,sequence=sequence,
                    teacher_regime='R',teacher_seed=20261024,stage='high_score',frame_number=i+4,row_index=0,track_id=i,
                    window_uid=uid,history_UIDs=['h0','h1','h2'],query_GT_id='q',current_GT_present=True,
                    raw_correct_UIDs=[p['uid'] for p in pairs if p['label']==1],anchor_drift=False,
                    earliest_stage_trusted3_anchor=dict(gt_id='q',frame_number=1),B_class='existing_class',history_bin='3',gap_bin='1',candidate_bin='9_to16',
                    unavailable_field=[],counts=dict(all_pairs=n,known_pairs=n-counts['unknown'],positive_pairs=counts['positive'],
                        known_negative_pairs=counts['known_negative'],unknown_pairs=counts['unknown']),scoring_counts=scoring,probability_counts=probability))
                candidates.extend(pairs);global_index+=1
            wref=dict(path=job['job_id']+'/windows',rows=500);cref=dict(path=job['job_id']+'/candidates',rows=len(candidates))
            data[wref['path']]=windows;data[cref['path']]=candidates
            units.append(dict(job=job,selected_windows=wref,selected_candidates=cref))
    return units,data

class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.units,cls.data=fixture()
    def reader(self,ref):return iter(self.data[ref['path']])
    def test_complete_original_denominators_and_bounded_cases(self):
        out=m.analyse_windows(self.units,self.reader);s=out['summary']
        self.assertEqual(s['counts'],dict(all_pairs=42465,known_pairs=35240,positive_pairs=1115,known_negative_pairs=34125,unknown_pairs=7225))
        self.assertEqual(len(out['records']),3000);self.assertLessEqual(s['case_slots'],60)
        self.assertLess(s['unique_case_windows'],s['case_slots']);self.assertTrue(all(r['negative_subtype']==r['unknown_subtype']=='not_retained' for r in out['records']))
        self.assertEqual(sum(s['reachability_counts'].values()),3000)
        self.assertEqual(sum(r['windows'] for r in s['cross_tables']['risk_by_reachability']),3000*len(m.RISKS))
        self.assertEqual(sum(r['windows'] for r in s['cross_tables']['label_context_by_reachability']),3000)
        self.assertEqual(s['new_confidence_intervals_computed'],0);self.assertTrue(s['teacher_state_is_not_new_model_free_state'])
    def test_case_sort_dedup_and_no_shortfall_fill(self):
        unit=self.units[0];rows,summary,slots,cases=m._analyse_unit(unit,self.reader)
        self.assertEqual(summary['selection_counts']['known_negative_strict_cost_feasible']['selected_slots'],0)
        self.assertEqual(summary['selection_counts']['known_negative_strict_cost_feasible']['shortfall'],2)
        first=next(s for s in slots if s['stratum']=='positive_probability_rejected' and s['rank']==1)
        self.assertEqual(first['window_uid'],unit['job']['job_id']+':0')
        self.assertGreater(len(cases[first['window_uid']]['selection_tags']),1)
        reversed_data={k:list(reversed(v)) for k,v in self.data.items()}
        _,_,slots2,_=m._analyse_unit(unit,lambda ref:iter(reversed_data[ref['path']]))
        self.assertEqual(slots,slots2)
    def test_reject_unknown_changed_to_negative_and_index_join_corruption(self):
        unit=self.units[0];d=deepcopy(self.data);pair=d[unit['selected_candidates']['path']][1]
        pair['label']=0
        with self.assertRaises(ValueError):m._analyse_unit(unit,lambda ref:iter(d[ref['path']]))
        d=deepcopy(self.data);d[unit['selected_candidates']['path']][1]['candidate_index']=0
        with self.assertRaises(ValueError):m._analyse_unit(unit,lambda ref:iter(d[ref['path']]))
    def test_reject_wrong_teacher_missing_unit_and_budgets(self):
        units=deepcopy(self.units);units[0]['job']['regime']='RS'
        with self.assertRaises(ValueError):m.analyse_windows(units,self.reader)
        with self.assertRaises(ValueError):m.analyse_windows(self.units[:-1],self.reader)
        unit=self.units[0];d=deepcopy(self.data);d[unit['selected_windows']['path']].append(d[unit['selected_windows']['path']][0])
        with self.assertRaises(ValueError):m._analyse_unit(unit,lambda ref:iter(d[ref['path']]))
        d=deepcopy(self.data);d[unit['selected_candidates']['path']].extend([d[unit['selected_candidates']['path']][0]]*600)
        with self.assertRaises(ValueError):m._analyse_unit(unit,lambda ref:iter(d[ref['path']]))
    def test_empty_raw_is_not_unknown_and_probability_is_not_assignment(self):
        unit=self.units[-1];window=self.data[unit['selected_windows']['path']][0]
        pairs=[p for p in self.data[unit['selected_candidates']['path']] if p['window_uid']==window['window_uid']]
        row,_=m._joined_window(window,pairs,unit['job'])
        self.assertEqual(row['reachability_level'],'no_trusted_correct_raw');self.assertFalse(row['raw_correct_present'])
        self.assertNotIn('assignment_success',row);self.assertFalse(row['new_causal_effect_estimated'])
    def test_empty_effective_known_and_unknown_reachability_are_preserved(self):
        unit=self.units[0];window=deepcopy(self.data[unit['selected_windows']['path']][0])
        pairs=deepcopy([p for p in self.data[unit['selected_candidates']['path']] if p['window_uid']==window['window_uid']])
        for p in pairs:p.update(enabled=False,motion_gate=False,scoring_eligible=False,probability_status='not_applicable')
        for group in m.LABELS:
            n=sum(p['label_group']==group for p in pairs);window['scoring_counts'][group]=dict(eligible=0,ineligible=n,unknown=0)
            window['probability_counts'][group]={s:int(s=='not_applicable')*n for s in m.STATUSES}
        window.update(current_GT_present=None,raw_correct_UIDs=None,anchor_drift=None)
        row,_=m._joined_window(window,pairs,unit['job']);self.assertTrue(row['risk_flags']['zero_effective_known'])
        self.assertEqual(row['reachability_level'],'GT_presence_unknown');self.assertIsNone(row['raw_correct_present'])
        self.assertIsNone(row['risk_flags']['anchor_drift']);self.assertEqual(row['candidate_UIDs'],[p['uid'] for p in pairs])
    def test_positive_rejection_unknown_feasibility_and_boundary_are_distinct(self):
        unit=self.units[0];window=deepcopy(self.data[unit['selected_windows']['path']][0])
        pairs=deepcopy([p for p in self.data[unit['selected_candidates']['path']] if p['window_uid']==window['window_uid']])
        row,_=m._joined_window(window,pairs,unit['job']);self.assertTrue(row['risk_flags']['positive_rejected_with_unknown_feasible'])
        self.assertEqual(row['reachability_level'],'correct_raw_probability_rejected')
        pairs[0].update(probability_status='boundary_unknown',reference_cost=.8)
        window['probability_counts']['positive']['probability_rejected']=0;window['probability_counts']['positive']['boundary_unknown']=1
        row,_=m._joined_window(window,pairs,unit['job']);self.assertFalse(row['risk_flags']['positive_rejected_with_unknown_feasible'])
        self.assertEqual(row['reachability_level'],'correct_raw_boundary_unknown');self.assertFalse(row['correct_raw_strict_cost_feasible'])

if __name__=='__main__':unittest.main()
