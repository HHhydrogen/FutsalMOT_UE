"""v6十模型串行crop接入验证；0新训练更新，全部seed/floor保留。"""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import time
from v6_crop_runtime import load,read,sha,bound,require,RESEARCH

PYTHON=Path('D:/projects/FutsalMOT/.venv/Scripts/python.exe')
MODELS=['pretrained']+[f'{arm}_seed{seed}' for seed in (20261024,20261025,20261026) for arm in ('R3','R3S_blue','R3S_terracotta')]

def atomic(path,value):
    path=Path(path);temporary=path.with_name(path.name+'.tmp');require(not temporary.exists(),'保留已有partial')
    with temporary.open('x',encoding='utf-8') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n');stream.flush();os.fsync(stream.fileno())
    for attempt,delay in enumerate((.05,.1,.2,.4,.8,0)):
        try:os.replace(temporary,path);return
        except PermissionError as error:
            if getattr(error,'winerror',None) not in (5,32) or attempt==5:raise
            time.sleep(delay)

def boundary(config,bundle):
    if config.get('gpu_boundary_receipt') is None:return False
    report=read(bound(config['gpu_boundary_receipt']));smoke_config=read(bound(config['gpu_boundary_config']))
    require(report['status']=='smoke_complete_not_full_tracking_input' and report['counts']['frames']==2 and report['batch_size']==16 and report['dtype']=='float32' and report['autocast'] is False,'实际GPU边界小样不符')
    require(report['config_sha256']==config['gpu_boundary_config']['sha256'] and report['configuration']==config['crop_configuration'],'边界小样并非同一参数')
    small_manifest=read(bound(smoke_config['bundle_manifest']));current_manifest=read(bound(config['bundle_manifest']))
    old={entry['path']:entry['sha256'] for entry in small_manifest['files']};new={entry['path']:entry['sha256'] for entry in current_manifest['files']}
    for name in ('python/src/grf_ue_bridge/fixed_detection_crop_pose_v6.py','tools/research_ops/v6_crop_runtime.py','tools/research_ops/v6_crop_attach.py'):
        require(old[name]==new[name],'GPU边界通过后core/runtime/attach字节改变')
    return True

def difference(a,b):
    return {sequence:dict(delta_pp={key:a[sequence]['metrics_percent'][key]-b[sequence]['metrics_percent'][key] for key in ('AssA','HOTA','IDF1')},IDSW_delta_count=a[sequence]['IDSW_count']-b[sequence]['IDSW_count']) for sequence in a}

