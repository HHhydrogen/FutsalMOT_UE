"""独立CIM权限故障恢复：只补第5评价和第6新训练/评价，零优化器重放。"""
import argparse
import gc
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import traceback

PROJECT=Path('D:/projects/FutsalMOT_UEDataset')
SPEC=importlib.util.spec_from_file_location('v4_recovery_original_driver_readonly',PROJECT/'tools/pose17_ops/run_poseonly_v4_a01.py')
H=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(H)
ROOT=H.ROOT/'recovery_cim_a01'
CONTROL=H.ROOT/'control_a01'
OLD_STATE=CONTROL/'driver_state.json'
STATE=ROOT/'driver_state.json'
FIRST4={(seed,arm) for seed in (20261024,20261025) for arm in H.ARMS}
FIFTH=CONTROL/'R3_seed20261026'
SIXTH=CONTROL/'R3S1_seed20261026'
require,read,sha,now,atomic_json=H.require,H.read,H.sha,H.now,H.atomic_json

def verify_old_failure(old):
    require(old.get('status')=='stopped_preserved_no_replay' and old.get('child_pid') is None
        and 'Get-CimInstance Win32_Process' in old.get('error',''),'只允许实际CIM权限失败，不猜测其他故障')
    require(len(old.get('completed',[]))==4 and {(r['seed'],r['arm']) for r in old['completed']}==FIRST4,'原4臂完成身份不符')
    records=[r for r in old['subprocesses'] if r['tag']=='R3_seed20261026.train']
    require(len(records)==1 and records[0].get('exit_code')==0,'第5训练不是实际exit0，不进入评价恢复')
    require(not any(r['tag']=='R3_seed20261026.evaluate' for r in old['subprocesses']),'第5评价已提交，不能重复推理')
    return records[0]

def verify_completed_rows(old,context):
    for row in old['completed']:
        out=Path(row['output']);require(out==CONTROL/f"{row['arm']}_seed{row['seed']}",'原臂目录变化')
        report_path=out/'pose_dev_evaluation/report.json';run_path=out/'run_receipt.json'
        require(sha(report_path)==row['evaluation_report_sha256'] and sha(run_path)==row['run_receipt_sha256'],'原已完成run/评价SHA变化')
        report=read(report_path);H.verify_arm_receipt(read(run_path),row['seed'],row['arm'],context)
        ref=report['prediction_receipt']['checkpoint']
        require(report['schema']=='futsalmot_coco_pose_dev_evaluation_v4' and report['binding']==context['binding']
            and ref['role']=='last_ema_v4' and ref['completed_updates']==1000 and sha(out/'last.pt')==ref['sha256'],
            '原已完成评价/实际last1000不匹配')

def verify_fifth_transaction(run,transaction):
    require(transaction.get('status')=='committed' and transaction.get('completed_updates')==1000
        and transaction.get('exposure_chain_sha256')==run['exposure_chain_sha256'],'第5完整更新事务未提交')

def verify_fifth_text(context):
    run=read(FIFTH/'run_receipt.json');H.verify_arm_receipt(run,20261026,'R3',context)
    verify_fifth_transaction(run,read(FIFTH/'update_transaction.json'))
    require(not list(FIFTH.glob('*.tmp')) and not (FIFTH/'pose_dev_evaluation').exists() and not SIXTH.exists(),
        '已有partial/第5评价/第6目录，拒绝覆盖或隐式重放')
    return run

def verify_fifth_checkpoint(context):
    """仅root实际执行时CPU载入完整last/optimizer/RNG链；不进行任何更新。"""
    import torch
    from grf_ue_bridge import coco_pose_dev_eval_v4 as adapter
    ref_path=FIFTH/'last.pt';run_path=FIFTH/'run_receipt.json'
    model,metadata=adapter.load_model(ref_path,sha(ref_path),'last_ema',context,run_path,sha(run_path))
    checkpoint=torch.load(ref_path,map_location='cpu',weights_only=False)
    completed=adapter.trainer.reconcile_resume(FIFTH,checkpoint,context['v4_contexts'][(20261026,'R3')])
    require(completed==1000,'第5完整曝光/优化器预算不是1000')
    del model,checkpoint;gc.collect()
    return dict(actual_checkpoint_sha256=sha(ref_path),actual_model_gate=metadata,reconciled_updates=completed,
        optimizer_replayed_updates=0,training_restarted=False)

def row_from_actual(seed,arm,context):
    out=CONTROL/f'{arm}_seed{seed}';run=read(out/'run_receipt.json');H.verify_arm_receipt(run,seed,arm,context)
    report_path=out/'pose_dev_evaluation/report.json';report=read(report_path)
    require(report.get('schema')=='futsalmot_coco_pose_dev_evaluation_v4' and report.get('status')=='official_public_dev_evaluated'
        and report.get('binding')==context['binding'] and report.get('test_read') is False,'实际补充评价失败')
    return dict(seed=seed,arm=arm,output=str(out),keypoints=report['official_COCOeval']['keypoints'],
        bbox=report['official_COCOeval']['bbox'],exposures=run['actual_exposures'],
        run_receipt_sha256=sha(out/'run_receipt.json'),evaluation_report_sha256=sha(report_path))

