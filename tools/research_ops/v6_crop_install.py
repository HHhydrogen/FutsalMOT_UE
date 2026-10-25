"""安装v6独立crop小样候选及十模型清单；不签root、不运行GPU。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

PROJECT=Path(__file__).resolve().parents[2];RESEARCH=Path('D:/projects/FutsalMOT_Research')
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def bind(path):return dict(path=str(Path(path).resolve()),sha256=sha(path))
def install(output):
    output=Path(output).resolve()
    if RESEARCH/'pose/association_dev_a01/v6_crop' not in output.parents or output.exists():raise ValueError('须全新DResearch/v6候选')
    relative=['python/src/grf_ue_bridge/fixed_detection_crop_pose_v6.py','tools/research_ops/v6_crop_runtime.py','tools/research_ops/v6_crop_attach.py']
    relative += [name for name in ('tools/research_ops/v6_crop_tracking.py','tools/research_ops/v6_crop_driver.py') if (PROJECT/name).is_file()]
    files=[dict(path=name,sha256=sha(PROJECT/name),size=(PROJECT/name).stat().st_size) for name in sorted(relative)]
    identity=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest();bundle=RESEARCH/'code'/identity
    if bundle.exists():
        if any(sha(bundle/entry['path'])!=entry['sha256'] for entry in files):raise ValueError('已有bundle字节变化，不覆盖')
    else:
        bundle.mkdir(parents=True)
        for entry in files:
            target=bundle/entry['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PROJECT/entry['path'],target)
    output.mkdir(parents=True)
    def write(name,value):(output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    write('bundle_manifest.json',dict(schema='v6_crop_content_addressed_bundle_v1',files=files,canonical_git_root=str(PROJECT)))
    base_config=RESEARCH/'pose/association_dev_a01/v5_association_frozen_a01/config.json';old=read(base_config)
    # 新module只定义纯CPU契约，安装时不加载模型。
    import sys
    sys.path.insert(0,str(PROJECT/'python/src'))
    from grf_ue_bridge.fixed_detection_crop_pose_v6 import configuration
    models={};training=Path(old['training_root']);protocol=read(old['training_protocol'])
    models['pretrained']=dict(role='pretrained_reference',seed=20261024,arm='R3',checkpoint=protocol['initialization'],full_frame_metrics=old['pretrained_metrics'])
    for seed in (20261024,20261025,20261026):
        for arm in ('R3','R3S_blue','R3S_terracotta'):
            key=f'{arm}_seed{seed}';folder=training/key;report=read(folder/'coco_dev/report.json')
            models[key]=dict(role='last_ema',seed=seed,arm=arm,checkpoint=dict(path=report['checkpoint']['path'],sha256=report['checkpoint']['sha256']),run_receipt=bind(folder/'train/run_receipt.json'),dev_report=bind(folder/'coco_dev/report.json'),full_frame_metrics=bind(Path(old['output_root'])/key/'metrics/report.json'))
    config=dict(schema='futsalmot_fixed_raw_crop_pose_exploratory_protocol_v6',status='candidate_not_root_frozen',approved_by=None,gpu_smoke_authorized=False,execution_authorized=False,
        v6_bundle=str(bundle),bundle_manifest=bind(output/'bundle_manifest.json'),frozen_v5_association_config=bind(base_config),models=models,
        crop_configuration=configuration(),original_geometry_configuration=old['configuration'],raw_cache=old['cache'],raw_jsonl=old['raw_jsonl'],association_protocol=old['association_protocol'],
        inherited_training_protocol=bind(old['training_protocol']),tracking_lambda=.1,formal_new_optimizer_updates=0,
        comparisons=['crop_R3S_blue_vs_crop_R3_same3000R','crop_R3S_terracotta_vs_crop_R3_same3000R','each_crop_model_vs_crop_pretrained','each_crop_model_vs_same_model_fullframe_cache'],
        GPU_boundary_admission_required=dict(first_two_fixed_frames=True,batch16_FP32=True,no_model_threshold_or_seed_selection=True),
        gpu_boundary_receipt=None,gpu_boundary_config=None,output_root=str(RESEARCH/'pose/association_dev_a01/v6_crop/control_a01'),
        exploratory=True,final116187_sealed=True,raw_reinferred=False,full_frame_cache_overwritten=False,
        limitations=['geometric_dedup_not_physical_identity_ground_truth','new_inference_interface_not_new_training','crop_changes_person_scale_and_context','same_game9_dev_only'])
    smoke=RESEARCH/'pose/association_dev_a01/v6_crop/smoke_pretrained_a01/crop_attachment_manifest.json'
    smoke_config=RESEARCH/'pose/association_dev_a01/v6_crop/candidate_core_a02/config.json'
    if smoke.is_file() and smoke_config.is_file():
        config['gpu_boundary_receipt']=bind(smoke);config['gpu_boundary_config']=bind(smoke_config)
    write('config.json',config);write('installation_receipt.json',dict(status='installed_candidate_GPU_not_run',bundle=str(bundle),models=len(models),code_files=len(files),new_training_updates=0,media_copied=False))
    print(json.dumps(dict(bundle=str(bundle),candidate=str(output),models=len(models))))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);install(parser.parse_args().output)
