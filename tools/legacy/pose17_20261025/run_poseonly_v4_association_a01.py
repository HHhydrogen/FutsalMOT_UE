"""独立v4固定真实检测关联候选；六训练及dev结束后root显式启动，不修改旧数值链。"""
import argparse
import gc
import importlib.util
import json
import os
from pathlib import Path
import signal
import statistics
import subprocess
import sys
import time
import traceback

PROJECT=Path('D:/projects/FutsalMOT_UEDataset')
SPEC=importlib.util.spec_from_file_location('v4_association_existing_process_gate',PROJECT/'tools/pose17_ops/run_poseonly_v4_a01.py')
H=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(H)
CODE,PYTHON,now,require,sha,read=H.CODE,H.PYTHON,H.now,H.require,H.sha,H.read
ROOT=Path('G:/FutsalMOT_Research/pose/association_dev_a01')
OUTPUT=ROOT/'v4_association_a01'
EXEC=Path('G:/FutsalMOT_Workspace/UE/Saved/Pose17Development/association_execution_a01')
CACHE,PROTOCOL,CONFIGURATION=ROOT/'raw_detections/cache_manifest.json',EXEC/'protocol.json',EXEC/'pose_configuration.json'
REGISTRATION=EXEC/'registration_receipt.json'
BASELINE=ROOT/'bbox_lambda0/receipt.json'
BBOX_METRICS=ROOT/'metrics_bbox_lambda0/report.json'
PRETRAINED_METRICS=ROOT/'metrics_pretrained_pose_lambda01/report.json'
TRAIN_STATE=H.ROOT/'control_a01/driver_state.json'
TRAIN_ROOT=H.ROOT/'control_a01'
STATE=OUTPUT/'driver_state.json'
LOCK=ROOT/'v4_association_a01.lock'
ATTACH=CODE/'experiments/sim2real/attach_fixed_detection_pose.py'
TRACK=CODE/'experiments/sim2real/run_pose_association_dev.py'
METRIC=CODE/'experiments/sim2real/evaluate_pose_association_dev.py'
MEMBERS=tuple((seed,arm) for seed in H.SEEDS for arm in H.ARMS)
FIXED={str(CACHE):'3028fa8cf73737ae459afda4226bad33b55c6ef34cd817efb548ae417e6c462d',
    str(PROTOCOL):'52133eb43be96c96782bbc92abc0a7659d21442b817199c8e7c1ff1767e988db',
    str(CONFIGURATION):'49916c92e1362655a7e21944e1be44d315bc99863d877b65f5da3b1e743b6e16',
    str(BASELINE):'bc433af5ba617ec8b0a94a3aea43318ec68e79d7f7a4c2ce242fe4439926bf23'}

def safe_output(path):
    raw=Path(path).absolute()
    for item in (raw,*raw.parents):
        require(not item.exists() or not (item.is_symlink() or getattr(item.stat(),'st_file_attributes',0)&0x400),'关联新输出禁止联接')
    actual=raw.resolve();require(actual==OUTPUT or OUTPUT in actual.parents,'关联输出必须实际位于独立G根v4_association_a01')
    return actual

def atomic_json(path,value):
    path=safe_output(path);temporary=path.with_name(path.name+'.tmp')
    require(not temporary.exists(),'已有partial，保留现场拒绝覆盖')
    with temporary.open('x',encoding='utf-8') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2,allow_nan=False);handle.write('\n');handle.flush();os.fsync(handle.fileno())
    for index,delay in enumerate((.05,.1,.2,.4,.8,0)):
        try:os.replace(temporary,path);return
        except PermissionError as error:
            if getattr(error,'winerror',None) not in (5,32) or index==5:raise
            time.sleep(delay)
def source_bindings():
    files = [Path(__file__), Path(H.__file__), ATTACH, TRACK, METRIC,
             CODE / 'src/grf_ue_bridge/fixed_detection_pose_attach_v2.py',
             CODE / 'src/grf_ue_bridge/pose_bytetrack_v2.py', CODE / 'src/grf_ue_bridge/pose_association_trackeval_v1.py',
             CODE / 'src/grf_ue_bridge/coco_pose_dev_eval_v4.py']
    return {str(path): sha(path) for path in files}


