"""纯CPU元数据夹具：同卷移动、跨机位非exact原值、partial与来源篡改。"""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import publish_multiseed_v10 as pub


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.parent = pub.ROOT / 'Saved/CPUFixtures/v10_publication'
        self.parent.mkdir(parents=True, exist_ok=True)
        self.base = Path(tempfile.mkdtemp(prefix='fixture_', dir=self.parent))
        self.root = self.base / 'project'; self.data = self.base / 'dataset'
        self.run = self.root / 'Saved/AppearancePlanning/multiseed_v10_a01'
        self.control = self.run / 'control_full_a01'; self.control.mkdir(parents=True)
        self.target = self.data / 'v4_pose17_multiseed_green_a01'
        self.stack = []
        for key, value in (('ROOT', self.root), ('RUN', self.run), ('DATASET_ROOT', self.data),
                           ('TARGET', self.target), ('identity', lambda pid: [])):
            p = patch.object(pub, key, value); p.start(); self.stack.append(p)
        self.units, completed = [], []
        self.write(self.run / 'short_acceptance_root.json', dict(acceptance_passed=True))
        self.write(self.run / 'P2_sources_prepare.json', dict(status='fixture_only'))
        for seed, window in pub.WINDOWS.items():
            for number, camera in enumerate(pub.CAMERAS):
                attempt = 'fixture_%s_%s' % (seed, camera)
                stage = self.data / '_staging' / attempt; stage.mkdir(parents=True)
                relative = 'cameras/' + camera + '/'
                plan = dict(source_scope='v10_fixture', source_motion=dict(root_seed=seed),
                            seeded_kit_pair=dict(green_floor=dict(id='fixture_green')))
                planref = self.write(self.run / (attempt + '.json'), plan)
                native = self.write(self.run / (attempt + '_native.json'), dict(fixture=True))
                capture = self.write(self.run / (attempt + '_state.json'), dict(fixture=True))
                self.units.append(dict(attempt=attempt, seed=seed, camera_id=camera, variant='B', stage='full', **planref))
                view = dict(view_ref=relative + 'view.json', pose2d_ref=relative + 'pose2d.jsonl',
                            pose3d_world_ref=relative + 'pose3d_world.jsonl', native_receipt=native)
                self.write(stage / view['view_ref'], dict(actual_camera=camera))
                pose = self.write(stage / view['pose2d_ref'], dict(fixture='no_media'))
                world = stage / view['pose3d_world_ref']
                with world.open('x', encoding='utf-8') as stream:
                    for frame in range(300):
                        for entity in sorted(pub.ENTITIES):
                            row = dict(frame_index=frame, source_frame_index=window[0] + frame, entity_id=entity,
                                       track_id=entity, mesh_identity='same_mesh', manifest_sha256='a'*64,
                                       world_m=[[0.007 if number == 3 else 0, 0, 0]] * 17)
                            stream.write(json.dumps(row, separators=(',', ':')) + '\n')
                self.write(stage / 'group.json', dict(capture_experiment='multiseed_v10_a01', stage='full',
                    independent_motion_scope='v10_fixture', seed=seed, split='train', variant='B', source_frame_range=window,
                    capture_scope=dict(camera_ids=[camera]), cameras={camera:view}, green_floor=plan['seeded_kit_pair']['green_floor'],
                    source_motion=plan['source_motion'], original_seeded_kit_binding=dict(seed=seed), keypoint_names=['p']*17,
                    world_values_modified=False, not_training=True, diagnostic_only=True, MRQ_sync_verified=False,
                    green_floor_restored=dict(status='original_floor_slot_restored_not_saved'), plan=planref, state=capture))
                index = self.write(stage / 'dataset.json', dict(status='complete', rgb_frames=300, mask_frames=300, person_pose=3000))
                self.write(stage / 'postprocess_complete.json', dict(status='complete', dataset_index=index,
                    producer_output_closed=True, bounded_worker_pool_closed=True,
                    views=[dict(frames=300, person_records=3000, pose_jsonl=pose,
                                world_jsonl=dict(path=str(world), sha256=pub.sha(world)))]))
                log = self.root / 'Saved/EditorStartup' / ('green_' + attempt) / 'editor.log'
                log.parent.mkdir(parents=True); log.write_text('LogExit: Exiting.\nLog file closed\n', encoding='utf-8')
                self.write(self.control / (attempt + '__shutdown.json'), dict(status='normal_exit_confirmed',
                           process_absent=True, pid=1000+number, log=str(log)))
                self.write(self.control / (attempt + '__EXR_complete.json'), dict(
                    status='exr_deleted_after_complete_consumers', file_count=300, bytes=300))
                completed.append(dict(attempt=attempt, seed=seed, variant='B', rgb=300, mask=300, person_pose=3000,
                                      normal_UE_exit=True, EXR_deleted=300, EXR_bytes=300, stage=str(stage)))
        self.write(self.run / 'manifest.json', dict(full_units=self.units))
        admission = self.write(self.run / 'admission_full_a01.json', dict(schema='futsalmot_v10_multiseed_admission_v1',
            stage='full', runtime_authorized=True, manifest_sha256=pub.sha(self.run/'manifest.json'),
            short_acceptance_sha256=pub.sha(self.run/'short_acceptance_root.json'),
            source_prepare_sha256=pub.sha(self.run/'P2_sources_prepare.json')))
        self.write(self.control / 'state.json', dict(schema='futsalmot_multiseed_v10_serial_v1', scope='v10_a01',
            status='complete_full_12_units_EXR_retired_wait_root_publication', completed=completed,
            rgb=3600, mask=3600, person_pose=36000, admission_sha256=admission['sha256'], pid=999))

    def tearDown(self):
        for p in reversed(self.stack): p.stop()
        # 只递归清除此测试刚创建的物理目录，先核绝对父路径且拒绝重解析点。
        pub.physical_child(self.base, self.parent)
        if self.base.parent.resolve() != self.parent.resolve(): raise RuntimeError('夹具清理边界错误')
        shutil.rmtree(self.base)

    @staticmethod
    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        return dict(path=str(path), sha256=pub.sha(path))

    def test_publish_preserves_nonexact_world_and_original_bytes(self):
        _, _, moves = pub.prepare()
        original = {(m['source'], name): (Path(m['source'])/name).read_bytes()
                    for m in moves for name in ('group.json','dataset.json','postprocess_complete.json')}
        result = pub.publish()
        self.assertEqual((result['rgb'],result['person_pose'],result['media_copied']), (3600,36000,0))
        self.assertFalse(result['all_world_exact']); self.assertAlmostEqual(result['max_world_delta_m'], .007)
        self.assertEqual(pub.read(self.target/'_publication_a01/complete.json')['dataset_sha256'], pub.sha(self.target/'dataset.json'))
        for move in moves:
            self.assertFalse(Path(move['source']).exists())
            for name in ('group.json','dataset.json','postprocess_complete.json'):
                self.assertEqual((Path(move['destination'])/name).read_bytes(), original[(move['source'],name)])
        with self.assertRaisesRegex(RuntimeError,'partial'): pub.prepare()

    def test_active_driver_is_refused(self):
        with patch.object(pub,'identity',lambda pid:[dict(Name='python.exe',CommandLine='run_multiseed_v10_serial.py')]), patch.object(pub,'running',lambda pid:True):
            with self.assertRaisesRegex(RuntimeError,'进程仍活动'): pub.prepare()
        self.assertFalse(self.target.exists())

    def test_changed_world_refuses_before_any_move(self):
        world = self.data/'_staging'/self.units[0]['attempt']/'cameras/CineCam_01/pose3d_world.jsonl'
        with world.open('a',encoding='utf-8') as stream: stream.write('{}\n')
        with self.assertRaisesRegex(RuntimeError,'行数'): pub.publish()
        self.assertFalse(self.target.exists())

    def test_unknown_partial_is_never_replayed(self):
        self.target.mkdir(parents=True)
        self.write(self.target/'intent.json',dict(status='interrupted_unknown'))
        with self.assertRaisesRegex(RuntimeError,'partial'): pub.publish()
        self.assertTrue((self.data/'_staging'/self.units[0]['attempt']).exists())


if __name__ == '__main__': unittest.main()
