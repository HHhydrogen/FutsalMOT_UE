"""v8三折/三seed/四臂唯一串行控制器；未知partial不重放，默认只读。"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/research_ops'))
from v8_train import read,sha,checked,require,atomic,GAMES,ARMS
RESEARCH=Path('D:/projects/FutsalMOT_Research')
SEEDS=(20261024,20261025,20261026)

def process_snapshot():
    command="Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    result=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,encoding='utf-8',errors='replace')
    require(result.returncode==0,'CIM查询失败，不把空表冒充无占用:'+result.stderr)
    values=json.loads(result.stdout) if result.stdout.strip() else []
    return values if isinstance(values,list) else [values]

def preflight(config,output):
    cfg=read(config);require(cfg.get('training_authorized') is True and cfg.get('tracking_authorized') is True and cfg.get('approved_by')=='root','需root新冻结训练及追踪准入')
    require(Path(__file__).resolve()==Path(cfg['bundle'])/'tools/research_ops/v8_control.py','只执行不可变bundle')
    for entry in read(checked(cfg['bundle_manifest']))['files']:require(sha(Path(cfg['bundle'])/entry['path'])==entry['sha256'],'源码绑定改变')
    require(cfg['test116187_sealed'] is True and cfg['seeds']==list(SEEDS) and cfg['arms']==list(ARMS),'封存或矩阵变化')
    admission=read(checked(cfg['admission']));require(admission['approved_by']=='root' and admission['training_authorized'] is True and admission['tracking_authorized'] is True and admission['test116187_read'] is False,'限定身份监督准入缺失')
    require(set(cfg['folds'])==set(GAMES),'三折缺失')
    for game in GAMES:
        for ref in [cfg['folds'][game]['real_pool'],cfg['folds'][game]['normalizer']]+list(cfg['folds'][game]['exposures'].values()):checked(ref)
    for key in ('synthetic_pool','pairs_complete','source_config','recovery_registry'):checked(cfg[key])
    require(read(checked(cfg['recovery_registry']))['status']=='complete_predeclared_detection_gap_registry','断档登记未完成')
    source=read(checked(cfg['source_config']));require(len(source['sources'])==7,'固定三真实/四合成来源')
    for item in source['sources']:
        checked(item['cache'])
        if item['domain']=='real':
            require(item['sequence'] in ('SNMOT-060','SNMOT-097','SNMOT-151'),'禁止扩大真实scope')
            for key in ('gt','gameinfo','seqinfo'):checked(item[key])
        else:require(item['seed']==1048 and item['floor']=='sport_blue_v1','只准1048蓝');checked(item['annotations'])
    output=Path(output).resolve();require(RESEARCH/'pose/learned_association_v8' in output.parents and not output.exists(),'需全新控制目录；partial禁止重放')
    processes=process_snapshot()
    blocked=[p for p in processes if p['ProcessId']!=os.getpid() and (str(p['Name']).lower().startswith('unrealeditor') or any(word in (p.get('CommandLine') or '') for word in ('v8_control.py','v8_train.py','v8_prediction_cache.py','train_pose_location','run_poseonly_')))]
    require(not blocked,'已有UE/同类自有GPU任务，拒绝重复启动:'+str(blocked))
    return cfg,dict(status='readonly_v8_preflight',protocol_sha256=sha(config),folds=list(GAMES),seeds=list(SEEDS),arms=list(ARMS),planned_train_runs=36,planned_actual_updates=36000,planned_real_window_exposures=108000,planned_synthetic_window_exposures=18000,processes=processes,test_read=False)

def execute(config,output):
    cfg,flight=preflight(config,output);output=Path(output).resolve();output.mkdir(parents=True)
    atomic(output/'preflight.json',flight)
    state=dict(schema='v8_serial_control',status='starting',pid=os.getpid(),protocol_sha256=sha(config),completed_train=[],completed_tracking=[],updated_utc=None,active=None)
    def save():state['updated_utc']=datetime.now(timezone.utc).isoformat();atomic(output/'driver_state.json',state)
    def child(tag,filename,args):
        require(not (output/'STOP').exists(),'STOP请求：在下一子任务边界停止')
        log=output/'logs'/tag;log.parent.mkdir(parents=True,exist_ok=True)
        require(not log.with_suffix('.stdout.txt').exists(),'同名任务日志已存在，禁止隐式重放')
        command=[sys.executable,'-B',str(Path(cfg['bundle'])/'tools/research_ops'/filename)]+list(map(str,args))
        started=time.perf_counter()
        with log.with_suffix('.stdout.txt').open('x',encoding='utf-8') as stdout,log.with_suffix('.stderr.txt').open('x',encoding='utf-8') as stderr:
            proc=subprocess.Popen(command,stdout=stdout,stderr=stderr,env=os.environ.copy())
            state['active']=dict(tag=tag,child_pid=proc.pid,command=command);save();code=proc.wait()
        duration=time.perf_counter()-started
        require(code==0,f'{tag} exit{code}；保留全部日志/last/曝光，禁止自动重放')
        state['active']=None;save();return duration
    def track_and_metric(game,mode,target,run=None):
        tag=target.relative_to(output).as_posix().replace('/','_');args=['--config',config,'--fold',game,'--mode',mode,'--output',target/'tracking','--execute']
        if run:args+=['--run',run]
        track_seconds=child(tag+'_tracking','v8_track.py',args)
        child(tag+'_metric','v8_metric.py',['--config',config,'--tracking',target/'tracking','--output',target/'metric','--execute'])
        child(tag+'_recovery','v8_gap_recovery.py',['--registry',checked(cfg['recovery_registry']),'--tracking',target/'tracking','--output',target/'recovery.json'])
        receipt=read(target/'tracking/receipt.json');metric=read(target/'metric/report.json')
        require(receipt['status']==metric['status']=='complete' and receipt['fold']==metric['fold']==game and receipt['protocol_sha256']==sha(config),'实际追踪/评价收据未闭合')
        state['completed_tracking'].append(dict(fold=game,mode=mode,path=str(target),receipt_sha256=sha(target/'tracking/receipt.json'),metric_sha256=sha(target/'metric/report.json'),track_seconds=track_seconds));save()
    try:
        state['status']='pretrained_fixed_baselines';save()
        for game in GAMES:
            for mode in ('PT_bbox','PT_static_pose'):track_and_metric(game,mode,output/'baselines'/game/mode)
        for game in GAMES:
            for seed in SEEDS:
                common=None
                for arm in ARMS:
                    state['status']='training_and_heldout_evaluation';save();directory=output/'runs'/game/str(seed)/arm
                    seconds=child(f'train_{game}_{seed}_{arm}','v8_train.py',['--config',config,'--output',directory/'training','--fold',game,'--seed',seed,'--arm',arm,'--device','cuda:0','--execute'])
                    receipt=read(directory/'training/run_receipt.json');binding=receipt['binding']
                    require(receipt['status']=='complete' and receipt['completed_updates']==1000 and receipt['real_window_exposures']==3000 and receipt['synthetic_window_exposures']==(1000 if arm.endswith('_RS') else 0),'真实更新或窗口曝光不足')
                    require(binding['protocol_sha256']==sha(config) and binding['fold']==game and binding['seed']==seed and binding['arm']==arm and receipt['checkpoint_sha256']==sha(directory/'training/last.pt'),'训练身份或last变化')
                    require(receipt['prefetch']['closed'] and not receipt['prefetch']['worker_alive'] and receipt['prefetch']['yielded']==1000,'预取未闭合')
                    identity=(binding['initialization_sha256'],binding['R_window_UID_chain_sha256'])
                    if common is None:common=identity
                    require(identity==common,'四臂实际初始化/真实窗口顺序不一致')
                    state['completed_train'].append(dict(fold=game,seed=seed,arm=arm,path=str(directory/'training'),receipt_sha256=sha(directory/'training/run_receipt.json'),process_wall_seconds=seconds,binding=binding));save()
                    track_and_metric(game,'learned',directory,run=directory/'training')
        state['status']='all_36_train_and_42_tracking_complete_wait_analysis';save()
        child('final_analysis','v8_analyze.py',['--config',config,'--control',output,'--output',output/'analysis_a01'])
        state['status']='complete_36_train_42_tracking_and_analysis';save()
    except BaseException as error:
        state['status']='failed_preserved_no_automatic_replay';state['error']=repr(error);state['traceback']=traceback.format_exc();save();raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    os.environ.update(PYTHONUTF8='0',PYTHONIOENCODING='utf-8',PYTHONPATH=str(RESEARCH/'runtime_dependencies'))
    if a.execute:execute(a.config,a.output)
    else:print(json.dumps(preflight(a.config,a.output)[1],ensure_ascii=False))
