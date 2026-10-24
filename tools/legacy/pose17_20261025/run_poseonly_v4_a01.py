"""独立v4六臂串行候选；无隐式重训/预算重放，仅root冻结后显式启动。"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import statistics
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET

PROJECT=Path('D:/projects/FutsalMOT_UEDataset')
CODE=PROJECT/'Content/FutsalMOT/code'
ROOT=Path('G:/FutsalMOT_Research/pose/poseonly_v4')
PYTHON=Path('D:/projects/FutsalMOT/.venv/Scripts/python.exe')
PROTOCOL=ROOT/'frozen_a01/protocol.json'
ADMISSION=ROOT/'frozen_a01/admission.json'
SCHEDULE=ROOT/'candidate_a02/schedule_manifest.json'
TRAINER=CODE/'experiments/sim2real/train_pose_location_separate_v4.py'
EVALUATOR=CODE/'experiments/sim2real/evaluate_coco_pose_location_v4.py'
SEEDS=(20261024,20261025,20261026)
ARMS=('R3','R3S1')
LOCK=ROOT/'_runtime/v4_serial_driver.lock'

def now():return datetime.now(timezone.utc).isoformat()
def require(ok,message):
    if not ok:raise ValueError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def safe_output(path):
    raw=Path(path).absolute()
    for item in (raw,*raw.parents):
        require(not item.exists() or not (item.is_symlink() or getattr(item.stat(),'st_file_attributes',0)&0x400),'v4新输出禁止联接')
    actual=raw.resolve()
    require(ROOT==actual or ROOT in actual.parents,'v4运行产物必须实际位于G:/FutsalMOT_Research/pose/poseonly_v4')
    return actual

def atomic_json(path,value,replace=os.replace,sleep=time.sleep):
    path=safe_output(path);temporary=path.with_name(path.name+'.tmp')
    require(not temporary.exists(),'已有partial，保留现场不覆盖: '+str(temporary))
    with temporary.open('x',encoding='utf-8') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2,allow_nan=False);handle.write('\n');handle.flush();os.fsync(handle.fileno())
    for attempt,delay in enumerate((.05,.1,.2,.4,.8,0)):
        try:replace(temporary,path);return
        except PermissionError as error:
            if getattr(error,'winerror',None) not in (5,32) or attempt==5:raise
            sleep(delay)
WORKLOAD_TOKENS = ('train_pose_location', 'evaluate_coco_pose_location', 'run_poseonly_v4_a01.py', 'run_poseonly_v3_a01.py',
                   'prepare_pose_association_dev.py', 'attach_fixed_detection_pose.py',
                   'pose_location_control_driver', 'location_control_recovery')


def classify_gpu_processes(xml_text, processes, current_pid):
    """WDDM的C+G不是纯计算证据；C阻止，C+G须结合真实进程身份。"""
    by_pid = {int(row['ProcessId']): row for row in processes}
    blockers, diagnostics = [], []
    for node in ET.fromstring(xml_text).findall('.//gpu/processes/process_info'):
        raw_pid = node.findtext('pid', '')
        if not raw_pid.isdigit() or int(raw_pid) == current_pid:
            continue
        pid = int(raw_pid); kind = node.findtext('type', '').strip()
        actual = by_pid.get(pid, {})
        name = (actual.get('Name') or node.findtext('process_name', '') or '').replace('\\', '/').split('/')[-1].lower()
        args = (actual.get('CommandLine') or '').lower()
        workload = (name in ('python.exe', 'pythonw.exe', 'unrealeditor.exe', 'blender.exe', 'ollama.exe',
                              'llama-server.exe', 'llama-cli.exe', 'trtexec.exe')
                    or any(token in args for token in WORKLOAD_TOKENS)
                    or any(token in name for token in ('pytorch', 'tensorflow', 'comfy', 'train', 'inference')))
        info = dict(pid=pid, gpu_type=kind, process_name=name or None, cim_identity_available=bool(actual))
        if kind == 'C' or workload:
            info['reason'] = 'explicit_compute_type' if kind == 'C' else 'actual_workload_process_identity'
            blockers.append(info)
        else:
            info['classification'] = ('combined_type_without_workload_signature' if kind == 'C+G'
                                      else 'unresolved_gpu_type_diagnostic_only')
            diagnostics.append(info)
    return blockers, diagnostics


def process_gate():
    """只读CIM与GPU XML；桌面C+G保留诊断，不误判为训练，不停止其他进程。"""
    command = "$ErrorActionPreference='Stop'; $OutputEncoding=[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); $p=Get-CimInstance Win32_Process; ConvertTo-Json -InputObject @($p | Select-Object ProcessId,Name,CommandLine) -Compress"
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                            check=True, capture_output=True)
    # 字节解码在主线程严格执行；不让subprocess后台reader的GBK错误退化成空进程表。
    processes = json.loads(result.stdout.decode('utf-8-sig'))
    if isinstance(processes, dict):
        processes = [processes]
    require(isinstance(processes, list) and len(processes) > 0, 'CIM进程表为空，不能声称无训练')
    blockers = []
    ignored_owned_launcher = []
    for process in processes:
        if process['ProcessId'] == os.getpid():
            continue
        args = (process.get('CommandLine') or '').lower()
        if process['ProcessId'] == os.getppid() and Path(__file__).name.lower() in args:
            # Windows venv python.exe启动器为当前实际解释器的直接父进程，非第二个驱动。
            ignored_owned_launcher.append(process['ProcessId']); continue
        # 只检查项目脚本的真实Python进程，避免powershell/codex命令文本引用造成假阳性。
        name = process['Name'].lower()
        if name == 'unrealeditor.exe' or (name in ('python.exe', 'pythonw.exe') and any(token in args for token in WORKLOAD_TOKENS)):
            blockers.append(process)
    require(not blockers, '已有Editor/训练/评价/驱动，禁止并发: ' + json.dumps(blockers, ensure_ascii=False))
    gpu = subprocess.run(['nvidia-smi', '-q', '-x'],
                         check=True, capture_output=True)
    occupied, diagnostics = classify_gpu_processes(gpu.stdout, processes, os.getpid())
    require(not occupied, 'CUDA计算进程尚未结束，禁止并发: ' + repr(occupied))
    return dict(checked_utc=now(), editor_or_training_blockers=[], compute_processes=[],
                gpu_auxiliary_diagnostics=diagnostics, gpu_gate_policy='pure_C_blocks_CplusG_requires_actual_workload_identity')


def command_plan(output):
    """只构建argv，不导入Torch、不读检查点或启动进程。"""
    output=safe_output(output)
    return [dict(seed=seed,arm=arm,output=str(output/f'{arm}_seed{seed}'),train=[str(PYTHON),'-B',str(TRAINER),'train',
        '--protocol',str(PROTOCOL),'--schedule-manifest',str(SCHEDULE),'--admission',str(ADMISSION),
        '--output',str(output/f'{arm}_seed{seed}'),'--arm',arm,'--seed',str(seed),'--device','cuda:0','--cache-mib','3072'])
        for seed in SEEDS for arm in ARMS]


def evaluation_command(output,protocol_sha,admission_sha):
    checkpoint=output/'last.pt';receipt=output/'run_receipt.json'
    return [str(PYTHON),'-B',str(EVALUATOR),'--protocol',str(PROTOCOL),'--protocol-sha256',protocol_sha,
        '--admission',str(ADMISSION),'--admission-sha256',admission_sha,'--checkpoint',str(checkpoint),
        '--checkpoint-sha256',sha(checkpoint),'--checkpoint-role','last_ema','--run-receipt',str(receipt),
        '--run-receipt-sha256',sha(receipt),'--output',str(output/'pose_dev_evaluation'),'--device','cuda:0']


def validate_shutdown_receipt(receipt):
    """旧失败attempt正常quit不能升级为完整a04采集发布完成。"""
    require(receipt.get('capture_batch')=='longpair_a04' and receipt.get('all_four_stages_complete') is True
        and receipt.get('publication_complete') is True and receipt.get('normal_exit_confirmed') is True
        and receipt.get('process_absent') is True,'缺本轮a04全部发布后的正常退出收据，旧失败attempt不可复用')
    require(receipt.get('published_counts')==dict(rgb=4800,mask=4800,person_pose=48000),'a04发布计数未完成')


def load_context():
    sys.path.insert(0,str(CODE/'src'))
    from grf_ue_bridge import coco_pose_dev_eval_v4 as adapter
    protocol_sha,admission_sha=sha(PROTOCOL),sha(ADMISSION)
    context=adapter.load_context(PROTOCOL,protocol_sha,ADMISSION,admission_sha)
    require(adapter.trainer.bound_file(context['protocol']['schedule_manifest'])==SCHEDULE.resolve(),
        'v4必须使用candidate_a02原shared3调度')
    shutdown=adapter.trainer.bound_file(read(ADMISSION)['shutdown_receipt'])
    validate_shutdown_receipt(read(shutdown))
    return context,protocol_sha,admission_sha,shutdown


def bind_inputs(context,shutdown):
    paths=[Path(__file__),PROTOCOL,ADMISSION,SCHEDULE,PYTHON,shutdown]
    protocol=context['protocol']
    paths.extend(Path(item['path']) for item in protocol['source_files']+protocol['evaluation']['source_files'])
    manifest=read(SCHEDULE)
    paths.extend(Path(item['path']) for item in manifest['schedules'])
    paths.extend(Path(manifest[key]['path']) for key in ('real_jsonl','synthetic_jsonl','selection_manifest'))
    return [dict(path=str(path.resolve()),sha256=sha(path)) for path in dict.fromkeys(paths)]


def assert_bindings(bindings):
    require(all(Path(item['path']).is_file() and sha(item['path'])==item['sha256'] for item in bindings),
        '运行时源码、协议、调度或解释器变化；保留现场，不隐式重新绑定')


def child_environment():
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='0',YOLO_AUTOINSTALL='false',YOLO_OFFLINE='true',
        WANDB_MODE='disabled',COMET_MODE='DISABLED',CUBLAS_WORKSPACE_CONFIG=':4096:8',PYTHONDONTWRITEBYTECODE='1')
    for key,folder in (('TORCH_HOME','torch'),('YOLO_CONFIG_DIR','ultralytics'),('MPLCONFIGDIR','matplotlib'),
        ('XDG_CACHE_HOME','cache'),('TEMP','tmp'),('TMP','tmp')):
        path=safe_output(ROOT/'_runtime'/folder);path.mkdir(parents=True,exist_ok=True);env[key]=str(path)
    # venv已有实际Torch；只补接已有数值评价依赖，不安装/升级依赖。
    env['PYTHONPATH']=os.pathsep.join([str(CODE/'src'),'G:/FutsalMOT_Research/runtime_dependencies'])
    return env


def verify_arm_receipt(receipt,seed,arm,context):
    require(receipt.get('schema')=='futsalmot_pose_location_separate_run_v4' and receipt.get('complete') is True
        and receipt.get('completed_updates')==receipt.get('planned_updates')==1000
        and receipt.get('seed')==seed and receipt.get('arm')==arm,'子臂不是实际完整last1000，禁止评价或重放')
    require(receipt.get('actual_exposures')==dict(real=3000,synthetic=1000 if arm=='R3S1' else 0)
        and receipt.get('actual_ema_fp32') is True and receipt.get('real_test_read') is False
        and receipt.get('bindings')==context['v4_contexts'][(seed,arm)]['bindings'],'子臂曝光、EMA或绑定错误')


def summarize(completed,bindings):
    require(len(completed)==6 and {(r['seed'],r['arm']) for r in completed}=={(s,a) for s in SEEDS for a in ARMS},
        '六臂不足/重复，不能汇总为完成')
    paired=[]
    for seed in SEEDS:
        real=next(r for r in completed if r['seed']==seed and r['arm']=='R3')
        mixed=next(r for r in completed if r['seed']==seed and r['arm']=='R3S1')
        delta={key:100*(mixed['keypoints'][key]-real['keypoints'][key]) for key in real['keypoints'] if key.startswith(('AP','AR'))}
        paired.append(dict(seed=seed,R3S1_minus_R3_pp=delta))
    return dict(schema='futsalmot_poseonly_v4_paired_COCO_dev_summary_a01',status='all_six_completed_and_dev_evaluated',
        bindings=bindings,rows=completed,paired=paired,
        paired_delta_pp={key:dict(mean=statistics.mean(row['R3S1_minus_R3_pp'][key] for row in paired),
            sample_std=statistics.stdev(row['R3S1_minus_R3_pp'][key] for row in paired),
            positive_seeds=sum(row['R3S1_minus_R3_pp'][key]>0 for row in paired)) for key in paired[0]['R3S1_minus_R3_pp']},
        real_exposures_per_arm=3000,synthetic_exposures_in_mixed=1000,all_negative_results_preserved=True,
        equal_FLOPs=False,test_read=False,football_or_futsal_generalization_established=False,
        limitation='仅固定200 COCO公开dev代理；不按结果筛seed/best/比例，主线固定足球AssA留后续阶段')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true',help='root实际完成准入和a04退出后显式运行；默认只读预飞')
    parser.add_argument('--output',type=Path,default=ROOT/'control_a01')
    parser.add_argument('--driver-sha256',help='执行时必须显式绑定本文件完整SHA')
    args=parser.parse_args();output=safe_output(args.output);state_path=output/'driver_state.json'
    require(not output.exists() and not LOCK.exists(),'已有运行目录/全局锁，拒绝覆盖或隐式resume；核对真实状态后另建明确attempt')
    context,protocol_sha,admission_sha,shutdown=load_context()
    bindings=bind_inputs(context,shutdown);gate=process_gate();plan=command_plan(output)
    if not args.execute:
        print(json.dumps(dict(status='readonly_preflight_no_launch',process_gate=gate,plan=plan,bindings=bindings),ensure_ascii=False));return
    require(args.driver_sha256==sha(__file__),'root执行须绑定实际driver SHA')
    LOCK.parent.mkdir(parents=True,exist_ok=True)
    with LOCK.open('x',encoding='utf-8') as handle:
        json.dump(dict(pid=os.getpid(),created_utc=now(),output=str(output),driver_sha256=sha(__file__)),handle)
        handle.flush();os.fsync(handle.fileno())
    output.mkdir(parents=True);(output/'logs').mkdir()
    state=dict(schema='futsalmot_poseonly_v4_serial_driver_a01',status='running',pid=os.getpid(),child_pid=None,
        started_utc=now(),current=None,completed=[],subprocesses=[],bindings=bindings,output=str(output),
        test_read=False,UE_started=False,automatic_resume_or_retrain=False,SIGINT_policy='finish_active_child_and_stop_before_next_step_no_kill')
    stop=[False]
    previous=signal.signal(signal.SIGINT,lambda *_:stop.__setitem__(0,True))
    def persist():
        state['updated_utc']=now();atomic_json(state_path,state)
    def check_stop():
        if stop[0] or (output/'STOP_AFTER_CURRENT').exists():
            raise InterruptedError('用户请求停在子进程边界；未结束的数学更新不重放')
    def run(command,tag):
        check_stop();process_gate();assert_bindings(bindings)
        stdout=output/'logs'/(tag+'.stdout.log');stderr=output/'logs'/(tag+'.stderr.log')
        with stdout.open('xb') as out,stderr.open('xb') as err:
            child=subprocess.Popen(command,cwd=CODE,stdout=out,stderr=err,env=child_environment(),creationflags=subprocess.CREATE_NO_WINDOW)
            record=dict(tag=tag,pid=child.pid,command=command,started_utc=now(),stdout=str(stdout),stderr=str(stderr))
            state['subprocesses'].append(record);state['child_pid']=child.pid;state['current']=tag;persist()
            code=child.wait()
        record.update(exit_code=code,finished_utc=now());state['child_pid']=None;persist()
        require(code==0,f'子任务退出{code}: {tag}；不重训、不自动resume、不猜步，保留现场')
    try:
        persist()
        for item in plan:
            seed,arm=item['seed'],item['arm'];arm_output=Path(item['output']);name=f'{arm}_seed{seed}'
            require(not arm_output.exists(),'单臂目录已存在，拒绝覆盖/隐式重放')
            run(item['train'],name+'.train')
            receipt=read(arm_output/'run_receipt.json');verify_arm_receipt(receipt,seed,arm,context)
            run(evaluation_command(arm_output,protocol_sha,admission_sha),name+'.evaluate')
            report_path=arm_output/'pose_dev_evaluation/report.json';report=read(report_path)
            require(report.get('schema')=='futsalmot_coco_pose_dev_evaluation_v4'
                and report.get('status')=='official_public_dev_evaluated' and report.get('binding')==context['binding']
                and report.get('test_read') is False,'v4公开dev评价身份错误')
            state['completed'].append(dict(seed=seed,arm=arm,output=str(arm_output),
                keypoints=report['official_COCOeval']['keypoints'],bbox=report['official_COCOeval']['bbox'],
                exposures=receipt['actual_exposures'],run_receipt_sha256=sha(arm_output/'run_receipt.json'),
                evaluation_report_sha256=sha(report_path)))
            persist()
        summary_path=output/'paired_summary.json';atomic_json(summary_path,summarize(state['completed'],bindings))
        state.update(status='complete_all_six_train_and_dev',current=None,completed_utc=now(),summary=str(summary_path),summary_sha256=sha(summary_path));persist()
    except BaseException as error:
        state.update(status='stopped_preserved_no_replay',error=repr(error),traceback=traceback.format_exc(),stopped_utc=now());persist();raise
    finally:
        signal.signal(signal.SIGINT,previous)
    # 成功才移除本驱动自有锁；失败保留供root核对，绝不根据PID缺席自动恢复。
    lock=read(LOCK);require(lock['pid']==os.getpid(),'全局锁所有者变化，保留现场');LOCK.unlink()


if __name__=='__main__':main()


