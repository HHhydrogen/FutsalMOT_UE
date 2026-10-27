"""独立C十八臂实际预算核对；只读原记录/权重，所有检查点读回，不执行模型预测。"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys

R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/real_substitution_a01'

def require(ok,msg):
    if not ok:raise ValueError(msg)

def count_run(logs,table,extra):
    """分别核对基础/额外真实组每步pair和loss/LR，不把计划数冒充实际数。"""
    totals=Counter()
    require(len(logs)==1000,'实际日志不足1000步')
    for i,row in enumerate(logs):
        base=table['real'][i*3:i*3+3];more=extra['extra_R'][i:i+1]
        require(row['real']==base+more and row['synthetic']==[] and row['R_windows']==4 and row['S_windows']==0,'实际R/S或顺序变化')
        counts=dict(base_R_windows=3,extra_R_windows=1,R_windows=4,S_windows=0,
            base_R_pairs=sum(x['candidate_pairs'] for x in base),extra_R_pairs=sum(x['candidate_pairs'] for x in more),
            base_R_known_pairs=sum(x['labelled_pairs'] for x in base),extra_R_known_pairs=sum(x['labelled_pairs'] for x in more),
            R_pairs=sum(x['candidate_pairs'] for x in base+more),R_known_pairs=sum(x['labelled_pairs'] for x in base+more),S_pairs=0,S_known_pairs=0)
        require(all(row[k]==v for k,v in counts.items()),'实际基础/额外R或known pair与对应UID不一致')
        require(row['learning_rates']==[.001] and row['gradients_clipped'] is False
            and all(math.isfinite(row[k]) and row[k]>=0 for k in ('loss','real_loss','base_real_loss','extra_real_loss','grad_l2','step_wall_seconds'))
            and row['synthetic_loss'] is None and abs(row['loss']-row['base_real_loss']-row['extra_real_loss']/3)<1e-6*(1+row['loss']),
            '实际LR/梯度/分组loss未完整记录')
        totals.update(counts)
    return dict(totals)

def execute(config,control,output):
    config=Path(config);cfg=json.loads(config.read_text(encoding='utf-8-sig'));bundle=Path(cfg['bundle'])
    require(bundle.parent==R/'code','C runtime必须来自D不可变bundle')
    entries=json.loads(Path(cfg['bundle_manifest']['path']).read_text(encoding='utf-8-sig'))['files']
    for e in entries:require(hashlib.sha256((bundle/e['path']).read_bytes()).hexdigest()==e['sha256'],'C源码身份变化')
    sys.path.insert(0,str(bundle/'tools/research_ops'))
    import substitution_C_runtime as rt
    rt.protocol(config);st=rt.storage();control=st.physical_child(control,EXP);output=st.physical_child(output,EXP)
    require(not output.exists(),'审计输出已存在/partial，拒绝覆盖')
    state=rt.read(control/'driver_state.json')
    require(state['status']=='complete18_C_training_wait_independent_audit_tracking' and state['active'] is None
        and len(state['completed_train'])==18 and [{k:x[k] for k in ('fold','seed','method')} for x in state['completed_train']]==cfg['training_matrix'],
        'C十八臂/矩阵终态未齐')
    cmd="Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    snap=subprocess.run(['powershell.exe','-NoProfile','-Command',cmd],capture_output=True,text=True,encoding='utf-8',errors='replace')
    require(snap.returncode==0,'实际C进程身份查询失败')
    active=json.loads(snap.stdout or '[]');active=[active] if isinstance(active,dict) else active
    blocked=[p for p in active if p['Name'].lower().startswith('unrealeditor') or any(w in (p.get('CommandLine') or '') for w in ('substitution_C_control.py','substitution_C_train.py'))]
    require(not blocked,'C生产者/launcher或UE未实际退出，稍后核对：'+str(blocked))
    import torch
    total=Counter();items=[];common={}
    for entry in state['completed_train']:
        run=st.physical_child(entry['path'],control)
        require(rt.sha(run/'run_receipt.json')==entry['receipt_sha256'] and rt.sha(run/'training_complete.json')==entry['complete_sha256'],'控制器成功收据变化')
        _,numeric,model,adapter,binding=rt.complete_model(config,run,all_checkpoints=True)
        f,s,m=(binding[k] for k in ('fold','seed','method'))
        table=rt.read(rt.checked(cfg['folds'][f]['exposures'][str(s)]));extra=rt.read(rt.checked(cfg['extra_exposures'][f][str(s)]))
        logs=rt.rows(run/'steps.jsonl');counts=count_run(logs,table,extra);complete=rt.read(run/'training_complete.json')
        require(counts==complete['totals'],'已测总预算与完整训练收据不同')
        point=rt.checked(complete['checkpoints'][0]);initial=torch.load(point,map_location='cpu',weights_only=False)
        _,base,_=rt.numeric(cfg);model.load_state_dict(initial['model'])
        require(base.model_sha(model)==binding['initialization_sha256'],'实际step0不等于登记初始化')
        signatures=(binding['R_window_UID_chain_sha256'],binding['extra_R_UID_chain_sha256'],counts['base_R_pairs'],counts['extra_R_pairs'],counts['base_R_known_pairs'],counts['extra_R_known_pairs'])
        key=(f,s);require(key not in common or common[key]==signatures,'同fold/seed两模型实际曝光不等')
        common[key]=signatures;total.update(counts);total['updates']+=1000
        items.append(dict(fold=f,seed=s,method=m,actual_updates=1000,checkpoints_read_back=21,counts=counts,
            actual_step0_initialization_equal=True,run_receipt_sha256=entry['receipt_sha256'],last=rt.read(run/'last_checkpoint.json')))
    require(total['updates']==18000 and total['R_windows']==72000 and total['base_R_windows']==54000
        and total['extra_R_windows']==18000 and total['S_windows']==0 and len(common)==9,'C总实际预算不闭合')
    output.parent.mkdir(parents=True,exist_ok=True)
    result=dict(schema='independent_C18_budget_audit_v1',status='complete18_C_actual_budget_full_records_and_exit_verified',
        protocol=dict(path=str(config),sha256=rt.sha(config)),control_state=dict(path=str(control/'driver_state.json'),sha256=rt.sha(control/'driver_state.json')),
        actual_totals=dict(total),runs=items,complete_checkpoints_read_back=378,training_processes_absent=True,
        nine_paired_method_exposure_groups_equal=True,diagnostic_updates_separate=4,diagnostic_R_separate=16,
        optimizer_replay=0,model_prediction=False,test_read=False,performance_comparison_not_yet_complete=True)
    from training_journal import write_new
    write_new(output,result);return {k:result[k] for k in ('status','actual_totals','complete_checkpoints_read_back','training_processes_absent')}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','control','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();print(json.dumps(execute(a.config,a.control,a.output),ensure_ascii=False))