def association_context():
    for path, identity in FIXED.items():
        require(sha(path) == identity, '冻结关联输入改变: ' + path)
    protocol, registration, baseline = read(PROTOCOL), read(REGISTRATION), read(BASELINE)
    require(registration['protocol_sha256'] == FIXED[str(PROTOCOL)]
            and registration['configuration_sha256'] == FIXED[str(CONFIGURATION)]
            and registration['pose_lambda'] == .1 and registration['test_read'] is False, 'root唯一参数登记不符')
    require(protocol['frozen_by'] == 'root' and protocol['pose_cost_candidate']['lambda_candidates'] == [0, .1]
            and protocol['test_split_used'] is False, '不能重选lambda/开发集')
    require(baseline['pose_lambda'] == 0 and baseline['protocol_sha256'] == FIXED[str(PROTOCOL)]
            and baseline['identity']['fixed_detection_set_sha256'] == FIXED[str(CACHE)]
            and all(value['frames'] == 150 and value['lambda0_equivalence']['passed'] is True
                    and value['lambda0_equivalence']['output_arrays_exact'] is True
                    for value in baseline['sequences'].values()), '缺真实450帧lambda0等价')
    metrics = {'bbox_lambda0': read(BBOX_METRICS), 'pretrained_pose_lambda01': read(PRETRAINED_METRICS)}
    for report in metrics.values():
        require(report['status'] == 'complete_fixed_development_TrackEval'
                and report['input_binding']['cache_manifest_sha256'] == FIXED[str(CACHE)]
                and report['input_binding']['protocol_sha256'] == FIXED[str(PROTOCOL)]
                and report['input_binding']['lambda0_receipt_sha256'] == FIXED[str(BASELINE)]
                and report['test_read'] is False and report['DO_PREPROC'] is False
                and report['predictions_filtered'] is False and report['frames']==450, '历史固定检测参考不同')
    v4protocol=read(H.PROTOCOL)
    rule=v4protocol['evaluation']['tracking_progress_definition']
    require(rule['fixed_pose_lambda']==.1 and rule['original_development_rule']['sha256']==FIXED[str(PROTOCOL)]
        and rule['test_116_187_sealed'] is True,'新v4协议未绑定原唯一lambda/封存规则')
    return dict(protocol=protocol, progress_rule=rule, v4_protocol_sha256=sha(H.PROTOCOL),
                source_sha256=source_bindings(), fixed_inputs=FIXED,
                references={name: dict(path=str(path), sha256=sha(path), summary=metrics[name]['summary'])
                            for name, path in (('bbox_lambda0', BBOX_METRICS), ('pretrained_pose_lambda01', PRETRAINED_METRICS))})


def training_complete():
    state = read(TRAIN_STATE)
    expected = set(MEMBERS)
    if state.get('status') != 'complete_all_six_train_and_dev' or len(state.get('completed', [])) != 6:
        return None, dict(status='blocked_v4_training_not_complete', driver_status=state.get('status'),
                          completed_arms=len(state.get('completed', [])), current=state.get('current'))
    require({(row['seed'], row['arm']) for row in state['completed']} == expected, '六臂身份不完整')
    summary_path = Path(state['summary'])
    require(summary_path == TRAIN_ROOT / 'paired_summary.json' and sha(summary_path) == state['summary_sha256'], 'v4三seed汇总缺失/改变')
    summary = read(summary_path)
    require(summary['status'] == 'all_six_completed_and_dev_evaluated' and summary['rows'] == state['completed']
            and summary['bindings'] == state['bindings'], 'v4完成状态与实际汇总不一致')
    return state, None


def output_paths(seed, arm):
    root = OUTPUT / f'{arm}_seed{seed}'
    return root, root / 'attachment', root / 'tracking', root / 'metrics'


def attachment_command(checkpoint, checkpoint_sha, output):
    return [str(PYTHON), str(ATTACH), '--cache-manifest', str(CACHE), '--cache-sha256', FIXED[str(CACHE)],
            '--configuration', str(CONFIGURATION), '--configuration-sha256', FIXED[str(CONFIGURATION)],
            '--checkpoint', str(checkpoint), '--checkpoint-sha256', checkpoint_sha, '--model-member', 'ema',
            '--output', str(output), '--device', 'cuda:0', '--execute-inference']


