"""v9只读CPU诊断：固定v8模型/窗口，不训练，不访问封存测试或媒体。"""
import argparse,hashlib,json,math,os,statistics,sys,time
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2];RESEARCH=Path('D:/projects/FutsalMOT_Research')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def ref(p):return dict(path=str(p),sha256=sha(p))
def write(p,value):
    with p.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def quantiles(values):
    import numpy as np
    return dict(n=len(values),p10=float(np.quantile(values,.1)),median=float(np.median(values)),p90=float(np.quantile(values,.9))) if values else dict(n=0)
def metric(logits,labels,windows):
    import numpy as np
    logits=np.asarray(logits,dtype=float);y=np.asarray(labels,dtype=int);bce=np.maximum(logits,0)-logits*y+np.log1p(np.exp(-np.abs(logits)));pred=logits>=0
    unique=np.unique(windows);window_bce=float(np.mean([bce[windows==i].mean() for i in unique]));pos=logits[y==1];neg=logits[y==0]
    if len(pos) and len(neg):
        ordered=np.sort(neg);auc=float(np.mean((np.searchsorted(ordered,pos,side='left')+np.searchsorted(ordered,pos,side='right'))/2)/len(neg))
    else:auc=None
    return dict(known_pairs=len(y),positive_pairs=int(y.sum()),window_count=len(unique),window_BCE=window_bce,pair_BCE=float(bce.mean()),accuracy=float((pred==y).mean()),AUC=auc,positive_recall=float(pred[y==1].mean()) if len(pos) else None,negative_recall=float((~pred[y==0]).mean()) if len(neg) else None)
