"""v5唯一九臂串行协调器；默认只读，root冻结后显式--execute。"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from train_longpair_v5 import preflight,read,sha,require,RESEARCH,ARMS

PYTHON=Path('D:/projects/FutsalMOT/.venv/Scripts/python.exe')
SEEDS=(20261024,20261025,20261026)

def process_gate():
    import psutil
    own={os.getpid(),os.getppid()};conflicts=[]
    for process in psutil.process_iter(['pid','name']):
        name=(process.info['name'] or '').lower()
        if name=='unrealeditor.exe':conflicts.append(dict(pid=process.pid,name=name));continue
        if process.pid in own or name not in ('python.exe','pythonw.exe'):continue
        try:command=' '.join(process.cmdline()).lower()
        except (psutil.AccessDenied,psutil.NoSuchProcess):raise RuntimeError('不能确认另一个Python进程用途，拒绝启动')
        if any(token in command for token in ('train_pose','train_longpair','evaluate_longpair','run_longpair_v5_control','run_poseonly','resume_location_control')):
            conflicts.append(dict(pid=process.pid,name=name,command=command))
    require(not conflicts,'UE/研究任务仍在:'+str(conflicts));return dict(status='clear',conflicts=[])

def atomic(path,value):
    path=Path(path);temporary=path.with_name(path.name+'.tmp');require(not temporary.exists(),'保留已有partial:'+str(temporary))
    with temporary.open('x',encoding='utf-8') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n');stream.flush();os.fsync(stream.fileno())
    for attempt,delay in enumerate((.05,.1,.2,.4,.8,0)):
        try:os.replace(temporary,path);return
        except PermissionError as error:
            if getattr(error,'winerror',None) not in (5,32) or attempt==5:raise
            time.sleep(delay)

def summarize(root):
    reports={}
    for seed in SEEDS:
        for arm in ARMS:
            path=root/f'{arm}_seed{seed}'/'coco_dev/report.json';report=read(path)
            reports[f'{arm}_seed{seed}']=dict(path=str(path),sha256=sha(path),metrics=report['official_COCOeval'])
    baseline=read(root/'pretrained_reference/report.json')['official_COCOeval']['keypoints']
    pairs={}
    for seed in SEEDS:
        real=reports[f'R3_seed{seed}']['metrics']['keypoints'];row={}
        for arm in ARMS[1:]:
            mixed=reports[f'{arm}_seed{seed}']['metrics']['keypoints']
            row[arm]=dict(vs_same_real_R3={k:mixed[k]-real[k] for k in mixed if isinstance(mixed[k],(int,float))},
                vs_pretrained={k:mixed[k]-baseline[k] for k in mixed if isinstance(mixed[k],(int,float))})
        pairs[str(seed)]=row
    return dict(schema='futsalmot_longpair_v5_ninearm_coco_summary_v1',all_nine_preserved=True,reports=reports,paired=pairs,
        mean_AP_delta={arm:statistics.mean(pairs[str(seed)][arm]['vs_same_real_R3']['AP'] for seed in SEEDS) for arm in ARMS[1:]},
        progress_claim='COCO_only_tracking_AssA_threshold_not_yet_evaluated',final116187_read=False)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime-context','protocol','admission','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--driver-sha256');args=parser.parse_args()
    if args.execute:require(args.driver_sha256==sha(__file__),'必须绑定实际driver SHA')
    require(PYTHON.is_file(),'研究Python缺失');gate=process_gate();runtime=read(args.runtime_context);bundle=Path(runtime['code_bundle'])
    protocol=read(args.protocol);output=args.output.resolve();require(RESEARCH/'pose/poseonly_v5' in output.parents,'driver输出仅独立v5目录')
    for seed in SEEDS:
        for arm in ARMS:
            preflight(args.runtime_context,args.protocol,args.admission,seed,arm)
            require(not (output/f'{arm}_seed{seed}').exists(),'已有arm/partial，禁止覆盖或隐式重放')
    require(not output.exists(),'新九臂控制目录必须全新')
    if not args.execute:print(json.dumps(dict(status='readonly_prerequisites_complete_no_launch',process_gate=gate,arms=9,bundle=str(bundle))));return
    output.mkdir(parents=True);lock=output/'driver.lock'
    with lock.open('x',encoding='utf-8') as stream:stream.write(json.dumps(dict(pid=os.getpid(),driver_sha256=sha(__file__))))
    state=dict(schema='futsalmot_longpair_v5_driver_state_v1',pid=os.getpid(),driver_sha256=sha(__file__),status='starting',completed=[],protocol_sha256=sha(args.protocol),admission_sha256=sha(args.admission))
    state_path=output/'driver_state.json';atomic(state_path,state)
    common=['--runtime-context',str(args.runtime_context),'--protocol',str(args.protocol),'--admission',str(args.admission)]
    def run(command,log):
        process_gate();log.parent.mkdir(parents=True,exist_ok=True)
        with log.open('x',encoding='utf-8') as stream:
            child=subprocess.Popen([str(PYTHON),'-B']+command,stdout=stream,stderr=subprocess.STDOUT,cwd=str(bundle),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            state['child_pid']=child.pid;state['child_command']=command;atomic(state_path,state);code=child.wait()
        require(code==0,'子进程失败，保留现场，不重放:'+str(log))
        state['child_pid']=None
    try:
        initial=protocol['initialization'];state['status']='pretrained_reference_dev';atomic(state_path,state)
        run([str(bundle/'tools/research_ops/evaluate_longpair_v5.py')]+common+['--seed',str(SEEDS[0]),'--arm','R3','--checkpoint',initial['path'],'--checkpoint-sha256',initial['sha256'],'--role','pretrained_reference','--output',str(output/'pretrained_reference')],output/'logs/pretrained_reference.log')
        for seed in SEEDS:
            for arm in ARMS:
                key=f'{arm}_seed{seed}';armroot=output/key;runroot=armroot/'train'
                state.update(status='training',current_arm=key);atomic(state_path,state)
                run([str(bundle/'tools/research_ops/train_longpair_v5.py')]+common+['--seed',str(seed),'--arm',arm,'--output',str(runroot),'--device','cuda:0','--execute'],output/f'logs/{key}_train.log')
                receipt=read(runroot/'run_receipt.json');require(receipt.get('complete') is True and receipt.get('completed_updates')==1000,'训练终态不完整，不转评价')
                state.update(status='evaluating_last1000');atomic(state_path,state)
                run([str(bundle/'tools/research_ops/evaluate_longpair_v5.py')]+common+['--seed',str(seed),'--arm',arm,'--checkpoint',str(runroot/'last.pt'),'--checkpoint-sha256',sha(runroot/'last.pt'),
                    '--run-receipt',str(runroot/'run_receipt.json'),'--run-receipt-sha256',sha(runroot/'run_receipt.json'),'--output',str(armroot/'coco_dev')],output/f'logs/{key}_dev.log')
                state['completed'].append(key);atomic(state_path,state)
                if (output/'STOP_AFTER_CURRENT').exists():
                    state.update(status='stopped_user_request_after_committed_arm');atomic(state_path,state);return
        summary=summarize(output);atomic(output/'paired_summary.json',summary)
        state.update(status='complete_all_nine_train_and_dev',summary=dict(path=str(output/'paired_summary.json'),sha256=sha(output/'paired_summary.json')));atomic(state_path,state);lock.unlink()
    except BaseException as error:
        state.update(status='stopped_preserved_no_replay',error_type=type(error).__name__,error=str(error));atomic(state_path,state);raise
if __name__=='__main__':main()
