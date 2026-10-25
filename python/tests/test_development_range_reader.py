"""HTTP短读不得发布为成功；完整块可验证后离线续传。"""
import importlib.util
import io
from pathlib import Path
import sys
import pytest

ENTRY=Path(__file__).parents[2]/'experiments/sim2real/download_development_extension.py'
sys.path.insert(0,str(ENTRY.parent))
spec=importlib.util.spec_from_file_location('extension_download',ENTRY)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class Response(io.BytesIO):
    status=206
    def __init__(self,data,content_range):
        super().__init__(data);self.headers={'Content-Range':content_range}

def test_short_read_retries_without_publishing_partial(tmp_path,monkeypatch):
    monkeypatch.setattr(module.time,'sleep',lambda delay:None)
    attempts=[]
    def opener(request,timeout):
        attempts.append(request.headers['Range'])
        return Response(b'xx' if len(attempts)==1 else b'abcd','bytes 0-3/4')
    reader=module.ChunkReader('https://example.invalid',4,tmp_path,100,chunk_size=4,opener=opener)
    assert reader.read()==b'abcd' and len(attempts)==2
    assert list(tmp_path.glob('*.bin'))[0].read_bytes()==b'abcd'
    assert not list(tmp_path.glob('*.part'))
    def offline(*args,**kwargs):raise AssertionError('完整缓存不应联网')
    resumed=module.ChunkReader('https://example.invalid',4,tmp_path,100,chunk_size=4,opener=offline)
    assert resumed.read()==b'abcd'

def test_unaligned_multi_block_reads_preserve_zip_offsets(tmp_path):
    data=b'0123456789abcdef'
    def opener(request,timeout):
        start,end=map(int,request.headers['Range'][6:].split('-'))
        return Response(data[start:end+1],f'bytes {start}-{end}/16')
    reader=module.ChunkReader('https://example.invalid',16,tmp_path,100,chunk_size=4,opener=opener)
    reader.seek(3);assert reader.read(8)==b'3456789a'
    reader.seek(-3,2);assert reader.read()==b'def'

def test_wrong_range_never_publishes_bytes(tmp_path,monkeypatch):
    monkeypatch.setattr(module.time,'sleep',lambda delay:None)
    def wrong(request,timeout):return Response(b'abcd','bytes 4-7/8')
    reader=module.ChunkReader('https://example.invalid',8,tmp_path,100,chunk_size=4,opener=wrong)
    with pytest.raises(RuntimeError):reader.read(4)
    assert not list(tmp_path.glob('*.bin'))
