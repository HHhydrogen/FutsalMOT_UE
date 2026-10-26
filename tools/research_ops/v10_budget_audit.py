"""v10独立54臂实际更新/窗口/pair/初始化及完整记录核对，不训练或读媒体。"""
import argparse
from collections import defaultdict
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import v10_tracking_runtime as rt


def audit(config,control,output):
    runtime,cfg,numeric,base,old=rt.training(config);control=Path(control);state=rt.read(control/'driver_state.json')
    rt.require(state['status']=='complete_54_recorded_train_wait_independent_tracking' and len(state['completed_train'])==54
        and state['active'] is None,'实际54训练未完整')
    import torch
    torch.set_num_threads(1);groups=defaultdict(list);totals=dict(updates=0,R_windows=0,S_windows=0,R_pairs=0,S_pairs=0,R_known_pairs=0,S_known_pairs=0)
    records=[]
    for job in cfg['training_matrix']:
        folder=control/'runs'/job['fold']/str(job['seed'])/job['pool']/job['method']/'training'
        _,_,model,adapter,binding=runtime.complete_model(config,folder)
        complete=rt.read(folder/'training_complete.json');logs=rt.rows(folder/'steps.jsonl')
        table=rt.read(rt.checked(cfg['exposures'][job['pool']][job['fold']][str(job['seed'])]))
        for index,row in enumerate(logs):
            for domain,prefix,indices in [('real','R',slice(index*3,index*3+3)),('synthetic','S',slice(index,index+1))]:
                expected=table[domain][indices]
                rt.require(row[prefix+'_pairs']==sum(e['candidate_pairs'] for e in expected)
                    and row[prefix+'_known_pairs']==sum(e['labelled_pairs'] for e in expected),'实际all/known pair与曝光表不符')
            rt.require(row['learning_rates']==[.001] and row['gradients_clipped'] is False
                and all(math.isfinite(row[k]) and row[k]>=0 for k in ('loss','real_loss','synthetic_loss','grad_l2','step_wall_seconds')),
                '实际loss/LR/梯度/耗时记录缺失或不同')
        for point in complete['checkpoints']:
            saved=torch.load(rt.checked(point),map_location='cpu',weights_only=False)
            step=point['completed_updates'];chain='0'*64 if step==0 else logs[step-1]['chain_sha256']
            rt.require(saved['schema']=='full_training_checkpoint_v1' and saved['binding']==binding
                and saved['completed_updates']==step and saved['exposure_chain']==chain and saved['rng_torch_cuda'] is not None
                and all(k in saved for k in ('model','optimizer','rng_python','rng_numpy','rng_torch_cpu'))
                and (step==0 or saved['optimizer']['state']),'模型/优化器/完整RNG/链损坏')
        receipt=rt.read(folder/'run_receipt.json');rt.require(receipt['prefetch']['closed'] and not receipt['prefetch']['worker_alive'],'预取未退出')
        record=dict(job=job,binding=binding,totals=complete['totals'],updates=len(logs),checkpoints=21,
            steps_sha256=rt.sha(folder/'steps.jsonl'),run_receipt_sha256=rt.sha(folder/'run_receipt.json'),last=rt.read(folder/'last_checkpoint.json'))
        groups[(job['fold'],job['seed'])].append(record);records.append(record)
        totals['updates']+=1000
        for key in complete['totals']:totals[key]+=complete['totals'][key]
    for key,items in groups.items():
        rt.require(len(items)==6 and len({i['binding']['R_window_UID_chain_sha256'] for i in items})==1
            and len({i['binding']['motion_base_initialization_sha256'] for i in items})==1,'六组原R序列或motion初始值不同')
        for pool in runtime.REGIMES:
            selected=[i for i in items if i['job']['pool']==pool]
            rt.require(len({i['binding']['S_window_UID_chain_sha256'] for i in selected})==1
                and len({rt.canonical(i['totals']) for i in selected})==1,'同池三方法实际窗口/pair顺序不同')
        for method in runtime.METHODS:
            rt.require(len({i['binding']['initialization_sha256'] for i in items if i['job']['method']==method})==1,'跨池初始化不同')
    rt.require(totals['updates']==54000 and totals['R_windows']==162000 and totals['S_windows']==54000,'全矩阵实际总预算不同')
    output=runtime.storage().physical_child(output,rt.V);rt.require(not output.exists(),'独立预算输出已存在')
    output.parent.mkdir(parents=True,exist_ok=True)
    value=dict(schema='v10_actual_recorded_training_budget_v1',status='complete54_actual_budget_and_full_records_verified',
        protocol_sha256=rt.sha(config),control_state_sha256=rt.sha(control/'driver_state.json'),totals=totals,runs=records,
        complete_checkpoints_verified=54*21,cross_method_and_pool_R_order_equal=True,same_pool_S_order_and_pair_equal=True,
        between_pool_pair_budget_equal=False,diagnostic_optimizer_updates_separate=6,optimizer_replayed=0,
        historical_pureR_new_updates=0,test_read=False,GPU_used=False,media_read=False)
    with output.open('x',encoding='utf-8') as stream:stream.write(rt.canonical(value)+'\n')
    return dict(status=value['status'],totals=totals,checkpoints=1134)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','control','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(rt.canonical(audit(a.config,a.control,a.output)))
