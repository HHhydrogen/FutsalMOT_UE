"""独立核R资格mask的原始/有效监督预算、记录链及378完整检查点；不重训或重审旧运行。"""
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
from datetime import datetime,timezone

RESEARCH=Path('D:/projects/FutsalMOT_Research');EXPERIMENT=RESEARCH/'pose/r_candidate_eligibility_a01'
FOLDS=('game4','game6','game9');SEEDS=(20261024,20261025,20261026);REGIMES=('R','RS')
STATUS='complete18_R_candidate_eligibility_actual_budget_effective_supervision_full_records_and_exit_verified'
OBJECTIVE='R_original_known_BCE_pre_probability_candidate_eligibility_mask_S_original_BCE_alpha_1_over_3'
EXTENSION='R_candidate_scoring_eligibility_record_extension_v1'
RUN_SCHEMA='R_candidate_eligibility_full_recorded_training_run_v1'
TRAINING_STATUS='complete18_R_candidate_eligibility_training_wait_independent_audit_tracking'
EFFECTIVE=('R_effective_known_pairs','R_effective_positive_pairs','R_effective_negative_pairs','R_effective_unknown_pairs','R_scoring_eligible_unknown_pairs','R_masked_out_known_pairs','R_zero_effective_windows','R_effective_nonempty_windows')
SOURCE_KEYS=('source_job_id','candidate_frame_number','source_stage','source_row_index','source_track_id','teacher_model_id','teacher_regime','teacher_seed','fold','sequence')

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

def blocked_processes(processes):
    scripts=(r'r_eligibility_train',r'control_r_eligibility_training',r'validate_r_eligibility_numeric',r'set_supervision_train',r'control_r_set_supervision_training',r'validate_r_set_supervision_numeric',
        r'state_aligned_(?:train|training_control)',r'validate_state_aligned_numeric',r'pose_velocity_learning_(?:train|control)',
        r'v10_(?:train|training_control)',r'substitution_C_(?:train|control)',r'substitution_validation_predictions')
    pattern=re.compile(r'(?:^|[\\/\s"\x27])(?:'+r'|'.join(scripts)+r')[.]py(?=$|[\s"\x27])',re.I)
    return [p for p in processes if (p.get('Name') or '').lower().startswith('unrealeditor') or pattern.search(p.get('CommandLine') or '')]

def process_snapshot():
    command="Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|powershell|pwsh|UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    response=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,encoding='utf-8',check=True)
    values=json.loads(response.stdout) if response.stdout.strip() else [];return [values] if isinstance(values,dict) else values


def run_producers(processes,run):
    needle=str(run).replace('\\','/').lower()
    pattern=re.compile(r'(?:^|[\\/\s"\x27])r_eligibility_train[.]py(?=$|[\s"\x27])',re.I)
    return [p for p in processes if pattern.search(p.get('CommandLine') or '')
        and needle in (p.get('CommandLine') or '').replace('\\','/').lower()]

def validate_prefetch(receipt,*,producer_processes_absent):
    """原预取器不承诺调用cache.close，不能把缺失/false改成true。"""
    p=receipt['prefetch'];require(producer_processes_absent is True and p.get('closed') is True and p.get('worker_alive') is False
        and type(p.get('loaded')) is int and p['loaded']==1000 and type(p.get('yielded')) is int and p['yielded']==1000
        and type(receipt['cache_peak_bytes']) is int and 0<=receipt['cache_peak_bytes']<=268435456,'实际预取join/完整消费/进程退出或缓存边界不足')
    cache=receipt.get('cache',{});flag=cache.get('closed') if isinstance(cache,dict) else None
    return dict(cache_explicit_close_called=flag is True,source_cache_closed_flag=flag,
        closure_evidence='producer_joined_and_run_process_exited',prefetch_closed=True,worker_alive=False,loaded=1000,yielded=1000)

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
            and group['amsgrad'] is False and len(group['params']) == len(set(group['params'])) == len(params), '实际AdamW配置或参数数量改变')
    if step == 0:
        require(not opt['state'] and all(torch.equal(payload['model'][k],v) for k,v in template.state_dict().items()), '第0步优化器已有更新或不是原初始化')
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


def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()


def ref(path):return dict(path=str(physical(path)),sha256=sha(physical(path)))


def read_ref(reference):
    path=physical(reference['path']);require(path.suffix=='.json' and sha(path)==reference['sha256'],'已签小JSON来源不符');return read(path)


