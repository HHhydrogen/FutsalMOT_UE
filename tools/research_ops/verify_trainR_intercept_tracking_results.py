"""独立终验截距180新/180旧来源及完整配对；不重推理、拟合或TrackEval。"""
import argparse
from collections import Counter
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
from statistics import mean
import stat
import subprocess
import sys
import traceback

R = Path('D:/projects/FutsalMOT_Research')
EXP = R/'pose/trainR_intercept_calibration_a01'
FOLDS = ('game4', 'game6', 'game9'); SEEDS = (20261024, 20261025, 20261026)
OLD = {'SNMOT-060':'game4', 'SNMOT-097':'game6', 'SNMOT-151':'game9'}
PANELS = ('original_heldout','old_external','seven_observed'); REGIMES = ('R','RS')
METRICS = ('AssA','HOTA','IDF1','DetA','MOTA')
COMPARISONS = ('R_beta_minus_zero','RS_beta_minus_zero','RS_minus_R_calibration_interaction')
DONE = 'complete180_trainR_intercept_tracking_and_paired_analysis'
ANALYSIS_DONE = 'complete180_trainR_intercept_results180_baselines270_pairs45_metric9_gap_descriptions'
STATUS = 'complete180_trainR_intercept_sources360_results270_pairs45_metric9_gap_intervals_and_exit_verified'
INTERVAL_SHA = '7458aa01dc5396124ac40d51ac3a3ff9851ce2a8cb4e61e64f4e7d9b6b695e7e'
FIT_COMPLETE_SHA = '8bceed51386e9302ca44425df5210fadf2b45a2ba2e6ff260a01c9265b683313'
OLD_PROTOCOL_SHA = 'f85e69bc2a50220528a2caf42243ee940768cc0a60a4fa845eab2d7c7da27ef1'
SEVEN_PROTOCOL_SHA = 'fd1b92c70ab91d021a8b055cf89eeb3775d34a506056efe85cb3da90038e9a78'
TOLERANCE_PP = 1e-8  # 仅数值序列化核对；不是效果等效/非劣效界限。
_CHECKED = set()


def require(ok, message):
    if not ok: raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def physical(value):
    path=Path(value); require(path.is_absolute(), '终验所有入口须绝对物理路径')
    path=Path(os.path.abspath(path))
    require(R in path.parents and not any(p.lower()=='test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',p.lower()) for p in path.parts),
        '仅实际研究根；最终测试封存')
    for p in (path,*path.parents):
        if p.exists() or p.is_symlink():
            info=p.lstat(); require(not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400, '不跟随junction或链接')
    return path


def sha(path):
    digest=hashlib.sha256()
    with physical(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):digest.update(block)
    return digest.hexdigest()


def ref(path): return dict(path=str(path),sha256=sha(path))


def checked(reference):
    require(isinstance(reference,dict) and set(reference)>={'path','sha256'} and re.fullmatch('[0-9a-f]{64}',reference['sha256']), '缺完整已签来源')
    path=physical(reference['path']); key=(str(path),reference['sha256'])
    require(path.is_file(), '来源不存在：'+str(path))
    if key not in _CHECKED:
        require(sha(path)==reference['sha256'], '来源SHA改变：'+str(path)); _CHECKED.add(key)
    return path


def read(reference):
    path=checked(reference);require(path.suffix=='.json','只解析已签JSON报告元数据')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def close(a,b):
    return type(a) in (int,float) and type(b) in (int,float) and math.isfinite(a) and math.isfinite(b) and abs(a-b)<=TOLERANCE_PP


