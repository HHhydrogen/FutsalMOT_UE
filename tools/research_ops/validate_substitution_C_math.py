"""真正调用新记录循环，CUDA对照手写C损失/优化器与完整检查点，四诊断更新另计。"""
import argparse
import copy
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).parent))
from recorded_association_loop import train as recorded_train
from training_journal import write_new
import substitution_C_runtime as rt

def tree_equal(a,b):
    import torch
    if torch.is_tensor(a):return torch.is_tensor(b) and torch.equal(a.detach().cpu(),b.detach().cpu())
    if isinstance(a,dict):return isinstance(b,dict) and a.keys()==b.keys() and all(tree_equal(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)):return type(a)==type(b) and len(a)==len(b) and all(tree_equal(x,y) for x,y in zip(a,b))
    return a==b

def verify(config,output):
    import torch
    rt.require(torch.__version__=='2.6.0+cu124' and torch.cuda.is_available(),'必须实际冻结CUDA环境')
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    output=rt.storage().physical_child(output,rt.EXP);rt.require(not output.exists(),'已有诊断/partial，不覆盖')
    output.mkdir(parents=True);results=[]
    fold,seed=rt.FOLDS[0],rt.SEEDS[0]
    for method in rt.METHODS:
        c,n,b,pools,table,plan,norm,adapter,a=rt.job(config,fold,seed,method)
        manual,cache,get=rt.model_and_cache(n,b,pools,norm,adapter,seed,method)
        model=copy.deepcopy(manual);manual.to('cuda:0');model.to('cuda:0')
        rt.require(b.model_sha(manual)==b.model_sha(model)==a['binding']['initialization_sha256'],'诊断初始化不同')
        load=rt.batch_loader(table,plan,get);batch=load(0)
        manual_opt=torch.optim.AdamW(manual.parameters(),lr=.001,weight_decay=.0001)
        opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
        manual_opt.zero_grad(set_to_none=True)
        base_loss=n.domain_loss(manual,batch['real']);extra_loss=n.domain_loss(manual,batch['extra_real'])
        loss=base_loss+extra_loss/3;loss.backward();manual_opt.step()
        spec=dict(schema='full_training_record_spec_v2_real_groups',updates=1000,R_per_update=4,S_per_update=0,
            base_R_per_update=3,extra_R_per_update=1,extra_R_alpha=1/3,checkpoint_interval=50,test116187_sealed=True,
            binding=dict(protocol_sha256=rt.sha(config),method=method,diagnostic_only_one_update_not_formal_training=True),
            runtime=dict(device='cuda:0',torch_version=torch.__version__))
        complete=recorded_train(output/method,spec,model,opt,[batch],n.domain_loss,
            checkpoint_extra=dict(diagnostic_only=True),diagnostic_updates=1)
        logged=rt.rows(output/method/'steps.jsonl');point=rt.read(output/method/'last_checkpoint.json')
        saved=torch.load(rt.checked(point),map_location='cpu',weights_only=False)
        rt.require(complete['status']=='diagnostic_only' and complete['completed_updates']==1 and len(logged)==1
            and logged[0]['loss']==float(loss.detach()) and logged[0]['base_real_loss']==float(base_loss.detach())
            and logged[0]['extra_real_loss']==float(extra_loss.detach())
            and tree_equal(manual.state_dict(),model.state_dict()) and tree_equal(manual_opt.state_dict(),opt.state_dict())
            and tree_equal(model.state_dict(),saved['model']) and tree_equal(opt.state_dict(),saved['optimizer'])
            and saved['schema']=='full_training_checkpoint_v2_real_groups' and saved['completed_updates']==1
            and saved['rng_torch_cuda'] is not None and {'rng_python','rng_numpy','rng_torch_cpu'}<=set(saved)
            and logged[0]['R_windows']==4 and logged[0]['S_windows']==0,'C实际循环/完整状态数值不一致')
        results.append(dict(method=method,model_equal=True,optimizer_equal=True,checkpoint_readback_equal=True,
            loss=float(loss.detach()),base_real_loss=float(base_loss.detach()),extra_real_loss=float(extra_loss.detach()),
            actual_diagnostic_optimizer_updates=2,R_exposures=8,S_exposures=0))
    receipt=dict(status='complete_C_two_methods_actual_loop_equal',protocol_sha256=rt.sha(config),results=results,
        all_equal=True,actual_diagnostic_optimizer_updates=4,diagnostic_R_windows=16,diagnostic_S_windows=0,
        formal_updates=0,full1000_integration_verified=False,test_read=False)
    rt.require(Path(c['numeric_validation_receipt_path'])==output/'receipt.json','诊断完成路径不同')
    write_new(output/'receipt.json',receipt);return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8';print(rt.canonical(verify(a.config,a.output)))