def tracking_command(attachment, output):
    manifest = attachment / 'attachment_manifest.json'
    return [str(PYTHON), str(TRACK), '--cache-manifest', str(CACHE), '--cache-sha256', FIXED[str(CACHE)],
            '--protocol', str(PROTOCOL), '--protocol-sha256', FIXED[str(PROTOCOL)], '--pose-lambda', '.1',
            '--attachment-manifest', str(manifest), '--attachment-sha256', sha(manifest),
            '--lambda0-receipt', str(BASELINE), '--output', str(output)]


def metric_command(tracking, output):
    return [str(PYTHON), str(METRIC), '--tracking-dir', str(tracking), '--cache-manifest', str(CACHE),
            '--cache-sha256', FIXED[str(CACHE)], '--protocol', str(PROTOCOL), '--protocol-sha256', FIXED[str(PROTOCOL)],
            '--lambda0-receipt', str(BASELINE), '--lambda0-receipt-sha256', FIXED[str(BASELINE)],
            '--tracking-receipt-sha256', sha(tracking / 'receipt.json'), '--output', str(output)]


def validate_model_member(member, context):
    """在完整六臂门禁后CPU加载真实EMA；验证独立v4来源，不凭schema声明准入。"""
    from grf_ue_bridge import coco_pose_dev_eval_v4 as adapter
    output = Path(member['output']); run_path = output / 'run_receipt.json'
    report_path = output / 'pose_dev_evaluation/report.json'
    require(output == TRAIN_ROOT / f"{member['arm']}_seed{member['seed']}", '模型输出离开冻结v4目录')
    require(sha(run_path) == member['run_receipt_sha256'] and sha(report_path) == member['evaluation_report_sha256'], '实际run/评价SHA改变')
    run, report = read(run_path), read(report_path)
    model_ref = report['prediction_receipt']['checkpoint']; checkpoint = output / 'last.pt'
    require(report['schema'] == 'futsalmot_coco_pose_dev_evaluation_v4' and report['test_read'] is False
            and model_ref['role'] == 'last_ema_v4' and model_ref['completed_updates'] == 1000
            and Path(model_ref['path']) == checkpoint and model_ref['run_receipt_sha256'] == member['run_receipt_sha256']
            and report['binding'] == context['binding'], 'v4实际评价未绑定本EMA和协议')
    model, metadata = adapter.load_model(checkpoint, model_ref['sha256'], 'last_ema', context, run_path, member['run_receipt_sha256'])
    require(metadata['seed'] == member['seed'] and metadata['arm'] == member['arm'], 'EMA seed/arm错配')
    del model; gc.collect()
    return dict(checkpoint=str(checkpoint), checkpoint_sha256=model_ref['sha256'], run_receipt_sha256=member['run_receipt_sha256'],
                evaluation_report_sha256=member['evaluation_report_sha256'], seed=member['seed'], arm=member['arm'])


def paired_delta(real,mixed):
    return dict(delta_pp={key:mixed['metrics_percent'][key]-real['metrics_percent'][key] for key in real['metrics_percent']},
        IDSW_delta=mixed['IDSW_count']-real['IDSW_count'])


