"""v9独立候选协议：复用原窗口/缓存，关闭授权，主54+预登记首seed消融24。"""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tools/research_ops'),str(ROOT/'python/src')]
from v9_control import expected_matrix
R=Path('D:/projects/FutsalMOT_Research');V=R/'pose/pose_quality_v9'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p))
def write(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def prepare(output):
    output=Path(output).resolve();assert V in output.parents and not output.exists();oldp=R/'pose/learned_association_v8/frozen_a02/protocol.json';old=read(oldp);old_bundle=Path(old['bundle']);closed={x['path']:x for x in read(old['bundle_manifest']['path'])['files']}
    legacy=['tools/research_ops/v8_train.py','tools/research_ops/v8_control.py','tools/research_ops/v8_gap_recovery.py','tools/performance/ordered_prefetch.py']+['python/src/grf_ue_bridge/'+x for x in ('__init__.py','learned_association_features_v8.py','learned_association_model_v8.py','learned_association_tracker_v8.py','pose_association_contract_v2.py')]
    new=['tools/research_ops/'+x for x in ('v9_train.py','v9_track.py','v9_metric.py','v9_control.py','v9_analyze.py','v9_budget_audit.py')]+['python/src/grf_ue_bridge/'+x for x in ('pose_quality_features_v9.py','quality_residual_association_v9.py')]
    files=[];sources={}
    for name in legacy:
        source=old_bundle/name;assert sha(source)==closed[name]['sha256'];sources[name]=source;files.append(dict(path=name,sha256=sha(source),size=source.stat().st_size))
    for name in new:source=ROOT/name;sources[name]=source;files.append(dict(path=name,sha256=sha(source),size=source.stat().st_size))
    files=sorted(files,key=lambda x:x['path']);identity=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest();bundle=R/'code'/identity
    if not bundle.exists():
        bundle.mkdir(parents=True)
        for row in files:dest=bundle/row['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(sources[row['path']],dest)
    else:
        for row in files:assert sha(bundle/row['path'])==row['sha256']
    output.mkdir(parents=True);write(output/'bundle_manifest.json',dict(files=files));folds={}
    for game in ('game4','game6','game9'):
        scale=V/f'diagnostic_a02/quality_scale_{game}.json';assert read(scale)['train_pool']==old['folds'][game]['real_pool'];folds[game]=dict(old['folds'][game],quality_scale=ref(scale))
    config=dict(schema='v9_quality_residual_control',approved_by=None,training_authorized=False,tracking_authorized=False,bundle=str(bundle),bundle_manifest=ref(output/'bundle_manifest.json'),v8_protocol=ref(oldp),v8_milestone=ref(R/'pose/learned_association_v8/milestone_complete_a01.json'),v8_analysis=ref(R/'pose/learned_association_v8/control_a02/analysis_a01/report.json'),diagnosis_summary=ref(V/'diagnostic_summary_a01/report.json'),folds=folds,synthetic_pool=old['synthetic_pool'],source_config=old['source_config'],recovery_registry=old['recovery_registry'],pose_checkpoint_sha256=old['tracking']['pose_checkpoint_sha256'],training_matrix=expected_matrix(),parameters=dict(updates=1000,R_per_step=3,S_per_RS_step=1,S_alpha=1/3,lr=.001,weight_decay=.0001,hidden_residual=32,delta_logit_bound=.5,amp=False,prefetch=2,cache_bytes=268435456,checkpoint_interval=50),augmentation=dict(drop_probability=.2,jitter_bbox_std=.03,key='seed/domain/epoch/prediction_UID/joint, shared across windows and matched variants',observation_cache_entries=4096,only_originally_valid_input_joints=True,GT_labels_unchanged=True),architecture=dict(input_dim=195,motion_input_dim=194,residual_input_dim=170,joint_training=True,frozen_previous_motion_RS=False,zero_initial_output=True,all_variants_same_parameter_count=True),progress_definition=dict(primary='gated_RS-minus-capacity_matched_motion_residual_RS AND gated_RS-minus-v8_motion_RS',AssA_min_pp=.5,positive_seed_min=2,nonnegative_game_min=2,HOTA_min_pp=0,IDF1_min_pp=-.5,also_report_pure_R_and_PT=True),test116187_sealed=True,new_images_or_render=False,main_seed_count=3,exploratory_seeds=[20261024])
    write(output/'protocol_candidate.json',config);return dict(status='candidate_no_training',bundle=str(bundle),protocol=str(output/'protocol_candidate.json'),protocol_sha256=sha(output/'protocol_candidate.json'),runs=len(config['training_matrix']))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);print(json.dumps(prepare(p.parse_args().output)))
