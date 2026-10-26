"""短样准入后的四个300帧变体：真实UE→安全退出→6CPU导出/EXR退休，逐组串行。"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from run_seeded_kit_short_a01 import ROOT,RUN,UEPY,read,sha,require,save,resources

PWSH=Path('C:/Users/20113/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe')
P1=ROOT/'python/.venv/Scripts/python.exe'
DATASET=Path('G:/FutsalMOT_Dataset')
RESEARCH=Path('D:/projects/FutsalMOT_Research/pose/seeded_kit_pair_a02/full_exports')


def bindings(admission):
    require(admission['runtime_authorized'] is True and admission['stage']=='full','缺独立整批准入')
    require(admission['short_acceptance_sha256']==sha(RUN/'short_acceptance_root.json'),'短样验收改变')
    require(read(RUN/'short_acceptance_root.json')['root_visual_reviewed'] is True,'短样未看真实画面')
    require(sha(RUN/'manifest.json')==admission['manifest_sha256'],'清单改变')
    for ref in admission['source_files']:require(sha(ROOT/ref['path'])==ref['sha256'],'绑定代码/资产改变：'+ref['path'])
    require(sha(ROOT/'Binaries/Win64/UnrealEditor-FutsalMOT.dll')==admission['module_sha256'],'DLL改变')


def identity(pid):
    code="$ErrorActionPreference='Stop';@(Get-CimInstance Win32_Process -Filter 'ProcessId=%d' | Select-Object ProcessId,Name,CommandLine) | ConvertTo-Json -Compress"%pid
    result=subprocess.run([str(PWSH),'-NoProfile','-Command',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    require(result.returncode==0,'实际进程身份查询失败，不能伪造空进程表')
    value=json.loads(result.stdout.decode('utf-8-sig')) if result.stdout.strip() else []
    return value if isinstance(value,list) else [value]


def call(name,action,admission_name,pid,work):
    result=RUN/'ue_receipts'/(name+'__'+action+'.json')
    require(not result.exists(),'动作已存在，不自动重放：'+action)
    save(RUN/'action_request.json',dict(attempt=name,action=action,admission_file=admission_name,editor_pid=pid))
    with (work/(name+'__'+action+'.log')).open('xb') as log:
        code=subprocess.call([str(UEPY),'-B',str(ROOT/'tools/mcp_cli.py'),'--request',str(RUN/'mcp_request.json'),
            '--receipt',str(work/(name+'__'+action+'_mcp.json'))],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    require(code==0 and result.exists(),'真实UE动作未确认，保留现场：'+action)
    return read(result)


def ready_mcp():
    sys.path.insert(0,str(ROOT/'python/tools/production'))
    from mcp_client import UnrealMCP
    until=time.monotonic()+180
    while True:
        try:
            UnrealMCP(timeout=10).describe('futsalmot_tools.FutsalMOTTools')
            return
        except Exception:
            require(time.monotonic()<until,'MCP启动未就绪，未重放任何写操作')
            time.sleep(2)


def postprocess(name,work,storage):
    stage=storage.safe(DATASET/'_staging'/name,DATASET)
    require(not stage.exists(),'stage已存在，不隐式重放partial')
    env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
    with (work/(name+'__export.log')).open('xb') as log:
        child=subprocess.Popen([str(P1),'-B','-m','grf_ue_bridge.tools.export_seeded_kit_pair',
            '--attempt',str(ROOT/'Saved/Pose17Development/smoke'/name),'--output',str(stage),'--workers','6'],
            cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        pid=child.pid;code=child.wait();del child
    require(code==0,'P1真实导出失败，保留partial且不重放')
    postpath=stage/'postprocess_complete.json';post=read(postpath)
    require(post['status']=='complete' and post['bounded_worker_pool_closed'] is True,'EXR消费尚未完整结束')
    research=storage.safe(RESEARCH/name,storage.RESEARCH);research.mkdir(parents=True,exist_ok=False)
    index=research/'input_index.json'
    save(index,dict(schema='seeded_kit_RGB_pose_inputs_v1',dataset_index=post['dataset_index'],views=post['views']),True)
    consumer=research/'exr_consumers_complete.json'
    save(consumer,dict(schema='exr_consumers_complete_v1',status='complete',attempt=name,postprocess_sha256=sha(postpath),
        consumer_scope='raw_exr_only',producer_output_closed=True,raw_exr_consumers_finished=True,raw_exr_required=False,
        raw_exr_consumer_process_ids=[post['consumer_process_id']],reference_indexes=[dict(path=str(index),sha256=sha(index))]),True)
    dry=storage.cleanup(postpath,consumer);save(work/(name+'__EXR_dryrun.json'),dry,True)
    done=storage.cleanup(postpath,consumer,True,dry['files_sha256']);save(work/(name+'__EXR_complete.json'),done,True)
    return dict(stage=str(stage),RGB=1200,mask=1200,person_pose=12000,EXR_deleted=done['file_count'],EXR_bytes=done['bytes'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--admission',required=True)
    parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    require(Path(args.admission).name==args.admission,'准入文件名越界')
    admission=read(RUN/args.admission);bindings(admission)
    refs=[r for r in read(RUN/'manifest.json')['plans'] if r['stage']=='full']
    require([(r['seed'],r['variant']) for r in refs]==[(1048,'A'),(1048,'B'),(1102,'A'),(1102,'B')],'整批矩阵改变')
    for ref in refs:require(sha(ref['path'])==ref['sha256'],'计划SHA改变')
    if not args.execute:
        print(json.dumps(dict(status='readonly_full_preflight',attempts=4,RGB=4800,mask=4800,person_pose=48000,
            lifecycle='fresh_Editor_each_variant_normal_quit_before_CPU_export',write_runtime=[12,8],resources=resources())));return
    work=RUN/'full_driver_a01';work.mkdir(exist_ok=False)
    state=dict(schema='seeded_kit_full_batch_v1',status='started',pid=os.getpid(),completed=[],
        admission_sha256=sha(RUN/args.admission),driver_sha256=sha(__file__),test_read=False)
    def put():save(work/'state.json',state)
    put()
    spec=importlib.util.spec_from_file_location('kit_storage',ROOT/'tools/storage/dataset_storage_policy.py')
    storage=importlib.util.module_from_spec(spec);spec.loader.exec_module(storage)
    try:
        for ref in refs:
            bindings(admission);name=ref['attempt'];capture=ROOT/'Saved/Pose17Development/smoke'/name
            require(not capture.exists() and not (DATASET/'_work'/name).exists(),'新整批attempt已有内容，不重放')
            require(storage.shutil.disk_usage(DATASET).free>=180*1024**3,'单变体raw+导出空间预算不足180GiB')
            state.update(status='launching_fresh_Editor',current=name);put()
            runname='kit_full_'+name
            with (work/(name+'__launch.log')).open('xb') as log:
                code=subprocess.call([str(PWSH),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'tools/open_editor.ps1'),
                    '-EngineRoot','E:/UE_5.8','-RunName',runname],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            require(code==0,'Editor启动保护未通过，保留现场')
            launch=read(ROOT/'Saved/EditorStartup'/runname/'launch.json');pid=launch['pid']
            rows=identity(pid)
            require(len(rows)==1 and rows[0]['Name']=='UnrealEditor.exe'
                and 'FustalMOT_UEDataset.uproject' in rows[0]['CommandLine'],'启动PID不是本项目Editor')
            state.update(editor_pid=pid,editor_launch=runname);put();ready_mcp()
            for action in ('initialize_runtime','preflight','prepare','configure_depth','floor_preflight','floor_apply'):
                call(name,action,args.admission,pid,work)
            budget=resources();require(budget['commit_headroom_bytes']>=20*1024**3,'fresh Editor提交余量不足20GiB，未开始MRQ')
            state.update(status='rendering',pre_submit_resources=budget,variant_min_commit_bytes=budget['commit_headroom_bytes']);put()
            call(name,'submit',args.admission,pid,work);until=time.monotonic()+6*3600
            while True:
                budget=resources();current=read(capture/'state.json')
                state.update(capture_status=current['status'],last_resources=budget,
                    variant_min_commit_bytes=min(state['variant_min_commit_bytes'],budget['commit_headroom_bytes']));put()
                if current['status']=='rendered_requires_RGB_mask_pose_alignment_acceptance':break
                require(current['status']=='submitted_async','MRQ失败：'+repr(current.get('errors')))
                if budget['commit_headroom_bytes']<6*1024**3:
                    call(name,'cancel_memory_guard',args.admission,pid,work)
                    raise RuntimeError('实际commit不足6GiB，已仅正常取消自有MRQ，不重试')
                require(time.monotonic()<until,'MRQ超过六小时，保留现场不强杀')
                time.sleep(2)
            for action in ('postflight','floor_restore','release','quit_after_release'):
                call(name,action,args.admission,pid,work)
            until=time.monotonic()+120
            while identity(pid):
                require(time.monotonic()<until,'正常quit后进程未退出，禁止强杀/继续');time.sleep(2)
            logpath=Path(launch['log'])
            with logpath.open('rb') as stream:
                stream.seek(max(0,logpath.stat().st_size-131072));tail=stream.read().decode('utf-8',errors='replace')
            require('LogExit: Exiting.' in tail and 'Log file closed' in tail,'本次正常退出日志未闭合')
            save(work/(name+'__shutdown.json'),dict(status='normal_exit_confirmed',pid=pid,process_absent=True,
                log=str(logpath),log_has_Exiting_and_closed=True,quit_receipt_sha256=sha(RUN/'ue_receipts'/(name+'__quit_after_release.json'))),True)
            state.update(status='CPU_export_and_EXR_retirement',Editor_open=False);put()
            result=postprocess(name,work,storage)
            state['completed'].append(dict(attempt=name,seed=ref['seed'],variant=ref['variant'],
                minimum_commit_headroom_bytes=state['variant_min_commit_bytes'],normal_UE_exit=True,**result));put()
        state.update(status='complete_four_full_exports_EXR_retired_all_UE_normal_exit_wait_root_publication',
            RGB=4800,mask=4800,person_pose=48000,EXR_deleted=4800,production_accepted=False)
        put()
    except BaseException as error:
        state.update(status='failed_preserved_no_replay',error=repr(error));put();raise


if __name__=='__main__':main()
