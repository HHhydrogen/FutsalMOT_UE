"""建立一次按SHA寻址的代码bundle与未签v5模板；绝不启动训练。"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import shutil
from prepare_longpair_v5 import source_bundle_plan,PROJECT,RESEARCH
from v5_numeric_loader import numeric_helpers

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def bind(path):return dict(path=str(Path(path).resolve()),sha256=sha(path))
def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def install(candidate_input,output):
    candidate_input=Path(candidate_input).resolve();output=Path(output).resolve()
    if RESEARCH/'pose/poseonly_v5' not in output.parents or output.exists():raise ValueError('新候选仅DResearch/v5；禁止覆盖')
    plan=source_bundle_plan();bundle=Path(plan['target']);bundle.parent.mkdir(parents=True,exist_ok=True)
    if bundle.exists():
        for row in plan['files']:
            if sha(bundle/row['path'])!=row['sha256']:raise ValueError('已存在bundle内容变化，拒绝覆盖')
    else:
        bundle.mkdir()
        for row in plan['files']:
            source=PROJECT/row['path'];target=bundle/row['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
            if sha(target)!=row['sha256']:raise ValueError('bundle复制SHA错误')
    output.mkdir(parents=True);write(output/'bundle_manifest.json',dict(schema='v5_content_addressed_code_bundle_v1',files=plan['files'],canonical_git_root=str(PROJECT),git_head=plan['git_head']))
    runtime=dict(schema='futsalmot_v5_explicit_runtime_context_v1',code_bundle=str(bundle),source_project_root=str(PROJECT),research_root=str(RESEARCH),bundle_manifest=bind(output/'bundle_manifest.json'))
    write(output/'runtime_context.json',runtime)
    for floor in ('sport_blue_v1','sport_terracotta_v1'):
        shutil.copy2(candidate_input/f'train.{floor}.virtual_location.jsonl',output/f'train.{floor}.virtual_location.jsonl')
    # 原COCO元数据只读引用，200个dev图像仍引用既有原图，不复制媒体。
    coco=RESEARCH/'pose/coco2017_location_a01';selection=read(coco/'subset/selection_manifest.json');ids=selection['splits']['val2017']['image_ids_in_sha_rank_order']
    old_images=read(coco/'images_receipt.json');by_id={row['image_id']:row for row in old_images['images'] if row['split']=='val2017'}
    images=[]
    for identity in ids:
        old=by_id[identity];images.append(dict(old,path=str(coco/'images/val2017'/f'{identity:012d}.jpg')))
    dev=dict(schema='futsalmot_v5_existing_coco200dev_manifest_v1',role='public_pose_development_only_not_final_test',image_ids=ids,images=images,
        ground_truth=bind(coco/'subset/val2017_person_annotations.json'),selection_source=bind(coco/'subset/selection_manifest.json'),images_receipt_source=bind(coco/'images_receipt.json'))
    write(output/'dev_manifest.json',dev)
    oldroot=RESEARCH/'pose/poseonly_v4/candidate_a02';oldmanifest=read(oldroot/'schedule_manifest.json');schedules={};source_schedules=[]
    for seed in (20261024,20261025,20261026):
        source=oldroot/'schedules'/f'seed_{seed}.jsonl';entry=next(e for e in oldmanifest['schedules'] if e['seed']==seed)
        if sha(source)!=entry['sha256']:raise ValueError('原真实曝光表SHA变化')
        prior=[json.loads(line) for line in source.read_text(encoding='utf-8').splitlines() if line];indices=random.Random(seed^0xF5A001).sample(range(1200),1000)
        schedule=[dict(schema='futsalmot_longpair_v5_schedule_row_v1',update_index=i,real_indices=row['real_indices'],synthetic_index=indices[i]) for i,row in enumerate(prior)]
        write(output/f'schedule_{seed}.json',schedule);schedules[str(seed)]=bind(output/f'schedule_{seed}.json');source_schedules.append(bind(source))
    numeric,identities=numeric_helpers(bundle)
    protocol=dict(schema='futsalmot_longpair_training_protocol_v5',status='candidate_not_frozen',training_authorized=False,
        seeds=[20261024,20261025,20261026],arms=['R3','R3S_blue','R3S_terracotta'],updates=1000,real_exposures=3000,synthetic_exposures_mixed=1000,
        normalization=numeric.NORMALIZATION,policy=numeric.POLICY,schedules=schedules,source_real_schedule_bindings=source_schedules,
        synthetic_selection='random.Random(training_seed XOR0xF5A001).sample(range1200,1000); sameblue_red; no_model_outcomes',
        real_jsonl=bind(coco/'subset/train2017.location.jsonl'),synthetic_jsonl={floor:bind(output/f'train.{floor}.virtual_location.jsonl') for floor in ('sport_blue_v1','sport_terracotta_v1')},
        initialization=bind(RESEARCH/'weights/yolo11n-pose_xy_location_exact_a01.pt'),numeric_function_bindings=identities,
        evaluation=dict(dev_manifest=bind(output/'dev_manifest.json'),numerical_source_sha256=sha(bundle/'python/src/grf_ue_bridge/coco_pose_dev_eval.py'),
            checkpoint='last1000_actual_FP32_EMA',pretrained_reference=True,tracking_progress_definition=dict(mean_AssA_delta_pp_min=.5,positive_seed_count_min=2,HOTA_mean_delta_min=0,IDF1_mean_delta_pp_min=-.5)),
        source_candidate=bind(candidate_input/'protocol_candidate.json'),source_profile=bind(candidate_input/'profile.json'),source_crop_table=bind(candidate_input/'paired_crop_table.jsonl'),
        limitations=['one_motion_train_seed1048;1102dev_only','unknown_visibility_retained','visible_mask_bbox_vs_COCO_annotation_bbox_not_identical_semantics','extraS_compute_not_equalFLOPs','COCO_pretrained_initialization'])
    write(output/'protocol_candidate.json',protocol)
    admission=dict(schema='futsalmot_longpair_training_admission_v5',approved_by=None,training_authorized=False,location_only=True,visibility_supervision=False,
        protocol_sha256=None,runtime_context_sha256=sha(output/'runtime_context.json'),all_rendering_finished=False,shutdown_receipt=None,
        required_root_checks=['CPU_crop_backward_and_exact_detector_freeze','actual_UE_safe_exit','process_gate','independent_source_metadata_admission'])
    write(output/'admission_template.json',admission)
    write(output/'installation_receipt.json',dict(status='installed_candidate_not_training_authorized',bundle=str(bundle),source_files=len(plan['files']),bytes=sum(row['size'] for row in plan['files']),media_copied=False,created_new_git=False))
    return bundle
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();print(install(args.input,args.output))
