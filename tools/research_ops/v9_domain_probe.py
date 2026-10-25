"""有限同尺度人物裁剪的R/S外观域差与合成投影吻合诊断；不推断拟真因果。"""
import argparse,hashlib,json,math,os,sys
from collections import OrderedDict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];R=Path('D:/projects/FutsalMOT_Research')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def write(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def describe(image):
    import cv2,numpy as np
    image=cv2.resize(image,(64,128),interpolation=cv2.INTER_AREA);hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV);gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY).astype(float)/255;result=[]
    for j,bound in enumerate((180,256,256)):
        histogram=np.histogram(hsv[:,:,j],bins=8,range=(0,bound))[0].astype(float);result.extend((histogram/histogram.sum()).tolist())
    dx=cv2.Sobel(gray,cv2.CV_64F,1,0);dy=cv2.Sobel(gray,cv2.CV_64F,0,1);gradient=np.hypot(dx,dy);result.extend([float(gray.mean()),float(gray.std()),float(gradient.mean()),float(gradient.std()),float((gradient>.2).mean())]);return result
def auc(score,y):
    import numpy as np
    neg=np.sort(score[y==0]);pos=score[y==1];return float(np.mean((np.searchsorted(neg,pos,'left')+np.searchsorted(neg,pos,'right'))/2)/len(neg))
def linear_probe(train,test,feature):
    import numpy as np
    x=np.asarray([r[feature] for r in train]);y=np.asarray([r['domain']=='synthetic' for r in train],dtype=float);mean=x.mean(0);std=np.maximum(x.std(0),.01);x=(x-mean)/std;w=np.zeros(x.shape[1]);b=0.
    for _ in range(200):
        score=1/(1+np.exp(-np.clip(x@w+b,-30,30)));w-=.1*(x.T@(score-y)/len(y)+.01*w);b-=.1*float((score-y).mean())
    def evaluate(rows):
        a=(np.asarray([r[feature] for r in rows])-mean)/std;labels=np.array([r['domain']=='synthetic' for r in rows]);scores=1/(1+np.exp(-np.clip(a@w+b,-30,30)));return dict(rows=len(rows),accuracy=float(((scores>=.5)==labels).mean()),AUC=auc(scores,labels),synthetic_score_mean=float(scores[labels].mean()),real_score_mean=float(scores[~labels].mean()))
    red=[r for r in test if r['domain']=='synthetic' and feature+'_red' in r]
    red_score=1/(1+np.exp(-np.clip(((np.asarray([r[feature+'_red'] for r in red])-mean)/std)@w+b,-30,30)))
    return dict(train=evaluate(train),heldout_time=evaluate(test),paired_red_synthetic_probability_mean=float(red_score.mean()),fit='48R/48S, train-time-only zscore, fixed logistic L2.01 lr.1 200 steps',meaning='domain distinguishability, not realism score or cause of tracking degradation')
