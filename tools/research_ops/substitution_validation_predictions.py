"""七比赛独立共享PT检测/裁剪Pose；完整输入和C退出后另签准入，默认只读。"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2];R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/real_substitution_a01'
POSE_SHA='c41fee957f91da4657f5b4f8822e22d53c6c527074c102e0a8c7490cf97736ec'
SOURCE_SHA='6293539cdd8dfc35b6f3459f6ae27c2bc5fa067a9fda6b547b9d4efe69cd8833'
PARAMETERS=dict(detector_imgsz=640,detector_conf=.1,detector_iou=.7,detector_max_det=300,detector_rect=True,
    pose_crop=640,pose_batch=16,FP32=True,prefetch=2,optimizer_updates=0)
def require(ok,msg):
    if not ok:raise ValueError(msg)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p))
def checked(v):
    p=Path(v['path']);require(p.is_file() and sha(p)==v['sha256'],'冻结来源改变：'+str(p));return p
def write(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
def module(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def process_gate(records,pid,script):
    by={x['ProcessId']:x for x in records};current=by.get(pid);own={pid}
    def tail(x):
        text=(x.get('CommandLine') or '').replace('"','').replace('/','\\').lower();needle=str(script).replace('/','\\').lower()
        return text[text.index(needle):] if needle in text else None
    for _ in range(4):
        parent=by.get(current.get('ParentProcessId')) if current else None
        if parent is None or tail(current) is None or tail(parent)!=tail(current):break
        own.add(parent['ProcessId']);current=parent
    words=('substitution_C_control.py','substitution_C_train.py','substitution_validation_inputs.py',
        'substitution_validation_predictions.py','prediction_cache.py','v10_training_control.py','v10_train.py')
    blocked=[x for x in records if x['ProcessId'] not in own and (x['Name'].lower().startswith('unrealeditor')
        or any(k in (x.get('CommandLine') or '') for k in words))]
    require(not blocked,'GPU/输入生产者仍活动，拒绝启动：'+str(blocked));return sorted(own)

def preflight(config):
    c=read(config);require(c.get('schema')=='seven_match_shared_PT_prediction_config_v1' and c.get('approved_by')=='root'
        and c.get('prediction_authorized') is True and c.get('training_authorized') is False and c.get('test_sealed') is True
        and c.get('parameters')==PARAMETERS and Path(c['bundle'])==ROOT and ROOT.parent==R/'code','缺新七比赛独立预测准入')
    names={'tools/research_ops/substitution_validation_predictions.py','tools/research_ops/substitution_validation_prediction_inputs.py',
        'tools/research_ops/v8_prediction_cache.py','tools/performance/ordered_prefetch.py','python/src/grf_ue_bridge/storage_policy.py'}
    entries={e['path']:e for e in c['code_files']};require(set(entries)==names and len(entries)==len(c['code_files']),'最小五文件闭包不符')
    for name,e in entries.items():require(sha(ROOT/name)==e['sha256'],'新预测源码变化')
    st=module('seven_match_prediction_storage',ROOT/'python/src/grf_ue_bridge/storage_policy.py');st.physical_child(ROOT,R/'code')
    for name in entries:st.physical_child(ROOT/name,ROOT)
    manifest=read(checked(c['input_manifest']));root=read(checked(c['input_completion']))
    require(root['status']=='complete4790_inputs_verified_processes_absent' and root['input_manifest']==c['input_manifest']
        and root['download_processes_absent'] is True and manifest['matches']==c['matches'],'输入根收据/七比赛不闭合')
    audit=read(checked(c['C_budget_audit']));require(audit['status']=='complete18_C_actual_budget_full_records_and_exit_verified'
        and audit['training_processes_absent'] is True and audit['complete_checkpoints_read_back']==378,'C实际预算/退出未闭合')
    source=read(checked(c['source_prediction']));require(c['source_prediction']['sha256']==SOURCE_SHA
        and c['detector_checkpoint']==source['detector_checkpoint'] and c['v6_protocol']==source['v6_protocol']
        and c['pose_checkpoint_sha256']==source['pose_checkpoint_sha256']==POSE_SHA,'同PT身份改变')
    source_files={e['path']:e for e in source['code_files']}
    for name in ('tools/research_ops/v8_prediction_cache.py','tools/performance/ordered_prefetch.py'):
        require(entries[name]['sha256']==source_files[name]['sha256'],'原裁剪Pose/预取数值改变')
    old_entry=Path(source['bundle'])/'tools/research_ops/v10_prediction_cache.py'
    require(sha(old_entry)==source_files['tools/research_ops/v10_prediction_cache.py']['sha256'],'原raw/attach数值改变')
    checked(c['detector_checkpoint']);checked(c['v6_protocol']);checked(c['analysis_plan'])
    inp=module('seven_match_prediction_inputs',ROOT/'tools/research_ops/substitution_validation_prediction_inputs.py')
    ledger=[json.loads(x) for x in checked(manifest['files']).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
    sources=inp.sources(manifest,read(checked(c['matches'])),ledger)
    for s in sources:
        checked(s['gt']);checked(s['seqinfo'])
        for f in s['frames']:
            p=st.physical_child(f['image_file'],inp.image_boundary(f['image_file']))
            require(p.is_file() and p.stat().st_size==f['image_bytes'],'登记图像缺失或大小变化；不重复哈媒体')
    output=st.physical_child(c['output'],EXP);require(not output.exists(),'已有预测/partial，不重放')
    cmd="Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    ps=subprocess.run(['powershell.exe','-NoProfile','-Command',cmd],capture_output=True,text=True,encoding='utf-8',errors='replace')
    require(ps.returncode==0,'CIM身份查询失败');records=json.loads(ps.stdout or '[]');records=[records] if isinstance(records,dict) else records
    own=process_gate(records,os.getpid(),Path(__file__).resolve());return c,inp,st,sources,output,old_entry,own

def execute(config,config_sha):
    require(config_sha and sha(config)==config_sha,'须显式传入新准入SHA')
    c,inp,st,sources,output,old_entry,own=preflight(config);output.mkdir(parents=True)
    write(output/'started.json',dict(status='started_not_complete',config=ref(config),optimizer_updates=0))
    try:
        os.environ.update(CUDA_VISIBLE_DEVICES='0',YOLO_AUTOINSTALL='false')
        legacy_cfg=read(checked(c['v6_protocol']));sys.path.insert(0,str(Path(legacy_cfg['v6_bundle'])/'tools/research_ops'))
        from v6_crop_runtime import load,configure_runtime,model
        old,_,base,legacy,core=load(Path(c['v6_protocol']['path']));legacy.training_complete(base.config,require_absent=True);configure_runtime()
        import cv2,numpy as np,torch,ultralytics
        from ultralytics import YOLO
        require(torch.__version__=='2.6.0+cu124' and ultralytics.__version__=='8.4.60' and torch.cuda.is_available()
            and torch.cuda.mem_get_info()[0]>2*1024**3,'冻结环境或GPU余量变化')
        torch.set_num_threads(4);cv2.setNumThreads(1);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.use_deterministic_algorithms(True)
        detector=YOLO(str(checked(c['detector_checkpoint'])));pose,identity=model(old,base,'pretrained')
        require(identity['sha256']==POSE_SHA,'独立PT Pose加载身份不符');pose=pose.to('cuda:0').float().eval()
        numeric=module('seven_match_original_pose',ROOT/'tools/research_ops/v8_prediction_cache.py')
        transfer=module('seven_match_original_raw_attach',old_entry);pref=module('seven_match_original_prefetch',ROOT/'tools/performance/ordered_prefetch.py');complete=[]
        for source in sources:
            seq=source['sequence'];counts=Counter();partial=output/(seq+'.partial.jsonl')
            def loader(f):
                p=st.physical_child(f['image_file'],inp.image_boundary(f['image_file']))
                image=cv2.imdecode(np.frombuffer(p.read_bytes(),np.uint8),cv2.IMREAD_COLOR)
                require(image is not None and image.shape[:2]==(720,1280),'实际模型解码/尺寸不符');return f,image
            prefetch=pref.OrderedPrefetch(loader,source['frames'],capacity=2,max_item_bytes=40*1024**2,measure_bytes=lambda x:int(x[1].nbytes))
            with partial.open('x',encoding='utf-8') as f,prefetch:
                for record,image in prefetch:
                    frame=inp.inference_frame(source,record)
                    raw=detector.predict(source=image,imgsz=640,conf=.1,iou=.7,classes=[0],max_det=300,agnostic_nms=False,
                        augment=False,half=False,rect=True,batch=1,device='cuda:0',verbose=False)[0]
                    detections,rejected=transfer.raw_detections(raw.boxes.data.detach().cpu().tolist(),frame);frame['detections']=detections
                    predicted=numeric.pose_predictions(image,detections,frame,pose,core)
                    cached=transfer.attach(frame,detections,predicted,identity['sha256'],c['detector_checkpoint']['sha256'])
                    cached['prediction_origin']='seven_match_same_PT_raw_detector_and_crop_pose_independent_schema'
                    f.write(json.dumps(cached,separators=(',',':'),allow_nan=False)+'\n')
                    counts['frames']+=1;counts['raw_detections']+=len(predicted);counts['degenerate_model_boxes']+=rejected
                    for d in predicted:counts['geometry_valid' if d['prediction_valid'] else 'bbox_only']+=1
                    if counts['frames']%50==0:f.flush();print(json.dumps(dict(sequence=seq,frames=counts['frames'])),flush=True)
                f.flush();os.fsync(f.fileno())
            require(counts['frames']==len(source['frames']) and prefetch.stats['closed'] and not prefetch.stats['worker_alive'],'源预测或预取未完整闭合')
            target=output/(seq+'.jsonl');partial.rename(target)
            result={k:v for k,v in source.items() if k!='frames'};result.update(cache=ref(target),counts=dict(counts),prefetch=prefetch.stats,GT_used_for_predictions=False)
            complete.append(result);write(output/(seq+'.complete.json'),result)
        require(len(complete)==7 and sum(x['counts']['frames'] for x in complete)==4790,'七场4790帧不完整')
        result=dict(schema='seven_match_shared_PT_prediction_manifest_v1',status='complete7_sources4790_frames_not_tracking_authorized',
            config=ref(config),sources=complete,pose_checkpoint=identity,detector=c['detector_checkpoint'],numeric_source=c['source_prediction'],
            input_manifest=c['input_manifest'],matches=c['matches'],analysis_plan=c['analysis_plan'],GT_used_for_predictions=False,
            det_file_used=False,test_read=False,new_optimizer_updates=0,new_R_training_exposure=0,training_authorized=False)
        write(output/'manifest.json',result);return dict(status=result['status'],frames=4790,optimizer_updates=0)
    except BaseException as e:
        write(output/'failed.json',dict(status='failed_preserved_no_replay',error=repr(e),config=ref(config)));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--config-sha256');p.add_argument('--execute',action='store_true');a=p.parse_args()
    if a.execute:print(json.dumps(execute(a.config,a.config_sha256),ensure_ascii=False))
    else:
        c,inp,st,sources,output,old_entry,own=preflight(a.config)
        print(json.dumps(dict(status='readonly_seven_match_PT_preflight',sources=len(sources),frames=4790,GPU=False,optimizer_updates=0)))
