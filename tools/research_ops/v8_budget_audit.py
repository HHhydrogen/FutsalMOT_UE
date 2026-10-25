"""独立读取完整v8实际曝光链，核对窗口/已知pair公平性；不训练、不重推预测。"""
import argparse,hashlib,json
from pathlib import Path
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)
def equal_quartet(rows):
    require(len(rows)==4 and {r['arm'] for r in rows}=={'motion_R','motion_RS','pose_R','pose_RS'},'四单元必须完整')
    keys=('real_UID_sequence_sha256','initialization_sha256','real_window_exposures','real_known_pairs','real_candidate_pairs')
    for key in keys:require(len({r[key] for r in rows})==1,'真实实际曝光/初始化不一致:'+key)
    mixed=[r for r in rows if r['arm'].endswith('_RS')]
    for key in ('synthetic_UID_sequence_sha256','synthetic_known_pairs','synthetic_candidate_pairs'):require(mixed[0][key]==mixed[1][key],'两混合组S实际曝光不一致:'+key)
def audit(config,control,output):
    cfg=read(config);control=Path(control);state=read(control/'driver_state.json');require(state['status']=='complete_36_train_42_tracking_and_analysis' and len(state['completed_train'])==36,'只消费全部结束的36臂')
    require(state['protocol_sha256']==sha(config) and cfg['test116187_sealed'] is True,'协议不符')
    rows=[]
    for game in ('game4','game6','game9'):
        for seed in (20261024,20261025,20261026):
            quartet=[]
            for arm in ('motion_R','motion_RS','pose_R','pose_RS'):
                directory=control/'runs'/game/str(seed)/arm/'training';receipt=read(directory/'run_receipt.json');transaction=read(directory/'update_transaction.json');chain='0'*64;real=[];synthetic=[];totals={k:0 for k in ('real_known_pairs','synthetic_known_pairs','real_candidate_pairs','synthetic_candidate_pairs')};count=0
                for line in (directory/'exposures.jsonl').read_text(encoding='utf-8').splitlines():
                    v=json.loads(line);stored=v.pop('chain_sha256');chain=hashlib.sha256((chain+canonical(v)).encode()).hexdigest();require(stored==chain and v['actual_update']==count+1 and v['update_index']==count,'实际曝光链断裂')
                    require(v['real_windows']==len(v['real'])==3 and v['synthetic_windows']==len(v['synthetic'])==int(arm.endswith('_RS')),'实际每步预算改变')
                    real.extend(r['window_uid'] for r in v['real']);synthetic.extend(r['window_uid'] for r in v['synthetic'])
                    totals['real_known_pairs']+=v['real_known_pairs'];totals['synthetic_known_pairs']+=v['synthetic_known_pairs'];totals['real_candidate_pairs']+=v['real_pair_exposures'];totals['synthetic_candidate_pairs']+=v['synthetic_pair_exposures'];count+=1
                require(count==1000 and len(real)==3000 and len(synthetic)==(1000 if arm.endswith('_RS') else 0),'实际总预算不足')
                require(receipt['status']=='complete' and receipt['completed_updates']==1000 and receipt['exposure_chain']==transaction['chain']==chain and receipt['checkpoint_sha256']==sha(directory/'last.pt'),'last/事务/曝光绑定不闭合')
                r_sha=hashlib.sha256(canonical(real).encode()).hexdigest();require(r_sha==receipt['binding']['R_window_UID_chain_sha256'],'实际R顺序不同于初始绑定')
                row=dict(heldout_game=game,seed=seed,arm=arm,actual_updates=count,real_window_exposures=len(real),synthetic_window_exposures=len(synthetic),real_UID_sequence_sha256=r_sha,synthetic_UID_sequence_sha256=hashlib.sha256(canonical(synthetic).encode()).hexdigest(),initialization_sha256=receipt['binding']['initialization_sha256'],source_receipt_sha256=sha(directory/'run_receipt.json'),**totals);quartet.append(row);rows.append(row)
            equal_quartet(quartet)
    result=dict(status='complete_actual_window_and_pair_budget_equal',protocol_sha256=sha(config),implementation_sha256=sha(__file__),rows=rows,actual_updates=sum(r['actual_updates'] for r in rows),real_window_exposures=sum(r['real_window_exposures'] for r in rows),synthetic_window_exposures=sum(r['synthetic_window_exposures'] for r in rows),all_nine_quartets_equal_real_UID_order_known_pair_count_and_initialization=True,budget_unit='association_window; pair counts separate; not image exposure',test_read=False,GPU_used=False)
    output=Path(output).resolve();require(Path('D:/projects/FutsalMOT_Research/pose/learned_association_v8') in output.parents and not output.exists(),'全新研究收据');output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','control','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=audit(a.config,a.control,a.output);print(json.dumps(dict(status=r['status'],actual_updates=r['actual_updates'])))
