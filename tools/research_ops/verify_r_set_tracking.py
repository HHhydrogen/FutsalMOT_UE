"""独立终验R集合监督180新追踪及两套180基线；只读MOT/报告，不重模型、GT或训练预算。"""
import argparse
import ast
from collections import Counter
from contextlib import contextmanager
import csv
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
from statistics import mean,stdev
import stat
import subprocess
import sys
import traceback

R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/r_set_supervision_a01'
FOLDS=('game4','game6','game9');SEEDS=(20261024,20261025,20261026);REGIMES=('R','RS')
OLD={'SNMOT-060':'game4','SNMOT-097':'game6','SNMOT-151':'game9'}
PANELS=('original_heldout','old_external','seven_observed');METRICS=('AssA','HOTA','IDF1','DetA','MOTA')
CONDITIONS=('newCE_R','newCE_RS','alignedBCE_R','alignedBCE_RS','originalstrongmotion_R','originalstrongmotion_RS')
COMPARISONS=('newCE_RS_minus_alignedBCE_RS','newCE_R_minus_alignedBCE_R','newCE_RS_minus_originalstrongmotion_RS','newCE_R_minus_originalstrongmotion_R','synthetic_increment_loss_interaction')
DONE='complete180_R_set_tracking_and_paired_analysis'
ANALYSIS_DONE='complete180_R_set_tracking_all540_results450_pairs75_metric15_gap_intervals'
STATUS='complete180_R_set_sources540_results450_pairs75_metric15_gap_intervals_and_exit_verified'
OBJECTIVE='R_candidate_set_CE_fixed_null_logit0_S_original_BCE_alpha_1_over_3'
LEARNING_SHA='301eb84a90c47e0fbf7d869600f134ef46ca3a5d481d9029ad6d8a8161e7f0f7'
BUNDLE='598df7569b5e4fb5dcbff1c84a8bd875c78d05ce449507723ab1292ef33d9d35'
OLD_PROTOCOL_SHA='f85e69bc2a50220528a2caf42243ee940768cc0a60a4fa845eab2d7c7da27ef1'
SEVEN_PROTOCOL_SHA='fd1b92c70ab91d021a8b055cf89eeb3775d34a506056efe85cb3da90038e9a78'
TOLERANCE_PP=1e-8  # 仅序列化核验，非性能等效界限。
_CHECKED=set()
NEW_SCHEMA='R_candidate_set_supervision_tracking_inventory_v1'

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


def same_signed_file(left,right):
    """引用路径允许系统分隔符差异；双方须真实SHA一致且是同一物理文件。"""
    first,second=checked(left),checked(right)
    # 不只比较摘要，也不只替换斜杠；显式核当前bytes，不能把同hash副本当同源。
    return first==second and left['sha256']==right['sha256'] and sha(first)==left['sha256'] and sha(second)==right['sha256']


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


