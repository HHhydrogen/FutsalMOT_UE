"""v10来源规划针对检查：四seed、源时间/图号、val隔离和GT不入模型。"""
import copy
from pathlib import Path
import unittest
import v10_prediction_inputs as inp


def group(seed):
    return dict(schema=('futsalmot_pose17_green_seeded_kit_paired_group_v1' if seed == 1048 else 'futsalmot_v10_multiseed_group_v1'),
        seed=seed, variant='B', split='train', source_frame_range=list(inp.WINDOWS[seed]), fps=10,
        not_training=True, MRQ_sync_verified=False, world_values_modified=False, green_floor=dict(id='grass_cool_v1'),
        cameras={c:dict(frames=300, record_layout='one_person_per_line', rgb_directory_ref='views/'+c+'/rgb',
                       pose2d_ref='views/'+c+'/pose2d.jsonl') for c in inp.CAMERAS})


class InputTests(unittest.TestCase):
    def test_source_time_is_not_image_number(self):
        original = group(1044); before = copy.deepcopy(original)
        source = inp.synthetic_sources(original, 'G:/FutsalMOT_Dataset/v4/groups/1044/group.json')[0]
        self.assertEqual(source['frames'][0]['source_frame_index'], 383)
        self.assertEqual(source['frames'][-1]['source_frame_index'], 682)
        self.assertEqual(source['frames'][0]['frame_number'], 1)
        self.assertTrue(source['frames'][0]['image_file'].endswith('000000.png'))
        self.assertEqual(source['frames'][0]['timestamp_sec'], 0)
        self.assertEqual(source['frames'][0]['source_timestamp_sec'], 38.3)
        self.assertEqual(original, before)
        self.assertFalse(source['raw_detection_reuse'])

    def test_synthetic_dev_and_A_and_escape_are_refused(self):
        for field, value in (('seed',1102), ('variant','A'), ('split','synthetic_dev'), ('MRQ_sync_verified',True)):
            g=group(1042); g[field]=value
            with self.assertRaises(ValueError): inp.synthetic_sources(g,'G:/fixture/group.json')
        g=group(1042);g['cameras'][inp.CAMERAS[0]]['rgb_directory_ref']='../escaped'
        with self.assertRaises(ValueError): inp.synthetic_sources(g,'G:/fixture/group.json')

    def test_inference_metadata_excludes_GT(self):
        source = inp.synthetic_sources(group(1048),'G:/fixture/group.json')[0]
        source.update(gt_reference=dict(path='private_GT'), GT_identity='must_not_enter_model')
        result=inp.inference_frame(source,source['frames'][0])
        self.assertFalse(result['GT_used_for_predictions'])
        self.assertNotIn('gt_reference',result); self.assertNotIn('GT_identity',result)
        self.assertNotIn('annotations',result); self.assertNotIn('detections',result)

    def test_external_order_time_and_validation_only(self):
        root=Path('D:/research/val'); rows=[]; proof=[]
        for sequence,count in inp.EXTERNAL.items():
            rows.append(dict(sequence=sequence,frames_for_registered_evaluation=count,
                seqinfo=dict(name=sequence,seqlength=str(count),imdir='img1',imext='.jpg',framerate='25',imwidth='1280',imheight='720'),
                files={'gt/gt.txt':dict(path=str(root/sequence/'gt/gt.txt')), 'seqinfo.ini':dict(path=str(root/sequence/'seqinfo.ini'))}))
            proof.append(dict(sequence=sequence,decoded_RGB_JPEG=count,frames=count))
        initial=dict(schema='v10_external_val_initial_acquisition_v1',sequences=rows)
        decode=dict(status='complete_inputs_decoded_GT_validated_no_model',frames=1125,test_requested=False,
                    new_R_training_exposure=0,sequences=proof)
        sources=inp.external_sources(initial,decode,root)
        self.assertEqual(sum(len(s['frames']) for s in sources),1125)
        self.assertTrue(sources[0]['frames'][0]['image_file'].endswith('000001.jpg'))
        self.assertTrue(all(s['role']=='external_validation_only' and s['new_R_training_exposure']==0 for s in sources))
        groups=[dict(group=group(seed),path='G:/fixture/%s/group.json'%seed) for seed in inp.WINDOWS]
        self.assertEqual(len(inp.assemble(groups,initial,decode,root)),18)
        initial['sequences'][0]['sequence']='SNMOT-116'
        with self.assertRaises(ValueError):inp.external_sources(initial,decode,root)


if __name__ == '__main__': unittest.main()