def deep_close(actual,expected):
    if type(expected) in (int,float):return close(actual,expected)
    if isinstance(expected,dict):return isinstance(actual,dict) and set(actual)==set(expected) and all(deep_close(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list):return isinstance(actual,list) and len(actual)==len(expected) and all(deep_close(a,b) for a,b in zip(actual,expected))
    return type(actual) is type(expected) and actual==expected


def panels_map(panels):
    require(set(panels)==set(PANELS) and [len(panels[p]) for p in PANELS]==[3,2,7]
        and set(panels['original_heldout'])==set(OLD), '固定3/2/7比赛面板不同')
    seqs=[s for p in PANELS for s in panels[p]];require(len(seqs)==len(set(seqs))==12,'比赛重复或缺失')
    return {s:p for p in PANELS for s in panels[p]}


def expected_cells(panels):
    return {(r,s,f,t) for r in REGIMES for s in panels_map(panels) for f in ((OLD[s],) if s in OLD else FOLDS) for t in SEEDS}


def key(row):return tuple(row[k] for k in ('regime','sequence','fold','seed'))


def process_snapshot():
    command="Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|powershell|UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    result=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,encoding='utf-8',errors='strict',check=True)
    rows=json.loads(result.stdout) if result.stdout.strip() else []
    return [rows] if isinstance(rows,dict) else rows


def processes_absent(rows,state):
    """完整脚本名匹配launcher，不能误匹配本终验器或按旧PID盲判。"""
    names=r'trainR_intercept_(?:tracking_control|tracking|fit_control|fit_job)|ocsort_(?:threshold|cached)_control|pose_velocity_tracking_control'
    pattern=re.compile(r'(?:^|[\\/\s"\x27])(?:'+names+r')[.]py(?=$|[\s"\x27])',re.I)
    blocked=[row for row in rows if (row.get('Name') or '').lower().startswith('unrealeditor') or pattern.search(row.get('CommandLine') or '')]
    require(not blocked,'相关controller/worker/launcher或UE仍在：'+canonical(blocked))
    historical={state['parent_pid']}|{v['worker_pid'] for v in state['workers']}
    reused=[{k:row.get(k) for k in ('ProcessId','ParentProcessId','Name','CommandLine')} for row in rows if row.get('ProcessId') in historical]
    return dict(actual_CIM_checked=True,producer_processes_absent=True,exact_script_name_match=True,
        historical_PIDs_currently_present_with_different_named_identity=reused,PID_alone_not_used_as_process_identity=True)


def public_counts(cfg):
    totals,gt={},{ }
    require(set(cfg['registries'])=={'old_five','seven'},'原两份公开gap分母来源不可缺失')
    for scope,binding in cfg['registries'].items():
        value=read(binding['receipt'])
        if scope=='old_five':
            require('schema' not in value and value['status']=='complete_old5_public_receipt_from_original_frozen_events', '旧五公开历史schema/status不同')
            current=value['event_counts']
        else:
            require(value['schema']=='seven_match_gap_registration_receipt_without_GT_v1' and value['status']=='complete7_gap_registry_before_tracking','七场公开schema/status不同')
            current=value['sequence_event_counts']
        require(value['registry']==binding['registry'] and value['contains_GT_coordinates'] is False and value['tracking_results_read'] is False
            and value['test_read'] is False and value['sources']=={s:cfg['sources'][s] for s in value['sources']}
            and set(current)==set(value['sources'])==set(value['GT_row_counts'])
            and not set(current)&set(totals) and all(type(n) is int and n>=0 for n in current.values())
            and sum(current.values())==value['event_count'],'原公开全事件/GT计数不齐或不同源')
        totals.update(current);gt.update(value['GT_row_counts'])
    require(set(totals)==set(cfg['sources']) and sum(totals.values())==3690 and gt==cfg['expected_GT_rows'],'原3690全事件/GT总行不同')
    return totals,gt


@contextmanager
def no_raw_reads(cfg,inventory):
    paths={os.path.normcase(os.path.abspath(v['path'])) for source in cfg['sources'].values() for k,v in source.items()
        if k in ('cache','gt','gt_reference','gameinfo','seqinfo')}
    paths.update(os.path.normcase(os.path.abspath(v['registry']['path'])) for v in cfg['registries'].values())
    for model in inventory['models']:
        for k in ('checkpoint','clean_R_pool','normalizer','baseR_exposure','historical_training_exposure_table'):
            if k in model:paths.add(os.path.normcase(os.path.abspath(model[k]['path'])))
    evidence=dict(enabled=True,blocked_open_attempts=0,protected_paths=len(paths))
    def hook(event,args):
        if evidence['enabled'] and event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
            path=os.path.normcase(os.path.abspath(os.fsdecode(args[0])))
            if path in paths or Path(path).suffix in ('.pt','.jsonl') or Path(path).name in ('gt.txt','posthoc_GT_labels.json','gap_registry.json'):
                evidence['blocked_open_attempts']+=1;raise PermissionError('终验不得打开原cache/GT/权重/训练池：'+path)
    sys.addaudithook(hook)
    try:yield evidence
    finally:evidence['enabled']=False


def terminal_gate(cfg,state,manifest,analysis,protocol):
    jobs=cfg['jobs'];expected=expected_cells(cfg['panels'])
    require(len(jobs)==len({j['job_id'] for j in jobs})==180 and {key(j) for j in jobs}==expected,'正式180矩阵缺失/重复')
    require(state['status']==DONE and state['protocol']==protocol and state['active']==[] and state['optimizer_updates']==0 and state['test_read'] is False,
        '实际180控制终态/无活动任务未齐')
    for name,kind in (('completed_tracking','track'),('completed_metrics','metric')):
        rows=state[name]
        require(len(rows)==len({v['job_id'] for v in rows})==180 and {v['job_id'] for v in rows}=={j['job_id'] for j in jobs}
            and all(v['status']=='complete' and v['kind']==kind for v in rows),'180实际track/metric清单缺项/重复')
    require(manifest['schema']=='trainR_intercept_tracking_manifest_v1' and manifest['status']=='complete180_trainR_intercept_tracking_and_evaluation'
        and manifest['config_sha256']==protocol['sha256'] and [v['job'] for v in manifest['reports']]==jobs,'实际180manifest/顺序不同')
    require(analysis['schema']=='trainR_intercept_complete_paired_intervals_v1' and analysis['status']==ANALYSIS_DONE
        and analysis['protocol']==protocol and analysis['new_tracking_evaluations']==analysis['historical_reference_evaluations']==180
        and analysis['paired_cells']==analysis['paired_gap_cells']==270 and analysis['paired_matches']==36
        and analysis['metric_interval_descriptions']==45 and analysis['gap_interval_descriptions']==9,'完整分析未闭合')
    return {j['job_id']:j for j in jobs}


def check_workers(state,manifest,control,cfg):
    ready=state['workers'];exits=state['worker_exits']
    require(len(ready)==len(exits)==3 and len({v['worker_pid'] for v in ready})==3
        and Counter(v['kind'] for v in ready)==Counter(track=2,metric=1) and manifest['worker_exits']==exits,'必须两track一metric独立worker')
    bypid={v['worker_pid']:v for v in ready};counts=Counter(v['worker_pid'] for name in ('completed_tracking','completed_metrics') for v in state[name])
    require(set(counts)==set(bypid),'完成任务应来自三个真实worker')
    for value in exits:
        pid=value['worker_pid'];closure=value['closure']
        require(pid in bypid and value['kind']==bypid[pid]['kind'] and value['status']=='closed' and value['joined'] is True
            and value['process_exited'] is True and value['exit_code']==0 and value['jobs']==closure['jobs']==counts[pid]
            and closure['status']=='closed' and closure['worker_pid']==pid and closure['source_closure_verified'] is True,'worker实际关闭/join/完整任务计数不同')
        if value['kind']=='track':
            guard=closure['GT_guard'];require(guard['python_open_audit_installed'] is True and guard['blocked_open_attempts']==0
                and guard['GT_annotations_opened'] is False and closure['evaluation_GT_coordinate_files_opened'] is False,'track关闭GT隔离证据缺失')
        else:require(closure['GT_isolated_to_metric_worker'] is True and set(closure['GT_sequences_loaded'])==set(cfg['sources']),'GT仅独立metric且十二源齐全')
    require(sum(v['jobs'] for v in exits if v['kind']=='track')==sum(v['jobs'] for v in exits if v['kind']=='metric')==180,'完整180track/metric任务数不同')
    logs=[ref(control/'logs'/name) for name in ('track_0.log','track_1.log','metric_0.log')]
    require(state['actual_exit_gate']['actual_CIM_checked'] is True and state['actual_exit_gate']['related_producers_absent'] is True,'控制器最后实际退出门禁缺失')
    return dict(worker_exits=exits,logs=logs,actual_workers_joined_exit0=3,track_workers=2,metric_workers=1)


def mot_counts(reference,frames):
    path=checked(reference);require(path.suffix=='.txt' and path.parent.name=='data' and path.parent.parent.name=='tracking','只读已签追踪MOT，不开GT文本')
    counts=[0]*frames;seen=set()
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line:continue
        fields=[float(v) for v in line.split(',')]
        require(len(fields)==10 and all(math.isfinite(v) for v in fields) and fields[0].is_integer() and 1<=fields[0]<=frames
            and fields[1].is_integer() and fields[1]>0 and min(fields[4:6])>0,'实际MOT行非法，不静默丢行')
        cell=(int(fields[0]),int(fields[1]));require(cell not in seen,'实际MOT同帧身份重复');seen.add(cell);counts[cell[0]-1]+=1
    return counts


def gap_values(value,denominator):
    total,success,rate=(value[k] for k in ('total_events','same_prediction_ID_recovered','recovery_rate'))
    require(type(total) is int and type(success) is int and total==denominator and 0<=success<=total,'全注册gap分母/成功数改变')
    require((rate is None and success==0) if not total else close(rate,success/total),'gap率/零事件null不同')
    return dict(total_events=total,success=success,rate=rate)


def report_metrics(body,sequence,frames,predicted,gt_rows):
    require(body['frames']==frames and body['GT_rows']==gt_rows and body['status']=='complete' and body['DO_PREPROC'] is False
        and body['predictions_GT_filtered'] is False and body['GT_used_only_for_metric'] is True and body['test_read'] is False,'实际评价全预测/GT总行数边界不同')
    require(body.get('GT_ID0_original',body.get('GT_identity0_preserved')) is True,'原ID0合法语义未保留')
    require(set(body['raw_results'])=={sequence,'COMBINED_SEQ'} and set(body['summary'])=={sequence,'COMBINED_SEQ'},'TrackEval范围不同')
    for name,classes in body['raw_results'].items():
        values=classes['pedestrian'];count=values['Count']
        require(count['Dets']==predicted and count['GT_Dets']==gt_rows and (name!='COMBINED_SEQ' or count.get('Frames',frames)==frames),'TrackEval丢预测/GT')
        if name==sequence:require(count['Frames']==frames,'单序列实际帧数改变')
        fractions={k:mean(values['HOTA'][k]) if isinstance(values['HOTA'][k],list) else float(values['HOTA'][k]) for k in ('AssA','HOTA','DetA')}
        fractions.update(IDF1=float(values['Identity']['IDF1']),MOTA=float(values['CLEAR']['MOTA']))
        require(all(close(100*fractions[k],body['summary'][name]['metrics_percent'][k]) for k in METRICS),'指标摘要不是原TrackEval数值')
    result={k:body['summary'][sequence]['metrics_percent'][k] for k in METRICS}
    require(all(type(v) in (float,int) and math.isfinite(v) for v in result.values()),'原五指标不完整/非有限')
    if 'metrics' in body:require(deep_close(body['metrics'],result),'新指标与实际原摘要不同')
    return result


def metadata(cfg,protocol):
    require(cfg['schema']=='trainR_intercept_tracking_protocol_v1' and cfg['phase']=='formal' and cfg['approved_by']=='root'
        and cfg['tracking_authorized'] is True and cfg['numeric_authorized'] is False and cfg['alias_enabled'] is False
        and cfg['test_sealed'] is True and cfg['formal_equivalence_or_noninferiority'] is False and cfg['new_optimizer_updates']==0,
        '独立正式协议/无alias/测试封存/零SGD边界不同')
    inventory=read(cfg['inventory']);original=read(cfg['source_velocity_protocol'])
    require(inventory['schema']=='trainR_intercept_source_inventory_v1'
        and inventory['status']=='complete18_model_refs3_cleanR_pools180_baseline_refs_no_weight_or_pool_loaded'
        and cfg['source_velocity_protocol']==inventory['source_refs']['velocity']
        and cfg['sources']==inventory['sources']==original['sources'] and cfg['panels']==inventory['panels']==original['panels']
        and cfg['registries']==original['registries'] and set(cfg['sources'])==set(panels_map(cfg['panels']))
        and sum(v['frames'] for v in cfg['sources'].values())==8165,'原十二/8165输入及全事件来源不同')
    models={v['model_id']:v for v in inventory['models']}
    require(len(inventory['models'])==len(models)==18 and {(m['regime'],m['fold'],m['seed']) for m in models.values()}
        =={(r,f,s) for r in REGIMES for f in FOLDS for s in SEEDS} and all(m['use_pose'] is False for m in models.values()),'原18强motion身份不同')
    require({key(v) for v in inventory['baseline_units']}==expected_cells(cfg['panels']) and len(inventory['baseline_units'])==180,'原180历史参照必须完整')
    for job in cfg['jobs']:
        require(set(job)=={'job_id','model_id','regime','sequence','fold','seed'} and job['model_id'] in models
            and all(job[k]==models[job['model_id']][k] for k in ('regime','fold','seed')),'新job不是原18模型')
    require(cfg['worker_profile']==dict(track_workers=2,metric_workers=1,numeric_threads=1,cache_limit_bytes=134217728,
        cache_max_sequences=2,model_cache_limit_bytes=268435456,model_cache_max_entries=3,
        reserve_RAM_bytes=8589934592,reserve_commit_bytes=6442450944,startup_estimate_bytes=268435456),'固定2+1线程/缓存/内存合同不同')
    require(cfg['tracker_parameters']==dict(track_high_thresh=.25,track_low_thresh=.1,new_track_thresh=.25,
        track_buffer=30,match_thresh=.8,fuse_score=True),'原候选/接受政策/生命周期参数改变')
    require(cfg['fit_complete']['sha256']==FIT_COMPLETE_SHA,'实际已验十八拟合完成根不同')
    done=read(cfg['fit_complete'])
    require(done['schema']=='trainR_intercept_fit_complete_v1'
        and done['status']=='complete18_trainR_only_scalar_calibrations_full_records_and_exit_verified'
        and done['fit_processes_absent'] is True and done['calibrations']==cfg['calibrations']
        and done['model_order']==[m['model_id'] for m in inventory['models']]
        and set(cfg['calibrations'])==set(models) and done['totals']['models']==18
        and done['totals']['clean_R_model_window_evaluations']==18000 and done['totals']['optimizer_updates']==0,
        '已验额外R拟合来源不同；不重复拟合预算审计')
    bundle=physical(cfg['bundle']);require(bundle.parent==R/'code','只准独立最小冻结bundle')
    for item in read(cfg['bundle_manifest'])['files']:checked(dict(path=str(bundle/item['path']),sha256=item['sha256']))
    require(cfg['interval_source']['sha256']==INTERVAL_SHA,'原统计纯函数字节不同')
    return inventory,models,done


def fit_metadata(cfg,inventory):
    """只比对已签拟合汇总与18行CSV；不重算logits、BCE、求根或曝光预算。"""
    result=[]
    for model in inventory['models']:
        reference=cfg['calibrations'][model['model_id']];body=read(reference)
        require(body['schema']=='trainR_intercept_fit_v1' and body['status']=='complete_finite_trainR_intercept_fit_not_tracking_effect'
            and body['model_spec']==model and all(body[k]==model[k] for k in ('model_id','regime','fold','seed'))
            and body['optimizer_updates']==0 and body['validation_or_test_inputs_used'] is False
            and body['fitting_objective_improvement_is_tracking_effectiveness_evidence'] is False,'实际beta拟合来源/效力口径不同')
        totals=body['totals']
        row=dict(model_id=model['model_id'],regime=model['regime'],fold=model['fold'],seed=model['seed'],fit=reference,
            beta64=body['beta64'],apply_beta32=body['apply_beta32'],windows=totals['windows'],
            all_pair_count=totals['all_pair_count'],known_pair_count=totals['known_pair_count'],unknown_pair_count=totals['unknown_pair_count'],
            optimizer_updates=0,before_NLL=body['before']['NLL'],after_fit64_NLL=body['after_fit64']['NLL'],after_apply32_NLL=body['after_apply32']['NLL'],
            NLL_fit_is_independent_tracking_effectiveness_evidence=False)
        require(row['windows']==1000 and all(type(row[k]) in (float,int) and math.isfinite(row[k])
            for k in ('beta64','apply_beta32','before_NLL','after_fit64_NLL','after_apply32_NLL')),'十八拟合摘要缺失/非有限')
        result.append(row)
    return result


def track_boundary(tr,job,model,cfg,protocol,fit):
    require(tr['schema']=='trainR_intercept_tracking_receipt_v1' and tr['status']=='complete' and tr['job']==job
        and tr['protocol_sha256']==protocol['sha256'] and tr['model_id']==job['model_id'] and tr['binding']==model['binding']
        and tr['fit']==cfg['calibrations'][job['model_id']] and tr['beta32']==fit['apply_beta32']
        and tr['calibrated_beta32']==tr['beta32'] and tr['source_cache']==cfg['sources'][job['sequence']]['cache']
        and tr['diagnostic_beta0'] is False and tr['prefix_frames'] is None and tr['alias_used'] is False
        and tr['GT_used_for_tracking'] is False and tr['evaluation_GT_coordinate_files_opened'] is False
        and tr['calibration_trainR_metadata_parsed'] is True and tr['test_read'] is False and tr['GPU_used'] is False and tr['new_optimizer_updates']==0,
        '新追踪必须原模型/固定beta32/全源且无GT坐标或alias')
    require(all(tr[k] is True for k in ('all_job_state_reset','source_inputs_unchanged','original_model_state_unchanged','original_normalizer_unchanged',
        'Torch_CPU_RNG_unchanged','native_ordered_batch_forward_preserved','input_Pose_columns_zeroed_after_original_normalization'))
        and tr['global_ID_before']==0 and tr['actual_dtype']=='float32' and tr['original_input_dim']==194
        and tr['original_probability_cutoff']==.5,'原FP32输入/批形状/门/normalizer/状态被改变')
    scope=tr['scope_adapter'];require(scope['numerical_AST_unchanged'] is True and scope['modified_AST_nodes']=='one_frame_scope_guard_only'
        and scope['original_tracker_sha256']=='7f7196d9ac812b17ea94a909aaa057910ebecdfd10ee769a9ebe8b7f92759688','原追踪数值AST不同')
    guard=tr['GT_guard'];require(guard['python_open_audit_installed'] is True and guard['blocked_open_attempts']==0 and guard['GT_annotations_opened'] is False,'实际track GT坐标隔离未闭合')
    loaded=tr['model_loading_receipt']
    require(loaded['schema']=='trainR_intercept_loaded_original_motion_model_v1'
        and all(loaded[k]==model[k] for k in ('model_id','regime','fold','seed','checkpoint','loader','binding'))
        and loaded['device']=='cpu' and loaded['actual_dtype']=='float32' and loaded['model_forward_calls']==0
        and loaded['original_complete_loader_used'] is True and loaded['input_Pose_used'] is False
        and loaded['model_parameters_frozen'] is True and loaded['new_optimizer_updates']==0
        and loaded['validation_or_test_read'] is False,'实际每追踪原完整模型加载证明不同')


def records(cfg,inventory,models,manifest,state,control,protocol,totals,gt_rows,fits):
    result=[];fit_lookup={v['model_id']:v for v in fits}
    tracking={v['job_id']:v for v in state['completed_tracking']};metrics={v['job_id']:v for v in state['completed_metrics']}
    for entry in manifest['reports']:
        job=entry['job'];jid=job['job_id'];seq=job['sequence'];folder=control/'runs'/jid
        require(checked(entry['report'])==folder/'metric/report.json' and metrics[jid]['result']['report']==entry['report']
            and metrics[jid]['result']['job']==tracking[jid]['result']['job']==job,'新track/metric/manifest实际job不同')
        tr_ref=tracking[jid]['result']['receipt'];require(checked(tr_ref)==folder/'tracking/receipt.json'
            and physical(tracking[jid]['result']['tracking'])==folder/'tracking','实际新追踪收据路径不同')
        tr=read(tr_ref);body=read(entry['report']);track_boundary(tr,job,models[job['model_id']],cfg,protocol,fit_lookup[job['model_id']])
        require(body['schema']=='trainR_intercept_tracking_metric_v1' and body['job']==job and body['protocol_sha256']==protocol['sha256']
            and body['tracking_receipt']==tr_ref and body['fit']==tr['fit'] and body['beta32']==tr['beta32']
            and body['source_cache']==tr['source_cache'],'新评价不是该全轨迹/固定beta')
        require(tr['mot']==dict(path=str(folder/'tracking/data'/(seq+'.txt')),sha256=tr['mot_sha256']),'新MOT实物引用不同')
        counts=mot_counts(tr['mot'],cfg['sources'][seq]['frames'])
        require(counts==tr['frame_counts'] and sum(counts)==tr['tracked_rows']==body['tracked_rows']
            and tr['frames']==body['frames']==len(counts),'新MOT全行/逐帧/评价计数不同')
        metric=report_metrics(body,seq,len(counts),sum(counts),gt_rows[seq])
        registry=cfg['registries']['seven' if seq in cfg['panels']['seven_observed'] else 'old_five']['registry']
        require(body['registry']==registry,'新gap不是原结果前注册来源')
        for path,digest in body['numerical_source_sha256'].items():checked(dict(path=path,sha256=digest))
        gap=gap_values(body['gap']['overall'],totals[seq])
        result.append(dict(**{k:job[k] for k in ('model_id','regime','sequence','fold','seed')},condition='calibrated_beta32',
            metrics=metric,gap=gap,report=entry['report'],tracking_receipt=tr_ref,frames=len(counts),
            source_origin='new_actual_tracking_even_when_beta32_exact_zero',alias_used=False))
    for entry in inventory['baseline_units']:
        seq=entry['sequence'];model=models[entry['model_id']];body=read(entry['metric_report']);tr=read(entry['tracking_receipt']);job=body['job']
        seven=seq in cfg['panels']['seven_observed'];source_protocol=SEVEN_PROTOCOL_SHA if seven else OLD_PROTOCOL_SHA
        require(body['schema']==('seven_match_ABC_trackeval_gap_v1' if seven else 'v10_independent_trackeval_gap_v1')
            and body['protocol_sha256']==tr['protocol_sha256']==source_protocol and body['tracking_receipt_sha256']==entry['tracking_receipt']['sha256']
            and tr['status']=='complete' and tr['job']==job and tr['binding']==model['binding']
            and all(entry[k]==model[k]==job[k] for k in ('fold','seed')) and entry['regime']==model['regime'] and job['sequence']==seq and job['method']=='motion'
            and tr['test_read'] is False,'历史180来源身份不同')
        if seven:
            require(job['kind']=='learned' and job['group']==('A' if entry['regime']=='R' else 'B')
                and tr['schema']=='seven_match_ABC_free_tracking_v1' and tr['GT_used_for_tracking'] is False
                and tr['evaluation_GT_annotations_loaded'] is False,'七场原A/B来源或GT隔离不同')
        else:
            require(job['kind']==('pure_R' if entry['regime']=='R' else 'new_RS') and (entry['regime']=='R' or job['pool']=='balanced')
                and tr['schema']=='v10_independent_free_tracking_v1' and tr['GT_read'] is False and tr['cache']==cfg['sources'][seq]['cache'],
                '旧五原R/平衡RS来源不同')
        require(entry['source_cache']==cfg['sources'][seq]['cache'] and entry['mot']['sha256']==tr['mot_sha256'],'原MOT/cache引用改变')
        counts=mot_counts(entry['mot'],cfg['sources'][seq]['frames'])
        require(counts==tr['frame_counts']==entry['frame_counts'] and sum(counts)==tr['tracked_rows']==entry['tracked_rows']
            and tr['frames']==len(counts),'历史MOT全行/逐帧计数不同')
        metric=report_metrics(body,seq,len(counts),sum(counts),gt_rows[seq])
        registry=cfg['registries']['seven' if seven else 'old_five']['registry']
        require(body['registry']==registry if seven else body['registry_sha256']==registry['sha256'],'历史原gap注册来源改变')
        gap=gap_values(body['recovery']['overall'],totals[seq])
        result.append(dict(**{k:entry[k] for k in ('model_id','regime','sequence','fold','seed')},condition='historical_beta_zero_reference',
            metrics=metric,gap=gap,report=entry['metric_report'],tracking_receipt=entry['tracking_receipt'],frames=len(counts),
            source_origin='historical_readonly_no_new_tracking',alias_used=False))
    require(len(result)==360 and len({(r['condition'],key(r)) for r in result})==360,'全部360实际报告不齐或重复')
    return result


def reconstruct(values,panels):
    """终验独立手写四项配对及比赛均值，不导入分析器配对实现。"""
    index={(v['condition'],key(v)):v for v in values};expected=expected_cells(panels)
    conditions=('calibrated_beta32','historical_beta_zero_reference')
    require(len(values)==len(index)==360 and set(index)=={(c,k) for c in conditions for k in expected},'实际360矩阵缺失/重复')
    bymatch=panels_map(panels);cells=[]
    cellids=sorted((seq,fold,seed) for r,seq,fold,seed in expected if r=='R')
    for comparison in COMPARISONS:
        for seq,fold,seed in cellids:
            q={regime+'_'+condition:index[('calibrated_beta32' if condition=='beta' else 'historical_beta_zero_reference',(regime,seq,fold,seed))]
                for regime in REGIMES for condition in ('beta','zero')}
            require(all(q[r+'_beta']['model_id']==q[r+'_zero']['model_id'] for r in REGIMES),'实际原模型配对错误')
            require(len({v['gap']['total_events'] for v in q.values()})==1,'四项同场gap分母不一致')
            total=q['R_beta']['gap']['total_events'];delta={}
            for metric in METRICS:
                r=q['R_beta']['metrics'][metric]-q['R_zero']['metrics'][metric]
                rs=q['RS_beta']['metrics'][metric]-q['RS_zero']['metrics'][metric]
                delta[metric]=r if comparison==COMPARISONS[0] else rs if comparison==COMPARISONS[1] else rs-r
            if comparison==COMPARISONS[2]:terms=q
            else:
                regime='R' if comparison==COMPARISONS[0] else 'RS';terms={k:q[k] for k in (regime+'_beta',regime+'_zero')}
            gap=None
            if total:
                r=100*(q['R_beta']['gap']['rate']-q['R_zero']['gap']['rate'])
                rs=100*(q['RS_beta']['gap']['rate']-q['RS_zero']['gap']['rate'])
                gap=r if comparison==COMPARISONS[0] else rs if comparison==COMPARISONS[1] else rs-r
            cells.append(dict(comparison=comparison,panel=bymatch[seq],sequence=seq,fold=fold,seed=seed,delta_pp=delta,
                gap=dict(total_registered_events=total,delta_recovery_rate_pp=gap,terms={k:v['gap'] for k,v in terms.items()}),
                source_terms={k:dict(model_id=v['model_id'],report=v['report']) for k,v in terms.items()}))
    matches=[]
    for comparison in COMPARISONS:
        for panel in PANELS:
            for seq in panels[panel]:
                rows=[r for r in cells if r['comparison']==comparison and r['sequence']==seq]
                expected_units={(OLD[seq],s) for s in SEEDS} if seq in OLD else {(f,s) for f in FOLDS for s in SEEDS}
                require(len(rows)==len(expected_units) and {(r['fold'],r['seed']) for r in rows}==expected_units,'配对比赛内训练单元缺失')
                require(len({r['gap']['total_registered_events'] for r in rows})==1,'同场分母不能随模型变化')
                total=rows[0]['gap']['total_registered_events']
                matches.append(dict(comparison=comparison,panel=panel,sequence=seq,matched_training_cells=len(rows),
                    delta_pp={k:mean(v['delta_pp'][k] for v in rows) for k in METRICS},total_registered_events=total,
                    delta_recovery_rate_pp=mean(v['gap']['delta_recovery_rate_pp'] for v in rows) if total else None))
    require(len(cells)==270 and len(matches)==36,'完整270配对/36比赛缺失')
    return cells,matches


def read_csv(reference,fields):
    path=checked(reference)
    with path.open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream);require(reader.fieldnames==fields,'CSV列名/顺序不同：'+str(path));rows=list(reader)
    require(all(None not in row and all(v is not None for v in row.values()) for row in rows),'CSV截断/额外列')
    return rows


