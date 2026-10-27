"""人工GT缺口不能由空模板、预测拷贝或自报审核补造；全部120分母保留。"""
from copy import deepcopy
import unittest

import pose_manual_quality_contract as contract
from pose_manual_quality_page import page


class Tests(unittest.TestCase):
    def fixture(self):
        plan = []; items = []; plan_sha = 'frozen-plan'
        for sequence in contract.SEQUENCES:
            for i in range(24):
                row = dict(uid=f'{sequence}:{i}', sequence=sequence,
                    frame_number=i+1, frame_index=i, image_file=f'D:/existing/{sequence}/{i}.jpg',
                    bbox_xywh_px=[10., 20., 40., 100.], xy_px=[[100.+j, 100.+j] for j in range(17)])
                plan.append(row)
                items.append(dict(sample_id=contract.sample_id(plan_sha, row), row_index=len(plan)-1, source=dict(sequence=sequence,
                    frame_number=i+1, frame_index=i, image_file=f'D:/existing/{sequence}/{i}.jpg',
                    image_file_url=f'file:///D:/existing/{sequence}/{i}.jpg', image_wh=[1920, 1080],
                    roi_bbox_xywh_px=[10., 20., 40., 100.])))
        manifest = dict(samples=items, source_plan=dict(sha256=plan_sha))
        return contract.empty_document(manifest, 'manifestSHA'), manifest, plan

    def event(self, document, sample, kind, actor, time='2026-10-27T01:00:10Z', **details):
        value = dict(event_id=len(document['interaction_log'])+1, sample_id=sample['sample_id'], kind=kind,
                     actor_id=actor, time_utc=time, image_displayed=True,
                     image_natural_wh=sample['source']['image_wh'], **details)
        document['interaction_log'].append(value)
        return value

    def submitted(self, document):
        sample = document['samples'][0]; sample['target_state'] = 'person_confirmed'
        sample['annotation'].update(status='submitted', annotator_id='human-A', declared_human=True,
            model_predictions_viewed=False, prediction_copy=False, started_at_utc='2026-10-27T01:00:00Z',
            submitted_at_utc='2026-10-27T01:01:00Z')
        self.event(document, sample, 'set_target', 'human-A', target_state='person_confirmed')
        self.event(document, sample, 'annotator_declaration', 'human-A',
            declaration=dict(declared_human=True, model_predictions_viewed=False, prediction_copy=False))
        for joint in sample['joints']:
            if joint['joint_id'] < 3:
                joint.update(status='visible', xy_image_px=[200.+joint['joint_id'], 300.], coco_v=2)
                kind = 'set_point'
            else:
                joint.update(status='unjudgeable', reason='too_small', coco_v=0); kind = 'set_status'
            self.event(document, sample, kind, 'human-A', joint_id=joint['joint_id'], joint=deepcopy(joint),
                       input_method='pointer' if kind == 'set_point' else 'status_selection')
        self.event(document, sample, 'submit_annotation', 'human-A', time=sample['annotation']['submitted_at_utc'])
        return sample

    def reviewed(self, document, sample):
        value = contract.annotation_digest(sample)
        sample['review'].update(status='reviewed', reviewer_id='human-B', declared_human=True,
            independent_of_annotator=True, model_predictions_viewed=False, prediction_copy=False,
            reviewed_at_utc='2026-10-27T01:03:00Z', annotation_digest=value,
            points_checked=[dict(joint_id=j, decision='accepted') for j in range(17)])
        self.event(document, sample, 'review_declaration', 'human-B', time='2026-10-27T01:02:00Z',
            declaration=dict(declared_human=True, independent_of_annotator=True,
                             model_predictions_viewed=False, prediction_copy=False))
        for joint in sample['joints']:
            self.event(document, sample, 'review_decision', 'human-B', time='2026-10-27T01:02:30Z',
                joint_id=joint['joint_id'], decision='accepted', joint=deepcopy(joint),
                annotation_submitted_at_utc=sample['annotation']['submitted_at_utc'])
        self.event(document, sample, 'submit_review', 'human-B', time=sample['review']['reviewed_at_utc'],
                   annotation_digest=value)

    def validate(self, doc, manifest, plan):
        return contract.validate_document(doc, manifest, 'manifestSHA', plan)

    def test_empty_template_remains_pending_full120_and2040_denominator(self):
        doc, manifest, plan = self.fixture(); result = self.validate(doc, manifest, plan)
        self.assertEqual(result['status'], 'pending_manual_annotation_or_independent_review')
        self.assertEqual(result['samples'], 120); self.assertEqual(result['joint_denominator'], 2040)
        self.assertEqual(result['submitted_annotation_claims'], 0)
        self.assertFalse(result['accuracy_metrics_generated'])
        html = page(doc)
        self.assertNotIn('"xy_px"', html); self.assertNotIn('"geometry_valid"', html)
        self.assertTrue(all(p['xy_image_px'] is None for s in doc['samples'] for p in s['joints']))

    def test_no_dropping_difficult_samples_or_source_substitution(self):
        doc, manifest, plan = self.fixture(); doc['samples'].pop()
        with self.assertRaises(ValueError): self.validate(doc, manifest, plan)
        doc, manifest, plan = self.fixture(); doc['samples'][0]['source']['image_file'] = 'wrong-image.jpg'
        with self.assertRaises(ValueError): self.validate(doc, manifest, plan)

    def test_submitted_without_review_is_pending_and_complete_claim_refused(self):
        doc, manifest, plan = self.fixture(); self.submitted(doc)
        result = self.validate(doc, manifest, plan)
        self.assertEqual(result['submitted_annotation_claims'], 1)
        self.assertEqual(result['independently_reviewed_claims'], 0)
        self.assertFalse(result['human_authenticity_proven_by_JSON'])
        doc['claimed_complete'] = True
        with self.assertRaises(ValueError): self.validate(doc, manifest, plan)

    def test_prediction_copy_or_missing_actual_pointer_record_refused(self):
        doc, manifest, plan = self.fixture(); sample = self.submitted(doc)
        sample['annotation']['prediction_copy'] = True
        with self.assertRaises(ValueError): self.validate(doc, manifest, plan)
        doc, manifest, plan = self.fixture(); sample = self.submitted(doc)
        for joint in sample['joints'][:3]:
            joint['xy_image_px'] = plan[0]['xy_px'][joint['joint_id']]
            for event in doc['interaction_log']:
                if event['kind'] == 'set_point' and event['joint_id'] == joint['joint_id']:
                    event['joint'] = deepcopy(joint)
        with self.assertRaisesRegex(ValueError, '精确拷贝'): self.validate(doc, manifest, plan)
        doc, manifest, plan = self.fixture(); self.submitted(doc)
        doc['interaction_log'][2]['input_method'] = 'filled_from_JSON'
        with self.assertRaises(ValueError): self.validate(doc, manifest, plan)

    def test_review_must_be_other_human_and_bind_actual_points(self):
        doc, manifest, plan = self.fixture(); sample = self.submitted(doc); self.reviewed(doc, sample)
        result = self.validate(doc, manifest, plan)
        self.assertEqual(result['independently_reviewed_claims'], 1)
        self.assertFalse(result['accuracy_metrics_generated'])
        sample['review']['reviewer_id'] = 'human-A'
        with self.assertRaises(ValueError): self.validate(doc, manifest, plan)
        doc, manifest, plan = self.fixture(); sample = self.submitted(doc); self.reviewed(doc, sample)
        sample['joints'][0]['xy_image_px'][0] += 1
        with self.assertRaises(ValueError): self.validate(doc, manifest, plan)

    def test_outside_full_image_and_unjudgeable_do_not_get_coordinates(self):
        doc, manifest, plan = self.fixture(); joint = doc['samples'][0]['joints'][0]
        joint.update(status='unjudgeable', coco_v=0, reason='blur', xy_image_px=[10., 20.])
        with self.assertRaises(ValueError): self.validate(doc, manifest, plan)
        joint.update(status='out_of_frame', coco_v=0, reason='too_small', xy_image_px=None)
        with self.assertRaises(ValueError): self.validate(doc, manifest, plan)
        sample = doc['samples'][0]; sample['target_state'] = 'person_confirmed'
        joint.update(status='visible', coco_v=2, reason='', xy_image_px=[1920., 1080.])
        with self.assertRaises(ValueError): self.validate(doc, manifest, plan)


if __name__ == '__main__':
    unittest.main()