def write_new(path,value):
    path=physical(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        stream.write(canonical(value)+'\n');stream.flush();os.fsync(stream.fileno())


@contextmanager
def no_raw_reads(cfg,inventory):
    """终验自身也隔离输入、GT、训练张量、权重和媒体，不能以SHA检查为由读取。"""
    protected={os.path.normcase(os.path.abspath(v['path'])) for source in cfg['sources'].values()
        for k,v in source.items() if isinstance(v,dict) and k in ('cache','gt','gt_reference','gameinfo','seqinfo','seqinfo_reference')}
    protected.update(os.path.normcase(os.path.abspath(v['registry']['path'])) for v in cfg['registries'].values())
    for model in inventory['models']:
        for k in ('checkpoint','clean_R_pool','normalizer','original_normalizer','baseR_exposure','historical_training_exposure_table'):
            if k in model:protected.add(os.path.normcase(os.path.abspath(model[k]['path'])))
    evidence=dict(enabled=True,blocked_open_attempts=0,protected_paths=len(protected))
    def hook(event,args):
        if evidence['enabled'] and event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
            value=os.path.normcase(os.path.abspath(os.fsdecode(args[0])));path=Path(value)
            if value in protected or path.suffix.lower() in ('.pt','.pth','.jsonl','.gz','.npz','.npy','.png','.jpg','.jpeg','.mp4','.exr') \
                or path.name.lower() in ('gt.txt','posthoc_gt_labels.json','gap_registry.json'):
                evidence['blocked_open_attempts']+=1;raise PermissionError('终验禁止原输入/GT/权重/媒体：'+value)
    sys.addaudithook(hook)
    try:yield evidence
    finally:evidence['enabled']=False


def metric_source(body):
    evidence=body['metric_pure_functions'];reference=evidence['source'];path=checked(reference)
    tree=ast.parse(path.read_text(encoding='utf-8'));names=('plain','prediction_rows','validate_count','trackeval_numeric')
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    require(len(nodes)==4 and evidence['numerical_functions']==list(names) and evidence['numerical_function_AST_unchanged'] is True
        and evidence['numerical_function_AST_sha256']==hashlib.sha256(ast.dump(ast.Module(body=nodes,type_ignores=[]),include_attributes=False).encode()).hexdigest(),'原四评价纯函数AST证据不同')
    require(isinstance(body['numerical_source_sha256'],dict) and body['numerical_source_sha256'],'TrackEval数值源码引用不足')
    for name,digest in body['numerical_source_sha256'].items():checked(dict(path=name,sha256=digest))


def interval(values):
    """独立比赛t95与显式MT19937抽样。无事件源保留null，不能缩小面板。"""
    observed={k:v for k,v in values.items() if v is not None};numbers=list(observed.values());n=len(numbers)
    require(all(type(v) in (int,float) and math.isfinite(v) for v in numbers),'区间非有限输入')
    result=dict(n_independent_matches=n,match_deltas_pp=values,mean_delta_pp=mean(numbers) if n else None,
        null_matches=[k for k,v in values.items() if v is None],match_sample_SD_pp=None,Student_t_95CI=None,
        percentile_match_bootstrap_95CI=None,leave_one_match_out_mean=None,bootstrap_seed=20261028,bootstrap_resamples=10000,
        bootstrap_algorithm='Python_random_MT19937_randrange_match_resampling_linear_quantile',formal_equivalence_or_noninferiority_test=False,margin=None)
    if n!=len(values) or n<2:
        result['interval_status']='null_missing_event_matches_or_fewer_than_two';return result
    critical={2:12.706204736432095,3:4.302652729749462,7:2.4469118511449692};require(n in critical,'独立源只能3/2/7')
    avg=mean(numbers);sd=stdev(numbers);half=critical[n]*sd/math.sqrt(n);rng=random.Random(20261028)
    samples=sorted(mean(numbers[rng.randrange(n)] for j in range(n)) for i in range(10000))
    def quantile(probability):
        position=9999*probability;lo=int(position);weight=position-lo
        return samples[lo]*(1-weight)+samples[min(lo+1,9999)]*weight
    result.update(match_sample_SD_pp=sd,Student_t_95CI=[avg-half,avg+half],percentile_match_bootstrap_95CI=[quantile(.025),quantile(.975)],
        leave_one_match_out_mean={k:mean(v for other,v in observed.items() if other!=k) for k in observed},
        interval_status='descriptive_uncorrected',Student_t_degrees_of_freedom=n-1,Student_t_critical_975=critical[n])
    return result


def check_intervals(report,matches,panels):
    require(set(report['comparisons'])==set(report['gap_comparisons'])==set(COMPARISONS),'四族描述不能省略')
    for family in COMPARISONS:
        require(set(report['comparisons'][family])==set(report['gap_comparisons'][family])==set(PANELS),'3/2/7独立面板不同')
        for panel in PANELS:
            rows={r['sequence']:r for r in matches if r['comparison']==family and r['panel']==panel}
            require(set(rows)==set(panels[panel]) and set(report['comparisons'][family][panel])==set(METRICS),'比赛/五指标缺失')
            for m in METRICS:
                expected=interval({s:rows[s]['delta_pp'][m] for s in panels[panel]})
                require(deep_close(report['comparisons'][family][panel][m],expected),'独立均值/t/固定bootstrap/LOO不同：'+family+'/'+panel+'/'+m)
            require(deep_close(report['gap_comparisons'][family][panel],interval({s:rows[s]['delta_recovery_rate_pp'] for s in panels[panel]})),'全gap分母/null/区间不同')
    return dict(metric_descriptions=75,gap_descriptions=15,independent_match_weighting_reconstructed=True,
        bootstrap_seed=20261028,bootstrap_resamples=10000,formal_equivalence_or_noninferiority=False,performance_margin=None)


def check_workers(state,manifest,cfg,values):
    ready=state['workers'];exits=state['worker_exits'];byid={r['worker_pid']:r['kind'] for r in ready}
    require(len(ready)==len(byid)==len(exits)==3 and Counter(byid.values())==Counter(track=2,metric=1) and exits==manifest['worker_exits'],'真实独立2track+1metric不齐')
    counts=Counter()
    for j in cfg['jobs']:
        tr=read(state['completed_track'][j['job_id']]['receipt']);me=read(state['completed_metric'][j['job_id']]['report'])
        require(byid.get(tr['worker_pid'])=='track' and byid.get(me['worker_pid'])=='metric','track/GT评价非独立真实worker')
        counts[tr['worker_pid']]+=1;counts[me['worker_pid']]+=1
    require(set(counts)==set(byid),'完成任务不能来自未注册worker')
    for out in exits:
        pid=out['worker_pid'];inside=out['closure']
        require(pid in byid and out['status']=='closed' and out['joined'] is True and out['process_exited'] is True and out['exit_code']==0
            and inside['status']=='closed' and inside['worker_pid']==pid and inside['jobs']==counts[pid] and inside['source_closure_verified'] is True,'worker未实际关闭/join/exit0或任务数不同')
        if byid[pid]=='track':
            g=inside['GT_guard'];require(g['python_open_audit_installed'] is True and g['blocked_open_attempts']==0 and g['GT_annotations_opened'] is False
                and inside['evaluation_GT_coordinate_files_opened'] is False and inside['intercept_applied'] is False
                and inside['calibration_metadata_read'] is False and inside['training_labels_used_in_tracking_features'] is False,'track关闭时GT或模型边界缺失')
        else:require(inside['GT_isolated_to_metric_worker'] is True and set(inside['GT_sequences_loaded'])==set(cfg['sources']) and inside['registry_count']==2,'GT只独立metric且12源/两原registry齐全')
    require(sum(counts[k] for k in counts if byid[k]=='track')==sum(counts[k] for k in counts if byid[k]=='metric')==180,'真实180track/metric任务计数不同')
    return dict(actual_workers_joined_exit0=3,track_workers=2,metric_workers=1,exits=exits)


def numeric_admission(cfg):
    proof=read(cfg['numeric_admission']);admission=read(proof['config']);folder=physical(admission['numeric_output'])
    require(proof['source_numeric_validation']==cfg['source_numeric_validation'],'训练数值准入来源不同');checked(proof['source_numeric_validation'])
    require(proof['status']=='complete_R_set_cold_ABA_two_spawn_numeric_admission' and proof['passed'] is True
        and proof['all_workers_joined_exited'] is True and proof['unique_source_frames']==96 and proof['diagnostic_frame_consumptions']==336
        and proof['new_optimizer_updates']==0 and proof['test_read'] is False and proof['alias_used'] is False and proof['intercept_applied'] is False
        and proof['original_tracker_and_scoped_AST_reused'] is True,'新模型真实数值准入未闭合')
    require(admission['phase']=='numeric_admission' and admission['numeric_authorized'] is True and admission['tracking_authorized'] is False,'数值准入不得倒签正式')
    for k in ('bundle','bundle_manifest','inventory','aligned_inventory','aligned_learning_protocol','aligned_tracking_manifest','aligned_tracking_protocol','aligned_analysis','source_state_aligned_runtime','learning_protocol','training_budget','training_complete','source_inventory','source_velocity_protocol',
        'source_worker_framework','original_inputs_source','sources','panels','registries','jobs','tracker_parameters','worker_profile','gate_job_ids','analysis_plan','track_guard_source','expected_GT_rows'):
        require(cfg[k]==admission[k],'数值准入后改变来源：'+k)
    require(len(proof['comparisons'])==5 and len(proof['exits'])==5,'2cold+ABA+2spawn完整退出不足')
    cold=[read(ref(folder/('cold_'+str(i)+'.json'))) for i in range(2)]
    cases=[next(j for j in cfg['jobs'] if j['job_id']==gid) for gid in cfg['gate_job_ids']]
    require(len(cases)==2 and {j['regime'] for j in cases}=={'R','RS'} and {j['sequence'] for j in cases}=={'SNMOT-060','v_2QhNRucNC7E_c017'},'两源R/RS真实准入不足')
    payloads=[read(ref(folder/('ABA_'+str(i)+'.json'))) for i in range(3)]+[read(ref(folder/('spawn_'+str(i)+'.json'))) for i in range(2)]
    for i,(actual,number) in enumerate(zip(payloads,(0,1,0,0,1))):
        reference=cold[number];compare=proof['comparisons'][i]
        for k in ('mot_text','raw_frames','frame_counts','audit','frames','tracked_rows'):
            require(canonical(actual[k])==canonical(reference[k]),'保存的cold/ABA/spawn完整原生输出不一致：'+k)
        require(all(compare[k] is True for k in ('original_ID_MOT_exact','raw_native_frames_exact','frame_counts_exact','audit_exact'))
            and compare['frames']==48 and compare['tracked_rows']==actual['tracked_rows']
            and compare['MOT_sha256']==hashlib.sha256(actual['mot_text'].encode()).hexdigest()
            and compare['raw_frames_sha256']==hashlib.sha256(canonical(actual['raw_frames']).encode()).hexdigest(),'数值比较摘要与完整保存输出不同')
    for payload in cold+payloads:
        require(payload['frames']==48 and len(payload['raw_frames'])==len(payload['frame_counts'])==48 and sum(payload['frame_counts'])==payload['tracked_rows']
            and all(payload[k] is True for k in ('original_base_forward_without_intercept_wrapper','all_job_state_reset','source_inputs_unchanged',
                'original_model_state_unchanged','original_normalizer_unchanged','Torch_CPU_RNG_unchanged'))
            and payload['global_ID_before']==0 and all(payload[k] is False for k in ('intercept_applied','calibration_metadata_read','GT_used_for_tracking',
                'evaluation_GT_coordinate_files_opened','alias_used','test_read')) and payload['new_optimizer_updates']==0,'数值保存边界缺证')
        g=payload['GT_guard'];require(g['python_open_audit_installed'] is True and g['blocked_open_attempts']==0 and g['GT_annotations_opened'] is False,'准入GT隔离不足')
    pids=set()
    for item in proof['exits']:
        inside=item['closure'];pids.add(item['worker_pid'])
        require(item['status']=='closed' and item['joined'] is True and item['process_exited'] is True and item['exit_code']==0
            and inside['status']=='closed' and inside['worker_pid']==item['worker_pid'] and inside['source_closure_verified'] is True,'数值worker未真实退出')
    require(len(pids)==5,'cold/ABA/spawn实际独立进程数不同')
    return dict(source=cfg['numeric_admission'],actual_payload_comparisons=5,actual_closed_workers=5,diagnostic_frame_consumptions=336,model_or_tracking_reexecuted=False)


def aligned_track_boundary(tr,job,model,cfg,protocol):
    require(tr['schema']=='state_aligned_tracking_receipt_v1' and tr['status']=='complete' and tr['job']==job
        and tr['protocol_sha256']==protocol['sha256'] and tr['model_id']==job['model_id'] and tr['baseline_model_id']==model['baseline_model_id']
        and tr['learning_protocol']==cfg['learning_protocol'] and tr['training_budget']==cfg['training_budget']
        and tr['source_cache']==cfg['sources'][job['sequence']]['cache'] and tr['prefix_frames'] is None,'新独立模型/全帧/来源不同')
    require(all(tr[k] is False for k in ('intercept_applied','calibration_metadata_read','training_labels_used_in_tracking_features','GT_used_for_tracking',
        'evaluation_GT_coordinate_files_opened','alias_used','test_read','GPU_used')) and tr['new_optimizer_updates']==0
        and not any(k in tr for k in ('fit','beta32','calibrated_beta32')),'不得截距/GT标签入特征/借旧身份')
    require(all(tr[k] is True for k in ('original_base_forward_without_intercept_wrapper','training_R_S_label_metadata_parsed_for_checkpoint_binding',
        'all_job_state_reset','source_inputs_unchanged','original_model_state_unchanged','original_normalizer_unchanged','Torch_CPU_RNG_unchanged',
        'native_ordered_batch_forward_preserved','input_Pose_columns_zeroed_after_original_normalization'))
        and tr['global_ID_before']==0 and tr['actual_dtype']=='float32' and tr['original_input_dim']==194 and tr['original_probability_cutoff']==.5,'原数值/缓存/状态边界改变')
    scope=tr['scope_adapter'];require(scope['numerical_AST_unchanged'] is True and scope['modified_AST_nodes']=='one_frame_scope_guard_only'
        and scope['original_tracker_sha256']=='7f7196d9ac812b17ea94a909aaa057910ebecdfd10ee769a9ebe8b7f92759688','原数值AST不同')
    guard=tr['GT_guard'];require(guard['python_open_audit_installed'] is True and guard['blocked_open_attempts']==0 and guard['GT_annotations_opened'] is False,'track GT坐标隔离不足')
    loaded=tr['model_loading_receipt'];require(loaded['schema']=='state_aligned_model_loading_receipt_v1'
        and loaded['model_id']==model['model_id'] and loaded['baseline_model_id']==model['baseline_model_id']
        and loaded['method_schema']==model['method_schema'] and loaded['learning_protocol']==cfg['learning_protocol']
        and loaded['training_budget']==cfg['training_budget'] and loaded['run_receipt']==model['training_receipt']
        and loaded['initialization_equal_original'] is True and loaded['normalizer_equal_original'] is True
        and loaded['checkpoint']=='last1000_not_EMA_no_best' and loaded['device']=='cpu' and loaded['actual_dtype']=='float32'
        and loaded['use_pose'] is False and loaded['Pose_columns_zeroed_after_normalization']==170
        and loaded['intercept_applied'] is False and loaded['new_optimizer_updates']==0 and loaded['test_read'] is False,'独立真实完整模型加载证据不同')
    require(all(tr['binding'][k]==model[k] for k in ('fold','seed','regime')) and tr['binding']['method']=='motion'
        and tr['binding']['initialization_sha256']==model['expected_initialization_sha256'],'模型binding不是原强motion初始化')


def original_records(cfg,old,originals,totals,gt_rows):
    result=[]
    for entry in old['baseline_units']:
        seq=entry['sequence'];model=originals[entry['model_id']];body=read(entry['metric_report']);tr=read(entry['tracking_receipt']);job=body['job']
        seven=seq in cfg['panels']['seven_observed'];source_protocol=SEVEN_PROTOCOL_SHA if seven else OLD_PROTOCOL_SHA
        require(body['schema']==('seven_match_ABC_trackeval_gap_v1' if seven else 'v10_independent_trackeval_gap_v1')
            and body['protocol_sha256']==tr['protocol_sha256']==source_protocol and body['tracking_receipt_sha256']==entry['tracking_receipt']['sha256']
            and tr['status']=='complete' and tr['job']==job and tr['binding']==model['binding']
            and all(entry[k]==model[k]==job[k] for k in ('fold','seed')) and entry['regime']==model['regime'] and job['sequence']==seq and job['method']=='motion'
            and tr['test_read'] is False,'历史原180模型/来源不同')
        if seven:require(job['kind']=='learned' and job['group']==('A' if entry['regime']=='R' else 'B')
            and tr['schema']=='seven_match_ABC_free_tracking_v1' and tr['GT_used_for_tracking'] is False and tr['evaluation_GT_annotations_loaded'] is False,'七场参照不是原A/B')
        else:require(job['kind']==('pure_R' if entry['regime']=='R' else 'new_RS') and (entry['regime']=='R' or job['pool']=='balanced')
            and tr['schema']=='v10_independent_free_tracking_v1' and tr['GT_read'] is False and tr['cache']==cfg['sources'][seq]['cache'],'旧五参照不是原R/RS')
        require(entry['source_cache']==cfg['sources'][seq]['cache'] and entry['mot']['sha256']==tr['mot_sha256'],'历史MOT/cache改变')
        counts=mot_counts(entry['mot'],cfg['sources'][seq]['frames'])
        require(counts==tr['frame_counts']==entry['frame_counts'] and sum(counts)==tr['tracked_rows']==entry['tracked_rows'] and tr['frames']==len(counts),'历史完整预测/count不同')
        values=report_metrics(body,seq,len(counts),sum(counts),gt_rows[seq]);registry=cfg['registries']['seven' if seven else 'old_five']['registry']
        require(body['registry']==registry if seven else body['registry_sha256']==registry['sha256'],'历史gap登记不同')
        gap_values(body['recovery']['overall'],totals[seq])
        result.append(dict(**{k:entry[k] for k in ('model_id','regime','sequence','fold','seed')},condition='originalstrongmotion_'+entry['regime'],metrics=values,
            gap=body['recovery']['overall'],report=entry['metric_report'],tracking_receipt=entry['tracking_receipt'],frames=len(counts),source_origin='historical_readonly'))
    return result


def processes_absent(rows,state):
    names=r'r_set_tracking_control|set_supervision_train|control_r_set_supervision_training|validate_r_set_supervision_numeric|state_aligned_tracking_control|pose_velocity_tracking_control|state_gap_control'
    pattern=re.compile(r'(?:^|[\\/\s"\x27])(?:'+names+r')[.]py(?=$|[\s"\x27])',re.I)
    historical={state['controller_pid']}|{r['worker_pid'] for r in state['workers']}
    blocked=[r for r in rows if pattern.search(r.get('CommandLine') or '') or (r.get('Name') or '').lower().startswith('unrealeditor')
        or (r.get('ProcessId') in historical and (r.get('Name') or '').lower().startswith('python') and 'multiprocessing.spawn' in (r.get('CommandLine') or ''))]
    require(not blocked,'真实controller/worker/launcher或UE仍在：'+canonical(blocked))
    return dict(actual_CIM_checked=True,producer_processes_absent=True,exact_Name_CommandLine_checked=True,PID_alone_not_used=True,
        historical_PIDs_present_with_different_identity=[r for r in rows if r.get('ProcessId') in historical])


def training_metadata(cfg):
    require(cfg['learning_protocol']['sha256']==LEARNING_SHA,'固定R集合监督学习协议不同')
    root=read(cfg['training_complete']);audit=read(cfg['training_budget'])
    require(root['schema']=='R_set_supervision_training_complete_root_v1'
        and root['status']=='complete18_R_set_supervision_training_actual_budget_records_exit_verified_not_tracking_complete'
        and same_signed_file(root['budget_audit'],cfg['training_budget']) and same_signed_file(root['protocol'],cfg['learning_protocol'])
        and root['actual_training_and_audit_processes_absent'] is True and root['test_read'] is False,'已完成训练根引用/实际退出不同')
    require(audit['schema']=='independent_R_set_supervision18_budget_audit_v1'
        and audit['status']=='complete18_R_set_supervision_actual_budget_full_records_and_exit_verified'
        and same_signed_file(audit['protocol'],cfg['learning_protocol']) and audit['training_processes_absent'] is True
        and audit['complete_checkpoints_read_back']==378 and audit['nine_paired_R_RS_exposures_equal'] is True and audit['test_read'] is False
        and all(audit['actual_totals'][k]==v for k,v in [('updates',18000),('R_windows',54000),('S_windows',9000)]),'只引用真实18训练/378/退出预算凭据')
    return dict(training_complete=cfg['training_complete'],training_budget=cfg['training_budget'],checkpoint_or_training_budget_audit_reexecuted=False)


def metadata(cfg):
    require(cfg['schema']=='r_set_tracking_protocol_v1' and cfg['phase']=='formal' and cfg['approved_by']=='root' and cfg['tracking_authorized'] is True
        and cfg['numeric_authorized'] is False and cfg['new_optimizer_updates']==0 and cfg['test_sealed'] is True
        and cfg['alias_enabled'] is False and cfg['formal_equivalence_or_noninferiority'] is False,'正式零更新/不借截距身份/测试封存边界不同')
    require(not any(k in cfg for k in ('calibrations','fit_complete','beta32')),'不得混入截距')
    inventory=read(cfg['inventory']);aligned=read(cfg['aligned_inventory']);old=read(cfg['source_inventory']);velocity=read(cfg['source_velocity_protocol'])
    require(inventory['schema']==NEW_SCHEMA and aligned['schema']=='state_aligned_strongmotion_tracking_inventory_v1'
        and all(x['sources']==cfg['sources'] and x['panels']==cfg['panels'] for x in (inventory,aligned,old,velocity))
        and velocity['registries']==cfg['registries'] and sum(s['frames'] for s in cfg['sources'].values())==8165
        and set(cfg['sources'])==set(panels_map(cfg['panels'])),'三模型库存/原12场8165帧/3690事件来源不同')
    modelsets=[{m['model_id']:m for m in inv['models']} for inv in (inventory,aligned,old)];models,aligned_models,originals=modelsets
    expected={(r,f,s) for r in REGIMES for f in FOLDS for s in SEEDS}
    for inv,idx in zip((inventory,aligned,old),modelsets):
        require(len(inv['models'])==len(idx)==18 and {(m['regime'],m['fold'],m['seed']) for m in idx.values()}==expected,'任一18模型矩阵缺失/重复')
    for m in models.values():
        a=aligned_models[m['baseline_model_id']];o=originals[m['original_baseline_model_id']]
        require(a['baseline_model_id']==o['model_id'] and all(m[k]==a[k]==o[k] for k in ('regime','fold','seed'))
            and len({m['model_id'],a['model_id'],o['model_id']})==3 and m['training_objective']==OBJECTIVE and m['learning_protocol']==cfg['learning_protocol']
            and m['original_normalizer']==a['original_normalizer']==o['normalizer'] and m['expected_initialization_sha256']==a['expected_initialization_sha256']==o['binding']['initialization_sha256']
            and m['use_pose'] is False and m['intercept_applied'] is False and m['output_transform']=='original_sigmoid_probability_cutoff_0.50','新→aligned→original身份/原init/norm不同')
        require(m['model_id']==hashlib.sha256(canonical([NEW_SCHEMA,LEARNING_SHA,m['fold'],m['seed'],m['regime']]).encode()).hexdigest()[:24],'新模型ID未绑定方法与学习协议')
    require(len(cfg['jobs'])==len({j['job_id'] for j in cfg['jobs']})==180 and {key(j) for j in cfg['jobs']}==expected_cells(cfg['panels']),'新180矩阵缺失/重复')
    for job in cfg['jobs']:
        m=models[job['model_id']];require(set(job)=={'model_id','baseline_model_id','original_baseline_model_id','regime','fold','seed','sequence','job_id'}
            and all(job[k]==m[k] for k in ('baseline_model_id','original_baseline_model_id','regime','fold','seed')),'双基线任务身份不同')
        require(job['job_id']==hashlib.sha256(canonical(['R_candidate_set_supervision_tracking_v1',{k:v for k,v in job.items() if k!='job_id'}]).encode()).hexdigest()[:24],'实际job ID来源不同')
    require(len(old['baseline_units'])==180 and {key(r) for r in old['baseline_units']}==expected_cells(cfg['panels']),'原180参照缺失')
    require(cfg['tracker_parameters']==dict(track_high_thresh=.25,track_low_thresh=.1,new_track_thresh=.25,track_buffer=30,match_thresh=.8,fuse_score=True),'原绝对追踪参数不同')
    profile=cfg['worker_profile'];require(profile['track_workers']==2 and profile['metric_workers']==1 and profile['numeric_threads']==1
        and profile['reserve_RAM_bytes']==8589934592 and profile['reserve_commit_bytes']==6442450944,'有界2track+1metric资源不同')
    bundle=physical(cfg['bundle']);require(bundle==R/'code'/BUNDLE,'本轮4文件冻结bundle不同')
    manifest=read(cfg['bundle_manifest']);require(len(manifest['files'])==4 and hashlib.sha256(canonical(manifest['files']).encode()).hexdigest()==BUNDLE,'四源码内容地址不同')
    for item in manifest['files']:checked(dict(path=str(bundle/item['path']),sha256=item['sha256']))
    for k in ('source_state_aligned_runtime','source_worker_framework','original_inputs_source','track_guard_source','worker_service','worker_support'):checked(cfg[k])
    plan=read(cfg['analysis_plan']);require(plan['bootstrap']['seed']==20261028 and plan['bootstrap']['repeats']==10000
        and plan['comparison_families']==5 and plan['metric_interval_count']==75 and read(cfg['learning_protocol'])['analysis_plan']==cfg['analysis_plan'],'训练前分析计划不同')
    aligned_cfg=read(cfg['aligned_tracking_protocol']);aligned_manifest=read(cfg['aligned_tracking_manifest']);aligned_analysis=read(cfg['aligned_analysis'])
    require(aligned_cfg['inventory']==cfg['aligned_inventory'] and same_signed_file(aligned_cfg['learning_protocol'],cfg['aligned_learning_protocol'])
        and aligned_manifest['schema']=='state_aligned_tracking_manifest_v1' and aligned_manifest['status']=='complete180_state_aligned_tracking_and_evaluation'
        and aligned_manifest['config_sha256']==cfg['aligned_tracking_protocol']['sha256'] and len(aligned_manifest['reports'])==len(aligned_manifest['tracking'])==180
        and aligned_analysis['status']=='complete180_state_aligned_tracking_all360_results_and_paired_intervals'
        and same_signed_file(aligned_analysis['protocol'],cfg['aligned_tracking_protocol']) and aligned_analysis['inventory']==cfg['aligned_inventory']
        and aligned_analysis['source_inventory']==cfg['source_inventory'] and aligned_analysis['formal_evaluation_manifest']==cfg['aligned_tracking_manifest']
        and aligned_analysis['all_actual_reports']==[x['report'] for x in aligned_manifest['reports']],'完整aligned180实际出处不同')
    for name in ('tracking','reports'):
        require({key(v['job']) for v in aligned_manifest[name]}==expected_cells(cfg['panels'])
            and [v['job'] for v in aligned_manifest[name]]==aligned_cfg['jobs'],'aligned180缺失/重复或不是该来源固定矩阵')
    return inventory,models,old,originals,aligned,aligned_models,aligned_cfg,aligned_manifest


def track_boundary(tr,job,model,cfg,protocol):
    require(tr['schema']=='r_set_tracking_receipt_v1' and tr['status']=='complete' and tr['job']==job and tr['model_id']==model['model_id']
        and tr['baseline_model_id']==model['baseline_model_id'] and tr['original_baseline_model_id']==model['original_baseline_model_id']
        and tr['protocol_sha256']==protocol['sha256'] and tr['learning_protocol']==cfg['learning_protocol'] and tr['training_budget']==cfg['training_budget']
        and tr['source_cache']==cfg['sources'][job['sequence']]['cache'] and tr['prefix_frames'] is None,'新完整轨迹双参照/训练来源不同')
    require(all(tr[k] is False for k in ('intercept_applied','calibration_metadata_read','training_labels_used_in_tracking_features','GT_used_for_tracking','evaluation_GT_coordinate_files_opened','alias_used','test_read','GPU_used'))
        and tr['new_optimizer_updates']==0 and not any(k in tr for k in ('fit','beta32','calibrated_beta32')),'不得GT/Pose/截距入新追踪')
    require(all(tr[k] is True for k in ('original_base_forward_without_intercept_wrapper','training_R_S_label_metadata_parsed_for_checkpoint_binding','all_job_state_reset','source_inputs_unchanged',
        'original_model_state_unchanged','original_normalizer_unchanged','Torch_CPU_RNG_unchanged','native_ordered_batch_forward_preserved','input_Pose_columns_zeroed_after_original_normalization'))
        and tr['global_ID_before']==0 and tr['actual_dtype']=='float32' and tr['original_input_dim']==194 and tr['original_probability_cutoff']==.5,'原FP32数值/状态/输入合同不同')
    scope=tr['scope_adapter'];require(scope['numerical_AST_unchanged'] is True and scope['modified_AST_nodes']=='one_frame_scope_guard_only'
        and scope['original_tracker_sha256']=='7f7196d9ac812b17ea94a909aaa057910ebecdfd10ee769a9ebe8b7f92759688','原追踪AST不同')
    g=tr['GT_guard'];require(g['python_open_audit_installed'] is True and g['blocked_open_attempts']==0 and g['GT_annotations_opened'] is False,'新GT隔离不足')
    loaded=tr['model_loading_receipt'];require(loaded['schema']=='R_candidate_set_model_loading_receipt_v1'
        and all(loaded[k]==model[k] for k in ('model_id','baseline_model_id','original_baseline_model_id','training_objective'))
        and loaded['learning_protocol']==cfg['learning_protocol'] and loaded['training_budget']==cfg['training_budget'] and loaded['training_complete']==cfg['training_complete']
        and loaded['run_receipt']==model['training_receipt'] and loaded['original_motion_forward'] is True and loaded['output_transform']=='sigmoid'
        and loaded['probability_cutoff']==.5 and loaded['use_pose'] is False and loaded['Pose_columns_zeroed_after_normalization']==170
        and loaded['initialization_equal_original'] is True and loaded['normalizer_equal_original'] is True and loaded['device']=='cpu' and loaded['actual_dtype']=='float32'
        and loaded['checkpoint']=='last1000_not_EMA_no_best' and loaded['intercept_applied'] is False and loaded['new_optimizer_updates']==0 and loaded['test_read'] is False,'实际集合监督加载状态不同')
    require(all(tr['binding'][k]==model[k] for k in ('fold','seed','regime')) and tr['binding']['method']=='motion'
        and tr['binding']['R_objective']=='candidate_set_CE_fixed_no_match_logit_0' and tr['binding']['protocol_sha256']==LEARNING_SHA
        and tr['binding']['initialization_sha256']==model['expected_initialization_sha256'],'实际新方法binding身份不同')


def records(cfg,models,old,originals,aligned_models,aligned_cfg,aligned_manifest,state,control,protocol,totals,gt_rows):
    output=[]
    for aligned in (False,True):
        if aligned:
            entries=aligned_manifest['reports'];tracks={v['job']['job_id']:v for v in aligned_manifest['tracking']};inventory=aligned_models;tracking_protocol=cfg['aligned_tracking_protocol']
        else:
            entries=[state['completed_metric'][j['job_id']] for j in cfg['jobs']];tracks=state['completed_track'];inventory=models;tracking_protocol=protocol
        for entry in entries:
            job=entry['job'];jid=job['job_id'];seq=job['sequence'];model=inventory[job['model_id']];body=read(entry['report']);tr_ref=tracks[jid]['receipt'];tr=read(tr_ref)
            if aligned:aligned_track_boundary(tr,job,model,aligned_cfg,tracking_protocol)
            else:
                folder=control/'runs'/jid;require(job in cfg['jobs'] and checked(entry['report'])==folder/'metric/report.json'
                    and checked(tr_ref)==folder/'tracking/receipt.json' and physical(tracks[jid]['tracking'])==folder/'tracking','新实际输出路径不同')
                track_boundary(tr,job,model,cfg,protocol)
            require(body['schema']==('state_aligned_tracking_metric_v1' if aligned else 'r_set_tracking_metric_v1') and body['job']==job
                and body['protocol_sha256']==tracking_protocol['sha256'] and body['tracking_receipt']==tr_ref and body['source_cache']==cfg['sources'][seq]['cache']
                and body['baseline_model_id']==model['baseline_model_id'] and body['learning_protocol']==tr['learning_protocol'] and body['training_budget']==tr['training_budget']
                and body['intercept_applied'] is False and body['new_optimizer_updates']==0,'两套实际评价收据来源不同')
            if not aligned:require(body['original_baseline_model_id']==model['original_baseline_model_id'],'新评价原参照ID不同')
            require(tr['mot']['sha256']==tr['mot_sha256'],'MOT摘要不同');counts=mot_counts(tr['mot'],cfg['sources'][seq]['frames'])
            require(counts==tr['frame_counts'] and sum(counts)==tr['tracked_rows']==body['tracked_rows'] and tr['frames']==body['frames']==len(counts),'全MOT/TrackEval预测计数不同')
            metric=report_metrics(body,seq,len(counts),sum(counts),gt_rows[seq]);metric_source(body)
            registry=cfg['registries']['seven' if seq in cfg['panels']['seven_observed'] else 'old_five']['registry'];require(body['registry']==registry,'gap原登记不同');gap_values(body['gap']['overall'],totals[seq])
            row=dict(**{k:job[k] for k in ('model_id','regime','sequence','fold','seed')},condition=('alignedBCE_' if aligned else 'newCE_')+job['regime'],
                baseline_model_id=model['baseline_model_id'],metrics=metric,gap=body['gap']['overall'],report=entry['report'],tracking_receipt=tr_ref,frames=len(counts))
            if not aligned:row['original_baseline_model_id']=model['original_baseline_model_id']
            output.append(row)
    return output+original_records(cfg,old,originals,totals,gt_rows)


def reconstruct(values,panels):
    """从已独立核查的540报告重建五项差分，不调用分析器。"""
    index={(v['condition'],v['sequence'],v['fold'],v['seed']):v for v in values}
    require(len({v['report']['path'] for v in values})==540,'540来源不能共用报告路径')
    expected={(c,s,f,d) for c in CONDITIONS for r,s,f,d in expected_cells(panels) if r==c.rsplit('_',1)[1]}
    require(len(values)==len(index)==540 and set(index)==expected,'540来源缺失/重复/额外单元')
    for row in values:
        require(set(row['metrics'])==set(METRICS) and all(type(v) in (int,float) and math.isfinite(v) for v in row['metrics'].values()),'绝对指标非完整有限五项')
        require(row['condition'].split('_')[1]==row['regime'],'条件与R/RS身份不同')
        gap_values(row['gap'],row['gap']['total_events'])
    coefficients=((('newCE_RS',1),('alignedBCE_RS',-1)),(('newCE_R',1),('alignedBCE_R',-1)),
        (('newCE_RS',1),('originalstrongmotion_RS',-1)),(('newCE_R',1),('originalstrongmotion_R',-1)),
        (('newCE_RS',1),('newCE_R',-1),('alignedBCE_RS',-1),('alignedBCE_R',1)))
    cells=[];byseq=panels_map(panels)
    for seq,fold,seed in sorted((s,f,d) for r,s,f,d in expected_cells(panels) if r=='R'):
        q={c:index[(c,seq,fold,seed)] for c in CONDITIONS}
        require(all(q['newCE_'+r]['baseline_model_id']==q['alignedBCE_'+r]['model_id']
            and q['newCE_'+r]['original_baseline_model_id']==q['originalstrongmotion_'+r]['model_id']
            and q['alignedBCE_'+r]['baseline_model_id']==q['originalstrongmotion_'+r]['model_id']
            and len({q[p+'_'+r]['model_id'] for p in ('newCE','alignedBCE','originalstrongmotion')})==3 for r in REGIMES),'双参照身份未完整匹配')
        totals={r['gap']['total_events'] for r in q.values()};require(len(totals)==1,'四条件同源gap分母不同');total=totals.pop()
        for family,terms in zip(COMPARISONS,coefficients):
            cells.append(dict(comparison=family,panel=byseq[seq],sequence=seq,fold=fold,seed=seed,
                delta_pp={m:sum(sign*q[c]['metrics'][m] for c,sign in terms) for m in METRICS},total_registered_events=total,
                delta_recovery_rate_pp=None if not total else 100*sum(sign*q[c]['gap']['recovery_rate'] for c,sign in terms),
                source_gap_terms={c:{k:q[c]['gap'][k] for k in ('total_events','same_prediction_ID_recovered','recovery_rate')} for c,sign in terms},
                source_terms={c:dict(coefficient=sign,model_id=q[c]['model_id'],report=q[c]['report']) for c,sign in terms}))
    matches=[]
    for family in COMPARISONS:
        for seq,panel in byseq.items():
            rows=[r for r in cells if r['comparison']==family and r['sequence']==seq]
            expected_units={(f,d) for f in ((OLD[seq],) if seq in OLD else FOLDS) for d in SEEDS}
            require(len(rows)==len(expected_units) and {(r['fold'],r['seed']) for r in rows}==expected_units,'比赛均值前匹配单元不足')
            require(len({r['total_registered_events'] for r in rows})==1,'同场gap分母随seed/fold改变')
            total=rows[0]['total_registered_events']
            matches.append(dict(comparison=family,panel=panel,sequence=seq,matched_training_cells=len(rows),
                delta_pp={m:mean(r['delta_pp'][m] for r in rows) for m in METRICS},total_registered_events=total,
                delta_recovery_rate_pp=mean(r['delta_recovery_rate_pp'] for r in rows) if total else None))
    absolute_matches=[];absolute_panels=[]
    for condition in CONDITIONS:
        for seq,panel in byseq.items():
            rows=[r for r in values if r['condition']==condition and r['sequence']==seq]
            total=rows[0]['gap']['total_events']
            require(len({r['gap']['total_events'] for r in rows})==1,'绝对成绩同源gap分母不同')
            absolute_matches.append(dict(condition=condition,panel=panel,sequence=seq,matched_training_cells=len(rows),
                metrics={m:mean(r['metrics'][m] for r in rows) for m in METRICS},total_registered_events=total,
                gap_recovery_rate_pp=100*mean(r['gap']['recovery_rate'] for r in rows) if total else None))
        for panel in PANELS:
            rows=[r for r in absolute_matches if r['condition']==condition and r['panel']==panel]
            rates=[r['gap_recovery_rate_pp'] for r in rows if r['gap_recovery_rate_pp'] is not None]
            absolute_panels.append(dict(condition=condition,panel=panel,independent_matches=len(rows),
                metrics={m:mean(r['metrics'][m] for r in rows) for m in METRICS},gap_recovery_rate_pp=mean(rates) if rates else None,
                gap_matches_with_events=len(rates),null_gap_matches=[r['sequence'] for r in rows if r['gap_recovery_rate_pp'] is None]))
    require((len(cells),len(matches),len(absolute_matches),len(absolute_panels))==(450,60,72,18),'完整比较/绝对汇总计数不同')
    return cells,matches,absolute_matches,absolute_panels


def check_csvs(report,values,cells,matches,absm,absp):
    fields=['condition','model_id','baseline_model_id','original_baseline_model_id','regime','sequence','fold','seed',*METRICS,'gap_events','gap_success','gap_rate','frames',
        'report_path','report_sha256','tracking_receipt_path','tracking_receipt_sha256']
    raw=[]
    for v in values:
        raw.append(dict(**{k:v[k] for k in ('condition','model_id','regime','sequence','fold','seed','frames')},
            baseline_model_id=v.get('baseline_model_id'),original_baseline_model_id=v.get('original_baseline_model_id'),**v['metrics'],gap_events=v['gap']['total_events'],gap_success=v['gap']['same_prediction_ID_recovered'],
            gap_rate=v['gap']['recovery_rate'],report_path=v['report']['path'],report_sha256=v['report']['sha256'],
            tracking_receipt_path=v['tracking_receipt']['path'],tracking_receipt_sha256=v['tracking_receipt']['sha256']))
    compare_csv(read_csv(report['all_results_csv'],fields),raw,['condition','model_id','sequence'])
    identity=['comparison','panel','sequence','fold','seed']
    pairs=[dict(**{k:r[k] for k in identity},**r['delta_pp'],source_terms=canonical(r['source_terms'])) for r in cells]
    compare_csv(read_csv(report['all_paired_cells_csv'],identity+[*METRICS,'source_terms']),pairs,identity)
    fields=identity+['total_registered_events','delta_recovery_rate_pp','source_gap_terms','source_terms']
    gaps=[dict(**{k:r[k] for k in identity+['total_registered_events','delta_recovery_rate_pp']},source_gap_terms=canonical(r['source_gap_terms']),source_terms=canonical(r['source_terms'])) for r in cells]
    compare_csv(read_csv(report['all_paired_gaps_csv'],fields),gaps,identity)
    fields=['comparison','panel','sequence','matched_training_cells',*METRICS,'total_registered_events','delta_recovery_rate_pp']
    rows=[dict(**{k:r[k] for k in fields if k not in METRICS},**r['delta_pp']) for r in matches]
    compare_csv(read_csv(report['all_paired_matches_csv'],fields),rows,['comparison','panel','sequence'])
    for name,rows,extra in [('absolute_matches_csv',absm,['sequence','matched_training_cells','total_registered_events']),
        ('absolute_panels_csv',absp,['independent_matches','gap_matches_with_events','null_gap_matches'])]:
        fields=['condition','panel',*extra,*METRICS,'gap_recovery_rate_pp']
        expected=[dict(**{k:canonical(r[k]) if isinstance(r[k],list) else r[k] for k in ['condition','panel',*extra,'gap_recovery_rate_pp']},**r['metrics']) for r in rows]
        compare_csv(read_csv(report[name],fields),expected,['condition','panel']+(['sequence'] if name=='absolute_matches_csv' else []))
    require(deep_close(report['absolute_matches'],absm) and deep_close(report['absolute_panels'],absp),'报告绝对成绩不是原值汇总')
    return dict(all_results=540,paired_metric_cells=450,paired_gap_cells=450,paired_matches=60,absolute_matches=72,absolute_panels=18)


def terminal_gate(cfg,state,manifest,analysis,protocol):
    ids={j['job_id'] for j in cfg['jobs']}
    require(state['schema']=='r_set_tracking_control_v1' and state['status']==DONE and state['protocol']==protocol and state['active']==[]
        and set(state['completed_track'])==set(state['completed_metric'])==ids,'真实180控制终态/活动/完成映射不齐')
    require(manifest['schema']=='r_set_tracking_manifest_v1' and manifest['status']=='complete180_R_set_tracking_and_evaluation'
        and manifest['config_sha256']==protocol['sha256'] and manifest['new_optimizer_updates']==0 and manifest['test_read'] is False
        and manifest['reports']==[state['completed_metric'][j['job_id']] for j in cfg['jobs']]
        and manifest['tracking']==[state['completed_track'][j['job_id']] for j in cfg['jobs']]
        and manifest['worker_exits']==state['worker_exits'],'实际manifest顺序/新180出处不同')
    require(analysis['schema']=='R_set_tracking_paired_analysis_v1' and analysis['status']==ANALYSIS_DONE
        and same_signed_file(analysis['protocol'],protocol) and analysis['new_tracking_evaluations']==analysis['aligned_reference_evaluations']==analysis['original_reference_evaluations']==180 and analysis['historical_reference_evaluations']==360
        and analysis['all_results']==540 and analysis['paired_cells']==analysis['paired_gap_cells']==450 and analysis['paired_matches']==60 and analysis['absolute_match_count']==72 and analysis['absolute_panel_count']==18
        and analysis['metric_interval_descriptions']==75 and analysis['gap_interval_descriptions']==15,'全部分析尚未闭合')


def verify(config,control,output):
    config,control,output=map(physical,(config,control,output));protocol=ref(config);cfg=read(protocol)
    require(EXP in control.parents and EXP in output.parents and physical(cfg['control_root'])==control and not output.parent.exists(),'独立终验不得覆盖partial/成功或越界')
    inventory,models,old,originals,aligned,aligned_models,aligned_cfg,aligned_manifest=metadata(cfg);training=training_metadata(cfg)
    state_ref=ref(control/'driver_state.json');state=read(state_ref);manifest_ref=ref(control/'manifest.json');manifest=read(manifest_ref)
    report_ref=ref(control/'analysis_a01/report.json');report=read(report_ref);terminal_gate(cfg,state,manifest,report,protocol)
    expected_sources={k:cfg[k] for k in ('inventory','aligned_inventory','source_inventory','aligned_analysis','analysis_plan','aligned_learning_protocol','aligned_tracking_protocol','learning_protocol','training_budget','training_complete')}
    expected_sources['formal_evaluation_manifest']=manifest_ref
    require(set(report['sources'])==set(expected_sources) and all(same_signed_file(report['sources'][k],v) for k,v in expected_sources.items())
        and same_signed_file(state['analysis'],report_ref) and report['panels']==cfg['panels'] and report['primary_comparison']==COMPARISONS[0] and report['primary_metric']=='AssA'
        and report['all_folds_seeds_negative_zero_and_null_results_retained'] is True and report['formal_equivalence_or_noninferiority'] is False and report['performance_margin'] is None
        and report['test_read'] is False and all(report[k]==0 for k in ('analysis_optimizer_updates','new_model_forwards','new_tracking','new_solver_calls','new_TrackEval'))
        and report['bootstrap_seed']==20261028 and report['bootstrap_resamples']==10000,'报告全来源闭包/零更新/统计口径不同')
    write_new(output.parent/'intent.json',dict(schema='r_set_tracking_terminal_intent_v1',status='started_not_committed',protocol=protocol,implementation=ref(__file__),
        control=str(control),new_optimizer_updates=0,new_model_forward_or_tracking_or_TrackEval_runs=0,test_read=False))
    try:
        initial=processes_absent(process_snapshot(),state)
        with no_raw_reads(cfg,dict(models=inventory['models']+aligned['models']+old['models'])) as guard:
            admission=numeric_admission(cfg);totals,gt=public_counts(cfg)
            values=records(cfg,models,old,originals,aligned_models,aligned_cfg,aligned_manifest,state,control,protocol,totals,gt)
            workers=check_workers(state,manifest,cfg,values)
            cells,matches,absm,absp=reconstruct(values,cfg['panels']);csvs=check_csvs(report,values,cells,matches,absm,absp);intervals=check_intervals(report,matches,cfg['panels'])
            require(report['source_gap_event_denominators']==totals and report['gap_events_counted_once_per_source']==sum(totals.values())==3690,'六条件原3690事件分母不同')
            for name,prefix in (('all_actual_reports','newCE_'),('all_aligned_reference_reports','alignedBCE_'),('all_original_reference_reports','originalstrongmotion_')):
                require(report[name]==[v['report'] for v in values if v['condition'].startswith(prefix)],'未保留完整180来源：'+name)
            gate=read(ref(control/'first_two_actual_metric_gate.json'));jobs=[next(j for j in cfg['jobs'] if j['job_id']==gid) for gid in cfg['gate_job_ids']]
            require(gate['status']=='complete_R_RS_two_sources_actual_metrics_ID0_full_predictions_gate' and gate['jobs']==jobs
                and gate['reports']==[state['completed_metric'][j['job_id']]['report'] for j in jobs],'首两实际GT/ID0/全预测门禁不同')
            require(guard['blocked_open_attempts']==0,'终验曾试图打开原缓存/GT/权重');guard_evidence=dict(guard)
        final=processes_absent(process_snapshot(),state)
        result=dict(schema='R_set_tracking_independent_verification_v1',status=STATUS,implementation=ref(__file__),protocol=protocol,state=state_ref,manifest=manifest_ref,analysis=report_ref,
            source_refs=expected_sources,training_metadata=training,numeric_admission=admission,workers=workers,all_csvs=csvs,intervals=intervals,
            source_gap_event_denominators=totals,gap_events_once_per_source=3690,new_tracking_evaluations=180,aligned_reference_evaluations=180,original_reference_evaluations=180,
            historical_reference_evaluations=360,complete_metric_source_count=540,paired_cells=450,paired_gap_cells=450,paired_matches=60,absolute_matches=72,absolute_panels=18,
            metric_interval_descriptions=75,gap_interval_descriptions=15,initial_exit=initial,final_exit=final,producer_processes_absent=True,old_raw_input_open_guard=guard_evidence,
            old_weights_cache_GT_coordinate_or_media_opened=False,training_budget_independent_audit_reexecuted=False,new_model_forward_or_tracking_or_TrackEval_runs=0,new_optimizer_updates=0,
            numerical_serialization_tolerance_pp=TOLERANCE_PP,formal_equivalence_or_noninferiority=False,performance_margin=None,
            all_negative_zero_null_folds_seeds_and_sources_retained=True,test_read=False,verified_utc=datetime.now(timezone.utc).isoformat())
        write_new(output,result);return result
    except BaseException as error:
        write_new(output.parent/'failed.json',dict(status='failed_R_set_tracking_verification_partial_preserved_no_replay',error=repr(error),traceback=traceback.format_exc(),
            source_modified=False,new_model_forward_or_tracking_or_TrackEval_runs=0,new_optimizer_updates=0,test_read=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','control','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--execute',action='store_true');args=p.parse_args()
    value=verify(args.config,args.control,args.output) if args.execute else dict(status='readonly_R_set_tracking_terminal_candidate_no_verification_or_output')
    print(canonical(dict(status=value['status'])))
