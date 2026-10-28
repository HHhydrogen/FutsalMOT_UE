"""九计划实际CPU输入/一步数学准入，不冒充CUDA完整记录或正式训练。"""
import argparse
import copy
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import sys
import traceback

sys.path.insert(0,str(Path(__file__).parent))
STATUS='complete9_state_aligned_R_inputs_original_motion_numeric_verified'

def require(ok,message):
    if not ok:raise ValueError(message)

def preflight(config,output,config_sha256=None,*,runtime=None):
    rt=runtime or importlib.import_module('state_aligned_training_runtime')
    if config_sha256 is not None:require(rt.sha(config)==config_sha256,'协议SHA不一致')
    cfg=rt.validate_protocol(config);output=rt.physical(output)
    require(Path(rt.EXPERIMENT) in output.parents and not output.exists(),'独立CPU准入目录已有/越界')
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='-1','CPU准入必须显式禁用CUDA')
    return rt,cfg,output,dict(status='readonly_state_aligned9_inputs_CPU_preflight',protocol_sha256=rt.sha(config),
        planned_CPU_diagnostic_optimizer_updates=4,formal_optimizer_updates=0,GPU_initialized=False,test_read=False)

def manual_domain_loss(model,windows,torch):
    """单域一次前向；保留原逐window均值而非将全部pair等权。"""
    from torch.nn import functional as F
    lengths=[len(w['labels']) for w in windows];require(lengths and all(n>0 for n in lengths),'每窗至少一个known')
    x=torch.cat([w['x'] for w in windows]);y=torch.cat([w['labels'] for w in windows])
    losses=F.binary_cross_entropy_with_logits(model(x).reshape(-1),y,reduction='none')
    return torch.stack([part.mean() for part in losses.split(lengths)]).mean()

