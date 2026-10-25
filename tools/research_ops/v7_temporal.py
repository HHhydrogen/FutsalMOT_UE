"""v7十模型时序CPU串行候选；不载权重、不GPU、不改训练量/附件/可见性。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
BUNDLE=Path(__file__).resolve().parents[2];sys.path[:0]=[str(BUNDLE/'python/src'),str(Path(__file__).resolve().parent)]
RESEARCH=Path('D:/projects/FutsalMOT_Research');BASE=RESEARCH/'pose/association_dev_a01';V6=BASE/'v6_crop/control_a01'
MODELS=['pretrained']+[f'{arm}_seed{seed}' for seed in (20261024,20261025,20261026) for arm in ('R3','R3S_blue','R3S_terracotta')];SEQUENCES=('SNMOT-151','SNMOT-152','SNMOT-153')
def require(ok,message):
    if not ok:raise ValueError(message)
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def bind(path):return dict(path=str(Path(path).resolve()),sha256=sha(path))
def checked(ref):
    path=Path(ref['path']).resolve();require(path.is_file() and sha(path)==ref['sha256'],'绑定变化:'+str(path));return path

def prepare(output):
    output=Path(output).resolve();require(BASE/'v7_temporal' in output.parents and not output.exists(),'需全新DResearch/v7_temporal候选')
    state=read(V6/'driver_state.json');require(state['status']=='complete_all_ten_models_crop_tracking' and state['completed']==MODELS,'v6不完整')
    names=['tools/research_ops/v7_temporal.py','tools/research_ops/v7_temporal_metric.py']+[f'python/src/grf_ue_bridge/{name}' for name in ('__init__.py','pose_association_contract_v2.py','pose_bytetrack_v2.py','pose_association_trackeval_v1.py','pose_temporal_shape_v7.py','pose_temporal_tracker_v7.py')]
    files=sorted([dict(path=name,sha256=sha(BUNDLE/name),size=(BUNDLE/name).stat().st_size) for name in names],key=lambda row:row['path']);identity=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest();bundle=RESEARCH/'code'/identity
    if not bundle.exists():
        bundle.mkdir(parents=True)
        for row in files:target=bundle/row['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(BUNDLE/row['path'],target)
    else:
        for row in files:require(sha(bundle/row['path'])==row['sha256'],'bundle不可覆盖')
    output.mkdir(parents=True);manifest=output/'bundle_manifest.json';manifest.write_text(json.dumps(dict(files=files),indent=2)+'\n',encoding='utf-8');models={}
    for key in MODELS:
        ref=V6/key/'attachment/crop_attachment_manifest.json';attachment=read(ref);models[key]=dict(manifest=bind(ref),records=attachment['attachments'],model_sha256=attachment['checkpoint']['sha256'],static_metrics=bind(V6/key/'metrics/report.json'))
    config=dict(schema='futsalmot_temporal_pose_protocol_v7',status='candidate_not_root_frozen',approved_by=None,execution_authorized=False,bundle=str(bundle),bundle_manifest=bind(manifest),source_v6_summary=state['summary'],models=models,
        raw=read(BASE/'raw_detections/cache_manifest.json')['detections_jsonl'],raw_manifest=bind(BASE/'raw_detections/cache_manifest.json'),lambda0_receipt=bind(BASE/'bbox_lambda0/receipt.json'),original_rule=bind(BUNDLE/'Saved/Pose17Development/association_execution_a01/protocol.json'),
        parameters=dict(actual_history_records=3,OLS_age_from_latest_observation_max=3,prediction_gap_max=3,per_joint_valid_observations_min=2,per_joint_latest_valid_prediction_gap_max=3,bbox_margin=.25,min_limbs=6,sigma=.1,pose_lambda=.1,reactivation_clear=True,low_score_stage='unchanged_bbox_only'),
        output=str(BASE/'v7_temporal/control_a01'),new_training_updates=0,all_ten_v5_weights_reused=True,GT_filtering=False,final116187_sealed=True)
    (output/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(status='temporal_candidate_installed_no_replay',config=str(output/'config.json'),bundle=str(bundle))))

def load(path):
    cfg=read(path);bundle=Path(cfg['bundle']);manifest=read(checked(cfg['bundle_manifest']));require(Path(__file__).resolve()==bundle/'tools/research_ops/v7_temporal.py','从DResearch bundle执行')
    require(bundle.name==hashlib.sha256(json.dumps(manifest['files'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),'bundle身份变化')
    for row in manifest['files']:require(sha(bundle/row['path'])==row['sha256'],'源码变化')
    require(list(cfg['models'])==MODELS and cfg['parameters']==dict(actual_history_records=3,OLS_age_from_latest_observation_max=3,prediction_gap_max=3,per_joint_valid_observations_min=2,per_joint_latest_valid_prediction_gap_max=3,bbox_margin=.25,min_limbs=6,sigma=.1,pose_lambda=.1,reactivation_clear=True,low_score_stage='unchanged_bbox_only'),'不能事后搜索时序参数/筛model')
    checked(cfg['source_v6_summary']);checked(cfg['original_rule']);return cfg,manifest['files']

def replay(path):
    cfg,sources=load(path);require(cfg['execution_authorized'] is True and cfg['approved_by']=='root','未root启用，不执行真实CPU对照')
    root=Path(cfg['output']).resolve();require(BASE/'v7_temporal' in root.parents and not root.exists(),'新control，不覆盖partial');os.environ.update(CUDA_VISIBLE_DEVICES='-1',YOLO_AUTOINSTALL='false',YOLO_OFFLINE='true',YOLO_CONFIG_DIR=str(BASE/'v7_temporal/_runtime/ultralytics'),MPLCONFIGDIR=str(BASE/'v7_temporal/_runtime/matplotlib'))
    sys.path.append(str(RESEARCH/'runtime_dependencies'))
    import torch
    import numpy as np
    import inspect
    import ultralytics
    import lap
    torch.set_num_threads(1)
    from grf_ue_bridge import pose_bytetrack_v2 as original
    from grf_ue_bridge.pose_temporal_tracker_v7 import temporal_tracker_class
    from ultralytics.trackers.byte_tracker import BYTETracker
    from v7_temporal_metric import evaluate
    frames=[json.loads(line) for line in checked(cfg['raw']).read_text(encoding='utf-8').splitlines() if line];require(len(frames)==450 and sum(len(frame['detections']) for frame in frames)==6901,'原450/6901范围改变')
    baseline=read(checked(cfg['lambda0_receipt']));base_identity=baseline['identity'];require(sha(original.__file__)==base_identity['implementation_sha256'] and sha(inspect.getfile(BYTETracker))==base_identity['upstream_bytetrack_sha256'] and ultralytics.__version__==base_identity['ultralytics'] and lap.__version__==base_identity['lap'],'原base依赖变化')
    Tracker=temporal_tracker_class();root.mkdir(parents=True);state=dict(schema='futsalmot_temporal_serial_state_v7',status='running',pid=os.getpid(),protocol_sha256=sha(path),completed=[]);write=lambda filename,value:(root/filename).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');write('state.json',state)
    lambda0={}
    for sequence in SEQUENCES:
        selected=[frame for frame in frames if frame['sequence_id']==sequence];expected,states,_=original.run_sequence(selected,fixed_sha=cfg['raw_manifest']['sha256'],reference=True)
        zero=Tracker(pose_lambda=0.,fixed_detection_set_sha256=cfg['raw_manifest']['sha256']);outputs=[];snapshots=[]
        for frame in selected:outputs.append(zero.update_frame(frame).copy());snapshots.append(original.tracker_state(zero))
        require(all(np.array_equal(a,b) for a,b in zip(expected,outputs)) and states==snapshots,'v7 lambda0未精确复现ByteTrack');lambda0[sequence]=dict(output_arrays_exact=True,Kalman_state_exact=True,frames=150)
    write('lambda0_equivalence.json',lambda0);reports={}
    for key,entry in cfg['models'].items():
        records={}
        for line in checked(entry['records']).read_text(encoding='utf-8').splitlines():
            if line:
                row=json.loads(line);require(row['schema']=='futsalmot_fixed_detection_crop_pose_frame_v6','只消费v6真实附件')
                for record in row['attachments']:require(record['detection_id'] not in records,'重复UID');records[record['detection_id']]=record
        require(len(records)==6901,'附件不完整');folder=root/key/'tracking';folder.mkdir(parents=True);(folder/'data').mkdir();receipt=dict(schema='futsalmot_temporal_pose_tracking_receipt_v7',status='tracking_complete_not_evaluated',protocol_sha256=sha(path),base_identity=base_identity,v7_sources=sources,model_sha256=entry['model_sha256'],pose_lambda=.1,sequences={},GT_read=False,GPU_used=False,new_training_updates=0,source_v6_attachment_manifest=entry['manifest'])
        for sequence in SEQUENCES:
            selected=[frame for frame in frames if frame['sequence_id']==sequence];tracker=Tracker(pose_lambda=.1,fixed_detection_set_sha256=cfg['raw_manifest']['sha256'],model_sha256=entry['model_sha256']);lines=[]
            for frame in selected:
                poses={det['detection_id']:records[det['detection_id']] for det in frame['detections']};output=tracker.update_frame(frame,poses)
                for value in output:
                    x,y,r,b,track_id,score,_,_=map(float,value);lines.append(','.join([str(frame['frame_number']),str(int(track_id))]+[format(item,'.17g') for item in (x,y,r-x,b-y,score)]+['-1']*3))
            target=folder/'data'/(sequence+'.txt');target.write_text('\n'.join(lines)+('\n' if lines else ''),encoding='utf-8');receipt['sequences'][sequence]=dict(frames=150,tracked_rows=len(lines),mot_sha256=sha(target),audit=tracker.audit)
        (folder/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');result=evaluate(folder,root/key/'metrics',cfg,sha(path),base_identity,sources);old=read(checked(entry['static_metrics']))
        deltas={sequence:dict(delta_pp={metric:result['summary'][sequence]['metrics_percent'][metric]-old['summary'][sequence]['metrics_percent'][metric] for metric in ('AssA','HOTA','IDF1')},IDSW_delta_count=result['summary'][sequence]['IDSW_count']-old['summary'][sequence]['IDSW_count']) for sequence in result['summary']}
        used=sum(row['audit'].get('temporal_shape_pairs_used',0) for row in receipt['sequences'].values());reports[key]=dict(summary=result['summary'],vs_same_model_static_v6=deltas,temporal_OLS_pairs=used,temporal_actually_used=used>0,receipt=bind(folder/'receipt.json'),report=bind(root/key/'metrics/report.json'));state['completed'].append(key);write('state.json',state)
        if (root/'STOP_AFTER_CURRENT').exists():state['status']='stopped_user_request';write('state.json',state);return
    write('summary.json',dict(schema='futsalmot_temporal_ten_model_summary_v7',models=reports,all_models_temporal_actually_used=all(row['temporal_actually_used'] for row in reports.values()),new_training_updates=0,all_negative_results_retained=True,limits=['descriptive_same_game9','same_v5_weights_real3000R','unknown_not_upgraded','final116187_sealed']))
    state.update(status='complete_all_ten_temporal_CPU_and_TrackEval',summary=bind(root/'summary.json'));write('state.json',state)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('operation',choices=('prepare','inspect','replay'),default='inspect',nargs='?');parser.add_argument('--config',type=Path);parser.add_argument('--output',type=Path);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if args.operation=='prepare':require(args.output is not None,'需要新候选目录');prepare(args.output);return
    require(args.config is not None,'需要config')
    if args.operation!='replay' or not args.execute:cfg,_=load(args.config);print(json.dumps(dict(status='temporal_CPU_candidate_no_real_replay',models=len(cfg['models']),execution_authorized=cfg['execution_authorized'])));return
    replay(args.config)
if __name__=='__main__':main()
