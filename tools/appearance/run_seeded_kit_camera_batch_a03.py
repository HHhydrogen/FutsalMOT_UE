"""16个显式单机位300帧单位；每次正常退出UE后导出、退休EXR，保持源时序/真实预算。"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

from run_seeded_kit_short_a01 import ROOT,UEPY,read,sha,require,save,resources
from run_seeded_kit_full_a02 import PWSH,P1,DATASET,identity,ready_mcp

RUN=ROOT/'Saved/AppearancePlanning/seeded_kit_capture_a03'
RESEARCH=Path('D:/projects/FutsalMOT_Research/pose/seeded_kit_pair_a03/camera_exports')


def atomic(path,value):
    for index in range(6):
        try:save(path,value);return
        except PermissionError as error:
            if getattr(error,'winerror',None) not in (5,32) or index==5:raise
            time.sleep(.05*(2**index))


def bindings(admission):
    require(admission['runtime_authorized'] is True and admission['scope']=='single_camera_300_continuous','没有新单机位准入')
    require(admission['manifest_sha256']==sha(RUN/'manifest.json'),'清单变化')
    require(admission['short_acceptance_sha256']==sha(ROOT/'Saved/AppearancePlanning/seeded_kit_capture_a02/short_acceptance_root.json'),'原短样准入变化')
    for ref in admission['source_files']:require(sha(ROOT/ref['path'])==ref['sha256'],'运行绑定变化：'+ref['path'])
    require(sha(ROOT/'Binaries/Win64/UnrealEditor-FutsalMOT.dll')==admission['module_sha256'],'实际DLL变化')


def call(unit,action,pid,control,event=None):
    name=unit['attempt'];output=RUN/'ue_receipts'/(name+'__'+action+'.json')
    require(not output.exists(),'单次动作已存在，不能重放')
    request=dict(attempt=name,action=action,editor_pid=pid)
    if event:request['guard_event_sha256']=sha(event)
    atomic(RUN/'action_request.json',request)
    env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUTF8='0')
    with (control/(name+'__'+action+'.log')).open('xb') as stream:
        code=subprocess.call([str(UEPY),'-B',str(ROOT/'tools/mcp_cli.py'),'--request',str(RUN/'mcp_request.json'),
            '--receipt',str(control/(name+'__'+action+'_mcp.json'))],cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
    require(code==0 and output.exists(),'实际UE动作未确认，保留现场：'+action)
    return read(output)


def wait_exit(pid,launch,control,name):
    until=time.monotonic()+120
    while identity(pid):
        require(time.monotonic()<until,'正常退出未完成，不强杀');time.sleep(2)
    path=Path(launch['log'])
    with path.open('rb') as f:f.seek(max(0,path.stat().st_size-131072));tail=f.read().decode('utf-8',errors='replace')
    require('LogExit: Exiting.' in tail and 'Log file closed' in tail,'本次退出日志不完整')
    save(control/(name+'__shutdown.json'),dict(status='normal_exit_confirmed',process_absent=True,
        editor_pid=pid,log=str(path)),True)


def export_unit(unit,control,storage):
    name=unit['attempt'];stage=storage.safe(DATASET/'_staging'/name,DATASET)
    require(not stage.exists(),'partial stage不重放')
    env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
    with (control/(name+'__export.log')).open('xb') as log:
        child=subprocess.Popen([str(P1),'-B','-m','grf_ue_bridge.tools.export_seeded_kit_camera',
            '--attempt',str(ROOT/'Saved/Pose17Development/smoke'/name),'--output',str(stage),'--workers','6'],
            cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        code=child.wait();del child
    require(code==0,'P1单机位实际导出失败')
    postpath=stage/'postprocess_complete.json';post=read(postpath);dataset=read(stage/'dataset.json')
    require(dataset['rgb_frames']==dataset['mask_frames']==300 and dataset['person_pose']==3000
        and len(post['views'])==1 and post['bounded_worker_pool_closed'] is True,'实际导出范围不等于一机位300帧')
    folder=storage.safe(RESEARCH/name,storage.RESEARCH);folder.mkdir(parents=True,exist_ok=False)
    index=folder/'inputs.json';save(index,dict(dataset=post['dataset_index'],views=post['views']),True)
    consumer=folder/'exr_consumers_complete.json'
    save(consumer,dict(schema='exr_consumers_complete_v1',status='complete',attempt=name,
        postprocess_sha256=sha(postpath),consumer_scope='raw_exr_only',producer_output_closed=True,
        raw_exr_consumers_finished=True,raw_exr_required=False,raw_exr_consumer_process_ids=[post['consumer_process_id']],
        reference_indexes=[dict(path=str(index),sha256=sha(index))]),True)
    dry=storage.cleanup(postpath,consumer);save(control/(name+'__EXR_dryrun.json'),dry,True)
    done=storage.cleanup(postpath,consumer,True,dry['files_sha256']);save(control/(name+'__EXR_complete.json'),done,True)
    return dict(stage=str(stage),rgb=300,mask=300,person_pose=3000,EXR_deleted=done['file_count'],EXR_bytes=done['bytes'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    admission=read(RUN/'admission_full_a01.json');bindings(admission);manifest=read(RUN/'manifest.json');units=manifest['units']
    require(len(units)==16 and len({u['attempt'] for u in units})==16,'需要16个唯一实际单位')
    for unit in units:require(sha(unit['plan']['path'])==unit['plan']['sha256'],'计划SHA变化')
    if not args.execute:print(json.dumps(dict(status='readonly_camera_batch_preflight',units=16,RGB=4800,resources=resources())));return
    control=RUN/'control_a01';control.mkdir(exist_ok=False)
    state=dict(schema='futsalmot_single_camera_batch_control_v1',status='started',pid=os.getpid(),completed=[],
        admission_sha256=sha(RUN/'admission_full_a01.json'),test_read=False)
    put=lambda:atomic(control/'state.json',state)
    put();spec=importlib.util.spec_from_file_location('kit_storage',ROOT/'tools/storage/dataset_storage_policy.py')
    storage=importlib.util.module_from_spec(spec);spec.loader.exec_module(storage)
    try:
        for unit in units:
            bindings(admission);name=unit['attempt'];capture=ROOT/'Saved/Pose17Development/smoke'/name
            require(not capture.exists() and not (DATASET/'_work'/name).exists(),'已有attempt，不能隐式恢复/重放')
            require(storage.shutil.disk_usage(DATASET).free>=100*1024**3,'单机位空间预算不足100GiB')
            state.update(status='launching',current=name,current_camera=unit['camera_id'],current_variant=unit['variant']);put()
            runname='camera_'+name
            with (control/(name+'__launch.log')).open('xb') as f:
                code=subprocess.call([str(PWSH),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'tools/open_editor.ps1'),
                    '-EngineRoot','E:/UE_5.8','-RunName',runname],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
            require(code==0,'真实Editor启动预算或进程门禁失败')
            launch=read(ROOT/'Saved/EditorStartup'/runname/'launch.json');pid=launch['pid'];rows=identity(pid)
            require(len(rows)==1 and rows[0]['Name']=='UnrealEditor.exe' and 'FustalMOT_UEDataset.uproject' in rows[0]['CommandLine'],'启动身份不符')
            state.update(editor_pid=pid,editor_launch=runname);put();ready_mcp()
            for action in ('initialize_runtime','preflight','prepare','configure_output','floor_preflight','floor_apply'):call(unit,action,pid,control)
            budget=resources();require(budget['commit_headroom_bytes']>=20*1024**3,'MRQ提交预算不足20GiB，未开始')
            state.update(status='rendering',pre_submit_resources=budget,min_commit_bytes=budget['commit_headroom_bytes']);put()
            call(unit,'submit',pid,control);until=time.monotonic()+4*3600
            while True:
                budget=resources();captured=read(capture/'state.json')
                state.update(capture_status=captured['status'],last_resources=budget,
                    min_commit_bytes=min(state['min_commit_bytes'],budget['commit_headroom_bytes']));put()
                if captured['status']=='rendered_requires_RGB_mask_pose_alignment_acceptance':break
                require(captured['status']=='submitted_async','MRQ实际失败，保留现场')
                if budget['commit_headroom_bytes']<6*1024**3:
                    event=control/(name+'__memory_guard_event.json')
                    save(event,dict(attempt=name,editor_pid=pid,controller_pid=os.getpid(),
                        sampled_epoch_seconds=time.time(),commit_headroom_bytes=budget['commit_headroom_bytes']),True)
                    state.update(status='memory_guard_requested');put();call(unit,'cancel_memory_guard',pid,control,event)
                    stop=time.monotonic()+120
                    while read(capture/'state.json')['status']=='submitted_async':
                        require(time.monotonic()<stop,'取消终态未知，保留现场');time.sleep(2)
                    for action in ('postflight','floor_restore','failed_release_quit'):call(unit,action,pid,control)
                    wait_exit(pid,launch,control,name);state['guard_cleanup_normal_exit']=True
                    raise RuntimeError('真实低commit保护正常取消且清理，不重试、不强杀')
                require(time.monotonic()<until,'四小时未完成，保留现场');time.sleep(2)
            for action in ('postflight','floor_restore','release','quit_after_release'):call(unit,action,pid,control)
            wait_exit(pid,launch,control,name);state.update(status='CPU_export_and_EXR_retirement',Editor_open=False);put()
            started=time.monotonic();result=export_unit(unit,control,storage)
            state['completed'].append(dict(attempt=name,seed=unit['seed'],variant=unit['variant'],camera_id=unit['camera_id'],
                normal_UE_exit=True,min_commit_bytes=state['min_commit_bytes'],export_wall_seconds=time.monotonic()-started,**result));put()
        state.update(status='complete_16_camera_units_all_UE_normal_exit_EXR_retired_wait_publication',rgb=4800,mask=4800,person_pose=48000)
        put()
    except BaseException as error:
        state.update(status='failed_preserved_no_replay',error=repr(error));put();raise


if __name__=='__main__':main()
