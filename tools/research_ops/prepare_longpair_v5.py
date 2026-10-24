"""v5长窗尺度候选：只读标注、共享裁剪表和不可变bundle计划；不读取媒体。"""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
from v5_virtual_crop import location_record

PROJECT=Path(__file__).resolve().parents[2]
DATASET=Path('G:/FutsalMOT_Dataset/v2_pose17_longpair_pilot_a01')
REAL=Path('D:/projects/FutsalMOT_Research/pose/coco2017_location_a01/subset/train2017.location.jsonl')
RESEARCH=Path('D:/projects/FutsalMOT_Research')
FLOORS=('sport_blue_v1','sport_terracotta_v1')
SEEDS=(20261024,20261025,20261026)
POLICY=dict(schema='pose_v5_crop_policy_candidate_v1',selection='all_train_frames_one_stable_hash_entity_per_frame_no_model_outcomes',
    input_size=640,crop_shape='square',minimum_side_px=256,maximum_side_px=2160,anchor='blue_bbox',
    target='real_train_all_person_bbox_height_median_at_640_letterbox',paired_floor_geometry='exact_same_integer_crop_box',
    bbox='clip_half_open',keypoints='xy_translate_then_crop_bounds_valid_then_letterbox',
    visibility='source_unknown_unchanged_never_promote',train_motion_seed=1048,synthetic_dev_motion_seed=1102)