def verify(config,output,config_sha256=None):
    rt,cfg,output,flight=preflight(config,output,config_sha256)
    import numpy as np
    import torch
    from validate_state_aligned_numeric import tree_equal
    require(torch.__version__=='2.6.0+cu124' and not torch.cuda.is_available() and not torch.cuda.is_initialized(),'CPU准入不能初始化或使用GPU')
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    output.mkdir(parents=True);rt.write_new(output/'preflight.json',flight)
    rt.write_new(output/'started.json',dict(status='started_CPU_input_contract_not_formal_training',pid=os.getpid(),created_utc=datetime.now(timezone.utc).isoformat()))
    results=[];feature_totals={};CPU_updates=0;numeric=[];first_contexts={}
    equal=lambda a,b:tree_equal(a,b,torch=torch,np=np)
    try:
        for fold in rt.FOLDS:
            for seed in rt.SEEDS:
                r=rt.prepare(config,fold,seed,'R');rs=rt.prepare(config,fold,seed,'RS')
                require(r['table']==rs['table'] and r['normalizer'].state()==rs['normalizer'].state(),'R/RS必须共用完整新R表和原标准化')
                a,b=rt.new_model(r,device='cpu'),rt.new_model(rs,device='cpu')
                require(equal(a.state_dict(),b.state_dict()) and r['base'].model_sha(a)==r['reference']['binding']['initialization_sha256'],
                    '原强motion初始化或组间匹配不同')
                from grf_ue_bridge.learned_association_features_v8 import features
                # 每fold新R原记录不随seed/epoch变化，首次逐窗完整核，其余seed仅核绑定与完整计划。
                if fold not in feature_totals:
                    checked_pairs=0
                    for uid,w in r['pools']['real'].items():
                        known=[c for c in w['candidates'] if c['label'] is not None]
                        actual=r['cache'].get('real',uid)
                        raw=[features(w['history'],c['prediction']) for c in known]
                        expected=[r['normalizer'].transform(x,use_pose=False) for x in raw]
                        require(all(len(x)==194 and all(v==0. for v in x[24:]) for x in expected),'194维/标准化后170Pose列遮蔽不同')
                        require(torch.equal(actual['x'],torch.tensor(expected,dtype=torch.float32))
                            and torch.equal(actual['labels'],torch.tensor([c['label'] for c in known],dtype=torch.float32))
                            and actual['candidate_pairs']==len(w['candidates']) and actual['known_pairs']==len(known)
                            and bool(torch.isfinite(actual['x']).all()),'原特征/known标签mask/全pair数不同')
                        checked_pairs+=len(known)
                    feature_totals[fold]=dict(unique_R_windows=1000,known_pairs_features_checked=checked_pairs,
                        source='all_new_R_known_pairs_original194_features_and_baseR_normalizer_exact',augmentation=False)
                # 原S完整表在prepare_inputs.validate_plan核过；首批再逐值比较原cache路径。
                first_r=rt.batch(r,0);first_rs=rt.batch(rs,0)
                require(equal((first_r['r'],first_r['real']),(first_rs['r'],first_rs['real'])),'首步R特征/真实窗口不同')
                s_entry=first_rs['s'][0];s_window=rs['pools']['synthetic'][s_entry['window_uid']]
                known=[c for c in s_window['candidates'] if c['label'] is not None]
                expected=torch.tensor([rs['normalizer'].transform(features(s_window['history'],c['prediction']),use_pose=False) for c in known],dtype=torch.float32)
                require(torch.equal(first_rs['synthetic'][0]['x'],expected),'S首步必须原无增广motion数值')
                results.append(dict(fold=fold,seed=seed,R_RS_same_R_plan=True,R_RS_same_initialization=True,
                    initialization_sha256=r['base'].model_sha(a),normalizer= r['source']['folds'][fold]['normalizer'],
                    R_UID_chain_sha256=rt.spec(r,a)['binding']['R_window_UID_chain_sha256'],
                    S_UID_chain_sha256=rt.spec(rs,b)['binding']['S_window_UID_chain_sha256'],
                    original_S_order_verified=True,original_motion_augmentation=False))
                if fold==rt.FOLDS[0] and seed==rt.SEEDS[0]:first_contexts={'R':r,'RS':rs}
                else:r['cache'].cache.clear();rs['cache'].cache.clear()
        for regime,ctx in first_contexts.items():
            batch=rt.batch(ctx,0);manual,reference=rt.new_model(ctx,device='cpu'),rt.new_model(ctx,device='cpu')
            opt=torch.optim.AdamW(manual.parameters(),lr=.001,weight_decay=.0001)
            refopt=torch.optim.AdamW(reference.parameters(),lr=.001,weight_decay=.0001)
            before=torch.get_rng_state().clone();opt.zero_grad(set_to_none=True);refopt.zero_grad(set_to_none=True)
            rm=manual_domain_loss(manual,batch['real'],torch)
            sm=manual_domain_loss(manual,batch['synthetic'],torch) if regime=='RS' else None
            expected_loss=rm+sm/3 if sm is not None else rm
            rr=ctx['numeric'].domain_loss(reference,batch['real'])
            sr=ctx['numeric'].domain_loss(reference,batch['synthetic']) if regime=='RS' else None
            actual_loss=rr+sr/3 if sr is not None else rr
            require(float(expected_loss.detach())==float(actual_loss.detach()),'CPU原window均值损失与手写不逐值相同')
            expected_loss.backward();actual_loss.backward()
            require(all(equal(a.grad,b.grad) for a,b in zip(manual.parameters(),reference.parameters())),'CPU梯度不逐值相同')
            opt.step();CPU_updates+=1;refopt.step();CPU_updates+=1
            require(equal(manual.state_dict(),reference.state_dict()) and equal(opt.state_dict(),refopt.state_dict())
                and torch.equal(before,torch.get_rng_state()),'CPU一步模型/AdamW或无随机数学改变')
            numeric.append(dict(regime=regime,model_optimizer_gradient_loss_exact=True,loss=float(actual_loss.detach()),
                diagnostic_CPU_optimizer_updates=2,R_windows=6,S_windows=2 if regime=='RS' else 0,
                full_training_journal_checked=False))
        require(len(results)==9 and CPU_updates==4 and not torch.cuda.is_initialized(),'完整九计划/CPU预算或GPU边界不同')
        value=dict(status=STATUS,protocol_sha256=rt.sha(config),plans=results,all_new_R_features=feature_totals,CPU_numeric=numeric,
            actual_CPU_diagnostic_optimizer_updates=4,CPU_diagnostic_R_windows=12,CPU_diagnostic_S_windows=2,
            formal_optimizer_updates=0,actual_CUDA_updates=0,full_CUDA_recording_admission=False,
            GPUs_initialized=False,normalizer_refit=False,test_read=False,images_read=False)
        rt.write_new(output/'receipt.json',value);return value
    except BaseException:
        rt.write_new(output/'failed.json',dict(status='failed_CPU_contract_preserved_no_replay',traceback=traceback.format_exc(),
            CPU_optimizer_calls_returned=CPU_updates,uncommitted_effects_not_guessed=True,formal_optimizer_updates=0,test_read=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','output'):p.add_argument('--'+key,required=True)
    p.add_argument('--config-sha256');p.add_argument('--execute',action='store_true');a=p.parse_args()
    value=verify(a.config,a.output,a.config_sha256) if a.execute else preflight(a.config,a.output,a.config_sha256)[3]
    print(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False))
