"""小元数据HTTP短读恢复只重试原范围，不放宽206/预算门禁。"""
import unittest
from unittest.mock import patch
import real_train_metadata_inventory as tool


class Tests(unittest.TestCase):
    def test_short_read_retries_same_position(self):
        reader=tool.BoundedMetadataReader('unused',100000,budget=200000);reader.position=15
        calls=[]
        def read(obj,length):
            calls.append(obj.position)
            if len(calls)==1:obj.position=99;raise RuntimeError('HTTP range 长度不匹配')
            return b'abc'
        with patch.object(tool.OriginalReader,'read',read):self.assertEqual(reader.read(3),b'abc')
        self.assertEqual(calls,[15,15]);self.assertEqual(len(reader.transient_failures),1)

    def test_invalid_response_is_not_retried(self):
        reader=tool.BoundedMetadataReader('unused',100000,budget=200000)
        with patch.object(tool.OriginalReader,'read',side_effect=RuntimeError('服务器未正确支持 HTTP range')) as mock:
            with self.assertRaises(RuntimeError):reader.read(3)
        self.assertEqual(mock.call_count,1)

    def test_budget_counts_retries(self):
        reader=tool.BoundedMetadataReader('unused',100000,budget=70000)
        with patch.object(tool.OriginalReader,'read',side_effect=RuntimeError('HTTP range 长度不匹配')) as mock:
            with self.assertRaisesRegex(RuntimeError,'预算'):reader.read(3)
        self.assertEqual(mock.call_count,1)


if __name__=='__main__':unittest.main()