def summarize(completed,context):
    require(len(completed)==6 and {(r['seed'],r['arm']) for r in completed}==set(MEMBERS),'六臂不足/重复，不汇总完成')
    pairs=[]
    for seed in H.SEEDS:
        real=next(r for r in completed if r['seed']==seed and r['arm']=='R3')['summary']
        mixed=next(r for r in completed if r['seed']==seed and r['arm']=='R3S1')['summary']
        require(set(real)==set(mixed),'两臂逐序列集合不同')
        pairs.append(dict(seed=seed,**paired_delta(real['COMBINED_SEQ'],mixed['COMBINED_SEQ']),
            sequence_deltas={seq:paired_delta(real[seq],mixed[seq]) for seq in real if seq!='COMBINED_SEQ'}))
    values={key:dict(mean=statistics.mean(p['delta_pp'][key] for p in pairs),
        sample_std=statistics.stdev(p['delta_pp'][key] for p in pairs),positive_seeds=sum(p['delta_pp'][key]>0 for p in pairs))
        for key in pairs[0]['delta_pp']}
    rule=context['progress_rule']
    checks=dict(AssA_mean=values['AssA']['mean']>=rule['paired_R3S1_minus_R3_mean_gain_pp_min'],
        AssA_positive_seeds=values['AssA']['positive_seeds']>=rule['positive_AssA_training_seeds_min'],
        HOTA_constraint=values['HOTA']['mean']>=rule['HOTA_mean_gain_pp_min'],
        IDF1_constraint=values['IDF1']['mean']>=-rule['IDF1_mean_drop_pp_max'])
    references={arm:{name:dict(mean_delta_pp={key:statistics.mean(
        row['summary']['COMBINED_SEQ']['metrics_percent'][key]-reference['summary']['COMBINED_SEQ']['metrics_percent'][key]
        for row in completed if row['arm']==arm) for key in values},
        mean_IDSW_delta=statistics.mean(row['summary']['COMBINED_SEQ']['IDSW_count']-
            reference['summary']['COMBINED_SEQ']['IDSW_count'] for row in completed if row['arm']==arm))
        for name,reference in context['references'].items()} for arm in H.ARMS}
    return dict(schema='futsalmot_poseonly_v4_fixed_detection_association_summary_a01',status='all_six_association_complete',
        rows=completed,paired_R3S1_minus_R3=pairs,paired_delta_pp=values,
        IDSW_delta_counts=dict(values=[p['IDSW_delta'] for p in pairs],mean=statistics.mean(p['IDSW_delta'] for p in pairs)),
        registered_progress_rule=rule,registered_checks=checks,registered_development_progress_passed=all(checks.values()),
        references=context['references'],arm_mean_reference_differences=references,
        fixed_inputs=context['fixed_inputs'],source_sha256=context['source_sha256'],v4_protocol_sha256=context['v4_protocol_sha256'],
        DO_PREPROC=False,test_read=False,all_negative_results_preserved=True,
        limitation='151/152/153同game9三个开发片段；三训练seed不是三场比赛，不能证明封存测试/跨比赛/真实五人制泛化')


def plan():
    return [dict(seed=seed,arm=arm,output=str(output_paths(seed,arm)[0]),model_member='ema',frames=450,
        stages=['actual_v4_EMA_CPU_gate','GPU_attachment_once','CPU_lambda01_tracking','CPU_TrackEval']) for seed,arm in MEMBERS]


