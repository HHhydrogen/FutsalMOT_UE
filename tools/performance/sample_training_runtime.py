"""轻量只读硬件采样；不导入Torch、模型或媒体，不修改正在运行的训练。"""
import argparse
import json
from pathlib import Path
import statistics
import subprocess
import time
from datetime import datetime, timezone


def sample(state_path, seconds):
    import psutil
    rows=[]
    psutil.cpu_percent(percpu=True)
    for _ in range(seconds):
        state=json.loads(Path(state_path).read_text(encoding='utf-8-sig'))
        gpu=subprocess.check_output(['nvidia-smi','--query-gpu=utilization.gpu,memory.used,power.draw','--format=csv,noheader,nounits'],text=True).strip().split(',')
        rows.append(dict(utc=datetime.now(timezone.utc).isoformat(),status=state['status'],arm=state.get('current_arm'),
            GPU_util_percent=float(gpu[0]),GPU_memory_MiB=float(gpu[1]),GPU_power_W=float(gpu[2]),
            CPU_logical_core_percent=psutil.cpu_percent(percpu=True),available_RAM_GiB=psutil.virtual_memory().available/1024**3))
        time.sleep(1)
    arms={}
    root=Path(state_path).parent
    for key in state['completed']:
        r=json.loads((root/key/'train/run_receipt.json').read_text(encoding='utf-8-sig'))
        arms[key]=dict(updates=r['completed_updates'],elapsed_seconds=r['elapsed_seconds'],checkpoint_seconds=r['checkpoint_seconds'],
            checkpoint_fraction=r['checkpoint_seconds']/r['elapsed_seconds'],updates_per_second=r['completed_updates']/r['elapsed_seconds'])
    training=[r for r in rows if r['status']=='training']
    return dict(schema='training_hardware_observation_v1',created_utc=datetime.now(timezone.utc).isoformat(),samples=rows,completed_arm_timing=arms,
        training_samples=len(training),training_GPU_mean_util_percent=statistics.mean(r['GPU_util_percent'] for r in training) if training else None,
        numerical_or_protocol_changes=False,images_models_or_test_read=False,
        limits=['snapshot_utilization_not_kernel_profiler','checkpoint_timing_excludes_per_step_log_fsync','no_speedup_claim_without_new_benchmark'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--state',type=Path,required=True);parser.add_argument('--seconds',type=int,default=20);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path('D:/projects/FutsalMOT_Research');output=args.output.absolute()
    if not 5<=args.seconds<=30 or root/'performance' not in output.parents or output.exists():raise ValueError('仅5..30秒、新DResearch/performance输出')
    for p in (output,*output.parents):
        if p.exists() and (p.is_symlink() or getattr(p.lstat(),'st_file_attributes',0)&0x400):raise ValueError('输出不接受联接')
    result=sample(args.state,args.seconds);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(output=str(output),training_samples=result['training_samples'],GPU_mean_util_percent=result['training_GPU_mean_util_percent'])))

if __name__=='__main__':main()
