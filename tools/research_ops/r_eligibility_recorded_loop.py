"""R评分资格mask的独立记录扩展；原事务/检查点/四RNG与原数值顺序不变。"""
from copy import deepcopy
import hashlib
import re
import signal
import time
from training_journal import TrainingJournal, canonical, require

EXTENSION_SCHEMA='R_candidate_scoring_eligibility_record_extension_v1'
ACCOUNTING_SCHEMA='R_candidate_eligibility_step_domain_accounting_v1'
EFFECTIVE_FIELDS=('R_effective_known_pairs','R_effective_positive_pairs','R_effective_negative_pairs',
    'R_effective_unknown_pairs','R_scoring_eligible_unknown_pairs','R_masked_out_known_pairs','R_zero_effective_windows','R_effective_nonempty_windows')

class EligibilityJournal(TrainingJournal):
    """额外字段先进入原pending，原commit对整行做SHA并累计本子类扩展totals。"""
    def __init__(self,directory,spec):
        require(spec['binding'].get('record_extension_schema')==spec['runtime'].get('record_extension_schema')==EXTENSION_SCHEMA,
            '缺独立资格监督记录schema')
        require(spec['schema']=='full_training_record_spec_v1','只准3R/可选1S原记录容器')
        super().__init__(directory,spec)
        self.totals.update({key:0 for key in EFFECTIVE_FIELDS})

    def record_mask_accounting(self,accounting):
        require(self.pending is not None and 'R_mask_accounting' not in self.pending,'必须每个已begin更新恰记一次mask')
        require(accounting.get('schema')==ACCOUNTING_SCHEMA and len(accounting.get('windows',[]))==3,'缺三R窗mask记录')
        require(accounting.get('real_window_count')==3 and accounting.get('domain_forward_calls')==1
            and accounting.get('original_known_order_preserved') is True and accounting.get('original_labels_unchanged') is True
            and accounting.get('empty_effective_windows_contribute_graph_zero') is True and accounting.get('window_resampling') is False
            and accounting.get('unknown_features_forwarded') is False and accounting.get('unknown_labels_used_for_loss') is False
            and accounting.get('known_mask_applied_after_unreduced_BCE') is True and accounting.get('numeric_dtype')=='float32','原前向/标签/损失资格边界不同')
        totals={key:0 for key in EFFECTIVE_FIELDS}
        domain_counts={}
        for item,original in zip(accounting['windows'],self.pending['real']):
            labels=item['known_labels'];uids=item['known_candidate_UIDs'];mask=item['known_scoring_eligible'];known=item['raw_known_pairs']
            require(item['window_uid']==original['window_uid'] and item['raw_candidate_pairs']==original['candidate_pairs']
                and known==original['labelled_pairs'] and type(known) is int and known>0,'原窗口顺序/all-known pair不得改写')
            require(len(labels)==len(uids)==len(mask)==known and len(set(uids))==known
                and all(isinstance(uid,str) for uid in uids) and all(type(v) is bool for v in mask)
                and all(type(v) is int and v in (0,1) for v in labels),'known UID/标签/资格向量不完整')
            require(all(isinstance(item.get(key),str) and re.fullmatch('[0-9a-f]{64}',item[key]) for key in ('sidecar_sha256','binding_sha256')),'缺原mask侧表/绑定双SHA')
            require(isinstance(item.get('source'),dict) and item['source'].get('teacher_regime')=='R'
                and item['source'].get('teacher_seed')==20261024 and item['source'].get('source_stage')=='high_score','不能换teacher或stage')
            positive=sum(keep and label==1 for keep,label in zip(mask,labels));negative=sum(keep and label==0 for keep,label in zip(mask,labels));effective=positive+negative
            unknown=item['raw_candidate_pairs']-known;kept_unknown=item['kept_unknown_pairs']
            require(type(kept_unknown) is int and 0<=kept_unknown<=unknown,'资格内unknown数不能冒充loss监督')
            groups=dict(candidate=(item['raw_candidate_pairs'],effective+kept_unknown),known=(known,effective),
                positive=(labels.count(1),positive),negative=(labels.count(0),negative),unknown=(unknown,kept_unknown))
            expected={prefix+'_'+group+'_pairs':value for group,(raw,kept) in groups.items() for prefix,value in (('raw',raw),('kept',kept),('excluded',raw-kept))}
            expected.update(raw_known_empty=0,effective_known_empty=int(effective==0))
            require(all(type(item.get(key)) is int and item[key]==value for key,value in expected.items()),'有效监督数须由原known标签和mask重计')
            for key,value in expected.items():domain_counts[key]=domain_counts.get(key,0)+value
            for key,value in dict(R_effective_known_pairs=effective,R_effective_positive_pairs=positive,R_effective_negative_pairs=negative,
                R_effective_unknown_pairs=0,R_scoring_eligible_unknown_pairs=kept_unknown,R_masked_out_known_pairs=known-effective).items():totals[key]+=value
            totals['R_zero_effective_windows']+=int(effective==0);totals['R_effective_nonempty_windows']+=int(effective>0)
        domain_counts.update(R_scoring_eligible_unknown_pairs=domain_counts['kept_unknown_pairs'],R_effective_unknown_pairs=0)
        require(accounting.get('totals')==domain_counts and accounting.get('forwarded_known_pairs')==domain_counts['raw_known_pairs'],'逐域有效统计/原全部known前向数不同')
        # 原pending中的real/synthetic保持逐值不变；这些额外字段参与原steps曝光链。
        self.pending.update(R_mask_accounting=deepcopy(accounting),
            R_mask_accounting_sha256=hashlib.sha256(canonical(accounting).encode()).hexdigest(),**totals)
        return totals

    def commit_step(self,**values):
        require(self.pending is not None and 'R_mask_accounting' in self.pending,'不能提交未记录mask的更新')
        require(values['R_known_pairs']==sum(w['raw_known_pairs'] for w in self.pending['R_mask_accounting']['windows'])
            and values['R_pairs']==sum(w['raw_candidate_pairs'] for w in self.pending['R_mask_accounting']['windows']), '原all/known预算必须保留')
        return super().commit_step(**values)