def new_commands(protocol_sha,admission_sha):
    sixth=next(item for item in H.command_plan(CONTROL) if item['seed']==20261026 and item['arm']=='R3S1')
    return [('R3_seed20261026.evaluate',H.evaluation_command(FIFTH,protocol_sha,admission_sha)),
        ('R3S1_seed20261026.train',sixth['train'])]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--source-sha256')
    args=parser.parse_args();old=read(OLD_STATE);verify_old_failure(old)
    context,protocol_sha,admission_sha,_=H.load_context();verify_completed_rows(old,context);fifth=verify_fifth_text(context)
    old_sha=sha(OLD_STATE);commands=new_commands(protocol_sha,admission_sha)
    if not args.execute:
        print(json.dumps(dict(status='readonly_recovery_candidate_no_launch',original_driver_remains_failed=True,
            original_completed=4,fifth_training_complete=1000,optimizer_replayed_updates=0,
            pending_commands=commands,final_command='R3S1_seed20261026.evaluate constructed after actual last exists'),ensure_ascii=False));return
    require(args.source_sha256==sha(__file__),'root需绑定实际恢复入口SHA')
    require(not ROOT.exists() and not (CONTROL/'paired_summary.json').exists(),'恢复/汇总已存在，禁止重复启动')
    H.process_gate()  # root在已批准权限环境启动；CIM失败不得伪造空进程表或自动绕过。
    H.assert_bindings(old['bindings'])
    ROOT.mkdir();(ROOT/'logs').mkdir()
    with (ROOT/'lock').open('x',encoding='utf-8') as handle:
        json.dump(dict(pid=os.getpid(),created_utc=now()),handle);handle.flush();os.fsync(handle.fileno())
    state=dict(schema='futsalmot_v4_independent_CIM_recovery_driver_a01',status='running',pid=os.getpid(),child_pid=None,
        started_utc=now(),completed=list(old['completed']),subprocesses=[],bindings=old['bindings'],
        recovery_source_sha256=sha(__file__),original_failed_state=dict(path=str(OLD_STATE),sha256=old_sha),
        original_failure=old['error'],optimizer_replayed_updates=0,implicit_resume=False)
    stop=[False];previous=signal.signal(signal.SIGINT,lambda *_:stop.__setitem__(0,True))
    def persist():state['updated_utc']=now();atomic_json(STATE,state)
    def guard():
        require(not stop[0] and not (ROOT/'STOP_AFTER_CURRENT').exists() and not (CONTROL/'STOP_AFTER_CURRENT').exists(),'用户停止，恢复不再开下一子任务')
        require(sha(OLD_STATE)==old_sha and sha(__file__)==state['recovery_source_sha256'],'原失败证据或恢复源码变化')
        H.assert_bindings(old['bindings']);H.process_gate()
    def run(tag,command):
        guard()
        with (ROOT/'logs'/(tag+'.stdout.log')).open('xb') as out,(ROOT/'logs'/(tag+'.stderr.log')).open('xb') as err:
            child=subprocess.Popen(command,cwd=H.CODE,stdout=out,stderr=err,env=H.child_environment(),creationflags=subprocess.CREATE_NO_WINDOW)
            record=dict(tag=tag,pid=child.pid,command=command,started_utc=now());state['subprocesses'].append(record)
            state.update(current=tag,child_pid=child.pid);persist();code=child.wait()
        record.update(exit_code=code,finished_utc=now());state['child_pid']=None;persist()
        require(code==0,'恢复子任务失败；保留现场，不重试/重放: '+tag)
    try:
        persist();guard();state['fifth_checkpoint_gate']=verify_fifth_checkpoint(context);persist()
        run(*commands[0]);state['completed'].append(row_from_actual(20261026,'R3',context));persist()
        run(*commands[1]);H.verify_arm_receipt(read(SIXTH/'run_receipt.json'),20261026,'R3S1',context)
        run('R3S1_seed20261026.evaluate',H.evaluation_command(SIXTH,protocol_sha,admission_sha))
        state['completed'].append(row_from_actual(20261026,'R3S1',context));persist()
        receipt=dict(schema='futsalmot_v4_CIM_permission_recovery_receipt_a01',status='completed_without_optimizer_replay',
            original_failed_state=state['original_failed_state'],original_failure=state['original_failure'],
            completed_original_train_eval_arms=4,reused_complete_fifth_train_updates=1000,
            fifth_train_optimizer_replayed_updates=0,new_sixth_train_updates=1000,new_evaluations=2,
            old_state_logs_lock_unchanged=True,recovery_source_sha256=sha(__file__),final_authority=str(STATE))
        atomic_json(ROOT/'recovery_receipt.json',receipt)
        summary=H.summarize(state['completed'],old['bindings']);summary['explicit_recovery']=dict(path=str(ROOT/'recovery_receipt.json'),sha256=sha(ROOT/'recovery_receipt.json'))
        canonical=CONTROL/'paired_summary.json';require(not canonical.exists(),'canonical汇总已有新产物，不覆盖');atomic_json(canonical,summary)
        state.update(status='complete_all_six_train_and_dev',current=None,completed_utc=now(),summary=str(canonical),summary_sha256=sha(canonical),
            recovery_receipt_sha256=sha(ROOT/'recovery_receipt.json'));persist()
    except BaseException as error:
        state.update(status='stopped_preserved_no_replay',error=repr(error),traceback=traceback.format_exc());persist();raise
    finally:signal.signal(signal.SIGINT,previous)
    require(read(ROOT/'lock')['pid']==os.getpid(),'恢复锁所有者变化');(ROOT/'lock').unlink()

if __name__=='__main__':main()
