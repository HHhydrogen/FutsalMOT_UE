"""v7 CPU静态关联敏感度候选；默认inspect，root冻结后才显式replay，无GT/模型/GPU。"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
BUNDLE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BUNDLE/'python/src'))
RESEARCH=Path('D:/projects/FutsalMOT_Research');BASE=RESEARCH/'pose/association_dev_a01';CONTROL=BASE/'v6_crop/control_a01'
MODELS=['pretrained']+[f'{arm}_seed{seed}' for seed in (20261024,20261025,20261026) for arm in ('R3','R3S_blue','R3S_terracotta')]
SEQUENCES=('SNMOT-151','SNMOT-152','SNMOT-153')
def require(ok,message):
    if not ok:raise ValueError(message)
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def bind(path):return dict(path=str(Path(path).resolve()),sha256=sha(path))
def checked(ref):
    path=Path(ref['path']).resolve();require(path.is_file() and sha(path)==ref['sha256'],'冻结文本/源码身份变化:'+str(path));return path

def prepare(output):
    output=Path(output).resolve();require(BASE/'v7_sensitivity' in output.parents and not output.exists(),'全新DResearch/v7候选，不覆盖')
    state=read(CONTROL/'driver_state.json');require(state['status']=='complete_all_ten_models_crop_tracking' and state['completed']==MODELS,'原v6十模型未完整结束')
    checked(state['summary']);files=[]
    for relative in ('tools/research_ops/v7_sensitivity.py','python/src/grf_ue_bridge/__init__.py','python/src/grf_ue_bridge/pose_association_contract_v2.py','python/src/grf_ue_bridge/pose_bytetrack_v2.py','python/src/grf_ue_bridge/pose_association_sensitivity_v7.py'):
        source=BUNDLE/relative;files.append(dict(path=relative,sha256=sha(source),size=source.stat().st_size))
    files.sort(key=lambda row:row['path']);identity=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest();bundle=RESEARCH/'code'/identity
    if not bundle.exists():
        bundle.mkdir(parents=True)
        for item in files:
            target=bundle/item['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(BUNDLE/item['path'],target)
    else:
        for item in files:require(sha(bundle/item['path'])==item['sha256'],'现有bundle不可覆盖')
    output.mkdir(parents=True)
    manifest=output/'bundle_manifest.json';manifest.write_text(json.dumps(dict(files=files,canonical_git_root=str(BUNDLE)),indent=2)+'\n',encoding='utf-8')
    models={}
    for key in MODELS:
        path=CONTROL/key/'attachment/crop_attachment_manifest.json';record=read(path)
        models[key]=dict(manifest=bind(path),records=record['attachments'],model_sha256=record['checkpoint']['sha256'],tracking_receipt=bind(CONTROL/key/'tracking/receipt.json'),
            static_MOT={sequence:bind(CONTROL/key/'tracking/data'/(sequence+'.txt')) for sequence in SEQUENCES})
    config=dict(schema='futsalmot_v7_PT_state_association_sensitivity_candidate',status='candidate_not_root_authorized',approved_by=None,execution_authorized=False,
        bundle=str(bundle),bundle_manifest=bind(manifest),source_v6_summary=state['summary'],source_v6_state=bind(CONTROL/'driver_state.json'),
        raw_manifest=bind(BASE/'raw_detections/cache_manifest.json'),raw_jsonl=read(BASE/'raw_detections/cache_manifest.json')['detections_jsonl'],models=models,
        source_association_rule=bind(BUNDLE/'Saved/Pose17Development/association_execution_a01/protocol.json'),
        lambda0_receipt=bind(BASE/'bbox_lambda0/receipt.json'),lambda0_MOT={sequence:bind(BASE/'bbox_lambda0/data'/(sequence+'.txt')) for sequence in SEQUENCES},
        pose_lambda=.1,sigma=.1,min_joints=6,joint_indices=list(range(5,17)),max_frame_gap=30,bbox_gate_thresholds=[.8,.7],low_score_stage='unchanged_upstream_bbox_only',
        reference='actual_pretrained_static_lambda01_track_states; other_models_evaluated_at_same_last_raw_UID_and_Kalman_centers',
        row_gap='row_best_to_second_gap; NOT global_Hungarian_margin',inversion_diagnostic=dict(model='pretrained',transform='1-pose_cost_only_for_original_valid_pairs',pose_lambda=.1,not_model_prediction=True,not_mainline_metric=True),
        output=str(BASE/'v7_sensitivity/replay_a01'),GT_read=False,final116187_sealed=True,new_training_updates=0,models_loaded=False)
    (output/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(status='candidate_installed_no_replay',config=str(output/'config.json'),bundle=str(bundle))))

def load(config_path):
    config=read(config_path);bundle=Path(config['bundle']).resolve();require(Path(__file__).resolve()==bundle/'tools/research_ops/v7_sensitivity.py' and bundle.parent==RESEARCH/'code','从DResearch独立bundle执行')
    manifest=read(checked(config['bundle_manifest']));require(bundle.name==hashlib.sha256(json.dumps(manifest['files'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),'内容地址变化')
    for item in manifest['files']:require(sha(bundle/item['path'])==item['sha256'],'源码变化')
    require(list(config['models'])==MODELS and config['pose_lambda']==.1 and config['bbox_gate_thresholds']==[.8,.7] and config['sigma']==.1 and config['min_joints']==6 and config['max_frame_gap']==30,'禁止搜索/暗改原参数')
    state=read(checked(config['source_v6_state']));require(state['status']=='complete_all_ten_models_crop_tracking' and state['completed']==MODELS,'v6源任务非完整终态');checked(config['source_v6_summary'])
    return config

def text_MOT(frames,outputs):
    lines=[]
    for frame,values in zip(frames,outputs):
        for row in values:
            x,y,r,b,track_id,score,_,_=map(float,row);lines.append(','.join([str(frame['frame_number']),str(int(track_id))]+[format(value,'.17g') for value in (x,y,r-x,b-y,score)]+['-1']*3))
    return '\n'.join(lines)+('\n' if lines else '')

def replay(config_path):
    config=load(config_path);require(config['execution_authorized'] is True and config['approved_by']=='root','未root启用，不执行真实replay')
    output=Path(config['output']).resolve();require(BASE/'v7_sensitivity' in output.parents and not output.exists(),'新输出，不覆盖/隐式重跑')
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',YOLO_AUTOINSTALL='false',YOLO_OFFLINE='true',YOLO_CONFIG_DIR=str(BASE/'v7_sensitivity/_runtime/ultralytics'),MPLCONFIGDIR=str(BASE/'v7_sensitivity/_runtime/matplotlib'))
    sys.path.append(str(RESEARCH/'runtime_dependencies'))
    import torch
    import numpy as np
    torch.set_num_threads(1)
    from grf_ue_bridge import pose_bytetrack_v2 as original
    from grf_ue_bridge.pose_association_sensitivity_v7 import instrumented_reference_class
    raw=checked(config['raw_jsonl']);frames=[json.loads(line) for line in raw.read_text(encoding='utf-8').splitlines() if line]
    require(len(frames)==450 and sum(len(frame['detections']) for frame in frames)==6901,'必须原450帧/6901raw')
    wanted=('schema','detection_id','source_index','class_id','fixed_detection_score','bbox_xywh_px','xy_px','geometry_valid','coordinate_space','source','validity_method','frame_index','sequence_id','camera_id','model_sha256','fixed_detection_set_sha256','prediction_valid','physical_visibility','visibility_state')
    models={}
    for key,entry in config['models'].items():
        manifest=read(checked(entry['manifest']));require(manifest['status']=='complete_crop_pose_attachment_not_tracking','不可用smoke/原fullframe附件');source=checked(entry['records']);records={}
        for line in source.read_text(encoding='utf-8').splitlines():
            if not line:continue
            frame=json.loads(line);require(frame['schema']=='futsalmot_fixed_detection_crop_pose_frame_v6','不是实际v6 crop')
            for row in frame['attachments']:
                require(row['detection_id'] not in records and row['visibility_state']==['unknown']*17,'UID重复或伪可见性');records[row['detection_id']]={name:row[name] for name in wanted}
        require(len(records)==6901,'模型UID不完整');models[key]=records
    output.mkdir(parents=True);trace=(output/'PT_state_cost_matrices.partial.jsonl').open('x',encoding='utf-8');aggregates={};events=0
    def sink(event):
        nonlocal events
        events+=1;trace.write(json.dumps(event,separators=(',',':'),allow_nan=False)+'\n')
        for key,detail in event['models'].items():
            counts=aggregates.setdefault(key,Counter());counts.update(detail['audit']);counts.update({name:detail['difference_vs_same_PT_states'][name] for name in ('cells_changed_exact','rows_any_candidate_rank_changed','rows_minimizer_set_changed','assignment_threshold_eligibility_changed_inside_bbox_gate')})
            if key=='pretrained':counts['rows_with_at_least_two_competing_candidates']+=event['pretrained_profile']['rows_with_at_least_two_competing_candidates'];counts['columns_with_at_least_two_competing_candidates']+=event['pretrained_profile']['columns_with_at_least_two_competing_candidates']
    reproduction={};lambda0={}
    try:
        for sequence in SEQUENCES:
            selected=[frame for frame in frames if frame['sequence_id']==sequence]
            for key in MODELS:
                poses={frame['frame_index']:{det['detection_id']:models[key][det['detection_id']] for det in frame['detections']} for frame in selected}
                if key=='pretrained':
                    Reference=instrumented_reference_class(models,sink);tracker=Reference(pose_lambda=.1,fixed_detection_set_sha256=config['raw_manifest']['sha256'],model_sha256=config['models'][key]['model_sha256'])
                    outputs=[tracker.update_frame(frame,poses[frame['frame_index']]).copy() for frame in selected]
                else:outputs,_,_=original.run_sequence(selected,fixed_sha=config['raw_manifest']['sha256'],pose_lambda=.1,model_sha=config['models'][key]['model_sha256'],poses_by_frame=poses)
                reference=checked(config['models'][key]['static_MOT'][sequence]);exact=text_MOT(selected,outputs)==reference.read_text(encoding='utf-8');require(exact,'静态规则未精确复现既有v6 MOT：'+key+'/'+sequence)
                reproduction.setdefault(key,{})[sequence]=dict(MOT_bytes_exact=True,reference_sha256=sha(reference))
            proof,outputs=original.verify_lambda_zero(selected,config['raw_manifest']['sha256'],return_outputs=True)
            expected=checked(config['lambda0_MOT'][sequence]);require(text_MOT(selected,outputs)==expected.read_text(encoding='utf-8'),'lambda0不符既有bbox基线');lambda0[sequence]=proof
        trace.close();(output/'PT_state_cost_matrices.partial.jsonl').rename(output/'PT_state_cost_matrices.jsonl')
        report=dict(schema='futsalmot_v7_PT_state_static_sensitivity_report',status='complete_CPU_diagnostic_no_GT_metrics',static_reproduction=reproduction,lambda0_equivalence=lambda0,matrix_events=events,
            counts={key:dict(value) for key,value in aggregates.items()},source_config_sha256=sha(config_path),GT_read=False,models_loaded=False,GPU_used=False,new_training_updates=0,
            interpretation=['all ten cost matrices conditional on same actual PT trajectory states and raw inputs','row gap is row-local only, not global Hungarian margin','PT cost inversion diagnostic is not a model prediction or mainline score','low score stage remains upstream bbox only','same game9; final116/187 sealed'])
        (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(status=report['status'],matrix_events=events)))
    except BaseException as error:
        trace.close();(output/'failure.json').write_text(json.dumps(dict(status='failed_preserved_no_metrics',error_type=type(error).__name__,error=str(error)))+'\n',encoding='utf-8');raise

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('operation',choices=('prepare','inspect','replay'),default='inspect',nargs='?');parser.add_argument('--config',type=Path);parser.add_argument('--output',type=Path);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if args.operation=='prepare':require(args.output is not None,'候选目录必需');prepare(args.output);return
    require(args.config is not None,'需要明确候选/冻结config')
    if args.operation!='replay' or not args.execute:
        config=load(args.config);print(json.dumps(dict(status='CPU_candidate_no_replay',models=len(config['models']),execution_authorized=config['execution_authorized'],GT_read=False,GPU_used=False)));return
    replay(args.config)
if __name__=='__main__':main()