def compare_csv(rows,expected,identity):
    """按完整单元身份核每值，不能只核行数或省略负差/null。"""
    def ident(row):return tuple(str(row[k]) for k in identity)
    index={ident(row):row for row in rows};expected_index={ident(row):row for row in expected}
    require(len(rows)==len(index)==len(expected)==len(expected_index) and set(index)==set(expected_index),'CSV缺失/重复/额外身份')
    for cell,expect in expected_index.items():
        actual=index[cell];require(set(actual)==set(expect),'CSV字段集合不同')
        for name,value in expect.items():
            if type(value) in (int,float):
                try:valid=close(float(actual[name]),value)
                except (ValueError,TypeError):valid=False
                require(valid,'CSV原数值/负结果不同：'+name)
            else:require(actual[name]==('' if value is None else str(value)),'CSV来源/分组/null不同：'+name)


def check_csvs(report,values,cells,matches,fits):
    raw_fields=['condition','model_id','regime','sequence','fold','seed',*METRICS,'gap_events','gap_success','gap_rate','frames',
        'source_origin','alias_used','report_path','report_sha256','tracking_receipt_path','tracking_receipt_sha256']
    raw=[dict(**{k:v[k] for k in ('condition','model_id','regime','sequence','fold','seed','frames','source_origin','alias_used')},
        **v['metrics'],gap_events=v['gap']['total_events'],gap_success=v['gap']['success'],gap_rate=v['gap']['rate'],
        report_path=v['report']['path'],report_sha256=v['report']['sha256'],tracking_receipt_path=v['tracking_receipt']['path'],
        tracking_receipt_sha256=v['tracking_receipt']['sha256']) for v in values]
    compare_csv(read_csv(report['all_results_csv'],raw_fields),raw,['condition','model_id','sequence'])
    pair_fields=['comparison','panel','sequence','fold','seed']
    pair=[dict(**{k:v[k] for k in pair_fields},**v['delta_pp'],source_terms=canonical(v['source_terms'])) for v in cells]
    compare_csv(read_csv(report['all_paired_cells_csv'],pair_fields+[*METRICS,'source_terms']),pair,pair_fields)
    gap_fields=pair_fields+['total_registered_events','delta_recovery_rate_pp','source_gap_terms','source_terms']
    gap=[dict(**{k:v[k] for k in pair_fields},total_registered_events=v['gap']['total_registered_events'],
        delta_recovery_rate_pp=v['gap']['delta_recovery_rate_pp'],source_gap_terms=canonical(v['gap']['terms']),source_terms=canonical(v['source_terms'])) for v in cells]
    compare_csv(read_csv(report['all_paired_gaps_csv'],gap_fields),gap,pair_fields)
    match_fields=['comparison','panel','sequence','matched_training_cells',*METRICS,'total_registered_events','delta_recovery_rate_pp']
    match=[dict(**{k:v[k] for k in ('comparison','panel','sequence','matched_training_cells','total_registered_events','delta_recovery_rate_pp')},**v['delta_pp']) for v in matches]
    compare_csv(read_csv(report['all_paired_matches_csv'],match_fields),match,['comparison','panel','sequence'])
    fit_fields=['model_id','regime','fold','seed','beta64','apply_beta32','windows','all_pair_count','known_pair_count','unknown_pair_count','optimizer_updates',
        'before_NLL','after_fit64_NLL','after_apply32_NLL','NLL_fit_is_independent_tracking_effectiveness_evidence','fit_path','fit_sha256']
    expected_fit=[dict(**{k:v[k] for k in fit_fields if k not in ('fit_path','fit_sha256')},fit_path=v['fit']['path'],fit_sha256=v['fit']['sha256']) for v in fits]
    compare_csv(read_csv(report['fit_records_csv'],fit_fields),expected_fit,['model_id'])
    return dict(all_results=360,paired_metric_cells=270,paired_gap_cells=270,paired_matches=36,fit_summary_rows=18)


