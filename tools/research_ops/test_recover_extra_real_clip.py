"""缺失源恢复的元数据与真实读取器短读边界；不联网/读媒体。"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import recover_extra_real_clip as recovery


def fixture():
    sources=[]
    for seq,game in [('SNMOT-061','4'),('SNMOT-098','6')]:
        names=[f'train/{seq}/img1/{i:06d}.jpg' for i in range(1,751)]+[f'train/{seq}/'+n for n in ('gt/gt.txt','seqinfo.ini','gameinfo.ini')]
        files=[dict(official_member=n,path=str(recovery.DATA/Path(n).relative_to('train')),bytes=1,sha256='0'*64) for n in names]
        sources.append(dict(sequence=seq,game_id=game,frames=750,width=1920,height=1080,fps=25,GT_rows=1,files=files))
    parent=dict(schema='extra_real_train_input_manifest_v1',status='failed_preserved_no_replay',error="RuntimeError('HTTP range 长度不匹配')",
        models_inferred=False,optimizer_updates=0,test_requested=False,det_file_extracted_or_used=False,sequences=sources,files=[f for s in sources for f in s['files']])
    proposal=dict(sources=[dict(sequence=s) for s in ['SNMOT-061','SNMOT-098','SNMOT-154']])
    return parent,proposal


class RecoveryTests(unittest.TestCase):
    def test_small_ranges_cover_once_and_rebuild_original_cache(self):
        class Reader:
            def __init__(self):self.data=bytes(range(50));self.calls=[]
            def seek(self,p):self.position=p
            def read(self,n):
                self.calls.append((self.position,n));data=self.data[self.position:self.position+n];self.position+=n;return data
        with tempfile.TemporaryDirectory() as tmp:
            reader=Reader();journal=Path(tmp)/'blocks.jsonl'
            recovery.bounded_clip_range(reader,3,41,journal,16)
            self.assertEqual(reader.calls,[(3,16),(19,16),(35,6)])
            self.assertEqual(reader.cache,reader.data[3:41]);self.assertEqual(reader.cache_start,3)
            self.assertEqual(sum(json.loads(x)['bytes'] for x in journal.read_text().splitlines()),38)

    def test_only_missing154_and_parent_unchanged(self):
        parent,proposal=fixture();before=json.dumps(parent,sort_keys=True)
        sources,files,missing=recovery.inheritance(parent,proposal)
        self.assertEqual([s['sequence'] for s in sources],['SNMOT-061','SNMOT-098'])
        self.assertEqual(len(files),1506);self.assertEqual(missing['sequence'],'SNMOT-154')
        self.assertEqual(json.dumps(parent,sort_keys=True),before)

    def test_partial_or_duplicate_not_success(self):
        parent,proposal=fixture();parent['files'].append(dict(path='third_partial'))
        with self.assertRaises(ValueError):recovery.inheritance(parent,proposal)
        parent,proposal=fixture();parent['sequences'][0]['files'][0]=parent['sequences'][0]['files'][1]
        with self.assertRaises(ValueError):recovery.inheritance(parent,proposal)

    def test_missing_directory_and_x_write_reject_replay(self):
        with self.assertRaises(ValueError):recovery.reserve_missing(recovery.DATA,lambda _:True)
        recovery.reserve_missing(recovery.DATA,lambda _:False)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'original.json';recovery.write_new(path,dict(status='failed_preserved_no_replay'))
            before=path.read_bytes()
            with self.assertRaises(FileExistsError):recovery.write_new(path,dict(status='complete'))
            self.assertEqual(path.read_bytes(),before)

    def test_actual_reader_short_range_three_attempts_no_position_advance(self):
        class Response:
            status=206;headers={'Content-Range':'bytes 0-65535/100000'}
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def read(self,n):return b'a'*100
        with tempfile.TemporaryDirectory() as tmp,patch.object(recovery.original.remote.urllib.request,'urlopen',return_value=Response()):
            journal=Path(tmp)/'http.jsonl'
            recovery.instrument_transport(recovery.original.remote,journal)
            reader=recovery.original.BoundedMetadataReader('https://unused.invalid/train.zip',100000,budget=3*65536)
            with self.assertRaisesRegex(RuntimeError,'HTTP range 长度不匹配'):reader.read(10)
            self.assertEqual(reader.position,0);self.assertEqual(reader.attempted_range_upper_bound,3*65536)
            rows=[json.loads(x) for x in journal.read_text().splitlines()]
            self.assertEqual(len(rows),3);self.assertTrue(all(r['actual_bytes']==100 for r in rows))


if __name__=='__main__':unittest.main()
