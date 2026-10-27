import unittest
import substitution_paired_analysis as entry
class Tests(unittest.TestCase):
    def test_training_repeats_are_not_extra_matches(self):
        matches=['one','two','three'];rows=[]
        for m,delta in zip(matches,[1,2,3]):
            for f in entry.FOLDS:
                for seed in entry.SEEDS:
                    for group,value in [('B',40+delta),('C',40)]:rows.append(dict(match=m,method='motion',group=group,fold=f,seed=seed,AssA=value))
        differences=entry.paired_match_differences(rows,matches,'motion');self.assertEqual(differences,dict(one=1.,two=2.,three=3.))
        report=entry.effect_intervals(differences);self.assertEqual(report['n_independent_matches'],3)
        self.assertEqual(report['mean_delta_pp'],2.);self.assertAlmostEqual(report['Student_t_95CI'][1],4.4841377117,places=7)
        with self.assertRaises(ValueError):entry.paired_match_differences(rows[:-1],matches,'motion')
    def test_zero_interval_does_not_make_equivalence_claim(self):
        report=entry.effect_intervals(dict(a=0.,b=0.,c=0.))
        self.assertEqual(report['Student_t_95CI'],[0.,0.]);self.assertFalse(report['formal_equivalence_or_noninferiority_test'])
        self.assertIsNone(report['margin'])
    def test_precision_is_assumption_not_C_result(self):
        scenarios=entry.precision_scenarios(7)
        self.assertEqual(len(scenarios),5);self.assertTrue(all(x['assumption_only_not_observed_C_variance'] for x in scenarios))
if __name__=='__main__':unittest.main()
