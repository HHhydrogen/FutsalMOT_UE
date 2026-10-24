"""安装独立v5关联bundle与未启用交接配置；不启动进程/模型推理。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from v5_association_runtime import RESEARCH,PROJECT,sha,read,CACHE_SHA,RAW_SHA,RULE_SHA,CONFIG_SHA,BASELINE_SHA,require

def bind(path):return dict(path=str(Path(path).resolve()),sha256=sha(path))
def install(output):
    output=Path(output).resolve();require(RESEARCH/'pose/association_dev_a01' in output.parents and not output.exists(),'候选必须为全新独立DResearch目录')
    package=['__init__.py','fixed_detection_pose_attach_v2.py','pose_association_contract_v2.py','pose_bytetrack_v2.py','pose_association_trackeval_v1.py']
    sources=[f'python/src/grf_ue_bridge/{name}' for name in package]+[f'experiments/sim2real/{name}' for name in ('prepare_pose_association_dev.py','attach_fixed_detection_pose.py','run_pose_association_dev.py','evaluate_pose_association_dev.py','bytetrack_fixed.yaml')]+[f'tools/research_ops/{name}' for name in ('v5_association_runtime.py','v5_association_stage.py','v5_association_driver.py','v5_association_handoff.py')]
    files=[dict(path=name,sha256=sha(PROJECT/name),size=(PROJECT/name).stat().st_size) for name in sorted(sources)]
    identity=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest();bundle=RESEARCH/'code'/identity
    if bundle.exists():
        for row in files:require(sha(bundle/row['path'])==row['sha256'],'已存在bundle字节变化；不覆盖')
    else:
        bundle.mkdir(parents=True)
        for row in files:
            target=bundle/row['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PROJECT/row['path'],target)
    output.mkdir(parents=True)
    def write(name,value):(output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    write('bundle_manifest.json',dict(schema='v5_association_content_addressed_bundle_v1',files=files,canonical_git_root=str(PROJECT)))
    root=RESEARCH/'pose/association_dev_a01';training=RESEARCH/'pose/poseonly_v5';execution=PROJECT/'Saved/Pose17Development/association_execution_a01'
    training_runtime=training/'candidate_a04/runtime_context.json';training_bundle=Path(read(training_runtime)['code_bundle'])
    config=dict(schema='futsalmot_v5_association_handoff_candidate_v1',execution_authorized=False,approved_by=None,association_bundle=str(bundle),association_bundle_manifest=bind(output/'bundle_manifest.json'),
        association_driver_sha256=sha(bundle/'tools/research_ops/v5_association_driver.py'),training_bundle=str(training_bundle),training_root=str(training/'control_a01'),training_state=str(training/'control_a01/driver_state.json'),
        training_driver=str(training_bundle/'tools/research_ops/run_longpair_v5_control.py'),training_protocol=str(training/'frozen_a01/protocol.json'),training_protocol_sha256='b988ac9846c58f597fc8bf09bde37ab5a92c94675889d5fa0d398d296564e727',
        training_admission=str(training/'frozen_a01/admission.json'),training_admission_sha256='3ecd3d51f3e85cd50478ac72f0a861a8fcd2fee3cc8e7a89f9e268c5821bb795',training_runtime_context=str(training_runtime),
        cache=bind(root/'raw_detections/cache_manifest.json'),raw_jsonl=bind(root/'raw_detections/detections.jsonl'),association_protocol=bind(execution/'protocol.json'),configuration=bind(execution/'pose_configuration.json'),lambda0=bind(root/'bbox_lambda0/receipt.json'),
        bbox_metrics=bind(root/'metrics_bbox_lambda0/report.json'),pretrained_metrics=bind(root/'metrics_pretrained_pose_lambda01/report.json'),
        literal_file_relocations=[dict(legacy=str(PROJECT/'Content/FutsalMOT/code/experiments/sim2real/bytetrack_fixed.yaml'),actual=str(bundle/'experiments/sim2real/bytetrack_fixed.yaml'),sha256=sha(bundle/'experiments/sim2real/bytetrack_fixed.yaml'),reason='same_immutable_YAML_after_single_Git_layout_migration_no_alias')],
        output_root=str(root/'v5_association_a01'),handoff_root=str(root/'v5_association_handoff_a01'),
        final116187_read=False,raw_or_pretrained_reinference=False,only_lambda=.1,models='all_nine_actual_last1000_FP32_EMA_no_selection')
    fixed={key:ref['sha256'] for key,ref in config.items() if isinstance(ref,dict) and set(ref)>={'path','sha256'}}
    require(fixed['cache']==CACHE_SHA and fixed['raw_jsonl']==RAW_SHA and fixed['association_protocol']==RULE_SHA and fixed['configuration']==CONFIG_SHA and fixed['lambda0']==BASELINE_SHA,'原关联输入身份变化')
    inputs=[output/'bundle_manifest.json',Path(config['training_protocol']),Path(config['training_admission']),training_runtime,training_bundle/'tools/research_ops/run_longpair_v5_control.py']+[Path(config[key]['path']) for key in ('cache','association_protocol','configuration','lambda0','bbox_metrics','pretrained_metrics')]
    inputs += [bundle/row['path'] for row in files]
    config['handoff_frozen_inputs']=[bind(path) for path in inputs]
    write('config.json',config);write('installation_receipt.json',dict(status='installed_not_enabled_not_launched',bundle=str(bundle),files=len(files),bytes=sum(f['size'] for f in files),training_source_or_bundle_changed=False,source_MEDIA_copied=False))
    print(json.dumps(dict(candidate=str(output),association_bundle=str(bundle),driver_sha256=config['association_driver_sha256']),ensure_ascii=False))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);install(parser.parse_args().output)
