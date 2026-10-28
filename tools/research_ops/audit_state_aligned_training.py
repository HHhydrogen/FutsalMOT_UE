"""独立核18臂实际预算、378完整检查点与生产者退出；不训练或预测。"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback

RESEARCH=Path('D:/projects/FutsalMOT_Research');EXPERIMENT=RESEARCH/'pose/state_aligned_training_a01'
FOLDS=('game4','game6','game9');SEEDS=(20261024,20261025,20261026);REGIMES=('R','RS')
STATUS='complete18_state_aligned_R_actual_budget_full_records_and_exit_verified'
def require(ok,message):
    if not ok:raise ValueError(message)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()
def physical(path):
    p=Path(os.path.abspath(path));require(RESEARCH in p.parents,'仅实际DResearch来源')
    require(not any(part.lower()=='test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',part.lower()) for part in p.parts),'测试继续封存')
    for part in (p,*p.parents):
        if part.exists() or part.is_symlink():require(not part.is_symlink() and not getattr(part.lstat(),'st_file_attributes',0)&0x400,'拒绝junction/符号链接')
    return p
def matrix():return [dict(fold=f,seed=s,regime=r) for f in FOLDS for s in SEEDS for r in REGIMES]
def validate_state(state,cfg):
    require(cfg['training_matrix']==matrix(),'事前18臂矩阵不同')
    require(state['status']=='complete18_state_aligned_training_wait_independent_audit_tracking' and state['active'] is None
        and [{k:v[k] for k in ('fold','seed','regime')} for v in state['completed_train']]==matrix(),'实际完整18臂或退出终态不足')
    paths=[v['path'] for v in state['completed_train']];require(len(set(paths))==len(paths)==18,'不能复用run目录伪造十八臂')
def blocked_processes(processes):
    scripts=(r'state_aligned_(?:train|training_control)',r'validate_state_aligned_numeric',r'pose_velocity_learning_(?:train|control)',
        r'v10_(?:train|training_control)',r'substitution_C_(?:train|control)',r'substitution_validation_predictions')
    pattern=re.compile(r'(?:^|[\\/\s"\x27])(?:'+r'|'.join(scripts)+r')[.]py(?=$|[\s"\x27])',re.I)
    return [p for p in processes if (p.get('Name') or '').lower().startswith('unrealeditor') or pattern.search(p.get('CommandLine') or '')]
def process_snapshot():
    command="Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    response=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,encoding='utf-8',check=True)
    values=json.loads(response.stdout) if response.stdout.strip() else [];return [values] if isinstance(values,dict) else values
def validate_prefetch(receipt,*,producer_processes_absent):
    """原预取器不承诺调用cache.close，不能把缺失/false改成true。"""
    p=receipt['prefetch'];require(producer_processes_absent is True and p.get('closed') is True and p.get('worker_alive') is False
        and type(p.get('loaded')) is int and p['loaded']==1000 and type(p.get('yielded')) is int and p['yielded']==1000
        and type(receipt['cache_peak_bytes']) is int and 0<=receipt['cache_peak_bytes']<=268435456,'实际预取join/完整消费/进程退出或缓存边界不足')
    cache=receipt.get('cache',{});flag=cache.get('closed') if isinstance(cache,dict) else None
    return dict(cache_explicit_close_called=flag is True,source_cache_closed_flag=flag,
        closure_evidence='producer_joined_and_run_process_exited',prefetch_closed=True,worker_alive=False,loaded=1000,yielded=1000)
def load_runtime(config):
    cfg=read(physical(config));bundle=physical(cfg['bundle']);require(bundle.parent==RESEARCH/'code','只加载独立冻结执行bundle')
    manifest=physical(cfg['bundle_manifest']['path']);require(sha(manifest)==cfg['bundle_manifest']['sha256'],'bundle索引不同')
    for item in read(manifest)['files']:require(sha(physical(bundle/item['path']))==item['sha256'],'训练执行闭包变化')
    sys.path.insert(0,str(bundle/'tools/research_ops'))
    spec=importlib.util.spec_from_file_location('independent_state_aligned_runtime',bundle/'tools/research_ops/state_aligned_training_runtime.py')
    rt=importlib.util.module_from_spec(spec);spec.loader.exec_module(rt);rt.validate_protocol(config);return cfg,rt


def count_run(logs, table, group):
    require(group in REGIMES and len(logs) == 1000 and len(table['real']) == 3000
            and len(table['synthetic']) == 1000, '正式预算/组别与原曝光表不符')
    totals = Counter(); chain = '0'*64
    for index, entry in enumerate(logs):
        row = dict(entry); recorded_chain = row.pop('chain_sha256')
        chain = hashlib.sha256((chain+canonical(row)).encode()).hexdigest()
        rr = table['real'][3*index:3*index+3]
        ss = [] if group == 'R' else table['synthetic'][index:index+1]
        require(recorded_chain == chain and type(row['actual_update']) is int
                and row['actual_update'] == index+1 and row['update_index'] == index
                and row['real'] == rr and row['synthetic'] == ss,
                '实际UID/epoch/顺序或连续曝光链不一致')
        counts = dict(R_windows=3, S_windows=len(ss),
            R_pairs=sum(r['candidate_pairs'] for r in rr),
            R_known_pairs=sum(r['labelled_pairs'] for r in rr),
            S_pairs=sum(s['candidate_pairs'] for s in ss),
            S_known_pairs=sum(s['labelled_pairs'] for s in ss))
        require(all(type(row[k]) is int and row[k] == v for k, v in counts.items()),
                '实际全部/已知pair或R/S窗口数与来源UID不符')
        require(all(type(row[k]) in (float, int) and math.isfinite(row[k]) and row[k] >= 0
                    for k in ('loss', 'real_loss', 'grad_l2', 'step_wall_seconds'))
                and row['learning_rates'] == [.001] and row['gradients_clipped'] is False,
                '逐步损失/LR/梯度/耗时缺失、非有限或改动裁剪')
        if ss:
            require(type(row['synthetic_loss']) in (float, int)
                    and math.isfinite(row['synthetic_loss']) and row['synthetic_loss'] >= 0
                    and abs(row['loss']-row['real_loss']-row['synthetic_loss']/3)
                        <= 1e-6*(1+row['loss']),
                    'RS分域loss未记录或登记权重改变')
        else:
            require(row['synthetic_loss'] is None and row['loss'] == row['real_loss'],
                    '纯R包含隐式S损失')
        totals.update(counts)
    return dict(totals), chain

def audit_payload(payload, *, step, binding, extra, chain, template, torch, np):
    require(payload['schema'] == 'full_training_checkpoint_v1'
            and payload['binding'] == binding and payload['completed_updates'] == step
            and payload['exposure_chain'] == chain and payload['extra'] == extra,
            '检查点实际步数/曝光链/方法身份不符')
    require(payload['model'].keys() == template.state_dict().keys()
            and all(torch.is_tensor(value) and value.dtype == torch.float32
                    and tuple(value.shape) == tuple(template.state_dict()[name].shape)
                    and bool(torch.isfinite(value).all()) for name, value in payload['model'].items()),
            '实际模型非FP32、形状/字段不同或非有限')
    opt = payload['optimizer']; require(len(opt['param_groups']) == 1, '原AdamW参数组变化')
    group = opt['param_groups'][0]; params = list(template.parameters())
    require(group['lr'] == .001 and group['weight_decay'] == .0001
            and tuple(group['betas']) == (.9, .999) and group['eps'] == 1e-8
            and len(group['params']) == len(params), '实际AdamW配置或参数数量改变')
    if step == 0:
        require(not opt['state'], '第0步优化器已有数学更新')
    else:
        require(set(opt['state']) == set(group['params']), '优化器缺实际参数状态')
        for key, parameter in zip(group['params'], params):
            state = opt['state'][key]
            require(torch.is_tensor(state['step']) and state['step'].numel() == 1
                    and float(state['step']) == step
                    and all(torch.is_tensor(state[k]) and state[k].dtype == torch.float32
                        and tuple(state[k].shape) == tuple(parameter.shape)
                        and bool(torch.isfinite(state[k]).all()) for k in ('exp_avg', 'exp_avg_sq')),
                    '实际AdamW步数/动量状态缺失或不符')
    import random
    random.Random().setstate(payload['rng_python'])
    np.random.RandomState().set_state(payload['rng_numpy'])
    cpu = payload['rng_torch_cpu']; cuda = payload['rng_torch_cuda']
    require(torch.is_tensor(cpu) and cpu.dtype == torch.uint8 and cpu.ndim == 1 and cpu.numel() > 0
            and isinstance(cuda, list) and len(cuda) > 0
            and all(torch.is_tensor(x) and x.dtype == torch.uint8 and x.ndim == 1 and x.numel() > 0 for x in cuda),
            '完整TorchCPU/CUDA随机状态缺失')
    torch.Generator(device='cpu').set_state(cpu)

def execute(config,control,output):
    require(all(Path(p).is_absolute() for p in (config,control,output)),'配置/control/输出必须绝对路径')
    config,control,output=Path(config),physical(control),physical(output);cfg,rt=load_runtime(config)
    require(EXPERIMENT in control.parents and EXPERIMENT in output.parents,'新审计目录越界')
    intent,failed=output.with_suffix('.intent.json'),output.with_suffix('.failed.json')
    require(not any(p.exists() for p in (output,intent,failed)),'已有审计/partial，拒绝覆盖或隐式重放')
    state_path=control/'driver_state.json';state_sha=sha(state_path);state=read(state_path);validate_state(state,cfg)
    require(state['protocol_sha256']==sha(config),'控制器不是本冻结协议');require(not blocked_processes(process_snapshot()),'真实训练/controller/launcher或UE尚未退出')
    output.parent.mkdir(parents=True,exist_ok=True);rt.write_new(intent,dict(status='started_readonly18_budget_audit_not_training',protocol_sha256=sha(config),control_state_sha256=state_sha,pid=os.getpid(),new_optimizer_updates=0,test_read=False))
    try:
        import torch
        import numpy as np
        torch.set_num_threads(1);require(not torch.cuda.is_available(),'审计仅CPU，须CUDA_VISIBLE_DEVICES=-1')
        rt.validate_learning_admission(config,cfg)
        first=read(control/'first_run_end_to_end_gate.json')
        require(first['status']=='complete_first_state_aligned1000_full21_checkpoints_verified' and first['actual_updates']==1000
            and first['checkpoints_read']==21 and first['R']==3000 and first['S']==0 and first['optimizer_replay']==0,'首千步实际21检查点门禁缺失')
        totals=Counter();items=[];common={};checkpoints=0
        for entry in state['completed_train']:
            fold,seed,regime=(entry[k] for k in ('fold','seed','regime'));run=physical(entry['path'])
            require(run==control/'runs'/fold/str(seed)/regime/'training','实际run路径与矩阵不同')
            require(sha(run/'run_receipt.json')==entry['receipt_sha256'] and sha(run/'training_complete.json')==entry['complete_sha256'],'完成收据bytes变化')
            ctx=rt.prepare(config,fold,seed,regime);receipt=read(run/'run_receipt.json');binding=receipt['binding']
            require(receipt['schema']=='state_aligned_full_recorded_training_run_v1' and receipt['status']=='complete' and receipt['completed_updates']==1000
                and {k:binding[k] for k in ('fold','seed','regime')}==dict(fold=fold,seed=seed,regime=regime)
                and binding['method']=='motion' and binding['protocol_sha256']==sha(config) and receipt['amp'] is False
                and receipt['actual_dtype']=='float32' and receipt['epoch_augmentation'] is False and receipt['trainable_parameters']==14593
                and receipt['optimizer_replay']==0,'新R来源强motion身份/容量/精度/预算不同')
            table=ctx['table'];logs=rt.rows(run/'steps.jsonl');counts,chain=count_run(logs,table,regime)
            complete=read(run/'training_complete.json');last=read(run/'last_checkpoint.json');transaction=read(run/'update_transaction.json');manifest=read(run/'run_manifest.json')
            require(complete['schema']=='full_training_process_complete_v1' and complete['status']=='complete' and complete['actual_updates']==1000
                and complete['totals']==counts and complete['exposure_chain']==last['exposure_chain']==chain
                and complete['steps_sha256']==sha(run/'steps.jsonl') and complete['manifest_sha256']==sha(run/'run_manifest.json')
                and complete['events_sha256']==sha(run/'events.jsonl') and complete['selection']=='step1000_last_no_best'
                and receipt['full_training_record']==sha(run/'training_complete.json') and manifest['binding']==binding
                and manifest['test116187_sealed'] is True and transaction==dict(status='committed',completed_updates=1000,chain_sha256=chain),'完整过程/曝光链/末事务不足')
            require(receipt['real_window_exposures']==counts['R_windows']==3000 and receipt['synthetic_window_exposures']==counts['S_windows']==1000*int(regime=='RS'),'实际R/S曝光不符')
            closure=validate_prefetch(receipt,producer_processes_absent=True)
            rchain=hashlib.sha256(canonical([r['window_uid'] for r in table['real']]).encode()).hexdigest()
            schain=hashlib.sha256(canonical([r['window_uid'] for r in table['synthetic']] if regime=='RS' else []).encode()).hexdigest()
            require(binding['R_window_UID_chain_sha256']==rchain and binding['S_window_UID_chain_sha256']==schain,'实际R/S UID链改变')
            source=ctx['source'];old_table=read(rt.checked(source['exposures']['balanced'][fold][str(seed)]))
            require(table['synthetic']==old_table['synthetic'],'RS来源必须完整原S顺序，R共享同表但不消费S')
            original_norm=read(rt.checked(source['folds'][fold]['normalizer']));require(ctx['normalizer'].state()==original_norm,'原baseR normalizer被重拟合')
            template=rt.new_model(ctx,device='cpu');base=ctx['base'];reference=ctx['reference']
            require(base.model_sha(template)==binding['initialization_sha256']==reference['binding']['initialization_sha256'],'初始化不等原强motion')
            expected_extra=rt.extra(ctx);require(expected_extra['normalizer']==original_norm and expected_extra['schema']=='state_aligned_strongmotion_method_state_v1'
                and hashlib.sha256(canonical(expected_extra).encode()).hexdigest()==binding['method_state_sha256'],'方法状态不等原标准化/新独立身份')
            points=complete['checkpoints'];require(len(points)==21 and [p['completed_updates'] for p in points]==list(range(0,1001,50)) and last==points[-1],'0/每50/最终21检查点不齐')
            for point in points:
                step=point['completed_updates'];path=run/'checkpoints'/f'step_{step:04d}.pt'
                require(Path(point['path'])==path and read(path.with_suffix('.json'))==point and sha(path)==point['sha256'] and path.stat().st_size==point['bytes'],'检查点/索引物理身份不同')
                payload=torch.load(path,map_location='cpu',weights_only=False)
                audit_payload(payload,step=step,binding=binding,extra=expected_extra,chain='0'*64 if step==0 else logs[step-1]['chain_sha256'],template=template,torch=torch,np=np)
                if step==0:
                    require(all(torch.equal(payload['model'][k],v) for k,v in template.state_dict().items()),'step0不等原模型初始化')
                checkpoints+=1
            signature=(binding['initialization_sha256'],rchain,counts['R_pairs'],counts['R_known_pairs'])
            key=(fold,seed);require(key not in common or common[key]==signature,'同fold/seed R/RS原初始化及新R顺序/allknown pair不同');common[key]=signature
            totals.update(counts);totals['updates']+=1000
            items.append(dict(fold=fold,seed=seed,regime=regime,actual_updates=1000,counts=counts,checkpoints_read_back=21,
                actual_step0_initialization_equal=True,original_normalizer_equal=True,original_balanced_S_order_equal=True,prefetch_closure=closure,
                run_receipt_sha256=entry['receipt_sha256'],last_checkpoint=last))
        require(totals['updates']==18000 and totals['R_windows']==54000 and totals['S_windows']==9000 and checkpoints==378 and len(common)==9,'18臂实际总预算/378检查点/9配对组不足')
        require(not blocked_processes(process_snapshot()) and sha(state_path)==state_sha,'审计期间生产者重新出现或控制器终态变化')
        result=dict(schema='independent_state_aligned18_budget_audit_v1',status=STATUS,protocol=dict(path=str(config),sha256=sha(config)),
            control_state=dict(path=str(state_path),sha256=state_sha),auditor=dict(path=str(Path(__file__).resolve()),sha256=sha(__file__)),
            actual_totals=dict(totals),runs=items,complete_checkpoints_read_back=checkpoints,nine_paired_R_RS_exposures_equal=True,
            training_processes_absent=True,diagnostic_updates_separate=4,diagnostic_R_separate=12,diagnostic_S_separate=2,new_optimizer_updates=0,
            optimizer_replay=0,model_prediction=False,test_read=False,numerical_loss_serialization_check_not_performance_equivalence=True)
        rt.write_new(output,result);return {k:result[k] for k in ('status','actual_totals','complete_checkpoints_read_back','training_processes_absent')}
    except BaseException:
        rt.write_new(failed,dict(status='failed_audit_preserved_sources_unchanged',traceback=traceback.format_exc(),new_optimizer_updates=0,test_read=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','control','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--execute',action='store_true');a=p.parse_args();os.environ['CUDA_VISIBLE_DEVICES']='-1'
    if a.execute:print(canonical(execute(a.config,a.control,a.output)))
    else:
        cfg,_=load_runtime(a.config);state=read(physical(a.control)/'driver_state.json');validate_state(state,cfg)
        require(not blocked_processes(process_snapshot()),'真实生产者未退出');print(canonical(dict(status='readonly18_state_aligned_budget_audit_preflight',new_optimizer_updates=0,test_read=False)))
