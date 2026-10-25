"""v9主对照先行、首seed单因素消融随后；唯一串行控制，不隐式重放。"""
import argparse,os,subprocess,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/research_ops'))
from v9_train import read,sha,checked,require,atomic
from v8_control import process_snapshot,own_launcher_chain
V=Path('D:/projects/FutsalMOT_Research/pose/pose_quality_v9')
MAIN=('motion_residual','robust','gated');EXPLORATORY=('mask','raw','drop','jitter')
def expected_matrix():
    return [dict(fold=f,seed=s,variant=v,regime=r) for f in ('game4','game6','game9') for s in (20261024,20261025,20261026) for v in MAIN for r in ('R','RS')]+[dict(fold=f,seed=20261024,variant=v,regime=r) for f in ('game4','game6','game9') for v in EXPLORATORY for r in ('R','RS')]
def preflight(config,output):
    cfg=read(config);require(cfg['training_authorized'] and cfg['tracking_authorized'] and cfg['approved_by']=='root','新v9准入')
    require(Path(__file__).resolve()==Path(cfg['bundle'])/'tools/research_ops/v9_control.py','只执行D bundle')
    for f in read(checked(cfg['bundle_manifest']))['files']:require(sha(Path(cfg['bundle'])/f['path'])==f['sha256'],'源码改变')
    require(cfg['training_matrix']==expected_matrix() and len(cfg['training_matrix'])==78,'事前78组计划变化')
    require(read(checked(cfg['v8_milestone']))['status']=='complete_registered_development_progress_with_pose_limit','v8未真实结束')
    for key in ('admission','diagnosis_summary','source_config','recovery_registry','v8_analysis'):checked(cfg[key])
    for f in cfg['folds'].values():
        for key in ('real_pool','normalizer','quality_scale'):checked(f[key])
        for ref in f['exposures'].values():checked(ref)
    checked(cfg['synthetic_pool']);output=Path(output).resolve();require(V in output.parents and not output.exists(),'新控制目录，保留partial')
    processes=process_snapshot();own=own_launcher_chain(processes,os.getpid(),Path(__file__).resolve());blocked=[p for p in processes if p['ProcessId'] not in own and ('unrealeditor' in p['Name'].lower() or any(t in (p.get('CommandLine') or '') for t in ('v9_control.py','v9_train.py','v9_track.py','v8_control.py','v8_train.py')))]
    require(not blocked,'自有任务/UE占用，禁止重复启动:'+str(blocked))
    return cfg,dict(status='readonly_v9_preflight',protocol_sha256=sha(config),planned_runs=78,main_runs=54,exploratory_runs=24,planned_updates=78000,R_windows_per_arm=3000,S_windows_per_RS_arm=1000,own_verified_launcher_chain=sorted(own),test_read=False)
def execute(config,output):
    cfg,flight=preflight(config,output);output=Path(output);output.mkdir(parents=True);atomic(output/'preflight.json',flight);state=dict(schema='v9_serial_quality_residual_control',status='starting',pid=os.getpid(),protocol_sha256=sha(config),completed_train=[],completed_tracking=[],active=None)
    def save():state['updated_utc']=datetime.now(timezone.utc).isoformat();atomic(output/'driver_state.json',state)
    def child(tag,script,args):
        require(not (output/'STOP').exists(),'STOP边界停止');log=output/'logs'/tag;log.parent.mkdir(parents=True,exist_ok=True);command=[sys.executable,'-B',str(Path(cfg['bundle'])/'tools/research_ops'/script)]+list(map(str,args));start=time.perf_counter()
        with log.with_suffix('.stdout.txt').open('x',encoding='utf-8') as stdout,log.with_suffix('.stderr.txt').open('x',encoding='utf-8') as stderr:
            p=subprocess.Popen(command,stdout=stdout,stderr=stderr,env=os.environ.copy());state['active']=dict(tag=tag,child_pid=p.pid,command=command);save();code=p.wait()
        require(code==0,f'{tag} exit{code}; 完整保留，不自动重放');state['active']=None;save();return time.perf_counter()-start
    identities={}
    try:
        for index,job in enumerate(cfg['training_matrix']):
            state['status']='main_training_and_tracking' if index<54 else 'exploratory_first_seed_ablations';save();fold=job['fold'];seed=job['seed'];variant=job['variant'];regime=job['regime'];directory=output/'runs'/fold/str(seed)/variant/regime;tag=f'{fold}_{seed}_{variant}_{regime}'
            seconds=child(tag+'_train','v9_train.py',['--config',config,'--output',directory/'training','--fold',fold,'--seed',seed,'--variant',variant,'--regime',regime,'--execute']);receipt=read(directory/'training/run_receipt.json');binding=receipt['binding'];require(receipt['status']=='complete' and receipt['completed_updates']==1000 and receipt['real_window_exposures']==3000 and receipt['synthetic_window_exposures']==(1000 if regime=='RS' else 0),'真实预算不足')
            common=(binding['initialization_sha256'],binding['R_window_UID_chain_sha256']);key=(fold,seed)
            if key not in identities:identities[key]=common
            require(identities[key]==common and receipt['prefetch']['closed'] and receipt['prefetch']['yielded']==1000 and not receipt['prefetch']['worker_alive'],'初始化/R顺序或预取未闭合')
            state['completed_train'].append(dict(**job,path=str(directory/'training'),receipt_sha256=sha(directory/'training/run_receipt.json'),process_wall_seconds=seconds));save()
            child(tag+'_tracking','v9_track.py',['--config',config,'--run',directory/'training','--output',directory/'tracking','--execute'])
            child(tag+'_metric','v9_metric.py',['--config',config,'--tracking',directory/'tracking','--output',directory/'metric','--execute'])
            child(tag+'_recovery','v8_gap_recovery.py',['--registry',checked(cfg['recovery_registry']),'--tracking',directory/'tracking','--output',directory/'recovery.json'])
            result=read(directory/'metric/report.json');require(result['status']=='complete' and result['protocol_sha256']==sha(config),'评价收据不闭合');state['completed_tracking'].append(dict(**job,path=str(directory),metric_sha256=sha(directory/'metric/report.json')));save()
            if index==53:state['main54_complete']=True;save()
        state['status']='complete_78_train_and_tracking_wait_analysis';save()
        child('final_analysis','v9_analyze.py',['--config',config,'--control',output,'--output',output/'analysis_a01']);state['status']='complete_78_train_tracking_and_analysis';save()
    except BaseException as error:state['status']='failed_preserved_no_automatic_replay';state['error']=repr(error);state['traceback']=traceback.format_exc();save();raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args();os.environ.update(PYTHONUTF8='0',PYTHONIOENCODING='utf-8',PYTHONPATH='D:/projects/FutsalMOT_Research/runtime_dependencies')
    if a.execute:execute(a.config,a.output)
    else:import json;print(json.dumps(preflight(a.config,a.output)[1],ensure_ascii=False))
