"""只用D项目小夹具验证新存储门禁，不运行生产清理。"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import os
import subprocess
import sys
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('policy', Path(__file__).with_name('dataset_storage_policy.py'))
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)


class StoragePolicyTest(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','只验证Windows真实进程句柄语义')
    def test_active_consumer_rejected_exited_held_handle_accepted(self):
        child=subprocess.Popen([sys.executable,'-c',
            "import sys;print('ready',flush=True);sys.stdin.readline()"],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
        try:
            self.assertEqual(child.stdout.readline().strip(),b'ready')
            with self.assertRaisesRegex(ValueError,'仍活动'):
                p.inactive({'raw_exr_consumer_process_ids':[child.pid]})
            child.stdin.write(b'\n');child.stdin.flush();self.assertEqual(child.wait(timeout=10),0)
            # 故意保留Popen与Win32进程句柄，复现生产中误拒已退出消费者的条件。
            p.inactive({'raw_exr_consumer_process_ids':[child.pid]})
        finally:
            if child.poll() is None:
                child.stdin.write(b'\n');child.stdin.flush();child.wait(timeout=10)
            child.stdin.close();child.stdout.close()

    def test_targeted_lifecycle_and_guards(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[2] / 'Saved' / 'StoragePolicy') as folder:
            root = Path(folder); dataset = root/'dataset'; research = root/'research'; saved = root/'saved'
            for d in (dataset, research, saved): d.mkdir()
            with patch.multiple(p, DATASET=dataset, RESEARCH=research, SAVED=saved):
                raw = dataset/'_work'/'a01'/'raw'; raw.mkdir(parents=True)
                (raw/'frame.exr').write_bytes(b'fixture-not-real-exr')
                (raw/'native.json').write_text('{}')
                view = dataset/'_staging'/'a01'/'view'; view.mkdir(parents=True)
                for name in ('rgb', 'mask'):
                    (view/name).mkdir(); (view/name/'000.png').write_bytes(b'fixture')
                for name in ('pose', 'world'):
                    (view/(name+'.jsonl')).write_text('{}\n')
                index = dataset/'_staging'/'a01'/'dataset.json'; index.write_text('{}')
                def bind(path): return {'path': str(path), 'sha256': p.sha(path)}
                post = dataset/'_work'/'a01'/'postprocess.json'
                post.write_text(json.dumps(dict(schema='exr_postprocess_complete_v1', status='complete',
                    attempt='a01', raw_root=str(raw), exr_decode_count=1, dataset_index=bind(index), views=[dict(frames=1,
                    rgb_directory=str(view/'rgb'), mask_directory=str(view/'mask'), person_records=1,
                    pose_jsonl=bind(view/'pose.jsonl'), world_jsonl=bind(view/'world.jsonl'))])))
                refs=research/'inputs.jsonl'; refs.write_text('{}\n')
                consumer=research/'consumers.json'
                con=dict(schema='exr_consumers_complete_v1', status='complete', attempt='a01',
                         consumer_scope='raw_exr_only', producer_output_closed=True,
                         raw_exr_consumers_finished=True, raw_exr_required=False, postprocess_sha256=p.sha(post),
                         reference_indexes=[bind(refs)], raw_exr_consumer_process_ids=[123])
                consumer.write_text(json.dumps(con))
                dry=p.cleanup(post,consumer)
                self.assertEqual(dry['file_count'],1); self.assertTrue((raw/'frame.exr').exists())
                with self.assertRaisesRegex(ValueError,'精确file-list SHA'):
                    p.cleanup(post,consumer,True,'bad',saved/'journal.jsonl')
                refs.write_text(json.dumps({'source_world_ref':'some.exr'})+'\n')
                con['reference_indexes']=[bind(refs)]; consumer.write_text(json.dumps(con))
                with self.assertRaisesRegex(ValueError,'仍引用EXR'): p.cleanup(post,consumer)
                refs.write_text('{}\n'); con['reference_indexes']=[bind(refs)]; consumer.write_text(json.dumps(con))
                with patch.object(p,'inactive'):
                    result=p.cleanup(post,consumer,True,dry['files_sha256'])
                self.assertEqual(result['status'],'exr_deleted_after_complete_consumers')
                self.assertTrue((raw/'native.json').exists()); self.assertTrue((view/'rgb'/'000.png').exists())
                with self.assertRaisesRegex(ValueError,'空/重复'): p.cleanup(post,consumer)
                with self.assertRaisesRegex(ValueError,'越界'): p.safe(saved/'other.exr',dataset)
                with patch.object(p.shutil,'disk_usage',return_value=type('U',(),{'free':30*p.GIB})()):
                    with self.assertRaisesRegex(ValueError,'空间不足'): p.preflight('a02',1,1)


if __name__=='__main__': unittest.main()