def require(ok,msg):
    if not ok:raise ValueError(msg)

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def rows(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        for line in stream:
            if line.strip():yield json.loads(line)
def stats(values):
    values=sorted(values)
    if not values:return dict(count=0)
    return dict(count=len(values),min=values[0],median=statistics.median(values),mean=statistics.mean(values),max=values[-1],
                p10=values[int((len(values)-1)*.1)],p90=values[int((len(values)-1)*.9)])
def anchor_crop(objects,width,height,target_height,frame_key):
    ordered=sorted(objects,key=lambda item:item['entity_id'])
    require(ordered,'无人物不能构造候选crop')
    index=int(hashlib.sha256(frame_key.encode()).hexdigest()[:16],16)%len(ordered)
    person=ordered[index];x,y,w,h=person['bbox_visible_xywh']
    side=min(width,height,POLICY['maximum_side_px'],max(POLICY['minimum_side_px'],round(h*640/target_height)))
    left=max(0,min(width-side,round(x+w/2-side/2)));top=max(0,min(height-side,round(y+h/2-side/2)))
    return [left,top,side,side],person['entity_id']
def transformed_profile(objects,crop):
    left,top,width,height=crop;heights=[];valid=0;people=0;unknown=0
    for person in objects:
        x,y,w,h=person['bbox_visible_xywh'];cl=max(x,left);cr=min(x+w,left+width);ct=max(y,top);cb=min(y+h,top+height)
        if cr<=cl or cb<=ct:continue
        heights.append((cb-ct)*640/max(width,height));people+=1
        for point,ok,state in zip(person['uv_px'],person['location_valid'],person['visibility_state']):
            if ok and point is not None and left<=point[0]<left+width and top<=point[1]<top+height:valid+=1
            unknown+=state=='unknown'
    return heights,valid,people,unknown

def source_bundle_plan():
    """Git为唯一源；仅登记训练闭包，同一内容摘要目标只需创建一次。"""
    relative=[
        'python/src/grf_ue_bridge/__init__.py',
        'python/src/grf_ue_bridge/coco_pose_dev_eval.py',
        'python/src/grf_ue_bridge/pose_location_dataset_v2.py',
        'python/src/grf_ue_bridge/pose_location_supervision_v2.py',
        'python/src/grf_ue_bridge/pose_location_supervision_v3.py',
        'python/src/grf_ue_bridge/pose_location_supervision_v4.py',
        'python/src/grf_ue_bridge/pose_only_calibration_v3.py',
        'python/src/grf_ue_bridge/pose_xy_head_transfer.py',
        'experiments/sim2real/train_pose_location_control.py',
        'experiments/sim2real/train_pose_location_poseonly_v3.py',
        'experiments/sim2real/train_pose_location_separate_v4.py',
        'experiments/sim2real/run_pose_location_control_windows.py',
        'tools/research_ops/prepare_longpair_v5.py',
        'tools/research_ops/train_longpair_v5.py',
        'tools/research_ops/evaluate_longpair_v5.py',
        'tools/research_ops/run_longpair_v5_control.py',
        'tools/research_ops/validate_longpair_v5_cpu.py',
        'tools/research_ops/v5_numeric_loader.py',
        'tools/research_ops/v5_virtual_crop.py']
    files=[PROJECT/name for name in sorted(relative)]
    entries=[dict(path=p.relative_to(PROJECT).as_posix(),sha256=digest(p),size=p.stat().st_size) for p in files]
    identity=hashlib.sha256(json.dumps(entries,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    git_head=subprocess.run(['git','rev-parse','HEAD'],cwd=PROJECT,capture_output=True,text=True,check=True).stdout.strip()
    return dict(schema='research_content_addressed_bundle_plan_v1',status='plan_only_not_materialized_not_training_authorized',
        canonical_git_root=str(PROJECT),git_head=git_head,source_tree_manifest_sha256=identity,files=entries,
        target=str(RESEARCH/'code'/identity),deduplication='one_immutable_bundle_per_manifest_SHA_reuse_across_all_runs',
        staging='root_must_verify_current_source_SHA_and_create_new_bundle_once_no_overwrite',
        execution='v5 explicit runtime_context separates code_bundle/source_project_root; no fake uproject; imports only bound function AST and approved modules; no new Git',
        data='reference GDataset RGB/mask only; no media copy into bundle or runs',
        incomplete_dependencies='candidate exact training closure; root must verify installed third-party environment and CPU backward before freeze')

def prepare(dataset,real,output):
    dataset=Path(dataset).resolve();real=Path(real).resolve();output=Path(output).absolute()
    require(Path('G:/FutsalMOT_Dataset').resolve() in dataset.parents,'合成数据仅GDataset')
    require(RESEARCH.resolve() in real.parents,'真实元数据仅DResearch')
    saved=PROJECT/'Saved/ResearchPlanning'
    require(saved in output.parents and not output.exists(),'候选输出须为Saved/ResearchPlanning下全新目录')
    index=read(dataset/'dataset.json');require(index['RGB_frames']==4800,'当前长窗数量变化须重新登记')
    real_heights=[];real_points=[]
    for frame in rows(real):
        ratio=640/max(frame['width'],frame['height'])
        for obj in frame['instances']:
            real_heights.append(obj['bbox_xywh_px'][3]*ratio);real_points.append(sum(obj['location_valid']))
    target=statistics.median(real_heights)
    report=dict(schema='longpair_v5_metadata_profile_candidate_v1',not_training=True,media_read=False,media_hash=False,
        actual_real_bbox_height_640=stats(real_heights),real_valid_points_per_person=stats(real_points),
        crop_policy=POLICY,target_anchor_height_px=target,groups={})
    crop_rows=[];virtual_rows=defaultdict(list);references=[dict(path=str(dataset/'dataset.json'),sha256=digest(dataset/'dataset.json')),dict(path=str(real),sha256=digest(real))]
    for group_key,ref in sorted(index['groups'].items()):
        group_path=dataset/ref['path'];group=read(group_path);seed=group['seed'];split=group['split']
        require((seed,split) in [(1048,'train'),(1102,'synthetic_dev')],'禁止扩张split/纳入dev训练')
        group_report={};blue_root=group_path.parent/group['variants'][FLOORS[0]]['directory']
        blue_variant=read(blue_root/'variant.json')
        for camera in sorted(blue_variant['cameras']):
            frames={}
            for floor in FLOORS:
                camera_root=group_path.parent/group['variants'][floor]['directory']/'cameras'/camera
                path=camera_root/'pose2d.jsonl';references.append(dict(path=str(path),sha256=digest(path)))
                frames[floor]=(camera_root,list(rows(path)))
            require(len(frames[FLOORS[0]][1])==len(frames[FLOORS[1]][1])==300,'每机位必须成对300帧')
            for blue,red in zip(frames[FLOORS[0]][1],frames[FLOORS[1]][1]):
                require((blue['source_frame_index'],blue['frame_index'])==(red['source_frame_index'],red['frame_index']),'地板帧配对不同')
                require(sorted(o['entity_id'] for o in blue['objects'])==sorted(o['entity_id'] for o in red['objects']),'地板身份配对不同')
                key=f'{seed}:{camera}:source{blue["source_frame_index"]}'
                crop,anchor=anchor_crop(blue['objects'],3840,2160,target,key)
                pairs={}
                for floor,frame in [(FLOORS[0],blue),(FLOORS[1],red)]:
                    camera_root=frames[floor][0];image=(camera_root/frame['rgb_ref']).absolute()
                    require(dataset in image.parents,'RGB引用不能越过GDataset')
                    virtual_rows[(split,floor)].append(location_record(frame,camera_root,crop,key+':'+floor))
                    pairs[floor]=dict(image_file=str(image),pose_metadata=str(camera_root/'pose2d.jsonl'),frame_index=frame['frame_index'])
                    section=group_report.setdefault(floor,dict(original_heights=[],crop_heights=[],valid_points=0,crop_valid_points=0,persons=0,crop_persons=0,frames=0))
                    section['frames']+=1;section['persons']+=len(frame['objects'])
                    section['original_heights'].extend(o['bbox_visible_xywh'][3]/6 for o in frame['objects'])
                    section['valid_points']+=sum(sum(o['location_valid']) for o in frame['objects'])
                    heights,valid,people,unknown=transformed_profile(frame['objects'],crop)
                    section['crop_heights'].extend(heights);section['crop_valid_points']+=valid;section['crop_persons']+=people
                crop_rows.append(dict(schema='paired_virtual_crop_candidate_v1',key=key,seed=seed,split=split,camera=camera,
                    source_frame_index=blue['source_frame_index'],anchor_entity=anchor,crop_xywh=crop,
                    source_wh=[3840,2160],input_size=640,pairs=pairs,unknown_remains_unknown=True))
        for floor,section in group_report.items():
            section['original_bbox_height_640']=stats(section.pop('original_heights'))
            section['crop_bbox_height_640']=stats(section.pop('crop_heights'))
        report['groups'][group_key]=dict(split=split,variants=group_report)
    output.mkdir(parents=True)
    def write(name,value):(output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    write('profile.json',report);write('bundle_plan.json',source_bundle_plan())
    with (output/'paired_crop_table.jsonl').open('w',encoding='utf-8') as stream:
        for row in crop_rows:stream.write(json.dumps(row,separators=(',',':'))+'\n')
    candidate=dict(schema='v5_longpair_exposure_candidate_protocol_v1',training_authorized=False,root_signature=None,
        seeds=SEEDS,arms=['R3','R3S_blue','R3S_terracotta'],updates=1000,real_exposures=3000,synthetic_exposures_mixed=1000,
        same_R_order=True,same_S_crop_schedule_across_floor=True,loss='v4 meanR+(1/3)meanS separate criterion',
        unchanged_numerics=['COCOsigmas','cv4_only','fixed_BN_detector','lr1e-4','FP32','last1000_EMA'],
        crop_table=dict(path=str(output/'paired_crop_table.jsonl'),sha256=digest(output/'paired_crop_table.jsonl')),
        source_metadata=references,all_media='G:/FutsalMOT_Dataset references only',
        run_layout=dict(bundle='DResearch/code/<source_manifest_SHA>',run='DResearch/pose/poseonly_v5/<protocol_SHA>/<arm>_seed<seed>',
                        cache='bounded in-memory only; no duplicated4K disk cache',logs_models='same per-run DResearch'),
        evaluation='COCO200dev then frozen450raw/lambda0.1/geometry; final116/187 sealed',
        progress_definition='reuse original AssA>=+0.5pp at least2of3positive HOTAmean>=0 IDF1mean>=-0.5pp; report vsR3 and vsPretrained separately',
        pending=['root limited position admission','complete imported dependency closure','virtual crop Dataset adapter actual CPU loss/backward','new independent evaluator identity','schedule derivation freeze','root process/UE shutdown gates'])
    for (split,floor),records in virtual_rows.items():
        file=output/f'{split}.{floor}.virtual_location.jsonl'
        with file.open('w',encoding='utf-8') as stream:
            for record in records:stream.write(json.dumps(record,separators=(',',':'))+'\n')
    candidate['virtual_location_files']=[dict(split=split,floor=floor,path=str(output/f'{split}.{floor}.virtual_location.jsonl'),sha256=digest(output/f'{split}.{floor}.virtual_location.jsonl'),records=len(records)) for (split,floor),records in virtual_rows.items()]
    write('protocol_candidate.json',candidate)
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--dataset',type=Path,default=DATASET);parser.add_argument('--real',type=Path,default=REAL)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();report=prepare(args.dataset,args.real,args.output)
    print(json.dumps(dict(status='metadata_candidate_only',target=report['target_anchor_height_px'],groups=report['groups']),ensure_ascii=False))
if __name__=='__main__':main()
