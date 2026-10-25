"""扩展开发片段下载：小块校验、有限重试和磁盘续传；不提供test入口。"""
import concurrent.futures
import hashlib
import io
import json
from pathlib import Path
import threading
import time
import urllib.request
import zipfile
import sys

import download_public as original

class ChunkReader(io.RawIOBase):
    """固定范围块只有完整206、长度和SHA通过后才写入缓存。"""
    def __init__(self,url,size,cache,budget,chunk_size=1048576,opener=None):
        self.url,self.size,self.cache,self.budget=url,size,Path(cache),budget
        self.chunk_size=chunk_size
        self.position=self.downloaded=self.requests=0
        self.cache.mkdir(parents=True,exist_ok=True)
        self.lock=threading.Lock()
        self.opener=opener or urllib.request.urlopen
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.position
    def seek(self,offset,whence=0):
        value=offset+(self.position if whence==1 else self.size if whence==2 else 0)
        if not 0<=value<=self.size:raise ValueError('范围越界')
        self.position=value
        return value
    def block(self,start):
        end=min(self.size-1,start+self.chunk_size-1)
        path=self.cache/f'{start:012d}_{end:012d}.bin'
        manifest=path.with_suffix('.sha256')
        if path.exists() and manifest.exists():
            data=path.read_bytes()
            if len(data)==end-start+1 and hashlib.sha256(data).hexdigest()==manifest.read_text():return data
        last=None
        for attempt in range(3):
            try:
                with self.lock:
                    if self.downloaded+end-start+1>self.budget:raise RuntimeError('下载预算用尽')
                    self.downloaded+=end-start+1;self.requests+=1
                request=urllib.request.Request(self.url,headers={'Range':f'bytes={start}-{end}'})
                with self.opener(request,timeout=30) as response:
                    expected=f'bytes {start}-{end}/{self.size}'
                    if response.status!=206 or response.headers.get('Content-Range')!=expected:
                        raise RuntimeError(f'错误范围响应：{response.status}, {response.headers.get("Content-Range")}')
                    data=response.read(end-start+2)
                if len(data)!=end-start+1:raise RuntimeError(f'短读：{len(data)}/{end-start+1}')
                temporary=path.with_suffix('.part')
                temporary.write_bytes(data);temporary.replace(path)
                manifest.write_text(hashlib.sha256(data).hexdigest())
                return data
            except Exception as exc:
                last=exc
                print('RANGE_RETRY',start,end,attempt+1,repr(exc),flush=True)
                if attempt<2:time.sleep(1+attempt)
        raise RuntimeError(f'范围{start}-{end}三次失败') from last
    def read(self,length=-1):
        length=self.size-self.position if length<0 else min(length,self.size-self.position)
        if not length:return b''
        first=self.position//self.chunk_size*self.chunk_size
        last=(self.position+length-1)//self.chunk_size*self.chunk_size
        starts=list(range(first,last+1,self.chunk_size))
        pieces={}
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures={executor.submit(self.block,start):start for start in starts}
            for index,future in enumerate(concurrent.futures.as_completed(futures),1):
                pieces[futures[future]]=future.result()
                if len(starts)>8 and index%8==0:print('RANGE_PROGRESS',index,len(starts),'requested_bytes',self.downloaded,flush=True)
        joined=b''.join(pieces[start] for start in starts)
        offset=self.position-first
        self.position+=length
        return joined[offset:offset+length]

def main():
    protocol=json.loads(Path(__file__).with_name('development_extension_protocol.json').read_text(encoding='utf-8'))
    assert protocol['official_split']=='train' and protocol['sequences']==['SNMOT-152','SNMOT-153']
    output=Path('D:/projects/FutsalMOT_Research/public/development_extension_v1')
    def open_archive(split,budget):
        if split!='train':raise ValueError('不允许最终test')
        url=f'https://huggingface.co/datasets/{original.REPO}/resolve/{original.REVISION}/train.zip?download=true'
        reader=ChunkReader(url,original.SIZES['train'],output/'range_cache',budget)
        return reader,zipfile.ZipFile(reader)
    original.open_archive=open_archive
    sys.argv=[__file__,'--split','train','--sequences',*protocol['sequences'],'--max-frame','150','--budget','500000000','--output',str(output)]
    original.main()

if __name__=='__main__':main()
