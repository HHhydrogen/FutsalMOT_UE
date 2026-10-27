"""七比赛完整矩阵/配对单位、GT ID0及新控制器独占检查。"""
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).parent))
import substitution_tracking_runtime as rt
import substitution_tracking_analysis as analysis
import substitution_tracking_control as control

class Tracking(unittest.TestCase):
    def results(self):
        out=[]
        for j in rt.tracking_matrix():
            n=rt.MATCHES.index(j['sequence']);v=(20 if j['mode']=='PT_bbox' else 21) if j['kind']=='PT' else (
                {'A':40,'B':42,'C':43}[j['group']]+(.2 if j['method']=='gated' else 0)+.1*rt.FOLDS.index(j['fold'])+.01*rt.SEEDS.index(j['seed']))
            out.append(dict(job=j,metrics={k:v+n/10 for k in analysis.METRICS}))
        return out
    def test_all54_models_seven_matches_and14_PT(self):
        jobs=rt.tracking_matrix();self.assertEqual(len(jobs),392);self.assertTrue(all(j['kind']=='PT' for j in jobs[:14]))
        models={(j['group'],j['method'],j['fold'],j['seed']) for j in jobs if j['kind']=='learned'}
        self.assertEqual(len(models),54)
        for key in models:self.assertEqual(sum(j['kind']=='learned' and tuple(j[k] for k in ('group','method','fold','seed'))==key for j in jobs),7)
    def test_exact_pairing_and_seven_match_not63_cell_CI(self):
        comparisons=analysis.paired_cells(self.results());self.assertEqual(len(comparisons),21)
        for rows in comparisons.values():self.assertEqual(len(rows),63)
        report=analysis.intervals(comparisons['motion/B-minus-C'])['AssA']
        self.assertEqual(report['n_independent_matches'],7);self.assertAlmostEqual(report['mean_delta_pp'],-1.)
        self.assertAlmostEqual(report['Student_t_95CI'][0],-1.);self.assertFalse(report['formal_equivalence_or_noninferiority_test'])
    def test_missing_duplicate_and_nonfinite_cannot_silently_report(self):
        results=self.results()
        with self.assertRaises(ValueError):analysis.paired_cells(results[:-1])
        with self.assertRaises(ValueError):analysis.paired_cells(results+[results[0]])
        results[-1]['metrics']['AssA']=float('nan')
        with self.assertRaises(ValueError):analysis.paired_cells(results)
    def test_GT_ID0_kept_and_duplicate_refused(self):
        source=dict(sequence=rt.MATCHES[0],role='external_validation_only',frames=2,gt={})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'gt.txt';path.write_text('1,0,10,20,30,40,1,1,1\n2,0,11,20,30,40,1,1,1\n',encoding='utf-8')
            with patch.object(rt,'checked',return_value=path):
                gt,text=rt.load_gt(source);self.assertEqual(gt[1][0]['gt_id'],'0');self.assertTrue(text[0].startswith('1,0,'))
                path.write_text('1,0,10,20,30,40,1,1,1\n'*2,encoding='utf-8')
                with self.assertRaises(ValueError):rt.load_gt(source)
    def test_only_actual_same_argument_launcher_chain_exempt(self):
        script=Path('D:/candidate/substitution_tracking_control.py')
        one=dict(ProcessId=1,ParentProcessId=0,Name='python.exe',CommandLine='python '+str(script)+' --config one')
        two=dict(one,ProcessId=2,ParentProcessId=1)
        self.assertEqual(control.process_gate([one,two],2,script),[1,2])
        other=dict(one,ProcessId=3,CommandLine='python '+str(script)+' --config other')
        with self.assertRaises(ValueError):control.process_gate([one,two,other],2,script)
    def test_B_loader_receives_original_training_protocol(self):
        protocol=dict(path='D:/frozen/protocol.json',sha256='a'*64)
        def loader(cfg,*args):
            self.assertEqual(cfg['training_protocol'],protocol)
            return ('model','adapter','binding',False)
        dep=({'training_protocol':protocol},SimpleNamespace(model_for_job=loader),None,None,None,None,None,None)
        refs={k:dict(path='D:/run/'+k+'.json',sha256='b'*64) for k in ('training_receipt','checkpoint','training_complete')}
        cc=dict(reference_B={'motion':{'game4':{'20261024':refs}}})
        job=dict(kind='learned',group='B',method='motion',fold='game4',seed=20261024)
        with patch.object(rt,'checked',side_effect=lambda x:Path(x['path'])):
            self.assertEqual(rt.load_model({},dep,None,cc,job)[0],'model')

if __name__=='__main__':unittest.main()
