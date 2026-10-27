"""额外真实窗口的scope/隔离/唯一配额；不读媒体或训练。"""
from copy import deepcopy
from pathlib import Path
import unittest
import extra_real_windows as entry
OLD=Path('D:/projects/FutsalMOT_Research/code/1ddcf191b3f33c3d350cdab64011721ae99854680b1b1d2f3eef4c2592a69806/tools/research_ops/v8_pairs.py')


class Tests(unittest.TestCase):
    def test_only_scope_guard_changed(self):
        pairs=entry.module('extra_R_pairs_fixture',OLD);labels=pairs.match_labels;enumerator=pairs.enumerate_windows
        proof=entry.scope_loader(pairs)
        self.assertTrue(proof['scope_only_AST_change']);self.assertIs(labels,pairs.match_labels);self.assertIs(enumerator,pairs.enumerate_windows)
        with self.assertRaisesRegex(ValueError,'真实源越界'):pairs.load_source(dict(domain='real',game='game4',sequence='SNMOT-060'))

    def test_source_role_game_and_full_prediction_required(self):
        s=dict(sequence='SNMOT-061',game='game4',domain='real',role='extra_R_training_input_only_C',counts=dict(frames=750),actual_decoded_frames=750,
            GT_used_for_predictions=False,first_frame=0,last_frame=749,fps=25,cache={},gt_reference={},gameinfo_reference={},seqinfo_reference={})
        self.assertEqual(entry.validate_source(s)['sequence'],'SNMOT-061')
        for changes in (dict(game='game6'),dict(role='validation'),dict(actual_decoded_frames=749),dict(GT_used_for_predictions=True)):
            bad=deepcopy(s);bad.update(changes)
            with self.assertRaises(ValueError):entry.validate_source(bad)

    def test_clip_clock_not_local_frame_alias(self):
        a=dict(start='1 - 08:10',stop='1 - 08:40')
        self.assertTrue(entry.clock_disjoint(a,dict(start='1 - 07:30',stop='1 - 08:00')))
        self.assertFalse(entry.clock_disjoint(a,dict(start='1 - 08:20',stop='1 - 08:50')))
        self.assertTrue(entry.clock_disjoint(a,dict(start='2 - 08:10',stop='2 - 08:40')))

    def test_stable_pool_has_500_per_allowed_game_no_duplicate_fill(self):
        pairs=entry.module('extra_R_pool_fixture',OLD)
        strata=[(g,gap) for g in ('game6','game9') for gap in pairs.GAPS];pool=pairs.BalancedPool(strata)
        for j,s in enumerate(strata):
            for i in range(101):pool.add(dict(stratum=list(s),window_uid=f'{j*1000+i:064x}',game=s[0]))
        selected=pool.finish();self.assertEqual(len(selected),1000);self.assertEqual(sum(w['game']=='game6' for w in selected),500)
        short=pairs.BalancedPool(strata)
        with self.assertRaises(ValueError):short.finish()


if __name__=='__main__':unittest.main()
