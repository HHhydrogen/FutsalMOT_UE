"""额外R独立固定PT检测/裁剪Pose入口；获取及退出闭合后另签准入，零训练。"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

R=Path('D:/projects/FutsalMOT_Research')
EXPERIMENT=R/'pose/pose_mechanism_a01/extra_R_inputs_a01'
DATA=R/'public/real_substitution_train_a01'
ROOT=Path(__file__).resolve().parents[2]
POSE_SHA='c41fee957f91da4657f5b4f8822e22d53c6c527074c102e0a8c7490cf97736ec'
V10_SOURCE_SHA='6293539cdd8dfc35b6f3459f6ae27c2bc5fa067a9fda6b547b9d4efe69cd8833'
PARAMETERS=dict(detector_imgsz=640,detector_conf=.1,detector_iou=.7,detector_max_det=300,
    detector_rect=True,pose_crop=640,pose_batch=16,FP32=True,prefetch=2,optimizer_updates=0)
PWSH='C:/Users/20113/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe'


def require(ok,message):
    if not ok:raise ValueError(message)
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path):return dict(path=str(path),sha256=sha(path))
def checked(value):
    p=Path(value['path']);require(p.is_file() and sha(p)==value['sha256'],'来源SHA变化：'+str(p));return p
def write(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def admission(cfg,manifest,completion):
    require(cfg.get('schema')=='extra_real_shared_prediction_config_v1' and cfg.get('approved_by')=='root'
        and cfg.get('prediction_authorized') is True and cfg.get('training_authorized') is False
        and cfg.get('test_sealed') is True and cfg.get('parameters')==PARAMETERS,'缺独立额外R预测准入')
    require(manifest.get('status')=='complete2250_extra_real_train_frames_decoded_not_prediction_or_training_authorized'
        and completion.get('status')=='complete2250_extra_real_inputs_verified_processes_absent'
        and completion.get('acquisition_manifest')==cfg['acquisition_manifest']
        and completion.get('download_processes_absent') is True,'获取/实际退出尚未完整验收')


def check_processes(rows,current_pid):
    by_id={r['ProcessId']:r for r in rows};own=set();cursor=current_pid
    while cursor in by_id and cursor not in own:
        own.add(cursor);cursor=by_id[cursor].get('ParentProcessId')
    markers=('prediction_cache.py','acquire_extra_real_clips.py','v10_training_control.py','v10_tracking_control.py',
             'pose_mechanism_control.py','pose_mechanism_jobs.py','residual_amplitude_probe.py')
    blocked=[r for r in rows if r['ProcessId'] not in own and (r['Name'].lower().startswith('unrealeditor')
        or (r['Name'].lower().startswith('python') and any(x in (r.get('CommandLine') or '').lower() for x in markers)))]
    require(not blocked,'GPU前仍有UE/生产者/实验进程：'+str(blocked));return sorted(own)


def producers_absent():
    script="$ErrorActionPreference='Stop'; @(Get-CimInstance Win32_Process -Filter \"Name LIKE 'UnrealEditor%' OR Name LIKE 'python%'\" | Select-Object ProcessId,ParentProcessId,Name,CommandLine) | ConvertTo-Json -Compress"
    r=subprocess.run([PWSH,'-NoProfile','-NonInteractive','-Command',script],check=True,capture_output=True,text=True,encoding='utf-8')
    rows=json.loads(r.stdout.strip() or '[]');return check_processes([rows] if isinstance(rows,dict) else rows,os.getpid())


def preflight(config):
    cfg=read(config);require(Path(cfg['bundle'])==ROOT and ROOT.parent==R/'code','仅独立D代码bundle')
    entries={r['path']:r for r in cfg['code_files']}
    expected={'tools/research_ops/extra_real_prediction_cache.py','tools/research_ops/extra_real_prediction_inputs.py',
        'tools/research_ops/v8_prediction_cache.py','tools/performance/ordered_prefetch.py','python/src/grf_ue_bridge/storage_policy.py'}
    require(set(entries)==expected and len(entries)==len(cfg['code_files']),'必要五份执行源码不完整或重复')
    for p,r in entries.items():require(sha(ROOT/p)==r['sha256'],'新冻结源码变化')
    storage=module('extra_real_prediction_storage',ROOT/'python/src/grf_ue_bridge/storage_policy.py');storage.physical_child(ROOT,R/'code')
    for p in entries:storage.physical_child(ROOT/p,ROOT)
    manifest=read(checked(cfg['acquisition_manifest']));completion=read(checked(cfg['acquisition_completion']));admission(cfg,manifest,completion)
    require(Path(cfg['acquisition_manifest']['path'])==DATA/'manifest.json'
        and manifest['protocol']==cfg['acquisition_config'],'独立获取来源/协议未闭合')
    checked(cfg['acquisition_config']);storage.physical_child(cfg['acquisition_manifest']['path'],DATA)
    source=read(checked(cfg['v10_prediction_source']));require(cfg['v10_prediction_source']['sha256']==V10_SOURCE_SHA,'原v10固定预测来源改变')
    source_files={r['path']:r for r in source['code_files']}
    require(cfg['detector_checkpoint']==source['detector_checkpoint'] and cfg['v6_protocol']==source['v6_protocol']
        and cfg['pose_checkpoint_sha256']==source['pose_checkpoint_sha256']==POSE_SHA,'PT身份改变')
    for p in ('tools/research_ops/v8_prediction_cache.py','tools/performance/ordered_prefetch.py'):
        require(entries[p]['sha256']==source_files[p]['sha256'],'原裁剪或预取数值改变')
    # 只调用旧v10已验raw/attach纯函数；不调用其18源preflight或冒用旧schema。
    old_entry=Path(source['bundle'])/'tools/research_ops/v10_prediction_cache.py'
    require(sha(old_entry)==source_files['tools/research_ops/v10_prediction_cache.py']['sha256'],'原检测转写数值改变')
    checked(cfg['v6_protocol']);checked(cfg['detector_checkpoint'])
    inputs=module('extra_real_prediction_inputs',ROOT/'tools/research_ops/extra_real_prediction_inputs.py')
    sources=inputs.sources(manifest,DATA)
    for s in sources:
        s['image_root']=str(DATA)
        for f in (s['frames'][0],s['frames'][-1]):require(storage.physical_child(f['image_file'],DATA).is_file(),'实际首尾帧缺失')
    output=storage.physical_child(cfg['output'],EXPERIMENT);require(not output.exists(),'输出已存在/partial，禁止隐式重放')
    own=producers_absent()
    return cfg,inputs,storage,sources,output,old_entry,own


def execute(config,expected_sha):
    require(expected_sha and sha(config)==expected_sha,'必须显式传入新配置SHA')
    cfg,inputs,storage,sources,output,old_entry,own=preflight(config)
    output.mkdir(parents=True,exist_ok=False);write(output/'started.json',dict(status='started_not_complete',config=ref(config),optimizer_updates=0))
    try:
        os.environ['CUDA_VISIBLE_DEVICES']='0'
        os.environ['YOLO_AUTOINSTALL']='false'
        old_cfg=read(checked(cfg['v6_protocol']));sys.path.insert(0,str(Path(old_cfg['v6_bundle'])/'tools/research_ops'))
        from v6_crop_runtime import load,configure_runtime,model
        old,_,base,legacy,core=load(Path(cfg['v6_protocol']['path']));legacy.training_complete(base.config,require_absent=True);configure_runtime()
        import cv2
        import numpy as np
        import torch
        import ultralytics
        from ultralytics import YOLO
        require(torch.__version__=='2.6.0+cu124' and ultralytics.__version__=='8.4.60','冻结数值环境改变')
        torch.set_num_threads(4);cv2.setNumThreads(1);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.use_deterministic_algorithms(True)
        require(torch.cuda.is_available() and torch.cuda.mem_get_info()[0]>=2*1024**3,'GPU余量不足')
        detector=YOLO(str(checked(cfg['detector_checkpoint'])));pose,identity=model(old,base,'pretrained')
        require(identity['sha256']==POSE_SHA,'独立PT Pose核验失败');pose=pose.to('cuda:0').float().eval()
        numeric=module('extra_real_frozen_pose_numeric',ROOT/'tools/research_ops/v8_prediction_cache.py')
        transfer=module('extra_real_frozen_raw_attach',old_entry)
        prefetch_module=module('extra_real_frozen_prefetch',ROOT/'tools/performance/ordered_prefetch.py');completed=[]
        for source in sources:
            seq=source['sequence'];counts=Counter();partial=output/(seq+'.partial.jsonl')
            def loader(frame):
                path=storage.physical_child(frame['image_file'],DATA);image=cv2.imdecode(np.frombuffer(path.read_bytes(),np.uint8),cv2.IMREAD_COLOR)
                require(image is not None and image.shape[:2]==(1080,1920),'必要模型解码/尺寸不符');return frame,image
            prefetch=prefetch_module.OrderedPrefetch(loader,source['frames'],capacity=2,max_item_bytes=40*1024**2,measure_bytes=lambda x:int(x[1].nbytes))
            with partial.open('x',encoding='utf-8') as stream,prefetch:
                for record,image in prefetch:
                    frame=inputs.inference_frame(source,record)
                    raw=detector.predict(source=image,imgsz=640,conf=.1,iou=.7,classes=[0],max_det=300,
                        agnostic_nms=False,augment=False,half=False,rect=True,batch=1,device='cuda:0',verbose=False)[0]
                    detections,rejected=transfer.raw_detections(raw.boxes.data.detach().cpu().tolist(),frame);frame['detections']=detections
                    predicted=numeric.pose_predictions(image,detections,frame,pose,core)
                    cached=transfer.attach(frame,detections,predicted,identity['sha256'],cfg['detector_checkpoint']['sha256'])
                    cached['prediction_origin']='extra_real_actual_PT_detector_crop_pose_independent_schema'
                    stream.write(json.dumps(cached,separators=(',',':'),allow_nan=False)+'\n')
                    counts['frames']+=1;counts['raw_detections']+=len(predicted);counts['degenerate_model_boxes']+=rejected
                    for d in predicted:counts['geometry_valid' if d['prediction_valid'] else 'bbox_only']+=1
                    if counts['frames']%50==0:stream.flush();print(json.dumps(dict(sequence=seq,frames=counts['frames'])),flush=True)
                stream.flush();os.fsync(stream.fileno())
            require(counts['frames']==750 and prefetch.stats['closed'] is True,'未完整消费或预取未闭合')
            target=output/(seq+'.jsonl');partial.rename(target);s={k:v for k,v in source.items() if k not in ('frames','model_inference_authorized')}
            s.update(cache=ref(target),counts=dict(counts),prefetch=prefetch.stats,GT_used_for_predictions=False,actual_decoded_frames=750,
                runtime_prediction_admission=ref(config))
            completed.append(s);write(output/(seq+'.complete.json'),s)
        require(len(completed)==3 and sum(s['counts']['frames'] for s in completed)==2250,'新真实输入矩阵未齐')
        manifest=dict(schema='extra_real_shared_prediction_manifest_v1',status='complete3_sources2250_frames_not_training_authorized',
            config=ref(config),sources=completed,acquisition=cfg['acquisition_manifest'],pose_checkpoint=identity,detector=cfg['detector_checkpoint'],
            numeric_source=cfg['v10_prediction_source'],GT_used_for_predictions=False,det_file_used=False,test_read=False,
            new_optimizer_updates=0,new_R_training_exposure=0,training_authorized=False)
        write(output/'manifest.json',manifest);return dict(status=manifest['status'],frames=2250,optimizer_updates=0)
    except BaseException as error:
        write(output/'failed.json',dict(status='failed_preserved_no_replay',error=repr(error),config=ref(config)));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--config-sha256');p.add_argument('--execute',action='store_true');a=p.parse_args()
    if a.execute:print(json.dumps(execute(a.config,a.config_sha256),ensure_ascii=False))
    else:
        *_,sources,output,old_entry,own=preflight(a.config)
        print(json.dumps(dict(status='readonly_extra_real_prediction_preflight',sources=len(sources),frames=2250,output=str(output),GPU=False,optimizer_updates=0)))
