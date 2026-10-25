"""v8已训练last1000/真实PT基线的独立750帧CPU追踪；不读GT。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
BUNDLE=Path(__file__).resolve().parents[2];sys.path[:0]=[str(BUNDLE/'python/src'),str(BUNDLE/'tools/research_ops'),str(Path('D:/projects/FutsalMOT_Research/runtime_dependencies'))]
from v8_train import require,sha,read,checked,canonical,rows,model_sha,GAMES,ARMS
RESEARCH=Path('D:/projects/FutsalMOT_Research');SEQUENCE={'game4':'SNMOT-060','game6':'SNMOT-097','game9':'SNMOT-151'}
def load_complete(run,cfg,config_sha,fold):
    import torch
    from grf_ue_bridge.learned_association_model_v8 import FeatureNormalizer,make_model
    run=Path(run);receipt=read(run/'run_receipt.json');saved=torch.load(run/'last.pt',map_location='cpu',weights_only=False);transaction=read(run/'update_transaction.json');exposures=rows(run/'exposures.jsonl')
    binding=receipt['binding'];require(receipt['status']=='complete' and receipt['checkpoint_sha256']==sha(run/'last.pt') and receipt['completed_updates']==1000 and saved['completed_updates']==1000 and transaction['status']=='committed' and transaction['completed_updates']==1000 and len(exposures)==1000,'只准实际1000已提交last')
    require(saved['schema']=='v8_learned_association_checkpoint' and saved['binding']==binding and binding['protocol_sha256']==config_sha and binding['fold']==fold and binding['arm'] in ARMS and binding['seed'] in (20261024,20261025,20261026),'训练身份不符')
    chain='0'*64
    for i,row in enumerate(exposures):value=dict(row);expected=value.pop('chain_sha256');chain=hashlib.sha256((chain+canonical(value)).encode()).hexdigest();require(expected==chain and row['update_index']==i and row['actual_update']==i+1,'曝光链断裂')
    require(saved['exposure_chain']==receipt['exposure_chain']==transaction['chain']==chain,'last/receipt/intent链不同')
    require(receipt['real_window_exposures']==3000 and receipt['synthetic_window_exposures']==(1000 if binding['arm'].endswith('_RS') else 0),'窗口预算不符')
    normalizer=FeatureNormalizer.from_state(read(checked(cfg['folds'][fold]['normalizer'])));require(saved['normalizer']==normalizer.state() and saved['actual_dtype']=='float32' and all(v.dtype==torch.float32 for v in saved['model'].values()),'Normalizer/FP32不符')
    model=make_model(binding['seed']);require(model_sha(model)==binding['initialization_sha256'],'初始化SHA不符');model.load_state_dict(saved['model']);model.eval();return model,normalizer,binding
def execute(config,fold,mode,output,run=None):
    cfg=read(config);require(cfg.get('tracking_authorized') is True and cfg.get('approved_by')=='root','root尚未授权真实CPU追踪')
    require(Path(__file__).resolve()==Path(cfg['bundle'])/'tools/research_ops/v8_track.py','必须从内容寻址bundle执行')
    for f in read(checked(cfg['bundle_manifest']))['files']:require(sha(Path(cfg['bundle'])/f['path'])==f['sha256'],'绑定源码变化')
    output=Path(output).resolve();require(RESEARCH/'pose/learned_association_v8' in output.parents and not output.exists(),'需全新v8输出，不覆盖partial')
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',YOLO_AUTOINSTALL='false',YOLO_CONFIG_DIR=str(RESEARCH/'pose/learned_association_v8/_runtime/ultralytics'))
    import torch
    import numpy as np
    from grf_ue_bridge.learned_association_tracker_v8 import tracker_class
    torch.set_num_threads(1);source_cfg=read(checked(cfg['source_config']));sources=[s for s in source_cfg['sources'] if s['domain']=='real' and s['game']==fold];require(len(sources)==1,'一个heldout对应一个完整序列')
    source=sources[0];frames=rows(checked(source['cache']));require(len(frames)==750 and source['sequence']==SEQUENCE[fold],'只准完整750帧')
    pose_sha=cfg['tracking']['pose_checkpoint_sha256'];require(isinstance(pose_sha,str) and len(pose_sha)==64,'root须绑定真实共享PT Pose checkpoint')
    model=normalizer=binding=None
    if mode=='learned':require(run is not None,'已训练run缺失');model,normalizer,binding=load_complete(run,cfg,sha(config),fold)
    tracker=tracker_class()(mode=mode,model=model,normalizer=normalizer,use_pose=(binding['arm'].startswith('pose_') if binding else True),pose_source_sha256=pose_sha,fixed_detection_sha256=source['cache']['sha256'])
    output.mkdir(parents=True);(output/'data').mkdir();text=[];counts=[]
    for frame in frames:
        tracks=tracker.update_frame(frame);counts.append(len(tracks))
        for row in tracks:
            x1,y1,x2,y2,identity,score=row[:6];text.append(','.join(map(str,[frame['frame_number'],int(identity),float(x1),float(y1),float(x2-x1),float(y2-y1),float(score),-1,-1,-1])))
    file=output/'data'/(source['sequence']+'.txt');file.write_text('\n'.join(text)+('\n' if text else ''),encoding='utf-8')
    receipt=dict(schema='v8_independent_tracking',status='complete',protocol_sha256=sha(config),mode=mode,fold=fold,sequence=source['sequence'],frames=750,tracked_rows=len(text),frame_counts=counts,mot_sha256=sha(file),cache=source['cache'],binding=binding,trained_checkpoint=(dict(path=str(Path(run)/'last.pt'),sha256=sha(Path(run)/'last.pt')) if run else None),sources=read(checked(cfg['bundle_manifest']))['files'],audit=tracker.audit,GT_read=False,GPU_used=False,test_read=False)
    (output/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return receipt
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--fold',choices=GAMES,required=True);p.add_argument('--mode',choices=('PT_bbox','PT_static_pose','learned'),required=True);p.add_argument('--run',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if a.execute:print(json.dumps(execute(a.config,a.fold,a.mode,a.output,a.run),ensure_ascii=False))
    else:print(json.dumps(dict(status='readonly_candidate_no_tracking',config_sha256=sha(a.config),fold=a.fold,mode=a.mode)))
