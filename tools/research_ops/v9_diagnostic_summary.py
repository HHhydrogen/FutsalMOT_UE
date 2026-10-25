"""汇合v9已完成诊断；新增颜色/纹理分离只用已算特征，不重读媒体。"""
import argparse,hashlib,importlib.util,json,statistics,sys
from pathlib import Path
R=Path('D:/projects/FutsalMOT_Research');V=R/'pose/pose_quality_v9'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def execute(config):
    cfg=read(config)
    for k in ('diagnostic','domain','free_state'):
        assert sha(cfg[k]['path'])==cfg[k]['sha256']
    d=read(cfg['diagnostic']['path']);domain=read(cfg['domain']['path']);free=read(cfg['free_state']['path']);assert d['status']=='complete_no_training_updates' and domain['status']=='complete_no_tracking_training' and free['status']=='complete_three_fixed_free_motion_reference_states'
    module_path=Path(cfg['domain_module']['path']);assert sha(module_path)==cfg['domain_module']['sha256'];spec=importlib.util.spec_from_file_location('fixed_domain_module',module_path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    rows=read(Path(cfg['domain']['path']).with_name('selected_crops_features.json'))
    for row in rows:
        for part,sl in [('color',slice(0,24)),('texture',slice(24,None))]:
            row[part]=row['whole'][sl]
            if row['domain']=='synthetic':row[part+'_red']=row['whole_red'][sl]
    separated={part:module.linear_probe([r for r in rows if r['split']=='train'],[r for r in rows if r['split']=='heldout_time'],part) for part in ('color','texture')}
    windows=[]
    for split in ('train_R','train_S','heldout_teacher_history'):
        subset=[x for x in d['model_window_reports'] if x['split']==split and x['restriction']=='all' and x['perturbation']=='clean']
        windows.append(dict(split=split,models={m:{k:statistics.mean(x['models'][m][k] for x in subset) for k in ('window_BCE','AUC','accuracy')} for m in ('motion_RS','pose_RS')}))
    sensitivity={}
    for corruption,restriction in [('clean','all'),('clean','mask'),('clean','coords'),('clean','zero'),('clean','limbs'),('drop','all'),('jitter','all'),('both','all')]:
        subset=[x for x in d['model_window_reports'] if x['split']=='heldout_teacher_history' and x['restriction']==restriction and x['perturbation']==corruption];sensitivity[corruption+'_'+restriction]={k:statistics.mean(x['models']['pose_RS'][k] for x in subset) for k in ('window_BCE','AUC','accuracy')}
    strata={}
    subset=[x for x in d['model_window_reports'] if x['split']=='heldout_teacher_history' and x['restriction']=='all' and x['perturbation']=='clean']
    for group in ('common_limbs_lt6','common_limbs_ge6'):strata[group]={m:{k:statistics.mean(x['models'][m][group][k] for x in subset if x['models'][m][group] is not None) for k in ('window_BCE','AUC','accuracy')} for m in ('motion_RS','pose_RS')}
    import numpy as np
    old=read(cfg['v8_protocol']['path']);sys.path[:0]=[str(Path(old['bundle'])/'python/src'),str(Path(__file__).resolve().parent)];import v8_pairs
    sources=read(old['source_config']['path'])['sources'];teams={t:[] for t in ('L','R')};angle_stats=[]
    for src in sources:
        frames,_=v8_pairs.load_source(src);angles={k:[] for k in ('elbow','knee')}
        for frame in frames.values():
            for det in frame['detections']:
                if frame['labels'][det['uid']]['state']!='matched':continue
                for tag,(a,b,c) in [('elbow',(5,7,9)),('elbow',(6,8,10)),('knee',(11,13,15)),('knee',(12,14,16))]:
                    if not all(det['geometry_valid'][j] for j in (a,b,c)):continue
                    x=np.asarray(det['xy_px'][a])-det['xy_px'][b];y=np.asarray(det['xy_px'][c])-det['xy_px'][b];norm=np.linalg.norm(x)*np.linalg.norm(y)
                    if norm>1e-8:angles[tag].append(float(np.degrees(np.arccos(np.clip(x@y/norm,-1,1)))))
        angle_stats.append(dict(sequence=src['sequence'],domain=src['domain'],angles={k:dict(n=len(v),p10=float(np.quantile(v,.1)),median=float(np.median(v)),p90=float(np.quantile(v,.9))) for k,v in angles.items()}))
        if src['domain']=='synthetic':
            for row in rows:
                if row['sequence']!=src['sequence']:continue
                label=frames[row['frame_index']]['labels'][row['uid']];team=str(label['gt_id'])[0];assert team in teams;teams[team].append(row['upper'][:24])
    means={team:np.asarray(v).mean(0) for team,v in teams.items()};cosine=float(means['L']@means['R']/(np.linalg.norm(means['L'])*np.linalg.norm(means['R'])))
    shirt=dict(sample_count={k:len(v) for k,v in teams.items()},upper_HSV_histogram_cosine_L_R=cosine,meaning='selected matched torso crops, background/lighting also contribute; not proof all assets/materials identical')
    out=dict(status='complete_readonly_diagnostic_synthesis',classification=windows,counterfactual_sensitivity=sensitivity,common_limb_strata=strata,appearance_color_texture_probes=separated,synthetic_shirt_similarity=shirt,predicted_2D_angle_distributions=angle_stats,free_state=free,diagnostic_sources={k:cfg[k] for k in ('diagnostic','domain','free_state')},formal_training_updates=0,test_read=False,causality='domain separability and prediction noise associations do not establish photorealism as causal factor; actual v9 retrained ablations required')
    output=Path(cfg['output']);assert V in output.parents and not output.exists();output.parent.mkdir(parents=True)
    with output.open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(dict(status=out['status'],appearance=separated,shirt=shirt,strata=strata),ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);execute(p.parse_args().config)