def mask_counts(labels,mask):
    require(len(labels)==len(mask) and all(x is None or type(x) is int and x in (0,1) for x in labels) and all(type(x) is bool for x in mask),'原标签或评分资格必须完整且不改unknown')
    result={}
    groups={'candidate':list(range(len(labels))),'known':[i for i,x in enumerate(labels) if x is not None],
        'positive':[i for i,x in enumerate(labels) if x==1],'negative':[i for i,x in enumerate(labels) if x==0],'unknown':[i for i,x in enumerate(labels) if x is None]}
    for name,indices in groups.items():
        raw=len(indices);kept=sum(mask[i] for i in indices);result.update({p+'_'+name+'_pairs':n for p,n in (('raw',raw),('kept',kept),('excluded',raw-kept))})
    result.update(raw_known_empty=int(result['raw_known_pairs']==0),effective_known_empty=int(result['kept_known_pairs']==0));return result


def independent_binding(window,sidecar):
    require(sidecar['schema']=='R_candidate_eligibility_sidecar_v1' and sidecar['eligibility_rule']=='original_pre_probability_stage_active_AND_enabled'
        and sidecar['eligibility_stage']=='pre_probability' and sidecar['labels_used_to_choose_mask'] is False,'只能原pre-probability资格mask，不由标签选mask')
    metadata=window['aligned_bank_metadata'];uids=[c['prediction']['uid'] for c in window['candidates']];history=[h['uid'] for h in window['history']]
    require(window['window_uid']==metadata['window_uid']==sidecar['window_uid'] and metadata['history_UIDs']==history==sidecar['history_UIDs']
        and metadata['candidate_UIDs']==uids==sidecar['candidate_UIDs'] and all(metadata[k]==sidecar[k] for k in SOURCE_KEYS),'侧表与原窗口UID/历史/teacher坐标不同')
    require(len(uids)==len(set(uids)) and len(history)==len(set(history))==3 and sidecar['source_stage']=='high_score'
        and sidecar['teacher_regime']=='R' and sidecar['teacher_seed']==20261024,'原可靠三历史/首seedR teacher不同')
    active=sidecar['active'];enabled=sidecar['enabled'];require(type(active) is bool and isinstance(enabled,list) and len(enabled)==len(uids)
        and all(type(x) is bool for x in enabled) and (active or not any(enabled)),'资格未知或inactive enabled不一致')
    mask=[active and x for x in enabled]
    if 'scoring_eligible' in sidecar:require(sidecar['scoring_eligible']==mask and all(type(x) is bool for x in sidecar['scoring_eligible']),'侧表评分资格不一致')
    labels=[c['label'] for c in window['candidates']];require(labels==metadata['pair_labels'],'标签/known原序不得改')
    accounting=mask_counts(labels,mask);indices=[i for i,x in enumerate(labels) if x is not None];require(indices,'原pool每窗须有known，空的是有效集合而非补采')
    body=dict(schema='R_candidate_eligibility_bound_window_v1',method_schema='R_candidate_eligibility_masked_BCE_method_v1',eligibility_rule='original_pre_probability_stage_active_AND_enabled',
        window_uid=window['window_uid'],history_UIDs=history,candidate_UIDs=uids,all_labels=labels,all_scoring_eligible=mask,known_indices=indices,
        known_candidate_UIDs=[uids[i] for i in indices],known_labels=[labels[i] for i in indices],known_scoring_eligible=[mask[i] for i in indices],
        source={k:sidecar[k] for k in SOURCE_KEYS},sidecar_sha256=digest(sidecar),accounting=accounting,labels_changed=False,original_forward_known_order_preserved=True)
    return dict(body,binding_sha256=digest(body))


