"""四个独立A/B短样串行执行；只继承明确已准备的首A，不重放未知事务。"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'Saved/AppearancePlanning/seeded_kit_capture_a02'
UEPY=Path('E:/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def require(ok,message):
    if not ok:raise RuntimeError(message)


def save(path,value,exclusive=False):
    if exclusive:
        with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)
    else:
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(temp,path)


def resources():
    class Info(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in
            ('CommitTotal','CommitLimit','CommitPeak','PhysicalTotal','PhysicalAvailable',
             'SystemCache','KernelTotal','KernelPaged','KernelNonpaged','PageSize')]+[
             ('HandleCount',ctypes.c_ulong),('ProcessCount',ctypes.c_ulong),('ThreadCount',ctypes.c_ulong)]
    info=Info();info.cb=ctypes.sizeof(info)
    require(ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(info),info.cb),'系统commit读取失败')
    return dict(commit_headroom_bytes=(info.CommitLimit-info.CommitTotal)*info.PageSize,
                physical_available_bytes=info.PhysicalAvailable*info.PageSize)


def bindings(admission):
    require(admission['runtime_authorized'] is True and admission['stage']=='short','只允许独立短样准入')
    require(sha(RUN/'manifest.json')==admission['manifest_sha256'],'清单变化')
    for ref in admission['source_files']:
        require(sha(ROOT/ref['path'])==ref['sha256'],'冻结代码/资产绑定变化：'+ref['path'])
    require(sha(ROOT/'Binaries/Win64/UnrealEditor-FutsalMOT.dll')==admission['module_sha256'],'DLL变化')


def perform(attempt,action,admission_name,work):
    result=RUN/'ue_receipts'/(attempt+'__'+action+'.json')
    require(not result.exists(),'动作已存在，拒绝隐式重放：'+action)
    save(RUN/'action_request.json',dict(attempt=attempt,action=action,admission_file=admission_name))
    output=work/(attempt+'__'+action+'_mcp.json')
    log=work/(attempt+'__'+action+'.log')
    with log.open('xb') as stream:
        code=subprocess.call([str(UEPY),'-B',str(ROOT/'tools/mcp_cli.py'),'--request',
            str(RUN/'mcp_request.json'),'--receipt',str(output)],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
    require(code==0 and result.exists(),'UE动作未确认成功，保留现场：'+action)
    return read(result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admission',required=True)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    require(Path(args.admission).name==args.admission,'准入文件名越界')
    admission=read(RUN/args.admission);bindings(admission)
    refs=[r for r in read(RUN/'manifest.json')['plans'] if r['stage']=='short']
    require([(r['seed'],r['variant']) for r in refs]==[(1048,'A'),(1048,'B'),(1102,'A'),(1102,'B')],'四短样矩阵变化')
    for ref in refs:require(sha(ref['path'])==ref['sha256'],'计划变化')
    work=RUN/'short_driver_a01'
    if not args.execute:
        print(json.dumps(dict(status='readonly_preflight',attempts=[r['attempt'] for r in refs],resources=resources())))
        return
    work.mkdir(exist_ok=False)
    state=dict(schema='seeded_kit_short_driver_v1',status='started',pid=os.getpid(),completed=[],
        admission_sha256=sha(RUN/args.admission),driver_sha256=sha(__file__),minimum_commit_headroom_bytes=None)
    statepath=work/'state.json';save(statepath,state)
    try:
        for index,ref in enumerate(refs):
            bindings(admission);name=ref['attempt'];state.update(current=name,status='preparing');save(statepath,state)
            capture=ROOT/'Saved/Pose17Development/smoke'/name
            if index==0 and admission.get('inherit_prepared_first_A') is True:
                current=read(capture/'state.json')
                require(current['status']=='prepared_not_submitted' and current['ready_to_render'] is True
                    and current['native_kit_settings_readback']==[dict(targets=10,apply_seeded=False)]*4
                    and read(RUN/'ue_receipts'/(name+'__floor_apply.json'))['status']=='preview_active',
                    '首A不是已知未提交的完整准备状态')
                state['inherited_first_prepare_only']=True
            else:
                require(not capture.exists(),'新短样attempt已存在')
                for action in ('preflight','prepare','configure_depth','floor_preflight','floor_apply'):
                    perform(name,action,args.admission,work)
            budget=resources();require(budget['commit_headroom_bytes']>=16*1024**3,'提交前commit不足16GiB，未提交')
            state.update(status='rendering',pre_submit_resources=budget);save(statepath,state)
            perform(name,'submit',args.admission,work)
            until=time.monotonic()+7200
            while True:
                budget=resources();minimum=state['minimum_commit_headroom_bytes']
                state['minimum_commit_headroom_bytes']=min(budget['commit_headroom_bytes'],minimum if minimum is not None else budget['commit_headroom_bytes'])
                current=read(capture/'state.json');state['capture_status']=current['status'];state['last_resources']=budget
                save(statepath,state)
                if current['status']=='rendered_requires_RGB_mask_pose_alignment_acceptance':break
                require(current['status']=='submitted_async','MRQ终态未成功：'+repr(current.get('errors')))
                if budget['commit_headroom_bytes']<6*1024**3:
                    perform(name,'cancel_memory_guard',args.admission,work)
                    raise RuntimeError('真实commit保护触发；仅取消自有MRQ，不自动重试')
                require(time.monotonic()<until,'等待超过两小时，保留现场不强杀')
                time.sleep(2)
            for action in ('postflight','floor_restore','release'):perform(name,action,args.admission,work)
            current=read(capture/'state.json')
            require(current.get('session_released') is True and not current['errors'],'收尾未成功')
            state['completed'].append(dict(attempt=name,seed=ref['seed'],variant=ref['variant'],state_sha256=sha(capture/'state.json')))
            state.update(status='stage_render_complete_not_exported');save(statepath,state)
        state.update(status='complete_four_short_MRQ_restored_released_wait_export',expected_RGB=48,production_accepted=False)
        save(statepath,state)
    except BaseException as error:
        state.update(status='failed_preserved_no_replay',error=repr(error));save(statepath,state)
        raise


if __name__=='__main__':main()
