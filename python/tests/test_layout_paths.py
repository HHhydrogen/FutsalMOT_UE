"""目录迁移定向CPU检查；不加载UE/模型，不读取媒体或封存测试集。"""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PROJECT/'python/src'))
from grf_ue_bridge import project_paths as P
from grf_ue_bridge.config.runtime import load_local_runtime_config

class LayoutPathsTest(unittest.TestCase):
    def test_nested_explicit_repo_does_not_inherit_project_local_config(self):
        isolated = PROJECT / 'Saved/Verification/isolated_repo'
        self.assertEqual(P.p1_private_root(isolated), isolated / '.futsalmot')
    def test_new_roots(self):
        self.assertEqual(P.project_root(),PROJECT)
        self.assertEqual(P.python_root(),PROJECT/'python')
        self.assertEqual(P.experiments_root(),PROJECT/'experiments/sim2real')
        self.assertEqual(P.ue_scripts_root(),PROJECT/'python/ue')
        self.assertEqual(P.p1_runtime_root(PROJECT/'python'),PROJECT/'Saved/P1/.futsalmot/runtime')
    def test_local_default_new_saved(self):
        expected=PROJECT/'Saved/P1/.futsalmot/local.json'
        # 不读取/重写实际用户配置，只验证默认读取地址。
        with patch.object(Path,'is_file',return_value=False) as method:
            self.assertEqual(load_local_runtime_config(PROJECT/'python'),{})
        self.assertEqual(P.p1_private_root(PROJECT/'python')/'local.json',expected)
    def test_portable_local(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);local=root/'.futsalmot/local.json';local.parent.mkdir()
            payload={'paths':{'dataset_root':str(root/'out'),'ue_project_root':str(root/'ue')}}
            local.write_text(json.dumps(payload),encoding='utf-8')
            self.assertEqual(load_local_runtime_config(root),payload)
            self.assertEqual(P.p1_runtime_root(root),root/'.futsalmot/runtime')
    def test_research_policy_and_lexical_media(self):
        target=Path('D:/projects/FutsalMOT_Research/pose/new_output')
        self.assertEqual(P.research_path(target),target.resolve())
        with self.assertRaises(ValueError):P.research_path('G:/FutsalMOT_Research/pose/new_output')
        lexical=Path('G:/FutsalMOT_Dataset/new_data/images/frame.png').absolute()
        self.assertEqual(P.research_media_path(lexical),lexical)
        with self.assertRaises(ValueError):P.research_media_path('D:/projects/other/images/frame.png')
    @unittest.skipUnless((PROJECT/"tools/maintenance/local/future_path_edits.json").is_file(),"仅本机迁移journal验收")
    def test_journal_worktree_and_baseline_syntax(self):
        journal=json.loads((PROJECT/'tools/maintenance/local/future_path_edits.json').read_text(encoding='utf-8'))
        for relative,row in journal['files'].items():
            path=PROJECT/relative
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),row['after_worktree_sha256'],relative)
            if path.suffix=='.py':ast.parse(path.read_text(encoding='utf-8-sig'),filename=relative)
            if row['source_oid']:
                source=subprocess.run(['git','cat-file','blob',row['source_oid']],cwd=PROJECT,check=True,capture_output=True).stdout.decode('utf-8-sig')
                for operation in row['operations']:
                    if operation['old'] in source:source=source.replace(operation['old'],operation['new'])
                self.assertEqual(hashlib.sha256(source.encode('utf-8')).hexdigest(),row['index_safe_sha256'],relative)
                if path.suffix=='.py':ast.parse(source,filename='index:'+relative)
    @unittest.skipUnless((PROJECT/"tools/maintenance/local/source_layout_phase2_map.json").is_file(),"仅本机号码WIP字节验收")
    def test_protected_number_bytes(self):
        mapping=json.loads((PROJECT/'tools/maintenance/local/source_layout_phase2_map.json').read_text(encoding='utf-8'))
        self.assertEqual(len(mapping['number_WIP_files']),23)
        for row in mapping['number_WIP_files']:
            self.assertEqual(hashlib.sha256((PROJECT/row['new']).read_bytes()).hexdigest(),row['sha256'],row['new'])

if __name__=='__main__':unittest.main()