def execute(config):
    cfg=read(config);require(cfg['approved_by']=='root' and cfg['new_optimizer_updates']==0,'只诊断，不训练追踪模型')
    for f in cfg['code_files']:require(sha(ROOT/f['path'])==f['sha256'],'新源码变化')
    old=read(cfg['v8_protocol']['path']);require(sha(cfg['v8_protocol']['path'])==cfg['v8_protocol']['sha256'],'旧绑定变化');bundle=Path(old['bundle']);sys.path[:0]=[str(bundle/'python/src'),str(ROOT/'tools/research_ops')]
    import v8_pairs,cv2,numpy as np
    cv2.setNumThreads(1)
    output=Path(cfg['output']);require(R/'pose/pose_quality_v9' in output.parents and not output.exists(),'全新诊断目录');output.mkdir(parents=True)
    sources=read(old['source_config']['path'])['sources'];selected=[];S_projection=[]
    for source in sources:
        frames,_=v8_pairs.load_source(source);raw={}
        with Path(source['cache']['path']).open(encoding='utf-8') as f:
            for line in f:r=json.loads(line);raw[r['frame_index']]=r
        pools={'train':[],'heldout_time':[]}
        for index,frame in frames.items():
            phase='train' if index<(.6*(750 if source['domain']=='real' else 300)) else 'heldout_time'
            for d in frame['detections']:
                label=frame['labels'][d['uid']]
                if label['state']=='matched':pools[phase].append(dict(source=source,frame=index,prediction=d,GT_identity=label['gt_id'],image_file=raw[index]['image_file']))
        quotas=(16,8) if source['domain']=='real' else (12,6)
        for phase,count in zip(('train','heldout_time'),quotas):
            chosen=sorted(pools[phase],key=lambda d:hashlib.sha256(('v9_domain|'+d['prediction']['uid']).encode()).hexdigest())[:count];require(len(chosen)==count,'预定分层样本不足')
            selected.extend(dict(item,split=phase) for item in chosen)
        if source['domain']=='synthetic':
            with Path(source['annotations']['path']).open(encoding='utf-8') as f:gt={r['frame_index']:{str(o['entity_id']):o for o in r['objects']} for r in map(json.loads,f)}
            groups={name:dict(location_valid_points=0,predicted_geometry_valid_points=0,errors_over_GT_visible_bbox_height=[]) for name in ('head5','limbs12')}
            for index,frame in frames.items():
                for det in frame['detections']:
                    label=frame['labels'][det['uid']]
                    if label['state']!='matched':continue
                    obj=gt[index][label['gt_id']];height=obj['bbox_visible_xywh'][3]
                    for j in range(17):
                        group=groups['head5' if j<5 else 'limbs12']
                        if not obj['location_valid'][j]:continue
                        group['location_valid_points']+=1
                        if det['geometry_valid'][j]:group['predicted_geometry_valid_points']+=1;group['errors_over_GT_visible_bbox_height'].append(math.dist(det['xy_px'][j],obj['uv_px'][j])/height)
            for g in groups.values():
                errors=g.pop('errors_over_GT_visible_bbox_height');g.update(geometry_coverage=g['predicted_geometry_valid_points']/g['location_valid_points'],conditional_median_error_height=float(np.median(errors)) if errors else None,conditional_PCK10=float(np.mean(np.array(errors)<=.1)) if errors else None,conditional_PCK20=float(np.mean(np.array(errors)<=.2)) if errors else None)
            S_projection.append(dict(sequence=source['sequence'],groups=groups,scope='matched detections; projection locations include unknown physical visibility',GT_used_for_training=False))
    cache=OrderedDict();rows=[];display=[]
    def image(path):
        key=str(path)
        if key in cache:value=cache.pop(key);cache[key]=value;return value
        value=cv2.imdecode(np.frombuffer(Path(path).read_bytes(),np.uint8),cv2.IMREAD_COLOR);require(value is not None,'图像无法解码');cache[key]=value
        while len(cache)>2:cache.popitem(last=False)
        return value
    for item in sorted(selected,key=lambda r:(r['image_file'],r['prediction']['uid'])):
        src=item['source'];d=item['prediction'];img=image(item['image_file']);x,y,w,h=d['bbox_xywh_px'];x1=max(0,int(x));y1=max(0,int(y));x2=min(img.shape[1],math.ceil(x+w));y2=min(img.shape[0],math.ceil(y+h));crop=img[y1:y2,x1:x2];require(crop.size>0,'正面积crop')
        upper=crop[int(.15*crop.shape[0]):max(int(.55*crop.shape[0]),int(.15*crop.shape[0])+1),int(.2*crop.shape[1]):max(int(.8*crop.shape[1]),int(.2*crop.shape[1])+1)]
        row=dict(sequence=src['sequence'],domain=src['domain'],frame_index=item['frame'],split=item['split'],uid=d['uid'],image_file=item['image_file'],bbox_xywh_px=d['bbox_xywh_px'],whole=describe(crop),upper=describe(upper))
        if src['domain']=='synthetic':
            red=Path('G:/FutsalMOT_Dataset/v2_pose17_longpair_pilot_a01/groups/seed_00001048/variants/sport_terracotta_v1/cameras')/src['camera']/'rgb'/f'{item["frame"]:06d}.png';other=image(red);redcrop=other[y1:y2,x1:x2];redu=redcrop[int(.15*redcrop.shape[0]):max(int(.55*redcrop.shape[0]),int(.15*redcrop.shape[0])+1),int(.2*redcrop.shape[1]):max(int(.8*redcrop.shape[1]),int(.2*redcrop.shape[1])+1)]
            row.update(whole_red=describe(redcrop),upper_red=describe(redu),red_image_file=str(red),red_usage='appearance-only paired crop at blue bbox, no new detection/Pose/tracking inference')
        rows.append(row)
        if item['split']=='heldout_time':display.append(dict(domain=src['domain'],image=cv2.cvtColor(cv2.resize(crop,(96,192)),cv2.COLOR_BGR2RGB),sequence=src['sequence'],uid=d['uid']))
    train=[r for r in rows if r['split']=='train'];test=[r for r in rows if r['split']=='heldout_time'];require(len(train)==96 and len(test)==48,'固定144个人物crop')
    probes={f:linear_probe(train,test,f) for f in ('whole','upper')}
    result=dict(schema='v9_bounded_domain_and_projection_probe',status='complete_no_tracking_training',config_sha256=sha(config),selection='matched GT player boxes, fixed UID SHA rank; R3seq24each, S4cam18each; time first60% train/last40% heldout across all cameras',crops=len(rows),original_images_not_copied=True,probe=probes,synthetic_projection=S_projection,GT_Pose_used_only_for_diagnostic=True,test116187_read=False,new_tracking_optimizer_updates=0,limitations=['source separability is not causal proof of photorealism effect','indoor futsal vs outdoor football/camera/clothing confound appearance','paired floor effect only tests handcrafted descriptor, not Pose/tracking utility','synthetic projected joint centers/anchors with unknown visibility are not COCO visible GT accuracy'])
    write(output/'report.json',result);write(output/'selected_crops_features.json',rows)
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,6,figsize=(9,6));
    for i,domain in enumerate(('real','synthetic')):
        items=[r for r in display if r['domain']==domain];sequences=sorted({r['sequence'] for r in items});selected=[]
        for turn in range(2):
            for sequence in sequences:
                choices=sorted([r for r in items if r['sequence']==sequence],key=lambda r:r['uid'])
                if turn<len(choices):selected.append(choices[turn])
        for j,item in enumerate(selected[:6]):axes[i,j].imshow(item['image']);axes[i,j].axis('off');axes[i,j].set_title(domain+' / '+item['sequence'],fontsize=7)
    fig.suptitle('Fixed person crops; different scenes, cameras and clothing. Not a realism score.',fontsize=10);fig.tight_layout();fig.savefig(output/'domain_person_crops.png',dpi=140);plt.close(fig);print(json.dumps(dict(status=result['status'],probe=probes)))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);a=p.parse_args();os.environ['CUDA_VISIBLE_DEVICES']='-1';execute(a.config)
