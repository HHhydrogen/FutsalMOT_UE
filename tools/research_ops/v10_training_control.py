"""v10唯一串行54训练控制器；完整记录已提交步，不隐式恢复partial。"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

sys.path.insert(0,str(Path(__file__).parent))
import v10_runtime as runtime
from training_journal import atomic


def preflight(config,output):
    cfg=runtime.validate_protocol(config);runtime.load_numeric(cfg)
    verified=runtime.read(cfg['numeric_validation_receipt_path'])
    runtime.require(verified['status']=='complete_three_methods_one_step_equal_with_recording'
        and verified['protocol_sha256']==runtime.sha(config) and verified['all_methods_equal'] is True,
        '记录接入实际数值诊断未通过')
    from v8_control import process_snapshot,own_launcher_chain
    processes=process_snapshot();own=own_launcher_chain(processes,os.getpid(),Path(__file__).resolve())
    blocked=[p for p in processes if p['ProcessId'] not in own and
        (p['Name'].lower().startswith('unrealeditor') or any(word in (p.get('CommandLine') or '') for word in
            ('v10_training_control.py','v10_train.py','v10_prediction_cache.py','run_multiseed_v10_serial.py')))]
    runtime.require(not blocked,'UE/自有GPU任务仍运行，不重复启动：'+str(blocked))
    output=runtime.storage().physical_child(output,runtime.EXPERIMENT)
    runtime.require(not output.exists(),'已有控制器输出/partial，不覆盖或隐式续跑')
    for pool in runtime.REGIMES:runtime.checked(cfg['synthetic_pools'][pool])
    for fold,ref in cfg['folds'].items():
        for key in ('real_pool','normalizer','quality_scale'):runtime.checked(ref[key])
        for pool in runtime.REGIMES:
            for seed in runtime.SEEDS:runtime.checked(cfg['exposures'][pool][fold][str(seed)])
    return cfg,dict(status='readonly_v10_training_control_preflight',runs=54,updates=54000,R_windows=162000,
        S_windows=54000,full_recording=True,own_verified_launcher_chain=sorted(own),test_read=False)


def execute(config,output):
    cfg,flight=preflight(config,output);output=Path(output);output.mkdir(parents=True)
    atomic(output/'preflight.json',flight)
    state=dict(schema='v10_recorded_training_control_v1',status='starting',pid=os.getpid(),
               protocol_sha256=runtime.sha(config),completed_train=[],active=None)
    def save():
        state['updated_utc']=datetime.now(timezone.utc).isoformat();atomic(output/'driver_state.json',state)
    save();identities={}
    try:
        for job in cfg['training_matrix']:
            if (output/'STOP').exists():state['status']='stopped_at_user_boundary_no_replay';save();return
            fold,seed,pool,method=(job[k] for k in ('fold','seed','pool','method'))
            directory=output/'runs'/fold/str(seed)/pool/method/'training'
            tag='%s_%s_%s_%s'%(fold,seed,pool,method);logs=output/'logs';logs.mkdir(exist_ok=True)
            command=[sys.executable,'-B',str(runtime.ROOT/'tools/research_ops/v10_train.py'),
                '--config',str(config),'--output',str(directory),'--fold',fold,'--seed',str(seed),'--pool',pool,'--method',method,'--execute']
            started=time.perf_counter()
            with (logs/(tag+'.stdout.txt')).open('x',encoding='utf-8') as stdout, (logs/(tag+'.stderr.txt')).open('x',encoding='utf-8') as stderr:
                process=subprocess.Popen(command,stdout=stdout,stderr=stderr,env=os.environ.copy())
                state.update(status='training',active=dict(job=job,child_pid=process.pid,command=command));save()
                code=process.wait()
            runtime.require(code==0,tag+'真实子进程失败，保留所有记录，不重放')
            receipt=runtime.read(directory/'run_receipt.json')
            if receipt['status']=='safely_paused':
                state.update(status='safely_paused_user_no_replay',active=None,paused_job=job);save();return
            runtime.require(receipt['status']=='complete' and receipt['completed_updates']==1000
                and receipt['real_window_exposures']==3000 and receipt['synthetic_window_exposures']==1000
                and receipt['prefetch']['closed'] and not receipt['prefetch']['worker_alive']
                and receipt['prefetch']['yielded']==1000,'实际预算或预取未闭合')
            binding=receipt['binding'];key=(fold,seed,method)
            common=(binding['initialization_sha256'],binding['R_window_UID_chain_sha256'])
            if key not in identities:identities[key]=common
            runtime.require(identities[key]==common,'跨S池初始化/R顺序改变')
            runtime.audit_steps(runtime.rows(directory/'steps.jsonl'),runtime.read(runtime.checked(cfg['exposures'][pool][fold][str(seed)])))
            complete=runtime.read(directory/'training_complete.json')
            runtime.require(complete['actual_updates']==1000 and len(complete['checkpoints'])==21,'完整检查点/记录不足')
            if not state['completed_train']:
                # 首个正式臂兼作端到端记录验收；验收失败立即停，不重放其预算。
                runtime.complete_model(config,directory)
                import torch
                expected_rng={'rng_python','rng_numpy','rng_torch_cpu','rng_torch_cuda'}
                step_rows=runtime.rows(directory/'steps.jsonl')
                for point in complete['checkpoints']:
                    payload=torch.load(runtime.checked(point),map_location='cpu',weights_only=False)
                    step=point['completed_updates'];expected_chain='0'*64 if step==0 else step_rows[step-1]['chain_sha256']
                    runtime.require(payload['completed_updates']==step and payload['exposure_chain']==expected_chain
                        and payload['binding']==binding and expected_rng<=set(payload)
                        and payload['rng_torch_cuda'] is not None and payload['optimizer']['param_groups']
                        and (step==0 or payload['optimizer']['state']), '首臂完整模型/优化器/RNG验收失败')
                atomic(output/'first_run_end_to_end_gate.json',dict(status='complete_first_formal1000_records_verified',
                    job=job,updates=1000,checkpoints_verified=21,optimizer_budget_replayed=0,
                    completion_sha256=runtime.sha(directory/'training_complete.json'),test_read=False))
            state['completed_train'].append(dict(**job,path=str(directory),receipt_sha256=runtime.sha(directory/'run_receipt.json'),
                complete_sha256=runtime.sha(directory/'training_complete.json'),process_wall_seconds=time.perf_counter()-started))
            state['active']=None;save()
        runtime.require(len(state['completed_train'])==54,'54训练未齐')
        state['status']='complete_54_recorded_train_wait_independent_tracking';save()
    except BaseException as error:
        state.update(status='failed_preserved_no_replay',error=repr(error),traceback=traceback.format_exc());save();raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('config','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    os.environ.update(PYTHONUTF8='0',PYTHONIOENCODING='utf-8',PYTHONPATH='D:/projects/FutsalMOT_Research/runtime_dependencies',CUBLAS_WORKSPACE_CONFIG=':4096:8')
    if args.execute:execute(args.config,args.output)
    else:print(runtime.canonical(preflight(args.config,args.output)[1]))