def summary(config,root):
    values={};references={}
    for key in MODELS:
        report_path=root/key/'metrics/report.json';report=read(report_path);attachment_path=root/key/'attachment/crop_attachment_manifest.json';attachment=read(attachment_path)
        require(report['DO_PREPROC'] is False and report['predictions_filtered'] is False and report['frames']==450,'TrackEval数值口径变化')
        counts=attachment['counts'];require(counts['raw_UID_crop_attempts']==6901 and counts.get('geometry_valid',0)+counts.get('bbox_fallback',0)==6901,'不能将尝试数伪装为全部有效')
        full_path=bound(config['models'][key]['full_frame_metrics']);full=read(full_path)
        values[key]=dict(metrics=dict(path=str(report_path),sha256=sha(report_path)),summary=report['summary'],coverage=dict(attempts=6901,geometry_valid=counts.get('geometry_valid',0),bbox_fallback=counts.get('bbox_fallback',0),geometry_fraction=counts.get('geometry_valid',0)/6901,rejections={name:value for name,value in counts.items() if name.startswith('reason:')}),
            crop_vs_same_model_full_frame=difference(report['summary'],full['summary']),full_frame_reference=dict(path=str(full_path),sha256=sha(full_path)))
        references[key]=full['summary']
    paired={}
    for seed in (20261024,20261025,20261026):
        real=values[f'R3_seed{seed}']['summary'];paired[str(seed)]={}
        for arm in ('R3S_blue','R3S_terracotta'):
            key=f'{arm}_seed{seed}';paired[str(seed)][arm]=dict(vs_same3000R_crop_R3=difference(values[key]['summary'],real),vs_crop_pretrained=difference(values[key]['summary'],values['pretrained']['summary']))
    rule=read(config['inherited_training_protocol']['path'])['evaluation']['tracking_progress_definition'];progress={}
    for arm in ('R3S_blue','R3S_terracotta'):
        rows=[paired[str(seed)][arm]['vs_same3000R_crop_R3']['COMBINED_SEQ'] for seed in (20261024,20261025,20261026)]
        means={key:statistics.mean(row['delta_pp'][key] for row in rows) for key in ('AssA','HOTA','IDF1')};positive=sum(row['delta_pp']['AssA']>0 for row in rows)
        progress[arm]=dict(mean_delta_pp=means,positive_training_seeds=positive,mean_IDSW_delta_count=statistics.mean(row['IDSW_delta_count'] for row in rows),
            inherited_descriptive_progress_rule_passed=means['AssA']>=rule['mean_AssA_delta_pp_min'] and positive>=rule['positive_seed_count_min'] and means['HOTA']>=rule['HOTA_mean_delta_min'] and means['IDF1']>=rule['IDF1_mean_delta_pp_min'])
    return dict(schema='futsalmot_ten_model_crop_pose_exploratory_summary_v6',status='complete_all_ten_models',exploratory=True,models=values,paired=paired,descriptive_progress=progress,registered_rule=rule,
        new_formal_optimizer_updates=0,raw_reinferred=False,old_fullframe_cache_changed=False,all_seed_floor_negative_zero_results_retained=True,
        limitations=['post_v5_exploratory_inference_interface_not_independent_training_confirmation','three_training_seeds_not_independent_matches','crop_plus_batch16_FP32_interface_changes_beyond_original_fullframe','geometry_valid_not_pose_accuracy_or_visibility','no_final116187_read'])

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--execute',action='store_true');parser.add_argument('--driver-sha256');args=parser.parse_args()
    config,bundle,base,legacy,core=load(args.config);require(list(config['models'])==MODELS,'必须原预训练+九actualEMA，不能筛model/seed')
    admitted=boundary(config,bundle)
    if not args.execute:print(json.dumps(dict(status='readonly_ten_model_crop_ready' if admitted else 'readonly_ten_model_crop_waiting_GPU_boundary',models=len(MODELS),GPU_boundary_passed=admitted,new_training_updates=0)));return
    require(config.get('execution_authorized') is True and config.get('approved_by')=='root' and admitted,'root尚未签完整探索或GPU边界未通过')
    require(args.driver_sha256==sha(__file__),'实际driver SHA不符');legacy.training_complete(base.config,require_absent=True)
    root=Path(config['output_root']).resolve();require(RESEARCH/'pose/association_dev_a01/v6_crop' in root.parents and not root.exists(),'全新控制目录，不覆盖partial/隐式重放')
    root.mkdir(parents=True)
    with (root/'driver.lock').open('x',encoding='utf-8') as stream:stream.write(json.dumps(dict(pid=os.getpid(),source_sha256=sha(__file__))))
    config_sha=sha(args.config);state=dict(schema='futsalmot_ten_model_crop_driver_state_v6',status='starting',pid=os.getpid(),config_sha256=config_sha,driver_sha256=sha(__file__),completed=[],child_pid=None)
    path=root/'driver_state.json';atomic(path,state)
    try:
        for key in MODELS:
            for stage in ('attachment','tracking','metrics'):
                require(sha(args.config)==config_sha,'已冻结输入改变，停止不重试');state.update(status=stage,current_model=key);atomic(path,state)
                if stage=='attachment':command=[str(PYTHON),'-B',str(bundle/'tools/research_ops/v6_crop_attach.py'),'--config',str(args.config),'--model',key,'--output',str(root/key/'attachment'),'--execute']
                else:
                    source=root/key/('attachment/crop_attachment_manifest.json' if stage=='tracking' else 'tracking')
                    command=[str(PYTHON),'-B',str(bundle/'tools/research_ops/v6_crop_tracking.py'),stage,'--config',str(args.config),'--model',key,'--input',str(source),'--output',str(root/key/stage),'--execute']
                log=root/'logs'/f'{key}_{stage}.log';log.parent.mkdir(exist_ok=True)
                with log.open('x',encoding='utf-8') as stream:
                    child=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,cwd=bundle,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));state['child_pid']=child.pid;atomic(path,state);code=child.wait()
                require(code==0,'阶段失败，保留日志和partial，不重训不重放:'+str(log));state['child_pid']=None
            state['completed'].append(key);atomic(path,state)
            if (root/'STOP_AFTER_CURRENT').exists():state.update(status='stopped_user_request_after_committed_model');atomic(path,state);return
        report=summary(config,root);atomic(root/'paired_summary.json',report);state.update(status='complete_all_ten_models_crop_tracking',summary=dict(path=str(root/'paired_summary.json'),sha256=sha(root/'paired_summary.json')));atomic(path,state);(root/'driver.lock').unlink()
    except BaseException as error:state.update(status='stopped_preserved_no_replay',error_type=type(error).__name__,error=str(error));atomic(path,state);raise
if __name__=='__main__':main()