def interval_function(reference):
    require(reference['sha256']==INTERVAL_SHA,'描述区间必须原已冻结纯函数')
    spec=importlib.util.spec_from_file_location('_intercept_verify_original_intervals',checked(reference));module=importlib.util.module_from_spec(spec)
    old=sys.dont_write_bytecode
    try:sys.dont_write_bytecode=True;spec.loader.exec_module(module)
    finally:sys.dont_write_bytecode=old
    return module.effect_intervals


def check_intervals(report,matches,panels,fn):
    require(set(report['comparisons'])==set(report['gap_comparisons'])==set(COMPARISONS),'三比较族不可缺失/增加')
    for comparison in COMPARISONS:
        require(set(report['comparisons'][comparison])==set(report['gap_comparisons'][comparison])==set(PANELS),'3/2/7面板不得混并')
        for panel in PANELS:
            rows=[r for r in matches if r['comparison']==comparison and r['panel']==panel]
            require([r['sequence'] for r in rows]==panels[panel],'独立重建比赛顺序不同')
            require(set(report['comparisons'][comparison][panel])==set(METRICS),'原五指标不可筛选')
            for metric in METRICS:
                deltas={r['sequence']:r['delta_pp'][metric] for r in rows}
                expected=fn(deltas,confidence=.95,resamples=10000,bootstrap_seed=20261027)
                require(deep_close(report['comparisons'][comparison][panel][metric],expected),'均差/t95/固定bootstrap/LOO不符：'+comparison+'/'+panel+'/'+metric)
            available={r['sequence']:r['delta_recovery_rate_pp'] for r in rows if r['delta_recovery_rate_pp'] is not None}
            absent=[r['sequence'] for r in rows if r['delta_recovery_rate_pp'] is None]
            if len(available)>=2:expected=fn(available,confidence=.95,resamples=10000,bootstrap_seed=20261027)
            else:expected=dict(n_independent_matches=len(available),match_deltas_pp=available,mean_delta_pp=mean(available.values()) if available else None,
                Student_t_95CI=None,percentile_match_bootstrap_95CI=None,leave_one_match_out_mean=None,
                formal_equivalence_or_noninferiority_test=False,margin=None,status='fewer_than_two_matches_with_registered_events_no_interval')
            expected.update(zero_event_matches_retained_null=absent,outcome='all_registered_trusted_detection_gap_proxy_not_physical_occlusion')
            require(deep_close(report['gap_comparisons'][comparison][panel],expected),'gap全分母/null/t95/bootstrap/LOO不同')
    return dict(metric_descriptions=45,gap_descriptions=9,independent_pairing_and_match_mean=True,
        effect_interval_source_reused=True,resamples=10000,bootstrap_seed=20261027,numerical_serialization_tolerance_pp=TOLERANCE_PP,
        performance_margin=None,formal_equivalence_or_noninferiority=False)