def train(output,spec,model,optimizer,batches,r_domain_loss,s_domain_loss,*,checkpoint_extra=None,diagnostic_updates=None):
    """r_domain_loss返回(loss, accounting)；S仍原BCE，空R窗不跳step或重采样。"""
    import torch
    require(spec['runtime'].get('device')!='cpu_fixture','夹具不能成为正式训练入口')
    require(diagnostic_updates is None or diagnostic_updates==1 and spec['binding'].get('diagnostic_only_one_update_not_formal_training') is True,'诊断必须明示一步')
    stop=[False];previous=signal.signal(signal.SIGINT,lambda *args:stop.__setitem__(0,True));start=time.perf_counter()
    try:
        with EligibilityJournal(output,spec) as journal:
            journal.save_checkpoint(model,optimizer,extra=checkpoint_extra)
            for batch in batches:
                if stop[0]:break
                clock=time.perf_counter();require(batch['index']==journal.completed,'实际优化步序变化')
                require(not batch.get('extra_real') and not batch.get('r_extra'),'不准额外R或替换S')
                journal.begin_step(batch['index'],batch['r'],batch['s']);optimizer.zero_grad(set_to_none=True)
                r_loss,accounting=r_domain_loss(model,batch['real']);effective=journal.record_mask_accounting(accounting)
                s_loss=s_domain_loss(model,batch['synthetic']) if batch['s'] else None
                loss=r_loss+s_loss/3 if s_loss is not None else r_loss
                require(torch.isfinite(loss).item(),'实际loss非有限');loss.backward()
                parameters=list(model.parameters());gradients=[p.grad.detach().reshape(-1) for p in parameters if p.grad is not None]
                require(gradients and torch.isfinite(torch.cat(gradients)).all().item(),'实际梯度非有限')
                if effective['R_effective_known_pairs']==0:
                    require(all(p.grad is not None for p in parameters),'全空R也必须保留全部参数的梯度图')
                    if s_loss is None:require(torch.count_nonzero(torch.cat(gradients)).item()==0,'纯R全空步必须实际zero梯度')
                grad_l2=float(torch.linalg.vector_norm(torch.cat(gradients)));rates=[float(g['lr']) for g in optimizer.param_groups]
                optimizer.step()
                journal.commit_step(loss=float(loss.detach()),real_loss=float(r_loss.detach()),synthetic_loss=float(s_loss.detach()) if s_loss is not None else None,
                    learning_rates=rates,grad_l2=grad_l2,R_pairs=sum(w['candidate_pairs'] for w in batch['real']),S_pairs=sum(w['candidate_pairs'] for w in batch['synthetic']),
                    R_known_pairs=sum(w['known_pairs'] for w in batch['real']),S_known_pairs=sum(w['known_pairs'] for w in batch['synthetic']),step_wall_seconds=time.perf_counter()-clock)
                if journal.completed%50==0:journal.save_checkpoint(model,optimizer,extra=checkpoint_extra)
                if diagnostic_updates is not None and journal.completed==diagnostic_updates:break
            require(journal.completed==1000 or stop[0] or journal.completed==diagnostic_updates,'输入提前结束，不伪装完成')
            journal.event('training_wall_seconds',seconds=time.perf_counter()-start,includes_checkpoints=True,includes_prefetch_wait=True)
            if journal.completed==1000:
                # 原training_complete.json容器保持；调用方run_receipt另签本方法身份。
                result=journal.finish()
                return dict(result,loop_receipt_schema='R_candidate_scoring_eligibility_formal_loop_receipt_v1',record_extension_schema=EXTENSION_SCHEMA)
            if diagnostic_updates is not None:
                journal.save_checkpoint(model,optimizer,extra=checkpoint_extra);journal.event('diagnostic_only_not_formal1000',actual_diagnostic_updates=journal.completed)
                return dict(schema='R_candidate_scoring_eligibility_one_step_diagnostic_receipt_v1',status='diagnostic_only',completed_updates=journal.completed,record_extension_schema=EXTENSION_SCHEMA,effective_totals={k:journal.totals[k] for k in EFFECTIVE_FIELDS})
            if journal.completed not in journal.checkpoints:journal.save_checkpoint(model,optimizer,extra=checkpoint_extra)
            journal.event('user_SIGINT_safely_paused_no_replay',completed_updates=journal.completed)
            return dict(schema='R_candidate_scoring_eligibility_paused_receipt_v1',status='safely_paused',completed_updates=journal.completed,record_extension_schema=EXTENSION_SCHEMA)
    finally:signal.signal(signal.SIGINT,previous)