def domain_accounting(bindings,exposures):
    require(len(exposures)==3,'固定每步3原R窗');windows=[];totals=Counter();effective=Counter({k:0 for k in EFFECTIVE})
    for source in exposures:
        b=bindings[source['window_uid']];counts=b['accounting'];require(source['candidate_pairs']==counts['raw_candidate_pairs'] and source['labelled_pairs']==counts['raw_known_pairs'],'原每窗all/known分母不同')
        item=dict(window_uid=b['window_uid'],binding_sha256=b['binding_sha256'],sidecar_sha256=b['sidecar_sha256'],source=b['source'],known_scoring_eligible=b['known_scoring_eligible'],
            known_candidate_UIDs=b['known_candidate_UIDs'],known_labels=b['known_labels'],**counts);windows.append(item);totals.update(counts)
        effective.update(dict(R_effective_known_pairs=counts['kept_known_pairs'],R_effective_positive_pairs=counts['kept_positive_pairs'],R_effective_negative_pairs=counts['kept_negative_pairs'],
            R_scoring_eligible_unknown_pairs=counts['kept_unknown_pairs'],R_masked_out_known_pairs=counts['excluded_known_pairs'],R_zero_effective_windows=counts['effective_known_empty'],R_effective_nonempty_windows=int(counts['kept_known_pairs']>0)))
    totals.update(R_scoring_eligible_unknown_pairs=totals['kept_unknown_pairs'],R_effective_unknown_pairs=0)
    accounting=dict(schema='R_candidate_eligibility_step_domain_accounting_v1',windows=windows,totals=dict(totals),real_window_count=3,domain_forward_calls=1,
        forwarded_known_pairs=totals['raw_known_pairs'],original_known_order_preserved=True,original_labels_unchanged=True,empty_effective_windows_contribute_graph_zero=True,
        window_resampling=False,unknown_features_forwarded=False,unknown_labels_used_for_loss=False,known_mask_applied_after_unreduced_BCE=True,numeric_dtype='float32')
    return accounting,dict(effective)


def count_run(logs,table,regime,bindings):
    require(regime in REGIMES and len(logs)==1000 and len(table['real'])==3000 and len(table['synthetic'])==1000,'实际1000步/原R/S曝光表不完整')
    total=Counter();chain='0'*64
    for i,saved in enumerate(logs):
        row=dict(saved);signed=row.pop('chain_sha256');chain=hashlib.sha256((chain+canonical(row)).encode()).hexdigest();rr=table['real'][i*3:i*3+3];ss=table['synthetic'][i:i+1] if regime=='RS' else []
        require(signed==chain and type(row['actual_update']) is int and row['actual_update']==i+1 and type(row['update_index']) is int and row['update_index']==i
            and canonical(row['real'])==canonical(rr) and canonical(row['synthetic'])==canonical(ss),'新有效字段必须进入原连续链，且UID/epoch原序不变')
        require(all(isinstance(x['window_uid'],str) and type(x['epoch']) is int and x['epoch']>=0 for x in rr+ss),'原UID/epoch无效')
        raw=dict(R_windows=3,S_windows=len(ss),R_pairs=sum(x['candidate_pairs'] for x in rr),R_known_pairs=sum(x['labelled_pairs'] for x in rr),
            S_pairs=sum(x['candidate_pairs'] for x in ss),S_known_pairs=sum(x['labelled_pairs'] for x in ss))
        accounting,effective=domain_accounting(bindings,rr)
        require(canonical(row['R_mask_accounting'])==canonical(accounting) and row['R_mask_accounting_sha256']==digest(accounting),'逐窗knownUID/labels/mask/侧表双SHA/accounting不同')
        require(all(type(row[k]) is int and row[k]==v for k,v in dict(raw,**effective).items()),'原始或有效监督计数被改写')
        require(all(type(row[k]) in (int,float) and math.isfinite(row[k]) and row[k]>=0 for k in ('loss','real_loss','grad_l2','step_wall_seconds'))
            and row['learning_rates']==[.001] and row['gradients_clipped'] is False,'loss/LR/梯度/耗时或裁剪改变')
        if ss:require(type(row['synthetic_loss']) in (int,float) and math.isfinite(row['synthetic_loss']) and row['synthetic_loss']>=0
            and abs(row['loss']-row['real_loss']-row['synthetic_loss']/3)<=1e-6*(1+row['loss']),'RS仍须原S BCE系数1/3')
        else:require(row['synthetic_loss'] is None and row['loss']==row['real_loss'],'纯R不得隐含S')
        if effective['R_effective_known_pairs']==0:
            require(row['real_loss']==0.,'全空有效R步须真实graph-zero')
            if not ss:require(row['grad_l2']==0.,'纯R全空步不得产生非零梯度')
        total.update(raw);total.update(effective)
    return dict(total),chain


def load_runtime(config):
    config=physical(config);cfg=read(config);bundle=physical(cfg['bundle']);require(bundle.parent==RESEARCH/'code','必须独立最小执行bundle')
    manifest=physical(cfg['bundle_manifest']['path']);require(sha(manifest)==cfg['bundle_manifest']['sha256'],'执行manifest SHA变化')
    files=read(manifest)['files'];require(digest(files)==bundle.name,'执行bundle内容地址不符')
    for f in files:require(sha(physical(bundle/f['path']))==f['sha256'],'执行闭包源码变化')
    sys.path.insert(0,str(bundle/'tools/research_ops'))
    spec=importlib.util.spec_from_file_location('independent_eligibility_training_runtime',bundle/'tools/research_ops/r_eligibility_training_runtime.py');rt=importlib.util.module_from_spec(spec);spec.loader.exec_module(rt)
    rt.validate_protocol(config);return cfg,rt