def numeric_admission(cfg):
    """独立复核已保存小前缀，而不重复任何模型前向或追踪。"""
    proof=read(cfg['numeric_admission']);admission=read(proof['config'])
    require(proof['schema']=='trainR_intercept_tracking_numeric_admission_v1'
        and proof['status']=='complete_trainR_intercept_cold_ABA_spawn_beta0_original_exact_numeric_admission'
        and proof['passed'] is True and proof['fit_complete']==cfg['fit_complete']
        and proof['all_workers_joined_exited'] is True and proof['unique_source_frames']==96
        and proof['diagnostic_frame_consumptions']==528 and proof['numeric_threads']==1
        and proof['new_optimizer_updates']==proof['new_TrackEval_runs']==0 and proof['test_read'] is False
        and proof['alias_used'] is False and proof['nearzero_alias_threshold'] is None
        and proof['evaluation_GT_coordinate_files_opened'] is False
        and proof['new_detector_or_Pose_inference'] is False,'真实小前缀数值准入未闭合')
    require(admission['phase']=='numeric_admission' and admission['numeric_authorized'] is True
        and admission['tracking_authorized'] is False,'不能用正式结果倒签准入')
    for name in ('bundle','bundle_manifest','inventory','fit_complete','calibrations','sources','panels','registries','jobs',
        'source_velocity_protocol','runtime_source','inputs_source','track_guard_source','tracker_parameters','worker_profile','gate_job_ids'):
        require(admission[name]==cfg[name],'数值准入后来源/参数改变：'+name)
    for name,regime,sequence in (('A','R','SNMOT-060'),('B','RS','v_2QhNRucNC7E_c017')):
        case=proof['cases'][name]
        require(case in cfg['jobs'] and case['regime']==regime and case['sequence']==sequence
            and case['fold']=='game4' and case['seed']==20261024,'准入两模型/两源不同')
    for key,value in (('original_beta0_prefix_runs',2),('wrapper_beta0_prefix_runs',2),('calibrated_cold_prefix_runs',2),
        ('persistent_prefix_runs',3),('independent_spawn_prefix_runs',2)):
        require(proof[key]==value,'诊断帧调用预算不同：'+key)
    payloads={name:read(reference) for name,reference in proof['cold_payloads'].items()}
    require(set(payloads)=={kind+'_'+name for kind in ('original_beta0','wrapper_beta0','calibrated_cold') for name in ('A','B')},
        '完整原模型/零包装/实际截距小前缀缺失')
    def equal(actual,reference,comparison):
        for key in ('mot_text','raw_frames','frame_counts','audit','frames','tracked_rows'):
            require(canonical(actual[key])==canonical(reference[key]),'实际原ID/逐帧/count/audit不相等：'+key)
        require(comparison['frames']==48 and comparison['tracked_rows']==actual['tracked_rows']
            and comparison['original_ID_MOT_exact'] is True and comparison['raw_native_frames_exact'] is True
            and comparison['frame_counts_exact'] is True and comparison['audit_exact'] is True
            and comparison['MOT_sha256']==hashlib.sha256(actual['mot_text'].encode()).hexdigest()
            and comparison['raw_frames_sha256']==hashlib.sha256(canonical(actual['raw_frames']).encode()).hexdigest(),
            '数值比较摘要不对应实际完整小前缀')
        for value in (actual,reference):
            require(value['frames']==48 and len(value['frame_counts'])==len(value['raw_frames'])==48
                and value['tracked_rows']==sum(value['frame_counts']) and value['all_job_state_reset'] is True
                and value['global_ID_before']==0 and value['source_inputs_unchanged'] is True
                and value['original_model_state_unchanged'] is True and value['original_normalizer_unchanged'] is True
                and value['Torch_CPU_RNG_unchanged'] is True and value['GT_used_for_tracking'] is False
                and value['evaluation_GT_coordinate_files_opened'] is False and value['test_read'] is False
                and value['new_optimizer_updates']==0 and value['alias_used'] is False,'实际小前缀状态/无GT边界不同')
            guard=value['GT_guard']
            require(guard['python_open_audit_installed'] is True and guard['blocked_open_attempts']==0
                and guard['GT_annotations_opened'] is False,'实际小前缀GT打开保护未闭合')
    for name in ('A','B'):
        equal(payloads['wrapper_beta0_'+name],payloads['original_beta0_'+name],proof['beta0_original_comparisons'][name])
    require([item['key'] for item in proof['persistent_ABA']]==['A','B','A'],'完整常驻A→B→A缺失')
    for item in proof['persistent_ABA']:
        equal(read(item['payload']),payloads['calibrated_cold_'+item['key']],item['comparison'])
    require(len(proof['independent_spawn_A'])==2,'实际两个spawn缺失')
    worker_pids=set()
    for item in proof['independent_spawn_A']:
        equal(read(item['payload']),payloads['calibrated_cold_A'],item['comparison'])
        closure=item['closure'];inner=closure['closure'];worker_pids.add(closure['worker_pid'])
        require(closure['status']=='closed' and closure['joined'] is True and closure['exitcode']==0
            and closure['actual_PID_absent_after_join'] is True and inner['status']=='closed'
            and closure['worker_pid']==inner['worker_pid'] and inner['source_closure_verified'] is True,
            '实际独立spawn关闭/join证据缺失')
    parent=proof['parent_closure']
    require(len(worker_pids)==2 and parent['status']=='closed' and parent['jobs']==9
        and parent['source_closure_verified'] is True,'父进程数值worker未闭合')
    return dict(source=cfg['numeric_admission'],config=proof['config'],unique_source_frames=96,
        diagnostic_frame_consumptions=528,full_saved_payload_comparisons=7,actual_spawn_joined_exit0=2,
        model_forward_or_tracking_reexecuted=False,all_source_and_parameter_bindings_equal=True)


