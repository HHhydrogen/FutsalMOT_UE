"""记录契约不允许缺loss、改真实曝光或把partial当完整训练。"""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('journal_contract',Path(__file__).with_name('training_journal.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class JournalContract(unittest.TestCase):
    def test_extra_real_group_is4000R_and_zeroS(self):
        spec=self.spec();spec.update(schema='full_training_record_spec_v2_real_groups',R_per_update=4,S_per_update=0,base_R_per_update=3,extra_R_per_update=1,extra_R_alpha=1/3)
        records=[dict(window_uid='r'+str(i),epoch=0,domain='real',candidate_pairs=2,labelled_pairs=1) for i in range(3)]
        extra=dict(window_uid='extra',epoch=0,domain='real',source_allocation='extra_R',candidate_pairs=3,labelled_pairs=2)
        with tempfile.TemporaryDirectory() as tmp,patch.object(module,'RESEARCH',Path(tmp)):
            with module.TrainingJournal(Path(tmp)/'C',spec) as journal:
                with self.assertRaises(ValueError):journal.begin_step(0,records,[extra])
                journal.begin_step(0,records+[extra],[])
                journal.commit_step(loss=.2,real_loss=.2,synthetic_loss=None,base_real_loss=.15,extra_real_loss=.15,
                    learning_rates=[.001],grad_l2=.1,R_pairs=9,S_pairs=0,R_known_pairs=5,S_known_pairs=0,step_wall_seconds=.1)
                self.assertEqual(journal.totals['R_windows'],4);self.assertEqual(journal.totals['S_windows'],0)
                self.assertEqual(journal.totals['base_R_windows'],3);self.assertEqual(journal.totals['extra_R_windows'],1)
    def spec(self):
        return dict(schema='full_training_record_spec_v1',updates=1000,R_per_update=3,S_per_update=1,
                    checkpoint_interval=50,test116187_sealed=True,fixture_only=True,
                    binding={'fixture': 'not_training_authorization'},runtime={'device':'cpu_fixture'})
    def step(self, journal):
        journal.begin_step(0,[dict(window_uid='r'+str(i),epoch=0) for i in range(3)],
                           [dict(window_uid='s0',epoch=0)])
    def commit(self, journal, **changes):
        fields=dict(loss=.2,real_loss=.15,synthetic_loss=.15,learning_rates=[.001],grad_l2=.1,
                    R_pairs=6,S_pairs=3,R_known_pairs=4,S_known_pairs=2,step_wall_seconds=.1)
        fields.update(changes);journal.commit_step(**fields)
    def test_complete_measured_step_and_no_implicit_partial_reuse(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(module,'RESEARCH',Path(tmp)):
            root=Path(tmp)/'run'
            with module.TrainingJournal(root,self.spec()) as journal:
                self.step(journal);self.commit(journal)
                self.assertEqual(journal.completed,1);self.assertEqual(journal.totals['R_windows'],3)
                with self.assertRaises(ValueError):journal.finish()
            with self.assertRaises(ValueError):module.TrainingJournal(root,self.spec())
    def test_missing_S_loss_or_nonfinite_grad_cannot_commit(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(module,'RESEARCH',Path(tmp)):
            with module.TrainingJournal(Path(tmp)/'run',self.spec()) as journal:
                self.step(journal)
                with self.assertRaises(ValueError):self.commit(journal,synthetic_loss=None)
                with self.assertRaises(ValueError):self.commit(journal,grad_l2=float('nan'))
                self.assertEqual(journal.completed,0)
    def test_changed_R_count_and_missing_RNG_refuse(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(module,'RESEARCH',Path(tmp)):
            with module.TrainingJournal(Path(tmp)/'run',self.spec()) as journal:
                with self.assertRaises(ValueError):journal.begin_step(0,[dict(window_uid='r',epoch=0)],[])
                point=journal.root/'checkpoints/step_0000.pt';point.write_bytes(b'CPU_fixture_not_a_model')
                with self.assertRaises(ValueError):journal.register_checkpoint(point,completed_updates=0,payload_fields=['model','optimizer'])
    def test_step_order_and_unknown_partial_transaction_refuse(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(module,'RESEARCH',Path(tmp)):
            with module.TrainingJournal(Path(tmp)/'run',self.spec()) as journal:
                self.step(journal)
                with self.assertRaises(ValueError):self.step(journal)
                self.commit(journal)
                with self.assertRaises(ValueError):self.step(journal)


if __name__=='__main__':unittest.main()
