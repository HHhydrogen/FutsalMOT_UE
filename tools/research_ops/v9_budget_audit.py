"""v9实际窗口/监督pair和初始化公平性独立核对；不读取媒体或重训。"""
import argparse,hashlib,json
from pathlib import Path
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def require(ok,msg):
    if not ok:raise ValueError(msg)
def audit(config,control,output):
    cfg=read(config);control=Path(control);state=read(control/'driver_state.json');require(state['status']=='complete_78_train_tracking_and_analysis' and len(state['completed_train'])==78,'只消费全部完成状态')
    all_rows=[];real_by_seed={};synthetic_by_seed={}
    for job in cfg['training_matrix']:
        d=control/'runs'/job['fold']/str(job['seed'])/job['variant']/job['regime']/'training';receipt=read(d/'run_receipt.json');transaction=read(d/'update_transaction.json');chain='0'*64;r_ids=[];s_ids=[];counts=dict(R_known_pairs=0,S_known_pairs=0,R_candidates=0,S_candidates=0);n=0
        for line in (d/'exposures.jsonl').read_text(encoding='utf-8').splitlines():
            value=json.loads(line);expected=value.pop('chain_sha256');chain=hashlib.sha256((chain+canonical(value)).encode()).hexdigest();require(expected==chain and value['actual_update']==n+1 and value['update_index']==n,'日志链/步数不符');r_ids.extend(r['window_uid'] for r in value['real']);s_ids.extend(r['window_uid'] for r in value['synthetic']);counts['R_known_pairs']+=value['real_known_pairs'];counts['S_known_pairs']+=value['synthetic_known_pairs'];counts['R_candidates']+=value['real_pair_exposures'];counts['S_candidates']+=value['synthetic_pair_exposures'];n+=1
        require(n==1000 and len(r_ids)==3000 and len(s_ids)==(1000 if job['regime']=='RS' else 0),'实际曝光不足');require(receipt['exposure_chain']==transaction['chain']==chain and receipt['checkpoint_sha256']==sha(d/'last.pt') and receipt['status']=='complete','实际last链不闭合')
        r_sha=hashlib.sha256(canonical(r_ids).encode()).hexdigest();s_sha=hashlib.sha256(canonical(s_ids).encode()).hexdigest();require(r_sha==receipt['binding']['R_window_UID_chain_sha256'],'实际R顺序不同于绑定')
        key=(job['fold'],job['seed']);r_value=(r_sha,counts['R_known_pairs'],counts['R_candidates'],receipt['binding']['initialization_sha256']);s_value=(s_sha,counts['S_known_pairs'],counts['S_candidates'])
        if key not in real_by_seed:real_by_seed[key]=r_value
        require(real_by_seed[key]==r_value,'同fold/seed R曝光、pair、初始化不一致')
        if job['regime']=='RS':
            if key not in synthetic_by_seed:synthetic_by_seed[key]=s_value
            require(synthetic_by_seed[key]==s_value,'同seed S实际窗口/pair不一致')
        all_rows.append(dict(**job,actual_updates=n,R_windows=len(r_ids),S_windows=len(s_ids),**counts))
    result=dict(status='complete_78_actual_exposure_fairness_verified',protocol_sha256=sha(config),implementation_sha256=sha(__file__),rows=all_rows,actual_updates=sum(r['actual_updates'] for r in all_rows),R_windows=sum(r['R_windows'] for r in all_rows),S_windows=sum(r['S_windows'] for r in all_rows),all_available_variants_same_real_order_pair_count_and_initialization=True,paired_RS_same_S_order_and_pair_count=True,augmentation_intentionally_changes_pose_inputs_not_identity_labels=True,test_read=False,GPU_used=False)
    output=Path(output);require(not output.exists(),'新收据');output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','control','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();r=audit(a.config,a.control,a.output);print(json.dumps(dict(status=r['status'],actual_updates=r['actual_updates'])))
