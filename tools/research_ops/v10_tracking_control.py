"""v10唯一253项CPU自由追踪/评价控制器；失败保存，不隐式重放。"""
import argparse
from datetime import datetime,timezone
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
sys.path.insert(0,str(Path(__file__).parent))
import v10_tracking_runtime as rt


def preflight(config,output):
    cfg,runtime,train,numeric,base,old=rt.validate_config(config)
    rt.require(cfg['tracking_matrix']==rt.tracking_matrix(train,cfg['training_control']),'253任务必须事前完整登记')
    gate=rt.read(rt.checked(cfg['numeric_validation']))
    rt.require(gate['status']=='complete_original750_three_modes_scope_equivalent'
        and all(c['all_rows_and_audit_equal'] for c in gate['checks']),'原数值等价实际验收缺失')
    budget=rt.read(rt.checked(cfg['actual_budget']))
    rt.require(budget['status']=='complete54_actual_budget_and_full_records_verified' and budget['totals']['updates']==54000,'独立实际训练预算缺失')
    exit=rt.read(rt.checked(cfg['training_exit']));rt.checked(exit['control_state'])
    from v8_control import process_snapshot,own_launcher_chain
    processes=process_snapshot();own=own_launcher_chain(processes,os.getpid(),Path(__file__).resolve())
    blocked=[p for p in processes if p['ProcessId'] not in own and (p['Name'].lower().startswith('unrealeditor')
        or any(name in (p.get('CommandLine') or '') for name in ('v10_train.py','v10_training_control.py','v10_prediction_cache.py','v10_tracking_control.py','v10_track.py')))]
    rt.require(not blocked,'相关工作仍活动或重复控制器：'+str(blocked))
    output=runtime.storage().physical_child(output,rt.V);rt.require(not output.exists(),'已有追踪控制目录/partial，不覆盖')
    for source in cfg['sources'].values():rt.checked(source['cache'])
    return cfg,runtime,dict(status='readonly253_v10_tracking_preflight',tracking_jobs=253,
        new_optimizer_updates=0,GPU_used=False,test_read=False,own_launcher_chain=sorted(own))


def execute(config,output):
    cfg,runtime,flight=preflight(config,output);output=Path(output);output.mkdir(parents=True)
    # 原子落盘工具也从已冻结训练bundle导入，避免第二份记录实现。
    journal=rt.load_file('v10_tracking_atomic',runtime.ROOT/'tools/research_ops/training_journal.py')
    journal.atomic(output/'preflight.json',flight)
    state=dict(schema='v10_independent_tracking_control_v1',status='starting',pid=os.getpid(),
        protocol_sha256=rt.sha(config),completed_tracking=[],active=None)
    def save():
        state['updated_utc']=datetime.now(timezone.utc).isoformat();journal.atomic(output/'driver_state.json',state)
    def child(tag,script,args):
        rt.require(not (output/'STOP').exists(),'STOP边界停止，不重放')
        logs=output/'logs';logs.mkdir(exist_ok=True)
        command=[sys.executable,'-B',str(rt.ROOT/'tools/research_ops'/script)]+list(map(str,args))
        with (logs/(tag+'.stdout.txt')).open('x',encoding='utf-8') as stdout,(logs/(tag+'.stderr.txt')).open('x',encoding='utf-8') as stderr:
            process=subprocess.Popen(command,stdout=stdout,stderr=stderr,env=os.environ.copy())
            state['active']=dict(tag=tag,child_pid=process.pid,command=command);save();code=process.wait()
        rt.require(code==0,tag+'实际进程失败，保留partial和日志');state['active']=None;save()
    save()
    try:
        for index,job in enumerate(cfg['tracking_matrix']):
            folder=output/'runs'/job['job_id'];state['status']='tracking_and_evaluating';save();start=time.perf_counter()
            child(job['job_id']+'_track','v10_track.py',['--config',config,'--job-id',job['job_id'],'--output',folder/'tracking','--execute'])
            child(job['job_id']+'_metric','v10_metric.py',['--config',config,'--tracking',folder/'tracking','--output',folder/'metric','--execute'])
            report=rt.read(folder/'metric/report.json')
            rt.require(report['status']=='complete' and report['job']==job and report['predictions_GT_filtered'] is False,'完整独立评价缺失')
            if job['kind']=='PT' and job['sequence'] in rt.EXTERNAL:
                expected=6622 if job['sequence']=='v_2QhNRucNC7E_c017' else 8137
                rt.require(report['GT_rows']==expected and report['GT_identity0_preserved'],'新比赛GT行数或ID0丢失')
            state['completed_tracking'].append(dict(job=job,report_sha256=rt.sha(folder/'metric/report.json'),wall_seconds=time.perf_counter()-start));save()
            if index==9:
                rt.require(all(j['job']['kind']=='PT' for j in state['completed_tracking']),'先完整验证五场两PT参考')
                journal.atomic(output/'all_five_PT_adapter_gate.json',dict(status='complete10_PT_all_five_matches_metric_and_gap',
                    checked_jobs=10,GT_identity0_preserved=True,predictions_filtered=False,test_read=False))
        state['status']='complete253_wait_analysis';save()
        child('complete_analysis','v10_analyze.py',['--config',config,'--control',output,'--output',output/'analysis_a01'])
        rt.require(rt.read(output/'analysis_a01/report.json')['status']=='complete_all253_tracking_comparisons','完整分析缺失')
        state['status']='complete253_tracking_and_analysis';save()
    except BaseException as error:
        state.update(status='failed_preserved_no_replay',error=repr(error),traceback=traceback.format_exc());save();raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--execute',action='store_true');a=p.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',PYTHONUTF8='0',PYTHONIOENCODING='utf-8',
        PYTHONPATH='D:/projects/FutsalMOT_Research/runtime_dependencies',YOLO_AUTOINSTALL='false')
    if a.execute:execute(a.config,a.output)
    else:print(rt.canonical(preflight(a.config,a.output)[2]))
