"""实际CPU加载三类两架构模型和适配器；仅原trainR特征接口探针，非七比赛评价。"""
import argparse
import os
import traceback
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import substitution_tracking_runtime as rt

def verify(config):
    c=rt.read(config);rt.require(c['schema']=='ABC_model_loading_diagnostic_v1' and c['approved_by']=='root'
        and c['diagnostic_authorized'] is True and c['tracking_authorized'] is False and c['test_sealed'] is True
        and Path(c['bundle'])==rt.ROOT and rt.ROOT.parent==rt.R/'code','缺独立模型加载诊断准入')
    for e in c['code_files']:rt.require(rt.sha(rt.ROOT/e['path'])==e['sha256'],'CPU诊断源码改变')
    dep=rt.dependencies(c['source_tracking_config']);cr=rt.C_runtime(rt.checked(c['C_protocol']));cc=cr.protocol(c['C_protocol']['path'])
    rt.checked(c['C_complete']);output=dep[3].storage().physical_child(c['output'],rt.EXP)
    rt.require(not output.exists(),'诊断输出已存在，不重放');output.mkdir(parents=True)
    import torch
    torch.set_num_threads(1);fold,seed='game4',20261024;checks=[];vectors={}
    window=rt.rows(rt.checked(cc['folds'][fold]['real_pool']))[0]
    raw=dep[5].features(window['history'],window['candidates'][0]['prediction'])
    for method in rt.METHODS:
        expected=rt.read(rt.checked(cc['reference_R'][method][fold][str(seed)]['training_receipt']))['binding']['initialization_sha256']
        for group in rt.GROUPS:
            job=dict(kind='learned',group=group,method=method,fold=fold,seed=seed)
            model,adapter,binding,use_pose=rt.load_model(c,dep,cr,cc,job)
            rt.require(binding['initialization_sha256']==expected and all(p.device.type=='cpu' and p.dtype==torch.float32 for p in model.parameters()),'实际模型/初始化/CPU FP32不同')
            values=adapter.transform(raw,use_pose=use_pose);x=torch.tensor([values],dtype=torch.float32)
            if method in vectors:rt.require(torch.equal(vectors[method],x),'同方法A/B/C的实际推理适配器不同')
            else:vectors[method]=x
            with torch.inference_mode():result=model(x)
            rt.require(result.numel()==1 and torch.isfinite(result).all().item(),'实际模型前向接口不兼容')
            checks.append(dict(group=group,method=method,fold=fold,seed=seed,checkpoint_binding=binding,
                actual_model_sha256=dep[6].model_sha(model),input_dimensions=len(values),forward_finite=True,
                initialization_matches=True,same_inference_adapter=True))
    result=dict(schema='ABC_model_loading_diagnostic_receipt_v1',status='complete6_ABC_model_loaders_CPU_adapters_verified',
        config=rt.ref(config),checks=checks,model_forward_probes=6,actual_optimizer_updates=0,validation_frames_processed=0,
        train_feature_probe_only=True,GPU_used=False,test_read=False,actual392_tracking_complete=False)
    (output/'receipt.json').write_text(rt.canonical(result)+'\n',encoding='utf-8');return dict(status=result['status'],models=6,updates=0,validation_frames=0)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);a=p.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES']='-1'
    try:print(rt.canonical(verify(a.config)))
    except BaseException as error:
        folder=Path(rt.read(a.config)['output'])
        if folder.exists() and not (folder/'failed.json').exists():
            with (folder/'failed.json').open('x',encoding='utf-8') as f:
                f.write(rt.canonical(dict(status='failed_preserved_no_replay',config=rt.ref(a.config),error=repr(error),
                    traceback=traceback.format_exc(),optimizer_updates=0,validation_frames=0))+'\n')
        raise
