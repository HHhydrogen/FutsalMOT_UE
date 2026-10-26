"""实际三方法首3R/1S的一步数值对照；六个诊断更新另计，不作为正式模型。"""
import argparse
import os
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).parent))
import v10_runtime as runtime


def verify(config,output):
    import torch
    from training_journal import TrainingJournal,write_new
    runtime.require(torch.__version__=='2.6.0+cu124' and torch.cuda.is_available(),'必须实际冻结CUDA环境，不能假装GPU验证')
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    output=runtime.storage().physical_child(output,runtime.EXPERIMENT)
    runtime.require(not output.exists(),'保留原诊断目录，不覆盖/重播')
    output.mkdir(parents=True);results=[]
    fold,seed,pool=runtime.FOLDS[0],runtime.SEEDS[0],runtime.REGIMES[0]
    for method in runtime.METHODS:
        cfg,numeric,base,pools,table,normalizer,adapter,reference=runtime.validate_job(config,fold,seed,pool,method)
        if method=='motion':
            from grf_ue_bridge.learned_association_model_v8 import make_model
            make=lambda:make_model(seed).to('cuda:0');cache=base.FeatureCache(pools,normalizer,False)
            get=lambda domain,row:cache.get(domain,row['window_uid'])
        else:
            make=lambda:numeric.make_model(seed,method).to('cuda:0');cache=numeric.Cache(pools,adapter,method,seed)
            get=lambda domain,row:cache.get(domain,row)
        old_model,new_model=make(),make()
        runtime.require(base.model_sha(old_model)==base.model_sha(new_model)==reference['binding']['initialization_sha256'],'诊断初始模型不同')
        old_opt=torch.optim.AdamW(old_model.parameters(),lr=.001,weight_decay=.0001)
        new_opt=torch.optim.AdamW(new_model.parameters(),lr=.001,weight_decay=.0001)
        rr=table['real'][:3];ss=table['synthetic'][:1];real=[get('real',r) for r in rr];synthetic=[get('synthetic',s) for s in ss]
        old_opt.zero_grad(set_to_none=True)
        expected_r=numeric.domain_loss(old_model,real);expected_s=numeric.domain_loss(old_model,synthetic)
        expected=expected_r+expected_s/3;expected.backward();old_opt.step()
        spec=dict(schema='full_training_record_spec_v1',updates=1000,R_per_update=3,S_per_update=1,checkpoint_interval=50,
            test116187_sealed=True,binding=dict(protocol_sha256=runtime.sha(config),method=method,
                diagnostic_only_one_update_not_formal_training=True),runtime=dict(device='cuda:0',torch_version=torch.__version__))
        with TrainingJournal(output/method,spec) as journal:
            journal.save_checkpoint(new_model,new_opt,extra=dict(diagnostic_only=True))
            clock=time.perf_counter();journal.begin_step(0,rr,ss);new_opt.zero_grad(set_to_none=True)
            r_loss=numeric.domain_loss(new_model,real);s_loss=numeric.domain_loss(new_model,synthetic)
            loss=r_loss+s_loss/3;loss.backward()
            gradients=[p.grad.detach().reshape(-1) for p in new_model.parameters() if p.grad is not None]
            norm=float(torch.linalg.vector_norm(torch.cat(gradients)));rates=[float(g['lr']) for g in new_opt.param_groups]
            new_opt.step()
            journal.commit_step(loss=float(loss.detach()),real_loss=float(r_loss.detach()),synthetic_loss=float(s_loss.detach()),
                learning_rates=rates,grad_l2=norm,R_pairs=sum(w['candidate_pairs'] for w in real),S_pairs=sum(w['candidate_pairs'] for w in synthetic),
                R_known_pairs=sum(w['known_pairs'] for w in real),S_known_pairs=sum(w['known_pairs'] for w in synthetic),step_wall_seconds=time.perf_counter()-clock)
            point=journal.save_checkpoint(new_model,new_opt,extra=dict(diagnostic_only=True))
            loaded=torch.load(point,map_location='cpu',weights_only=False)
            runtime.require(float(expected.detach())==float(loss.detach())
                and all(torch.equal(v,new_model.state_dict()[k]) for k,v in old_model.state_dict().items())
                and all(torch.equal(v.detach().cpu(),loaded['model'][k]) for k,v in new_model.state_dict().items())
                and loaded['completed_updates']==1 and loaded['optimizer']['state']
                and all(k in loaded for k in ('rng_python','rng_numpy','rng_torch_cpu','rng_torch_cuda'))
                and loaded['rng_torch_cuda'] is not None,'记录分支改变实际数值/模型或未存完整优化器/RNG')
            journal.event('diagnostic_one_step_equal_not_formal1000',actual_diagnostic_updates=2)
        results.append(dict(method=method,loss=float(loss.detach()),initialization=reference['binding']['initialization_sha256'],
            model_equal=True,checkpoint_readback_equal=True,actual_diagnostic_optimizer_updates=2,R_windows_per_copy=3,S_windows_per_copy=1))
    value=dict(status='complete_three_methods_one_step_equal_with_recording',protocol_sha256=runtime.sha(config),
        all_methods_equal=True,actual_diagnostic_optimizer_updates=6,formal_optimizer_updates=0,
        diagnostic_R_window_exposures=18,diagnostic_S_window_exposures=6,results=results,test_read=False,
        full1000_integration_verified=False,next_gate='first_formal_arm1000_full21checkpoints_before_remaining53')
    write_new(output/'receipt.json',value)
    runtime.require(Path(cfg['numeric_validation_receipt_path'])==output/'receipt.json','诊断收据不是事前路径')
    return value


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    print(runtime.canonical(verify(args.config,args.output)))
