"""只读采样本次UE的CPU/内存/进程I/O及整卡GPU；不把进程写入量当物理盘吞吐。"""
import argparse,ctypes,json,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--launch',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
deadline=time.monotonic()+180
while not a.launch.exists():
    if time.monotonic()>deadline:raise TimeoutError('等待启动收据超时')
    time.sleep(1)
launch=json.loads(a.launch.read_text(encoding='utf-8-sig'));k=ctypes.windll.kernel32;k.OpenProcess.restype=ctypes.c_void_p
handle=k.OpenProcess(0x0410,False,launch['pid'])
if not handle:raise ctypes.WinError()
h=ctypes.c_void_p(handle)
class Mem(ctypes.Structure):
    _fields_=[('cb',ctypes.c_ulong),('pagefaults',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in ('peak_rss','rss','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile','private')]
class Io(ctypes.Structure):
    _fields_=[(n,ctypes.c_ulonglong) for n in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
a.output.parent.mkdir(parents=True,exist_ok=True)
try:
    with a.output.open('x',encoding='utf-8') as f:
        while True:
            code=ctypes.c_ulong()
            if not k.GetExitCodeProcess(h,ctypes.byref(code)) or code.value!=259:break
            times=[ctypes.c_ulonglong() for _ in range(4)];m=Mem();m.cb=ctypes.sizeof(m);io=Io()
            if not k.GetProcessTimes(h,*[ctypes.byref(t) for t in times]):raise ctypes.WinError()
            if not ctypes.windll.psapi.GetProcessMemoryInfo(h,ctypes.byref(m),m.cb):raise ctypes.WinError()
            if not k.GetProcessIoCounters(h,ctypes.byref(io)):raise ctypes.WinError()
            r={'epoch':time.time(),'pid':launch['pid'],'cpu_seconds':(times[2].value+times[3].value)/1e7,'rss_bytes':m.rss,'private_bytes':m.private,'process_read_bytes':io.read_bytes,'process_write_bytes':io.write_bytes}
            result=subprocess.run(['nvidia-smi','--query-gpu=utilization.gpu,memory.used,utilization.memory','--format=csv,noheader,nounits'],capture_output=True,text=True)
            if result.returncode==0:
                v=[int(s.strip()) for s in result.stdout.strip().split(',')];r.update(gpu_percent=v[0],vram_mib=v[1],gpu_memory_percent=v[2])
            f.write(json.dumps(r)+'\n');f.flush();time.sleep(2)
finally:k.CloseHandle(h)