def execute(config):
    started=time.perf_counter();cfg=read(config);require(cfg['approved_by']=='root' and cfg['training_updates_authorized']==0,'只读诊断准入')
    for f in cfg['code_files']:require(sha(ROOT/f['path'])==f['sha256'],'诊断代码改变')
    old_path=Path(cfg['v8_protocol']['path']);require(sha(old_path)==cfg['v8_protocol']['sha256'],'原协议变化');old=read(old_path);old_bundle=Path(old['bundle'])
    for f in read(old['bundle_manifest']['path'])['files']:require(sha(old_bundle/f['path'])==f['sha256'],'v8数值闭包变化')
    sys.path[:0]=[str(old_bundle/'python/src'),str(old_bundle/'tools/research_ops'),str(ROOT/'tools/research_ops')]
    from v8_track import load_complete
    import v8_pairs
    from grf_ue_bridge.learned_association_features_v8 import features,candidate_gate
    sys.path.insert(0,str(ROOT/'python/src'))
    # 新模块与冻结v8包共享namespace，不替换已加载的v8特征。
    import grf_ue_bridge;grf_ue_bridge.__path__.append(str(ROOT/'python/src/grf_ue_bridge'))
    from grf_ue_bridge.pose_quality_features_v9 import quality,restrict,perturb
    import numpy as np,torch
    torch.set_num_threads(1);output=Path(cfg['output']);require(RESEARCH/'pose/pose_quality_v9' in output.parents and not output.exists(),'全新v9输出')
    output.mkdir(parents=True);write(output/'started.json',dict(config_sha256=sha(config),status='started_no_updates'))
    sources=read(old['source_config']['path'])['sources'];heldout={};domain_stats=[]
    for source in sources:
        frames,labels=v8_pairs.load_source(source);limbs=[];scores=[];heights=[]
        for frame in frames.values():
            for d in frame['detections']:limbs.append(sum(d['geometry_valid'][5:]));scores.append(d['score']);heights.append(d['bbox_xywh_px'][3]/d['image_wh'][1])
        domain_stats.append(dict(sequence=source['sequence'],domain=source['domain'],frames=len(frames),detections=len(limbs),valid_at_least_6_limbs_fraction=float(np.mean(np.asarray(limbs)>=6)),valid_limb_count=quantiles(limbs),score=quantiles(scores),relative_height=quantiles(heights),GT_match_labels=labels))
        if source['domain']=='real':
            pool=v8_pairs.BalancedPool([(source['game'],gap) for gap in v8_pairs.GAPS])
            for window in v8_pairs.enumerate_windows(source,frames,candidate_gate):pool.add(window)
            heldout[source['game']]=pool.finish()
    reports=[];scales={};settings=[('clean','all'),('clean','mask'),('clean','coords'),('clean','zero'),('clean','limbs'),('drop','all'),('jitter','all'),('both','all')]
    for fold in ('game4','game6','game9'):
        real=list(v8_pairs.rows(old['folds'][fold]['real_pool']['path']));synthetic=list(v8_pairs.rows(old['synthetic_pool']['path']));sets={'train_R':real,'train_S':synthetic,'heldout_teacher_history':heldout[fold]};quality_values=[]
        for w in real:
            for c in w['candidates']:
                q=quality(features(w['history'],c['prediction']))
                if c['label']==1 and q['common_limbs']>=6 and q['shape_change_proxy'] is not None:quality_values.append(q['shape_change_proxy'])
        scale=max(.03,float(np.quantile(quality_values,.75))) if quality_values else .03
        scales[fold]=dict(shape_change_scale=scale,fit_scope='positive known-label train_R only',train_pool=old['folds'][fold]['real_pool'],samples=len(quality_values),quantile=.75,floor=.03,not_physical_noise_truth=True)
        for seed in (20261024,20261025,20261026):
            models={}
            for name in ('motion_RS','pose_RS'):
                run=Path(cfg['v8_control'])/'runs'/fold/str(seed)/name/'training';models[name]=load_complete(run,old,sha(old_path),fold)
            normalizer=models['pose_RS'][1]
            for split,windows in sets.items():
                use_settings=settings if split=='heldout_teacher_history' else settings[:1]
                for perturbation,restriction in use_settings:
                    vectors=[];labels=[];indices=[];common=[];changes=[];clips=[]
                    for index,w in enumerate(windows):
                        for c in w['candidates']:
                            if c['label'] is None:continue
                            h,p=perturb(w['history'],c['prediction'],perturbation,context='fixed_v9_diagnostic');raw=features(h,p);z=normalizer.transform(raw,use_pose=True);q=quality(raw)
                            vectors.append(restrict(z,restriction));labels.append(c['label']);indices.append(index);common.append(q['common_limbs']);changes.append(q['shape_change_proxy']);clips.append(sum(abs(x)>=5 for x in z[24:])/170)
                    x=torch.tensor(vectors,dtype=torch.float32);y=np.array(labels);ids=np.array(indices);common=np.array(common);values={}
                    with torch.inference_mode():
                        for name,(model,_,binding) in models.items():
                            actual=x.clone()
                            if name=='motion_RS':actual[:,24:]=0
                            logits=model(actual).reshape(-1).numpy();detail=metric(logits,y,ids)
                            for tag,mask in [('common_limbs_lt6',common<6),('common_limbs_ge6',common>=6)]:
                                detail[tag]=metric(logits[mask],y[mask],ids[mask]) if mask.any() else None
                            values[name]=detail
                    reports.append(dict(fold=fold,seed=seed,split=split,perturbation=perturbation,restriction=restriction,models=values,common_limbs=quantiles(common.tolist()),shape_change_proxy=quantiles([x for x in changes if x is not None]),pose_feature_clip_fraction=statistics.mean(clips)))
        print(json.dumps(dict(fold=fold,status='diagnostic_complete',reports=len(reports))),flush=True)
    for fold,value in scales.items():write(output/f'quality_scale_{fold}.json',value)
    result=dict(schema='v9_frozen_model_pose_diagnostic',status='complete_no_training_updates',v8_protocol=cfg['v8_protocol'],config_sha256=sha(config),domain_stats=domain_stats,quality_scales=scales,model_window_reports=reports,new_optimizer_updates=0,GPU_used=False,test_read=False,limitations=['counterfactual feature deletion and perturbation are diagnostics, not retrained ablations','heldout windows use teacher-forced trusted histories, not free tracker states','temporal changes combine genuine motion with prediction error','real football lacks GT Pose; geometry validity is not accuracy'],wall_seconds=time.perf_counter()-started)
    write(output/'report.json',result);print(json.dumps(dict(status=result['status'],reports=len(reports),wall_seconds=result['wall_seconds'])))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);a=p.parse_args();os.environ['CUDA_VISIBLE_DEVICES']='-1';execute(a.config)