def write_new(path,value):
    path=physical(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        stream.write(canonical(value)+'\n');stream.flush();os.fsync(stream.fileno())


def verify(config,control,output):
    config,control,output=map(physical,(config,control,output));protocol=ref(config);cfg=read(protocol)
    require(control==physical(cfg['control_root'])==EXP/'tracking_control_a01'
        and EXP in output.parents and not output.parent.exists(),'独立终验范围/未知partial，拒绝覆盖')
    inventory,models,done=metadata(cfg,protocol)
    state=read(ref(control/'driver_state.json'));manifest_ref=ref(control/'manifest.json');manifest=read(manifest_ref)
    analysis_ref=ref(control/'analysis_a01/report.json');analysis=read(analysis_ref)
    terminal_gate(cfg,state,manifest,analysis,protocol)
    require(state['manifest']==analysis['formal_evaluation_manifest']==manifest_ref and state['report']==analysis_ref
        and analysis['inventory']==cfg['inventory'] and analysis['fit_complete']==cfg['fit_complete']
        and analysis['interval_source']==cfg['interval_source'] and analysis['test_read'] is False
        and analysis['historical_alias_used'] is False and analysis['formal_equivalence_or_noninferiority'] is False
        and analysis['performance_margin'] is None and analysis['all_folds_seeds_negative_zero_and_null_results_retained'] is True,
        '最终报告来源/完整负结果/无等效口径不同')
    output.parent.mkdir(parents=True)
    write_new(output.parent/'intent.json',dict(schema='trainR_intercept_tracking_terminal_intent_v1',status='started_not_committed',
        protocol=protocol,implementation=ref(__file__),control=str(control),new_optimizer_updates=0,
        new_model_forward_or_tracking_or_TrackEval_runs=0,test_read=False))
    try:
        initial=processes_absent(process_snapshot(),state)
        with no_raw_reads(cfg,inventory) as raw_guard:
            workers=check_workers(state,manifest,control,cfg)
            admission=numeric_admission(cfg)
            totals,gt_rows=public_counts(cfg)
            fits=fit_metadata(cfg,inventory)
            values=records(cfg,inventory,models,manifest,state,control,protocol,totals,gt_rows,fits)
            cells,matches=reconstruct(values,cfg['panels'])
            csvs=check_csvs(analysis,values,cells,matches,fits)
            intervals=check_intervals(analysis,matches,cfg['panels'],interval_function(cfg['interval_source']))
            require(analysis['source_gap_event_denominators']==totals and analysis['gap_events_counted_once_per_source']==sum(totals.values())==3690,
                '原3690全事件分母或逐源计数不同')
            require(analysis['all_actual_reports']==[v['report'] for v in values if v['condition']=='calibrated_beta32']
                and analysis['all_reference_reports']==[v['report'] for v in values if v['condition']=='historical_beta_zero_reference']
                and analysis['all_fit_records']==[v['fit'] for v in fits],'最终报告未保留全部新旧来源/拟合记录')
            require(raw_guard['blocked_open_attempts']==0,'终验曾尝试读取禁止的原始输入')
            guard_evidence=dict(raw_guard)
        final=processes_absent(process_snapshot(),state)
        result=dict(schema='trainR_intercept_tracking_independent_verification_v1',status=STATUS,implementation=ref(__file__),
            protocol=protocol,inventory=cfg['inventory'],fit_complete=cfg['fit_complete'],
            formal_manifest=manifest_ref,state=ref(control/'driver_state.json'),analysis=analysis_ref,
            numeric_admission=admission,workers=workers,all_csvs=csvs,intervals=intervals,
            source_gap_event_denominators=totals,gap_events_once_per_source=3690,new_tracking_evaluations=180,
            historical_reference_evaluations=180,complete_metric_source_count=360,paired_cells=270,paired_gap_cells=270,
            paired_matches=36,metric_interval_descriptions=45,gap_interval_descriptions=9,
            initial_exit=initial,final_exit=final,producer_processes_absent=True,
            old_raw_input_open_guard=guard_evidence,old_weights_cache_GT_coordinate_or_media_opened=False,
            calibration_trainR_metadata_parsed=True,fit_budget_independent_audit_reexecuted=False,
            new_model_forward_or_tracking_or_TrackEval_runs=0,new_optimizer_updates=0,
            additional_supervised_fit_budget_in_source=done['totals'],formal_equivalence_or_noninferiority=False,
            numerical_serialization_tolerance_pp=TOLERANCE_PP,performance_margin=None,
            all_negative_zero_null_folds_seeds_and_sources_retained=True,test_read=False,
            verified_utc=datetime.now(timezone.utc).isoformat())
        write_new(output,result);return result
    except BaseException as error:
        write_new(output.parent/'failed.json',dict(status='failed_intercept_tracking_verification_partial_preserved_no_replay',
            error=repr(error),traceback=traceback.format_exc(),source_modified=False,
            new_model_forward_or_tracking_or_TrackEval_runs=0,new_optimizer_updates=0,test_read=False));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('config','control','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if args.execute:
        receipt=verify(args.config,args.control,args.output)
        print(canonical(dict(status=receipt['status'],complete_metric_source_count=360,paired_cells=270,
            metric_interval_descriptions=45,gap_interval_descriptions=9,new_model_forward_or_tracking_or_TrackEval_runs=0)))
    else:print(canonical(dict(status='readonly_trainR_tracking_terminal_candidate_no_verification_or_output',
        expected_new_evaluations=180,expected_old_evaluations=180,expected_metric_intervals=45,expected_gap_intervals=9,
        new_model_forward_or_tracking_or_TrackEval_runs=0,new_optimizer_updates=0,test_read=False)))