def independent_prepare(config,rt,fold,seed,regime):
    cfg,original=rt.load_source_runtime(config);ctx=original.prepare(cfg['source_training_protocol']['path'],fold,seed,regime)
    manifest=read(rt.checked(cfg['mask_inputs'][fold]));root=read(rt.checked(cfg['selected_R_bank_root']))
    require(manifest['schema']=='R_candidate_eligibility_fold_inputs_v1' and manifest['status']=='complete1000_original_R_windows_pre_probability_masks_bound'
        and manifest['fold']==fold and rt.checked(manifest['original_pool'])==rt.checked(root['folds'][fold]['pool']),'原pool/独立mask输入绑定不同')
    sidecars=rt.rows(rt.checked(manifest['sidecars'])) if hasattr(rt,'rows') else [json.loads(x) for x in rt.checked(manifest['sidecars']).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
    require(len(sidecars)==len(ctx['pools']['real'])==1000 and len({s['window_uid'] for s in sidecars})==1000,'每fold1000唯一侧表不完整')
    side_index={s['window_uid']:s for s in sidecars};require(set(side_index)==set(ctx['pools']['real']),'侧表不能少窗或改采样')
    bindings={uid:independent_binding(window,side_index[uid]) for uid,window in ctx['pools']['real'].items()}
    require(any(b['accounting']['kept_known_pairs']>0 for b in bindings.values()),'整fold有效监督为空，不能训练')
    if manifest.get('bindings') is not None:
        supplied=[json.loads(x) for x in rt.checked(manifest['bindings']).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
        require(len(supplied)==1000 and len({b['window_uid'] for b in supplied})==1000 and canonical({b['window_uid']:b for b in supplied})==canonical(bindings),'已验mask绑定与独立重建逐值不同')
    ctx.update(eligibility_cfg=cfg,eligibility_protocol_sha256=sha(config),eligibility_oldrt=original,eligibility_bindings=bindings,eligibility_mask_manifest=manifest)
    return ctx


def expected_extra(ctx):
    cfg=ctx['eligibility_cfg'];bundle=physical(cfg['bundle']);value=dict(ctx['eligibility_oldrt'].extra(ctx))
    value.update(schema='r_candidate_eligibility_strongmotion_method_state_v1',training_objective=OBJECTIVE,
        R_loss='original_unreduced_known_BCE_mask_then_window_mean_then_fixed_mean3R',S_loss='unchanged_original_known_pair_BCE_alpha_1_over_3',full_original_known_forward_preserved=True,
        empty_effective_window='sum_of_part_times_zero_graph_no_resampling_no_skipped_updates',eligibility_mask_input=cfg['mask_inputs'][ctx['fold']],selected_R_bank_root=cfg['selected_R_bank_root'],
        original_training_protocol=cfg['source_training_protocol'],record_extension_schema=EXTENSION,R_objective_code_sha256=sha(bundle/'tools/research_ops/r_candidate_eligibility_method.py'),
        recorded_loop_sha256=sha(bundle/'tools/research_ops/r_eligibility_recorded_loop.py'),matched_control_reuse_status='conditional_on_fresh_CPU_CUDA_numeric_admission_not_static_claim')
    return value


def expected_binding(ctx,model,config):
    cfg=ctx['eligibility_cfg'];value=dict(ctx['eligibility_oldrt'].spec(ctx,model,ctx['seed'],ctx['regime'],diagnostic=False)['binding']);method=expected_extra(ctx)
    value.update(protocol_sha256=sha(config),source_training_protocol_sha256=cfg['source_training_protocol']['sha256'],R_objective=OBJECTIVE,
        R_objective_code_sha256=method['R_objective_code_sha256'],recorded_loop_sha256=method['recorded_loop_sha256'],record_extension_schema=EXTENSION,
        mask_input_sha256=cfg['mask_inputs'][ctx['fold']]['sha256'],method_state_sha256=digest(method));return value


def validate_inherited_gate(old,*,run,protocol,source_refs,points,unit,totals,method_sha):
    require(old['schema']=='independent_R_candidate_eligibility_first_run_audit_v1'
        and old['status']=='complete_first_R_candidate_eligibility1000_full21_checkpoints_independently_verified'
        and physical(old['run'])==physical(run) and old['protocol']['sha256']==protocol['sha256'] and physical(old['protocol']['path'])==physical(protocol['path'])
        and old['source_refs']==source_refs and old['checkpoint_points']==points and old['unit']==unit and old['counts']==totals
        and old['full_checkpoints_read']==21 and old['inherited_checkpoint_readbacks']==0 and old['complete_checkpoint_coverage']==21
        and old['method_state_sha256']==method_sha and old['new_optimizer_updates']==0 and old['test_read'] is False,
        '首run只能继承同来源/全部SHA/21已读回的真实独立gate')


def audit_run(config,run,all_checkpoints=True,inherited_checkpoint_audit=None):
    """首1000门禁也可调用；只读本run，不要求空闲等待中的主controller退出。"""
    import torch
    import numpy as np
    require(all_checkpoints is True,'独立门禁必须读0/每50/1000全21，不能缩减成末权重')
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='-1' and not torch.cuda.is_initialized(),'独立审计仅CPU，不初始化CUDA')
    torch.set_num_threads(1);cfg,rt=load_runtime(config);run=physical(run);require(EXPERIMENT in run.parents,'只核本轮新run')
    require(not run_producers(process_snapshot(),run),'本run真实训练进程尚未退出，不能仅据文件称闭合')
    receipt=read(run/'run_receipt.json');binding=receipt['binding'];unit={k:binding[k] for k in ('fold','seed','regime')}
    require(unit in cfg['training_matrix'] and receipt['schema']==RUN_SCHEMA and receipt['status']=='complete' and receipt['completed_updates']==1000
        and receipt['formal'] is True and receipt['test_read'] is False and receipt['optimizer_replay']==0 and receipt['amp'] is False and receipt['epoch_augmentation'] is False
        and receipt['actual_dtype']=='float32' and receipt['trainable_parameters']==14593 and binding['record_extension_schema']==EXTENSION
        and receipt['diagnostic_variant'] is None and receipt['numeric_only_virtual_mask_overrides']==[] and receipt['synthetic_stress_initial_step'] is None,'独立masked-BCE完整run身份/预算不同')
    ctx=independent_prepare(config,rt,**unit);table=ctx['table'];logs=[json.loads(x) for x in (run/'steps.jsonl').read_text(encoding='utf-8-sig').splitlines() if x.strip()]
    totals,chain=count_run(logs,table,unit['regime'],ctx['eligibility_bindings']);complete=read(run/'training_complete.json');last=read(run/'last_checkpoint.json');manifest=read(run/'run_manifest.json');tx=read(run/'update_transaction.json')
    require(complete['schema']=='full_training_process_complete_v1' and complete['status']=='complete' and complete['actual_updates']==1000 and complete['totals']==totals
        and complete['exposure_chain']==last['exposure_chain']==chain and complete['steps_sha256']==sha(run/'steps.jsonl') and complete['events_sha256']==sha(run/'events.jsonl')
        and complete['manifest_sha256']==sha(run/'run_manifest.json') and complete['selection']=='step1000_last_no_best' and receipt['full_training_record']==sha(run/'training_complete.json')
        and manifest['binding']==binding and manifest['schema']=='full_training_record_spec_v1' and manifest['test116187_sealed'] is True
        and manifest['runtime']['record_extension_schema']==EXTENSION and tx==dict(status='committed',completed_updates=1000,chain_sha256=chain),'原v1容器+独立extension/完整链/末事务不同')
    environment=manifest['runtime'];require(manifest['updates']==1000 and manifest['R_per_update']==3 and manifest['S_per_update']==int(unit['regime']=='RS')
        and manifest['checkpoint_interval']==50 and manifest['images_copied'] is False and environment['device']=='cuda:0' and environment['torch_version']=='2.6.0+cu124'
        and environment['amp'] is False and environment['prefetch']==2,'原正式CUDA/FP32/1000步/记录频率改变')
    require(receipt['real_window_exposures']==3000 and receipt['synthetic_window_exposures']==1000*int(unit['regime']=='RS'),'原R/S曝光不可改写为有效数量')
    closure=validate_prefetch(receipt,producer_processes_absent=True)
    model=ctx['eligibility_oldrt'].new_model(ctx,device='cpu');original_norm=read(rt.checked(ctx['source']['folds'][unit['fold']]['normalizer']))
    require(ctx['normalizer'].state()==original_norm and sum(p.numel() for p in model.parameters())==14593
        and ctx['base'].model_sha(model)==binding['initialization_sha256']==ctx['reference']['binding']['initialization_sha256'],'原init/normalizer/14593参数不同')
    method=expected_extra(ctx);require(method['normalizer']==original_norm and binding==expected_binding(ctx,model,config),'独立方法状态不是原BCE+资格mask')
    rchain=digest([r['window_uid'] for r in table['real']]);schain=digest([s['window_uid'] for s in table['synthetic']] if unit['regime']=='RS' else [])
    require(binding['R_window_UID_chain_sha256']==rchain and binding['S_window_UID_chain_sha256']==schain,'R/S原UID链不同')
    old_table=read(rt.checked(ctx['source']['exposures']['balanced'][unit['fold']][str(unit['seed'])]));require(table['synthetic']==old_table['synthetic'],'原S顺序被改写')
    points=complete['checkpoints'];require(len(points)==21 and [p['completed_updates'] for p in points]==list(range(0,1001,50)) and last==points[-1],'完整21检查点不足')
    source_refs={name:ref(run/name) for name in ('run_receipt.json','training_complete.json','steps.jsonl','run_manifest.json','events.jsonl','last_checkpoint.json','update_transaction.json')}
    if inherited_checkpoint_audit is not None:
        validate_inherited_gate(inherited_checkpoint_audit,run=run,protocol=ref(config),source_refs=source_refs,points=points,unit=unit,totals=totals,method_sha=digest(method))
    newly_loaded=0
    for point in points:
        step=point['completed_updates'];path=run/'checkpoints'/f'step_{step:04d}.pt'
        require(Path(point['path'])==path and sha(path)==point['sha256'] and path.stat().st_size==point['bytes'] and read(path.with_suffix('.json'))==point,'每检查点实物/SHA/sidecar不同')
        if inherited_checkpoint_audit is None:
            payload=torch.load(path,map_location='cpu',weights_only=False)
            audit_payload(payload,step=step,binding=binding,extra=method,chain='0'*64 if step==0 else logs[step-1]['chain_sha256'],template=model,torch=torch,np=np);newly_loaded+=1
    require(not run_producers(process_snapshot(),run) and source_refs=={name:ref(run/name) for name in source_refs},'审计期间本run重现或已完成来源变化')
    return dict(unit=unit,updates=1000,R_windows=3000,S_windows=1000*int(unit['regime']=='RS'),counts=totals,full_checkpoints_read=newly_loaded,
        inherited_checkpoint_readbacks=21 if inherited_checkpoint_audit is not None else 0,complete_checkpoint_coverage=21,checkpoint_points=points,source_refs=source_refs,run=str(run),
        exposure_chain_sha256=chain,
        R_exposure_table_sha256=digest(table['real']),S_exposure_table_sha256=digest(table['synthetic'] if unit['regime']=='RS' else []),initialization_sha256=binding['initialization_sha256'],
        original_initialization_equal=True,original_normalizer_equal=True,original_S_order_equal=True,prefetch_closure=closure,method_state_sha256=digest(method),mask_input=cfg['mask_inputs'][unit['fold']],
        run_process_absent=True,new_optimizer_updates=0,model_prediction=False,test_read=False)


def diagnostic_budget(admission,protocol_sha):
    require(admission['schema']=='R_candidate_eligibility_numeric_admission_v1' and admission['status']=='complete_R_candidate_eligibility_CPU_CUDA_full_record_numeric_admission'
        and admission['protocol_sha256']==protocol_sha and admission['formal_optimizer_updates']==0 and admission['actual_diagnostic_optimizer_updates']==20
        and admission['manual_optimizer_updates']==10 and admission['recorded_optimizer_updates']==10 and admission['diagnostic_R_windows']==60 and admission['diagnostic_S_windows']==8
        and admission['all_groups_equal'] is True and admission['actual_CPU_and_CUDA_numeric_verified'] is True and admission['full_record_contract_verified'] is True
        and admission['test_read'] is False,'20独立诊断更新/60R8S不得混同正式18000')
    groups=admission['groups'];expected={(v,d,r) for v in ('alltrue_original_BCE','actual_mask') for d in ('cpu','cuda:0') for r in REGIMES}|{('empty_stress',d,'R') for d in ('cpu','cuda:0')}
    require(len(groups)==10 and {(g['variant'],g['device'],g['regime']) for g in groups}==expected,'全部10组准入缺失/重复')
    for g in groups:require(g['manual_updates']==g['recorded_updates']==1 and g['R_windows']==6 and g['S_windows']==2*int(g['regime']=='RS')
        and [c['completed_updates'] for c in g['checkpoints']]==[0,1] and all(c['model_equal'] is True and c['optimizer_equal'] is True and c['all_RNG_equal'] is True for c in g['checkpoints'])
        and g['per_parameter_gradients_exact'] is True and g['all_RNG_exact'] is True and g['loss_model_AdamW_exact'] is True,'每组准入完整模型/梯度/AdamW/RNG证据不足')
    return dict(diagnostic_updates_separate=20,diagnostic_R_separate=60,diagnostic_S_separate=8,manual_diagnostic_updates=10,recorded_diagnostic_updates=10)


def state_entries(state,cfg):
    require(cfg['training_matrix']==matrix() and state['schema']=='R_candidate_eligibility18_training_control_v1' and state['status']==TRAINING_STATUS
        and state['active'] is None and state['formal_optimizer_updates']==18000 and state['unverified_completed_runs']==[],'实际完整18训练状态/事务不足')
    entries=state['completed_train'];require(len(entries)==18 and [{k:e[k] for k in ('fold','seed','regime')} for e in entries]==matrix()
        and len({str(physical(e['path'])) for e in entries})==18,'18单元/原独立run路径不能重复或缺失')
    exits=state['observed_child_exits'];require(len(exits)==18 and [x['job'] for x in exits]==matrix()
        and all(x['exit_code']==0 and x['reported_completed_updates']==1000 and x['receipt_sha256']==e['receipt_sha256'] for x,e in zip(exits,entries)),'实际18训练子进程退出/收据不足')
    return entries


def write_new(path,value):
    path=physical(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:stream.write(canonical(value)+'\n');stream.flush();os.fsync(stream.fileno())


def first_run(config,run,output):
    output=physical(output);require(EXPERIMENT in output.parents and not output.exists() and not output.with_suffix('.intent.json').exists() and not output.with_suffix('.failed.json').exists(),'独立首run审计拒绝覆盖')
    write_new(output.with_suffix('.intent.json'),dict(status='started_first_run_independent_CPU_audit',protocol=ref(config),run=str(physical(run)),new_optimizer_updates=0))
    try:
        value=audit_run(config,run,all_checkpoints=True)
        result=dict(value,schema='independent_R_candidate_eligibility_first_run_audit_v1',status='complete_first_R_candidate_eligibility1000_full21_checkpoints_independently_verified',
            protocol=ref(config),auditor=ref(__file__),verified_utc=datetime.now(timezone.utc).isoformat())
        write_new(output,result);return result
    except BaseException as error:
        write_new(output.with_suffix('.failed.json'),dict(status='failed_first_run_audit_preserved_no_replay',error=repr(error),traceback=traceback.format_exc(),new_optimizer_updates=0));raise


def execute(config,control,output):
    config,control,output=physical(config),physical(control),physical(output);cfg,_=load_runtime(config)
    require(EXPERIMENT in control.parents and EXPERIMENT in output.parents and not output.exists() and not output.with_suffix('.intent.json').exists() and not output.with_suffix('.failed.json').exists(),'独立全18审计范围或已有partial不同')
    state_path=control/'driver_state.json';state_ref=ref(state_path);state=read(state_path);entries=state_entries(state,cfg)
    require(state['protocol_sha256']==sha(config) and not blocked_processes(process_snapshot()),'全18完成但真实controller/train/launcher或UE尚未退出')
    gate_ref=state['first_run_gate'];gate=read_ref(gate_ref);require(Path(gate['run'])==physical(entries[0]['path']),'first_run_gate不是第一个正式1000run')
    admission_root=read(cfg['learning_admission_root_path']);require(admission_root['status']=='complete_R_candidate_eligibility_training_numeric_full_record_admission'
        and admission_root['approved_by']=='root' and admission_root['protocol']['sha256']==sha(config) and physical(admission_root['protocol']['path'])==config
        and admission_root['matched_control_reuse_verified'] is True and admission_root['actual_CPU_and_CUDA_numeric_verified'] is True and admission_root['full_record_contract_verified'] is True
        and admission_root['formal_optimizer_updates']==0 and admission_root['test_read'] is False,'实际训练准入根未闭合')
    inputs=read_ref(admission_root['input_validation']);require(inputs['status']=='complete3000_R_candidate_eligibility_inputs_sources_masks_bindings_and_exposures_independently_verified'
        and inputs['windows']==3000 and inputs['R_window_exposures_shared_once']==27000 and inputs['original_pool_order_labels_UIDs_and_known_projection_exact'] is True
        and inputs['pre_probability_mask_not_chosen_by_labels'] is True and inputs['original_R_S_order_references_unchanged'] is True and inputs['GT_coordinates_read'] is False and inputs['test_read'] is False,'原输入独立核验来源不足')
    # numeric_validation为唯一20更新receipt引用；只读其已验结果，不重跑数值诊断。
    numeric_ref=admission_root['numeric_validation'];numeric=read_ref(numeric_ref);diagnostics=diagnostic_budget(numeric,sha(config))
    write_new(output.with_suffix('.intent.json'),dict(status='started_readonly18_eligibility_budget_audit',protocol=ref(config),control_state=state_ref,first_run_gate=gate_ref,new_optimizer_updates=0,test_read=False))
    try:
        totals=Counter();items=[];paired={};new_reads=0;inherited_reads=0
        for i,entry in enumerate(entries):
            run=physical(entry['path']);require(run==control/'runs'/entry['fold']/str(entry['seed'])/entry['regime']/'training'
                and sha(run/'run_receipt.json')==entry['receipt_sha256'] and sha(run/'training_complete.json')==entry['complete_sha256'],'实际新run/收据SHA不同')
            audit=audit_run(config,run,all_checkpoints=True,inherited_checkpoint_audit=gate if i==0 else None)
            totals.update(audit['counts']);totals['updates']+=1000;new_reads+=audit['full_checkpoints_read'];inherited_reads+=audit['inherited_checkpoint_readbacks'];items.append(audit)
            unit=(entry['fold'],entry['seed']);signature=(audit['initialization_sha256'],audit['R_exposure_table_sha256'],audit['mask_input']['sha256'],audit['counts']['R_effective_known_pairs'],audit['counts']['R_zero_effective_windows'])
            require(unit not in paired or paired[unit]==signature,'九R/RS组原init/R UIDepoch/mask/有效监督顺序不一致');paired[unit]=signature
        expected=dict(updates=18000,R_windows=54000,S_windows=9000,R_pairs=764370,R_known_pairs=634320,S_pairs=46287,S_known_pairs=25191,
            R_effective_known_pairs=110754,R_effective_positive_pairs=19656,R_effective_negative_pairs=91098,R_effective_unknown_pairs=0,
            R_zero_effective_windows=17874,R_effective_nonempty_windows=36126,R_masked_out_known_pairs=634320-110754)
        require(all(totals[k]==v for k,v in expected.items()) and len(paired)==9 and new_reads==357 and inherited_reads==21,'实际原始/有效预算/357新读+21继承/九配对不足')
        require(not blocked_processes(process_snapshot()) and ref(state_path)==state_ref and read_ref(gate_ref)==gate,'审计期间生产者重新出现或冻结终态/首gate改变')
        result=dict(schema='independent_R_candidate_eligibility18_budget_audit_v1',status=STATUS,protocol=ref(config),control_state=state_ref,auditor=ref(__file__),
            actual_totals=dict(totals),runs=items,numeric_admission=numeric_ref,first_run_gate=gate_ref,nine_paired_R_RS_exposures_equal=True,training_processes_absent=True,
            current_checkpoint_deserializations=new_reads,inherited_checkpoint_readbacks=inherited_reads,complete_checkpoint_coverage=378,complete_checkpoints_read_back=378,
            complete_checkpoints_read_back_semantics='coverage_of21_prior_independent_first_run_and357_current_CPU_deserializations_not378_new_reads',
            original_normalizer_initialization_S_exposure_unchanged=True,unknown_used_for_loss=0,eligible_unknown_tracked_separately=totals['R_scoring_eligible_unknown_pairs'],
            old_experiment_budget_reaudited=False,optimizer_replay=0,new_optimizer_updates=0,model_prediction=False,test_read=False,**diagnostics)
        write_new(output,result);return result
    except BaseException as error:
        write_new(output.with_suffix('.failed.json'),dict(status='failed_independent_eligibility_audit_sources_preserved',error=repr(error),traceback=traceback.format_exc(),new_optimizer_updates=0,test_read=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--control',type=Path);p.add_argument('--run',type=Path);p.add_argument('--first-run-only',action='store_true');p.add_argument('--execute',action='store_true');a=p.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES']='-1'
    if a.execute:
        require(a.run is not None if a.first_run_only else a.control is not None,'first-run需--run，全18需--control')
        value=first_run(a.config,a.run,a.output) if a.first_run_only else execute(a.config,a.control,a.output)
    else:value=dict(status='readonly_R_candidate_eligibility_independent_auditor_candidate_no_execution')
    print(canonical(dict(status=value['status'])))