def environment(gpu):
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='0' if gpu else '-1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',
        YOLO_AUTOINSTALL='false',YOLO_OFFLINE='true',WANDB_MODE='disabled',COMET_MODE='DISABLED',CUBLAS_WORKSPACE_CONFIG=':4096:8')
    for key,folder in (('TORCH_HOME','torch'),('YOLO_CONFIG_DIR','ultralytics'),('MPLCONFIGDIR','matplotlib'),
        ('XDG_CACHE_HOME','cache'),('TEMP','tmp'),('TMP','tmp')):
        path=safe_output(OUTPUT/'_runtime'/folder);path.mkdir(parents=True,exist_ok=True);env[key]=str(path)
    env['PYTHONPATH']=os.pathsep.join([str(CODE/'src'),'G:/FutsalMOT_Research/runtime_dependencies'])
    return env


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--driver-sha256');args=parser.parse_args()
    context=association_context();complete,blocked=training_complete()
    if not args.execute:
        gate=H.process_gate() if complete else None
        print(json.dumps(dict(status=blocked['status'] if blocked else 'readonly_prerequisites_complete_no_launch',
            launch_authorized_by_this_preflight=False,blocking=blocked,process_gate=gate,plan=plan(),
            actual_model_gate='deferred_execution_only_after_all_six_and_driver_exit'),ensure_ascii=False));return
    require(complete is not None,'六训练+COCOdev尚未完整结束，禁止启动: '+repr(blocked))
    require(args.driver_sha256==sha(__file__),'执行需root绑定新driver完整SHA')
    require(sys.version_info[:2]==(3,10),'实际EMA加载必须用研究Python3.10，非UE Python3.11')
    H.process_gate();safe_output(OUTPUT)
    require(not OUTPUT.exists() and not LOCK.exists(),'已有结果/锁，禁止覆盖、隐式恢复或重复推理')
    sys.path.insert(0,str(CODE/'src'));sys.path.append('G:/FutsalMOT_Research/runtime_dependencies')
    v4context,_,_,_=H.load_context()
    inputs=dict(context['fixed_inputs'])
    inputs.update({str(path):sha(path) for path in (TRAIN_STATE,Path(complete['summary']),H.PROTOCOL,H.ADMISSION,
        REGISTRATION,BBOX_METRICS,PRETRAINED_METRICS)})
    with LOCK.open('x',encoding='utf-8') as handle:
        json.dump(dict(pid=os.getpid(),created_utc=now(),source_sha256=context['source_sha256']),handle);handle.flush();os.fsync(handle.fileno())
    OUTPUT.mkdir();os.environ.update(environment(False))
    state=dict(schema='futsalmot_poseonly_v4_association_serial_driver_a01',status='running',pid=os.getpid(),child_pid=None,
        started_utc=now(),current=None,completed=[],subprocesses=[],bindings=context,input_sha256=inputs,test_read=False,
        v4_driver_state_sha256=sha(TRAIN_STATE),v4_summary_sha256=complete['summary_sha256'],automatic_resume=False)
    stop=[False];previous=signal.signal(signal.SIGINT,lambda *_:stop.__setitem__(0,True))
    def persist():state['updated_utc']=now();atomic_json(STATE,state)
    def boundaries():
        require(not stop[0] and not (OUTPUT/'STOP_AFTER_CURRENT').exists(),'用户请求在子任务边界停止，保留当前完整产物')
        H.process_gate()
        require(source_bindings()==context['source_sha256'],'源码变化，不隐式重新绑定或重放')
        require(all(sha(path)==identity for path,identity in inputs.items()),'冻结输入变化，不重绑定')
    def run(command,tag,logs,gpu):
        boundaries()
        with (logs/(tag+'.stdout.log')).open('xb') as out,(logs/(tag+'.stderr.log')).open('xb') as err:
            process=subprocess.Popen(command,cwd=CODE,env=environment(gpu),stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
            record=dict(tag=tag,pid=process.pid,command=command,started_utc=now());state['subprocesses'].append(record)
            state.update(child_pid=process.pid,current=tag);persist();code=process.wait()
        record.update(exit_code=code,finished_utc=now());state['child_pid']=None;persist()
        require(code==0,f'{tag}退出{code}；保留现场，无隐式重试/重复GPU推理')
    try:
        persist()
        import torch
        import ultralytics
        require(torch.__version__=='2.6.0+cu124' and ultralytics.__version__=='8.4.60','实际执行需已冻结Torch/Ultralytics运行时')
        for seed,arm in MEMBERS:
            boundaries();member=next(row for row in complete['completed'] if row['seed']==seed and row['arm']==arm)
            identity=validate_model_member(member,v4context)
            output,attachment,tracking,metrics=output_paths(seed,arm);output.mkdir();logs=output/'logs';logs.mkdir()
            atomic_json(output/'v4_model_gate.json',identity)
            run(attachment_command(Path(identity['checkpoint']),identity['checkpoint_sha256'],attachment),f'{arm}_{seed}.attachment',logs,True)
            run(tracking_command(attachment,tracking),f'{arm}_{seed}.tracking',logs,False)
            run(metric_command(tracking,metrics),f'{arm}_{seed}.metrics',logs,False)
            report=read(metrics/'report.json')
            require(report['status']=='complete_fixed_development_TrackEval' and report['pose_lambda']==.1
                and report['pose_model_sha256']==identity['checkpoint_sha256'] and report['test_read'] is False
                and report['DO_PREPROC'] is False and report['predictions_filtered'] is False,'实际关联报告身份/无过滤约束失败')
            summary=report['summary']
            state['completed'].append(dict(identity,output=str(output),summary=summary,
                attachment_sha256=sha(attachment/'attachment_manifest.json'),tracking_receipt_sha256=sha(tracking/'receipt.json'),
                metrics_report_sha256=sha(metrics/'report.json'),reference_differences={name:{seq:paired_delta(ref['summary'][seq],summary[seq])
                    for seq in summary} for name,ref in context['references'].items()}));persist()
        summary_path=OUTPUT/'paired_summary.json';atomic_json(summary_path,summarize(state['completed'],context))
        state.update(status='complete_all_six_association_and_metrics',current=None,summary=str(summary_path),summary_sha256=sha(summary_path),completed_utc=now());persist()
    except BaseException as error:
        state.update(status='stopped_preserved_no_replay',error=repr(error),traceback=traceback.format_exc());persist();raise
    finally:signal.signal(signal.SIGINT,previous)
    require(read(LOCK)['pid']==os.getpid(),'锁所有者变化，不删除');LOCK.unlink()


if __name__=='__main__':main()


