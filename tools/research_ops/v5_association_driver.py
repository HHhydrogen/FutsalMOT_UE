"""v5九臂固定检测追踪串行driver；默认只读，训练真退出后root启用。"""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from v5_association_runtime import load,check_fixed,training_complete,require,read,sha,bound
SEEDS=(20261024,20261025,20261026)
ARMS=('R3','R3S_blue','R3S_terracotta')
PYTHON=Path('D:/projects/FutsalMOT/.venv/Scripts/python.exe')

def atomic(path,value):
    path=Path(path);tmp=path.with_name(path.name+'.tmp');require(not tmp.exists(),'保留未知partial')
    with tmp.open('x',encoding='utf-8') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n');stream.flush();os.fsync(stream.fileno())
    for attempt,delay in enumerate((.05,.1,.2,.4,.8,0)):
        try:os.replace(tmp,path);return
        except PermissionError as error:
            if getattr(error,'winerror',None) not in (5,32) or attempt==5:raise
            time.sleep(delay)

def delta(current,reference):
    result={}
    for sequence,row in current.items():
        ref=reference[sequence]
        result[sequence]=dict(delta_pp={k:row['metrics_percent'][k]-ref['metrics_percent'][k] for k in ('AssA','HOTA','IDF1')},IDSW_delta_count=row['IDSW_count']-ref['IDSW_count'])
    return result

def summarize(runtime):
    config=runtime.config;references={name:read(bound(config[name]))['summary'] for name in ('bbox_metrics','pretrained_metrics')};reports={};pairs={}
    for seed in SEEDS:
        for arm in ARMS:
            path=runtime.root/f'{arm}_seed{seed}'/'metrics/report.json';report=read(path)
            require(report['frames']==450 and report['DO_PREPROC'] is False and report['predictions_filtered'] is False,'指标口径改变')
            reports[f'{arm}_seed{seed}']=dict(path=str(path),sha256=sha(path),summary=report['summary'])
        real=reports[f'R3_seed{seed}']['summary'];pairs[str(seed)]={}
        for arm in ARMS[1:]:
            mixed=reports[f'{arm}_seed{seed}']['summary'];pairs[str(seed)][arm]=dict(vs_same_real_R3=delta(mixed,real),vs_pretrained=delta(mixed,references['pretrained_metrics']),vs_bbox=delta(mixed,references['bbox_metrics']))
    rule=read(config['training_protocol'])['evaluation']['tracking_progress_definition'];results={}
    for arm in ARMS[1:]:
        values=[pairs[str(seed)][arm]['vs_same_real_R3']['COMBINED_SEQ'] for seed in SEEDS]
        means={key:statistics.mean(value['delta_pp'][key] for value in values) for key in ('AssA','HOTA','IDF1')};positive=sum(value['delta_pp']['AssA']>0 for value in values)
        results[arm]=dict(mean_delta_pp=means,positive_AssA_training_seeds=positive,mean_IDSW_delta_count=statistics.mean(value['IDSW_delta_count'] for value in values),
            registered_progress_passed=means['AssA']>=rule['mean_AssA_delta_pp_min'] and positive>=rule['positive_seed_count_min'] and means['HOTA']>=rule['HOTA_mean_delta_min'] and means['IDF1']>=rule['IDF1_mean_delta_pp_min'])
    return dict(schema='futsalmot_v5_ninearm_fixed_detection_tracking_summary_v1',status='all_nine_association_and_metrics_complete',reports=reports,paired=pairs,registered_rule=rule,progress_by_floor=results,
        all_negative_and_zero_results_retained=True,raw_detections_reinferred=False,pretrained_pose_reinferred=False,three_training_seeds_not_three_matches=True,final116187_read=False,
        limitations=['same_game9_three_development_clips','no_crossmatch_or_futsal_generalization_claim','scale_matching_also_changes_person_density_valid_points_and_compute'])

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--execute',action='store_true');parser.add_argument('--driver-sha256');args=parser.parse_args()
    runtime=load(args.config);manifest,frames,configuration=check_fixed(runtime);complete=training_complete(runtime.config,require_absent=False)
    if not args.execute:
        print(json.dumps(dict(status='readonly_prerequisites_complete_no_launch' if complete else 'readonly_fixed_inputs_valid_waiting_training',frames=len(frames),detections=sum(len(f['detections']) for f in frames),training_complete=complete is not None),ensure_ascii=False));return
    require(runtime.config.get('execution_authorized') is True and runtime.config.get('approved_by')=='root','root尚未启用关联')
    require(args.driver_sha256==sha(__file__),'必须绑定实际trackingdriver SHA');complete=training_complete(runtime.config,require_absent=True);require(complete is not None,'九训练未完成')
    require(not runtime.root.exists(),'原目录/partial保持；拒绝覆盖或隐式重跑');runtime.root.mkdir(parents=True)
    lock=runtime.root/'driver.lock'
    with lock.open('x',encoding='utf-8') as stream:stream.write(json.dumps(dict(pid=os.getpid(),driver_sha256=sha(__file__))))
    state=dict(schema='futsalmot_v5_association_driver_state_v1',status='starting',pid=os.getpid(),source_sha256=sha(__file__),config_sha256=sha(args.config),
        training_summary_sha256=complete['summary_sha256'],completed=[],child_pid=None);path=runtime.root/'driver_state.json';atomic(path,state)
    try:
        for seed in SEEDS:
            for arm in ARMS:
                key=f'{arm}_seed{seed}'
                for stage in ('attachment','tracking','metrics'):
                    state.update(status=stage,current_arm=key);atomic(path,state)
                    command=[str(PYTHON),'-B',str(runtime.bundle/'tools/research_ops/v5_association_stage.py'),stage,'--config',str(args.config),'--seed',str(seed),'--arm',arm,'--execute']
                    log=runtime.root/'logs'/f'{key}_{stage}.log';log.parent.mkdir(exist_ok=True)
                    with log.open('x',encoding='utf-8') as stream:
                        child=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,cwd=runtime.bundle,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));state['child_pid']=child.pid;atomic(path,state);code=child.wait()
                    require(code==0,'阶段失败；保留日志，不自动重放:'+str(log));state['child_pid']=None
                report=runtime.root/key/'metrics/report.json';state['completed'].append(dict(seed=seed,arm=arm,report=dict(path=str(report),sha256=sha(report))));atomic(path,state)
                if (runtime.root/'STOP_AFTER_CURRENT').exists():state.update(status='stopped_user_request_after_committed_arm');atomic(path,state);return
        summary=summarize(runtime);atomic(runtime.root/'paired_summary.json',summary);state.update(status='complete_all_nine_association_and_metrics',summary=dict(path=str(runtime.root/'paired_summary.json'),sha256=sha(runtime.root/'paired_summary.json')));atomic(path,state);lock.unlink()
    except BaseException as error:
        state.update(status='stopped_preserved_no_replay',error_type=type(error).__name__,error=str(error));atomic(path,state);raise
if __name__=='__main__':main()
