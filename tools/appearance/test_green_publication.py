"""发布只消费完整绿色终态，保留实际world差并拒绝来源破坏。"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import publish_green_kit_pair_a01 as publication


class GreenPublicationTests(unittest.TestCase):
    def files(self,root,delta=0):
        data=[dict(frame_index=i,source_frame_index=i,entity_id='L0',track_id=1,
                   mesh_identity='actual_mesh',manifest_sha256='a'*64,
                   world_m=[[float(i),float(j),0.0] for j in range(17)]) for i in range(2)]
        a=root/'a.jsonl';b=root/'b.jsonl'
        a.write_text(''.join(json.dumps(r)+'\n' for r in data),encoding='utf-8')
        data[0]['world_m'][0][0]+=delta
        b.write_text(''.join(json.dumps(r)+'\n' for r in data),encoding='utf-8')
        return a,b

    def test_nonexact_is_reported_and_original_values_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            a,b=self.files(Path(folder),.00001);before=[p.read_bytes() for p in (a,b)]
            hashes=[hashlib.sha256(value).hexdigest() for value in before]
            report=publication.compare_world(a,b,*hashes,expected_records=2)
            self.assertFalse(report['all_world_exact']);self.assertEqual(report['max_world_delta_m'],.00001)
            self.assertFalse(report['world_values_modified']);self.assertEqual(before,[p.read_bytes() for p in (a,b)])

    def test_bad_sha_and_identity_refuse(self):
        with tempfile.TemporaryDirectory() as folder:
            a,b=self.files(Path(folder));h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            with self.assertRaises(RuntimeError):publication.compare_world(a,b,h(a),'0'*64,expected_records=2)
            lines=b.read_text(encoding='utf-8').splitlines();row=json.loads(lines[0]);row['entity_id']='R0'
            lines[0]=json.dumps(row);b.write_text('\n'.join(lines)+'\n',encoding='utf-8')
            with self.assertRaises(RuntimeError):publication.compare_world(a,b,h(a),h(b),expected_records=2)

    def test_incomplete_state_does_not_create_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);control=root/'control';control.mkdir();target=root/'must_not_exist'
            (control/'state.json').write_text(json.dumps(dict(status='rendering',completed=[])),encoding='utf-8')
            (root/'manifest.json').write_text('{}',encoding='utf-8')
            with patch.object(publication,'CONTROL',control),patch.object(publication,'RUN',root),patch.object(publication,'TARGET',target):
                with self.assertRaises(RuntimeError):publication.prepare()
            self.assertFalse(target.exists())


if __name__=='__main__':unittest.main()
