"""v9真实last1000质量残差自由追踪；复用固定v8候选/分配，不读GT。"""
import argparse,hashlib,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'python/src'),str(ROOT/'tools/research_ops'),str(Path('D:/projects/FutsalMOT_Research/runtime_dependencies'))]
from v8_train import read,checked,sha,require,canonical,rows,model_sha
from grf_ue_bridge.quality_residual_association_v9 import Adapter,make_model
V=Path('D:/projects/FutsalMOT_Research/pose/pose_quality_v9')
def complete_model(config,run,fold):
    import torch
    cfg=read(config);run=Path(run);receipt=read(run/'run_receipt.json');saved=torch.load(run/'last.pt',map_location='cpu',weights_only=False);transaction=read(run/'update_transaction.json');logs=rows(run/'exposures.jsonl');binding=receipt['binding']
    require(receipt['schema']=='v9_actual_window_training' and receipt['status']=='complete' and receipt['completed_updates']==saved['completed_updates']==1000 and len(logs)==1000 and receipt['checkpoint_sha256']==sha(run/'last.pt'),'完整真实last1000缺失')
    require(saved['schema']=='v9_quality_residual_checkpoint' and saved['binding']==binding and binding['protocol_sha256']==sha(config) and binding['fold']==fold,'v9模型身份缺失')
    require({k:binding[k] for k in ('fold','seed','variant','regime')} in cfg['training_matrix'],'未登记run')
    chain='0'*64
    for i,r in enumerate(logs):row=dict(r);expected=row.pop('chain_sha256');chain=hashlib.sha256((chain+canonical(row)).encode()).hexdigest();require(chain==expected and row['actual_update']==i+1 and row['update_index']==i,'曝光链错误')
    require(receipt['exposure_chain']==saved['exposure_chain']==transaction['chain']==chain and transaction['status']=='committed' and transaction['completed_updates']==1000,'last/事务链不闭合')
    require(receipt['real_window_exposures']==3000 and receipt['synthetic_window_exposures']==(1000 if binding['regime']=='RS' else 0),'实际预算不符')
    adapter=Adapter.from_state(saved['adapter']);require(hashlib.sha256(canonical(adapter.state()).encode()).hexdigest()==binding['adapter_sha256'],'adapter状态变更')
    require(saved['actual_dtype']=='float32' and all(v.dtype==torch.float32 for v in saved['model'].values()),'FP32不符');model=make_model(binding['seed'],binding['variant']);require(model_sha(model)==binding['initialization_sha256'],'初始化变更');model.load_state_dict(saved['model']);model.eval();return model,adapter,binding
def execute(config,run,output):
    cfg=read(config);require(cfg['tracking_authorized'] and cfg['approved_by']=='root','v9准入缺失');require(Path(__file__).resolve()==Path(cfg['bundle'])/'tools/research_ops/v9_track.py','只运行bundle')
    for f in read(checked(cfg['bundle_manifest']))['files']:require(sha(Path(cfg['bundle'])/f['path'])==f['sha256'],'源码变更')
    receipt=read(Path(run)/'run_receipt.json');fold=receipt['binding']['fold'];output=Path(output).resolve();require(V in output.parents and not output.exists(),'全新输出，不覆盖')
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',YOLO_AUTOINSTALL='false',YOLO_CONFIG_DIR=str(V/'_runtime/ultralytics'))
    import torch
    from grf_ue_bridge.learned_association_tracker_v8 import tracker_class
    torch.set_num_threads(1);model,adapter,binding=complete_model(config,run,fold);source=next(s for s in read(checked(cfg['source_config']))['sources'] if s['domain']=='real' and s['game']==fold);frames=rows(checked(source['cache']));require(len(frames)==750,'固定750帧')
    tracker=tracker_class()(mode='learned',model=model,normalizer=adapter,use_pose=True,pose_source_sha256=cfg['pose_checkpoint_sha256'],fixed_detection_sha256=source['cache']['sha256']);text=[]
    for f in frames:
        for row in tracker.update_frame(f):
            x1,y1,x2,y2,identity,score=row[:6];text.append(','.join(map(str,[f['frame_number'],int(identity),float(x1),float(y1),float(x2-x1),float(y2-y1),float(score),-1,-1,-1])))
    output.mkdir(parents=True);(output/'data').mkdir();mot=output/'data'/(source['sequence']+'.txt');mot.write_text('\n'.join(text)+'\n',encoding='utf-8')
    value=dict(schema='v9_quality_residual_tracking',status='complete',protocol_sha256=sha(config),binding=binding,fold=fold,sequence=source['sequence'],mode='quality_residual_v9',frames=750,tracked_rows=len(text),mot_sha256=sha(mot),cache=source['cache'],trained_checkpoint=dict(path=str(Path(run)/'last.pt'),sha256=sha(Path(run)/'last.pt')),audit=tracker.audit,GT_read=False,GPU_used=False,test_read=False)
    (output/'receipt.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return value
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','run','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--execute',action='store_true');a=p.parse_args();print(json.dumps(execute(a.config,a.run,a.output) if a.execute else dict(status='readonly_v9_track_no_GT'),ensure_ascii=False))
