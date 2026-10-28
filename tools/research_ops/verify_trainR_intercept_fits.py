"""十八个训练R截距的独立终验；只核新logit/数学记录，不重前向或读取旧权重。"""
import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import traceback

R = Path('D:/projects/FutsalMOT_Research')
EXP = R/'pose/trainR_intercept_calibration_a01'
FOLDS = ('game4', 'game6', 'game9')
SEEDS = (20261024, 20261025, 20261026)
OLD = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
STATUS = 'complete18_trainR_intercept_fits18000_windows_full_records_and_exit_verified'
FIT_STATUS = 'complete_finite_trainR_intercept_fit_not_tracking_effect'
MANIFEST_STATUS = 'complete18_trainR_intercept_fits_wait_independent_verification'
WINDOWS = 1000


def require(ok, message):
    if not ok: raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def physical(value):
    path = Path(value); require(path.is_absolute(), '终验必须绝对物理路径'); path = Path(os.path.abspath(path))
    require(R in path.parents and not any(p.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', p.lower()) for p in path.parts),
            '只准研究物理根；最终测试继续封存')
    for current in (path, *path.parents):
        if current.exists() or current.is_symlink():
            info = current.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400, '不跟随junction')
    return path


def sha(path):
    digest = hashlib.sha256()
    with physical(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''): digest.update(chunk)
    return digest.hexdigest()


def ref(path): return dict(path=str(path), sha256=sha(path))


def checked(reference):
    require(isinstance(reference, dict) and set(reference) >= {'path', 'sha256'} and
            re.fullmatch('[0-9a-f]{64}', reference['sha256']), '缺完整已签来源引用')
    path = physical(reference['path'])
    require(path.is_file() and sha(path) == reference['sha256'], '新记录/明确源码SHA改变：'+str(path))
    return path


def read(path): return json.loads(physical(path).read_text(encoding='utf-8-sig'))


def f32(value):
    require(type(value) in (int, float) and math.isfinite(value), '必须有限数值')
    try: result = struct.unpack('<f', struct.pack('<f', value))[0]
    except (OverflowError, struct.error) as error: raise ValueError('不能表示为有限FP32') from error
    require(math.isfinite(result), '部署FP32不可溢出'); return result


def same(actual, expected, location='math'):
    if type(expected) in (float, int) and type(expected) is not bool:
        require(type(actual) in (int, float) and math.isfinite(actual) and math.isfinite(expected)
            and abs(actual-expected) <= 2e-13*max(1., abs(expected)), '数值/字段不同：'+location)
    elif isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), '字段不完整：'+location)
        for key, value in expected.items(): same(actual[key], value, location+'.'+key)
    elif isinstance(expected, (list, tuple)):
        require(isinstance(actual, (list, tuple)) and len(actual) == len(expected), '顺序/分母不同：'+location)
        for index, value in enumerate(expected): same(actual[index], value, location+'.'+str(index))
    else: require(actual == expected and type(actual) is type(expected), '声明不同：'+location)


def _sigmoid(value):
    if value >= 0.: return 1./(1.+math.exp(-value))
    exponential = math.exp(value); return exponential/(1.+exponential)


def _loss(value, label):
    return (max(value, 0.) if label == 0 else max(-value, 0.)) + math.log1p(math.exp(-abs(value)))


def _residual(value, label): return _sigmoid(value) if label == 0 else -_sigmoid(-value)


def objective(windows, beta):
    """独立按已存窗口等权核BCE/导数；不寻找新的beta，不调用原fit。"""
    losses, gradients = [], []
    for window in windows:
        known = window['known_pair_indices']
        losses.append(math.fsum(_loss(window['logits'][i]+beta, window['labels'][i]) for i in known)/len(known) if known else 0.)
        gradients.append(math.fsum(_residual(window['logits'][i]+beta, window['labels'][i]) for i in known)/len(known) if known else 0.)
    return dict(NLL=math.fsum(losses)/WINDOWS, derivative=math.fsum(gradients)/WINDOWS)


def descriptive(windows, beta, arithmetic='fit64'):
    nll, brier, accepted_known, accepted_all = [], [], [], []
    supervised = sum(bool(w['known_pair_indices']) for w in windows)
    for window in windows:
        values = ([*window['logits']] if beta == 0. else [f32(value+beta) for value in window['logits']]) if arithmetic == 'apply32' else [value+beta for value in window['logits']]
        known = window['known_pair_indices']; probabilities = [_sigmoid(value) for value in values]
        nll.append(math.fsum(_loss(values[i], window['labels'][i]) for i in known)/len(known) if known else 0.)
        brier.append(math.fsum(_residual(values[i], window['labels'][i])**2 for i in known)/len(known) if known else 0.)
        accepted_known.append(sum(probabilities[i] >= .5 for i in known)/len(known) if known else 0.)
        accepted_all.append(sum(p >= .5 for p in probabilities)/len(probabilities) if probabilities else 0.)
    return dict(NLL=math.fsum(nll)/WINDOWS, Brier=math.fsum(brier)/WINDOWS,
        probability_acceptance_known_pairs_window_equal=math.fsum(accepted_known)/WINDOWS,
        probability_acceptance_all_pairs_window_equal=math.fsum(accepted_all)/WINDOWS,
        known_supervised_window_NLL_description=math.fsum(nll)/supervised if supervised else None,
        known_supervised_window_Brier_description=math.fsum(brier)/supervised if supervised else None,
        denominator_all_windows=WINDOWS, supervised_window_count=supervised,
        arithmetic=('FP64_metrics_after_FP32_logit_addition' if arithmetic == 'apply32' else
            'FP64_original_logits_plus_projected_beta32_without_FP32_addition' if arithmetic == 'projected' else 'FP64_original_logits_plus_beta64'),
        acceptance_rule='sigmoid64(z)>=0.5_descriptive_only_not_actual_Torch_FP32_tracker_decision',
        actual_Torch_probability_or_cost_gate_verified=False)


def prepare_records(records, spec):
    require(len(records) == WINDOWS and len({w['window_uid'] for w in records}) == WINDOWS, '必须完整1000唯一原R窗，不删unknown或补UID')
    prepared, signatures = [], []; chain = '0'*64
    totals = dict(windows=WINDOWS, supervised_window_count=0, empty_known_window_count=0, all_pair_count=0,
        known_pair_count=0, unknown_pair_count=0, positive_pair_count=0, negative_pair_count=0)
    for index, record in enumerate(records):
        row = dict(record); claimed_chain = row.pop('record_chain_sha256')
        chain = hashlib.sha256((chain+canonical(row)).encode()).hexdigest()
        require(chain == claimed_chain, '原logit逐窗记录链断裂')
        require(row['model_id'] == spec['model_id'] and row['domain'] == 'real' and row['game'] != spec['fold']
            and row['game'] in FOLDS and OLD.get(row['sequence']) == row['game'] and row['source_uid'] == row['window_uid']
            and re.fullmatch('[0-9a-f]{64}', row['window_uid']) and row['source_pool_row'] == index
            and row['epoch'] == 0 and row['augmentation'] is False and row['use_pose'] is False, '原pool/训练域/顺序或无增广身份不同')
        logits, labels, candidates = row['logits'], row['labels'], row['candidate_UIDs']
        require(len(logits) == len(labels) == len(candidates) == len(row['known_mask']) == len(row['pair_source_UIDs'])
            and len(set(candidates)) == len(candidates) and all(type(x) in (float, int) and f32(x) == x for x in logits), '原逐pair顺序/有限FP32 logits不同')
        require(all(label is None or (type(label) is int and label in (0, 1)) for label in labels), 'unknown不能补0或伪造标签')
        known = [i for i, label in enumerate(labels) if label is not None]
        require(row['known_mask'] == [label is not None for label in labels], 'known mask与原标签不同')
        require(re.fullmatch('[0-9a-f]{64}', row['features_sha256']), '原194维输入digest缺失')
        history, indices, current = row['history_UIDs'], row['history_frame_indices'], row['candidate_frame_index']
        require(len(history) == len(indices) == 3 and indices == sorted(set(indices)) and all(type(v) is int and v >= 0 for v in indices)
            and type(current) is int and current > indices[-1] and row['candidate_frame_number'] == current+1, '历史未来/原帧域不同')
        for uid, frame in [*zip(history, indices), *((uid,current) for uid in candidates)]:
            require(type(uid) is str and re.fullmatch(re.escape(row['sequence'])+r':\d{6}:\d{6}', uid)
                and int(uid.split(':')[1]) == frame+1, '原UID/一基图像零基缓存映射不同')
        expected_pairs = [hashlib.sha256(canonical([row['window_uid'], history, uid]).encode()).hexdigest() for uid in candidates]
        require(row['pair_source_UIDs'] == expected_pairs, 'history/candidate/window pair来源不同')
        prepared.append(dict(window_uid=row['window_uid'], logits=[float(value) for value in logits], labels=list(labels),
            known_pair_indices=known, all_pairs=len(labels), known_pairs=len(known), unknown_pairs=len(labels)-len(known),
            objective_window_weight=1./WINDOWS, known_pair_weight_within_window=1./len(known) if known else None,
            empty_known_contributes_exact_zero=not bool(known), candidate_UIDs=list(candidates)))
        signatures.append({key:row[key] for key in ('window_uid','domain','game','sequence','source_uid','source_pool_row',
            'history_UIDs','candidate_UIDs','pair_source_UIDs','labels','known_mask','features_sha256','history_frame_indices',
            'candidate_frame_index','candidate_frame_number','epoch','augmentation','use_pose')})
        totals['supervised_window_count'] += bool(known); totals['empty_known_window_count'] += not bool(known)
        totals['all_pair_count'] += len(labels); totals['known_pair_count'] += len(known); totals['unknown_pair_count'] += len(labels)-len(known)
        totals['positive_pair_count'] += labels.count(1); totals['negative_pair_count'] += labels.count(0)
    return prepared, totals, dict(record_chain_sha256=chain,
        original_pool_order_UID_sha256=hashlib.sha256(canonical([w['window_uid'] for w in records]).encode()).hexdigest(),
        shared_clean_R_input_signature_sha256=hashlib.sha256(canonical(signatures).encode()).hexdigest(),
        actual_forward_calls=sum(bool(w['logits']) for w in records))


def check_search(fit, windows, parameters):
    """只核已记录评价点、相邻区间和终止规则；没有重新运行求根。"""
    beta = fit['beta64']; require(type(beta) in (float,int) and math.isfinite(beta), '实际beta必须有限')
    lower, upper = -1., 1.; zero = objective(windows, 0.)['derivative']
    brackets, iterations = fit['bracket_trace'], fit['bisection_trace']
    reason, expected = None, None
    if zero == 0.:
        require(not brackets and not iterations, '机器exact零导数时不能虚构额外搜索')
        expected, reason = 0., 'exact_zero_derivative_at_zero'
    else:
        require(1 <= len(brackets) <= parameters['max_bracket_doublings']+1, '二分初始bracket记录缺失')
        for index, entry in enumerate(brackets):
            require(entry['iteration'] == index and entry['lower'] == lower and entry['upper'] == upper, 'bracket必须从正负1逐次倍增')
            lo, hi = objective(windows, lower)['derivative'], objective(windows, upper)['derivative']
            same(entry['derivative_lower'],lo,'bracket.derivative_lower');same(entry['derivative_upper'],hi,'bracket.derivative_upper')
            done = lo == 0. or hi == 0. or lo < 0. < hi
            if index < len(brackets)-1:
                require(not done, '已找到bracket仍继续倍增，不是已冻结算法');lower*=2.;upper*=2.
            else:
                require(done, '最终bracket不能包住唯一有限解')
                if lo == 0.:expected,reason=lower,'exact_zero_derivative_at_bracket_endpoint'
                elif hi == 0.:expected,reason=upper,'exact_zero_derivative_at_bracket_endpoint'
        if expected is not None: require(not iterations, 'endpoint已machine exact求解不能另跑二分')
        else:
            require(1 <= len(iterations) <= parameters['max_bisection_iterations'], '完整二分轨迹缺失')
            for index, entry in enumerate(iterations):
                midpoint = lower+(upper-lower)/2.; value = objective(windows, midpoint)
                require(entry['iteration'] == index and entry['lower'] == lower and entry['upper'] == upper and entry['midpoint'] == midpoint,
                        '二分midpoint/区间连续性不同')
                same(entry['derivative'],value['derivative'],'bisection.derivative');same(entry['NLL'],value['NLL'],'bisection.NLL')
                stop = value['derivative'] == 0. or upper-lower <= parameters['tolerance']
                if index == len(iterations)-1:
                    require(stop, '不能以小梯度或迭代耗尽冒充有限精度终止')
                    expected = midpoint
                    reason = 'exact_zero_derivative_in_bisection' if value['derivative'] == 0. else 'absolute_beta_bracket_width_tolerance'
                else:
                    require(not stop and midpoint != lower and midpoint != upper, '已终止或FP64停滞还伪造二分记录')
                    if value['derivative'] < 0.:lower=midpoint
                    else:upper=midpoint
    require(beta == expected and fit['stopping_reason'] == reason, '部署beta不属已记录根或终止原因错误')
    same(fit['final_bracket'],dict(lower=lower,upper=upper,width=upper-lower),'final_bracket')
    same(fit['derivative_at_solution'],objective(windows,beta)['derivative'],'derivative_at_solution')


def check_rank(windows, beta):
    comparisons=collapsed=reversals=changed=0
    for window in windows:
        raw=sorted(set(window['logits'])); shifted=raw if beta == 0. else [f32(x+beta) for x in raw]
        current=0
        for left,right in zip(shifted,shifted[1:]): comparisons+=1;reversals+=left>right;current+=left==right
        collapsed+=current;changed+=current>0
    require(reversals == 0,'常数FP32平移不能被报告为行内顺序反转')
    return dict(scope='adjacent_distinct_original_logits_within_each_window_all_pairs_including_unknown',
        adjacent_distinct_input_comparisons=comparisons,order_reversals=reversals,
        adjacent_distinct_logits_collapsed_to_FP32_ties=collapsed,windows_with_new_FP32_ties=changed,
        mathematical_constant_shift_preserves_ranking=True,finite_precision_can_create_new_ties=True,strict_rank_equality_claim=False)


def check_fit(fit, records, spec, parameters):
    require(fit['schema']=='trainR_intercept_fit_v1' and fit['status']==FIT_STATUS and fit['finite_minimizer'] is True
        and fit['parameters']==parameters and fit['model_spec']==spec and
        all(fit[key]==spec[key] for key in ('model_id','regime','fold','seed')), '十八原模型/有限解/协议字段不同')
    require(fit['optimizer_updates']==0 and fit['new_model_training'] is False and fit['validation_or_test_inputs_used'] is False
        and fit['source_weights_or_normalizer_or_features_changed'] is False
        and fit['fitting_objective_improvement_is_tracking_effectiveness_evidence'] is False
        and fit['actual_Torch_numeric_admission_required'] is True, '不能把监督标量拟合冒充训练收益/实际追踪证据')
    windows,totals,signatures=prepare_records(records,spec)
    require(totals['positive_pair_count']>0 and totals['negative_pair_count']>0, '单类/无known不得伪装有限截距')
    same(fit['input_windows'],windows,'input_windows');same(fit['totals'],totals,'totals')
    require(fit['input_sha256']==hashlib.sha256(canonical(windows).encode()).hexdigest(),'原prepared输入SHA不同')
    check_search(fit,windows,parameters)
    beta,beta32=fit['beta64'],fit['apply_beta32']
    require(type(beta32) in (float,int) and f32(beta32)==beta32 and
        struct.pack('<f',f32(beta))==struct.pack('<f',beta32),'beta32必须原beta64一次FP32投影；不近零截断')
    before=descriptive(windows,0.);after=descriptive(windows,beta);projected=descriptive(windows,beta32,'projected');applied=descriptive(windows,beta32,'apply32')
    for key,value in (('before',before),('after_fit64',after),('after_projected_beta32_sum64',projected),('after_apply32',applied)):
        same(fit[key],value,key)
    same(fit['NLL_numeric_drift'],dict(beta32_projection_vs_beta64=projected['NLL']-after['NLL'],
        FP32_addition_vs_projected_beta32_sum64=applied['NLL']-projected['NLL'],FP32_addition_vs_beta64=applied['NLL']-after['NLL']),'NLL_numeric_drift')
    same(fit['objective_delta'],after['NLL']-before['NLL'],'objective_delta');same(fit['apply32_rank_audit'],check_rank(windows,beta32),'rank_audit')
    require(fit['original_prediction_alias_necessary_zero_condition'] is (beta32==0.) and fit['original_prediction_alias_authorized'] is False
        and fit['alias_requires_source_and_forward_identity_proof'] is True and fit['alias_comparison']=='exact_FP32_zero_no_epsilon', '精确零条件不能自行授权历史别名')
    recording=fit['recording'];require(recording['record_chain_sha256']==signatures['record_chain_sha256'] and
        recording['forward_calls']==signatures['actual_forward_calls'] and recording['RNG_unchanged'] is True and
        re.fullmatch('[0-9a-f]{64}',recording['model_digest_before']) and recording['model_digest_before']==recording['model_digest_after'] and
        recording['optimizer_state']=='not_applicable_scalar_root_finding_no_SGD' and
        type(recording['wall_seconds']) in (float,int) and math.isfinite(recording['wall_seconds']) and recording['wall_seconds']>=0., '前向/权重/RNG声明或完整记录链缺失')
    source=fit['input_receipt'];require(source['model_id']==spec['model_id'] and source['fold']==spec['fold'] and source['seed']==spec['seed'] and
        source['regime']==spec['regime'] and source['pool']==spec['clean_R_pool'] and source['normalizer']==spec['normalizer'] and
        source['original_pool_order_UID_sha256']==signatures['original_pool_order_UID_sha256'] and source['objective_denominator']==WINDOWS and
        source['unknown_pairs_retained_not_fitted'] is True and source['normalizer_fitted'] is False and source['augmentation'] is False and
        source['new_optimizer_updates']==source['model_forward_calls']==source['actual_model_window_evaluations']==0 and
        source['planned_extra_R_model_window_evaluations']==WINDOWS and source['validation_or_test_read'] is False and
        source['training_S_windows_read'] is False,'原clean R准备/预算来源不同')
    for key,value in source['counts'].items():require(value==totals[key],'原pool与已存logit的全部/known/unknown分母不同')
    return dict(model_id=spec['model_id'],regime=spec['regime'],fold=spec['fold'],seed=spec['seed'],
        totals=totals,signatures=signatures,beta64=beta,apply_beta32=beta32,
        complete_math_trace_verified=True,fitting_NLL_is_in_sample_only=True,performance_pass_flag=None)


def check_matrix(checks, inventory):
    expected={(regime,fold,seed) for regime in ('R','RS') for fold in FOLDS for seed in SEEDS}
    require(len(checks)==18 and {(v['regime'],v['fold'],v['seed']) for v in checks}==expected
        and {v['model_id'] for v in checks}=={s['model_id'] for s in inventory['models']},'全部18匹配模型矩阵缺失/重复')
    for fold in FOLDS:
        current=[v for v in checks if v['fold']==fold]
        require(len(current)==6 and len({v['signatures']['shared_clean_R_input_signature_sha256'] for v in current})==1
            and len({v['signatures']['original_pool_order_UID_sha256'] for v in current})==1,'同fold六模型的窗口/标签/候选/特征digest不一致')
    return dict(models=18,clean_R_model_window_evaluations=18000,
        all_pair_count=sum(v['totals']['all_pair_count'] for v in checks),known_pair_count=sum(v['totals']['known_pair_count'] for v in checks),
        unknown_pair_count=sum(v['totals']['unknown_pair_count'] for v in checks),optimizer_updates=0)


def source_file(cfg, name):
    manifest=read(checked(cfg['bundle_manifest']));relative='tools/research_ops/'+name
    entries=[v for v in manifest['files'] if v['path']==relative]
    require(len(entries)==1,'必要冻结源码缺失：'+name)
    path=physical(Path(cfg['bundle'])/relative);reference=dict(path=str(path),sha256=entries[0]['sha256']);checked(reference);return reference


def runtime_parameters(reference):
    path=checked(reference);spec=importlib.util.spec_from_file_location('trainR_terminal_parameters_only',path);module=importlib.util.module_from_spec(spec)
    previous=sys.dont_write_bytecode
    try:sys.dont_write_bytecode=True;spec.loader.exec_module(module)
    finally:sys.dont_write_bytecode=previous
    return module.PARAMETERS


def blocked_processes(records,state):
    pattern=re.compile(r'(?:^|[\\/\s"\x27])(?:trainR_intercept_(?:fit_control|fit_job|tracking_control)|'
        r'bounded_error_control|ocsort_(?:threshold|cached)_control|pose_velocity_tracking_control)[.]py(?=$|[\s"\x27])',re.I)
    start=datetime.fromisoformat(state['created_utc'].replace('Z','+00:00')); result=[]
    for row in records:
        command=row.get('CommandLine') or '';spawn=False
        if 'spawn_main' in command and re.search(r'\bparent_pid\s*=\s*'+str(state['parent_pid'])+r'\b',command):
            require(row.get('CreationUtc'),'相关spawn缺创建时间，不能按旧PID猜退出')
            when=datetime.fromisoformat(row['CreationUtc'].replace('Z','+00:00'))
            spawn=start-timedelta(seconds=2)<=when<=datetime.now(timezone.utc)+timedelta(seconds=2)
        if (row.get('Name') or '').lower().startswith('unrealeditor') or pattern.search(command) or spawn:result.append(row)
    return result


def processes_absent(state):
    query=("Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | "
        "Select-Object ProcessId,ParentProcessId,Name,CommandLine,@{n='CreationUtc';e={$_.CreationDate.ToUniversalTime().ToString('o')}} | ConvertTo-Json -Compress")
    answer=subprocess.run(['powershell.exe','-NoProfile','-Command',query],check=True,capture_output=True,text=True,encoding='utf-8')
    records=json.loads(answer.stdout) if answer.stdout.strip() else [];records=[records] if isinstance(records,dict) else records
    require(not blocked_processes(records,state),'拟合控制器/实际worker/UE仍在，不杀进程或盲用旧PID')
    return dict(actual_CIM_checked=True,producer_processes_absent=True,historical_PID_reuse_not_rejected=True)


def check_closure(state, manifest, control):
    require(state['status']==MANIFEST_STATUS and state['active']==[] and state['protocol']==manifest['protocol'] and
        state['manifest']==ref(control/'manifest.json') and state['optimizer_updates']==0 and state['test_read'] is False,'拟合控制器尚未真实完整闭合')
    ready,exits=state['workers'],state['worker_exits']; counts=Counter(v['worker_pid'] for v in state['completed'])
    require(len(ready)==len(exits)==2 and len({v['worker_pid'] for v in ready})==2 and
        {v['worker_pid'] for v in exits}=={v['worker_pid'] for v in ready} and sum(counts.values())==18 and
        set(counts)<={v['worker_pid'] for v in ready} and manifest['worker_exits']==exits and manifest['fit_workers_joined'] is True,'两个worker/18任务完成归属不同')
    for value in ready:require(value['status']=='ready','worker实际就绪缺失')
    for value in exits:require(value['status']=='closed' and value['jobs']==counts[value['worker_pid']] and
        value['features_cache_cleared'] is True and value['joined'] is True and value['process_exited'] is True and value['exit_code']==0,
        'worker cache/关闭/join/exit0未齐')
    require(state['actual_exit_gate']['actual_CIM_checked'] is True and state['actual_exit_gate']['related_producers_absent'] is True,'原父控制器实际退出门禁缺失')
    require({v['model_id']:v['fit'] for v in state['completed']}==manifest['calibrations'] and len(state['completed'])==18 and
        all(v['status']=='complete' for v in state['completed']),'manifest与真实完成18项不同')
    logs=[control/'logs'/('fit_%d.log'%i) for i in range(2)];require(all(v.is_file() for v in logs),'两个原stdout/stderr日志缺失')
    return dict(workers=2,actual_jobs=18,closures=exits,logs=[ref(v) for v in logs],all_joined_exit0=True)


def write_new(path,value):
    with Path(path).open('x',encoding='utf-8') as stream:stream.write(canonical(value)+'\n');stream.flush();os.fsync(stream.fileno())


def verify(config,control,output):
    config,control,output=physical(config),physical(control),physical(output);cfg=read(config)
    require(cfg['schema']=='trainR_intercept_fit_protocol_v1' and cfg['phase']=='fit' and cfg['approved_by']=='root' and
        cfg['test_sealed'] is True and cfg['execute_authorized'] is True and cfg['formal_equivalence_or_noninferiority'] is False and
        cfg['validation_used_for_beta_selection'] is False and physical(cfg['output_root'])==EXP,'独立训练R校准授权/来源或统计边界不同')
    require(control==EXP/'fits_a01' and EXP in output.parents and not output.parent.exists() and control not in output.parents,
            '终验必须新attempt，不覆盖旧partial或拟合原始输出')
    inventory=read(checked(cfg['inventory']));manifest=read(control/'manifest.json');state=read(control/'state.json')
    require(manifest['schema']=='trainR_intercept_fits_manifest_v1' and manifest['status']==MANIFEST_STATUS and
        manifest['protocol']==ref(config) and manifest['inventory']==cfg['inventory'] and manifest['test_read'] is False and
        manifest['optimizer_updates']==0 and manifest['model_order']==cfg['model_order']==[v['model_id'] for v in inventory['models']] and
        len(manifest['calibrations'])==18 and set(manifest['calibrations'])==set(cfg['model_order']),'实际18拟合manifest不完整')
    runtime_ref=source_file(cfg,'trainR_intercept_runtime.py');inputs_ref=source_file(cfg,'trainR_intercept_inputs.py')
    parameters=runtime_parameters(runtime_ref);require(cfg['parameters']==parameters,'不能改变原一维目标/1000分母/二分精度')
    gate=read(checked(cfg['numeric_admission']))
    require(gate['status']=='complete6_models3_clean_R_inputs_FP32_intercept_numeric_admission' and gate['passed'] is True and
        gate['inventory']==cfg['inventory'] and gate['full_clean_pool_UID_games_labels_validated'] is True and
        gate['SGD_updates']==gate['scalar_fits']==gate['new_tracking']==0 and gate['validation_or_test_read'] is False and
        gate['GT_coordinates_read'] is False,'真实六模型/全训练池数值准入未闭合')
    require(gate['diagnostic_window_evaluations']==384,'诊断384模型窗必须单列，不混正式18000')
    output.parent.mkdir(parents=True);write_new(output.parent/'intent.json',dict(protocol=ref(config),manifest=ref(control/'manifest.json'),
        implementation=ref(__file__),model_forward_calls=0,optimizer_updates=0,test_read=False))
    try:
        initial_exit=processes_absent(state);closure=check_closure(state,manifest,control);checks=[]
        for spec in inventory['models']:
            reference=manifest['calibrations'][spec['model_id']];fit_path=checked(reference)
            require(fit_path==control/'models'/spec['model_id']/'fit.json','拟合来源不能跳出实际model任务目录')
            fit=read(fit_path)
            require(fit['source_refs']==dict(protocol=ref(config),inventory=cfg['inventory'],runtime=runtime_ref,inputs=inputs_ref),'每拟合协议/源码/输入来源绑定不同')
            recording=fit['recording'];window_path=checked(recording['window_records'])
            require(window_path==fit_path.parent/'windows.jsonl.gz','原1000逐窗logit账本缺失或换源')
            with gzip.open(window_path,'rt',encoding='utf-8') as stream:
                records=[]
                for line in stream:require(bool(line.strip()),'不能跳过空窗/空行');records.append(json.loads(line))
            result=check_fit(fit,records,spec,parameters)
            require(fit['input_receipt']['feature_source']==inventory['feature_source'] and fit['input_receipt']['normalizer_source']==inventory['normalizer_source'],'冻结原194维特征/normalizer来源不同')
            loaded=recording['model_loader_receipt']
            require(loaded['schema']=='trainR_intercept_loaded_original_motion_model_v1' and loaded['model_id']==spec['model_id'] and
                loaded['regime']==spec['regime'] and loaded['fold']==spec['fold'] and loaded['seed']==spec['seed'] and loaded['binding']==spec['binding'] and
                loaded['checkpoint']==spec['checkpoint'] and loaded['loader']==spec['loader'] and loaded['device']=='cpu' and loaded['actual_dtype']=='float32' and
                loaded['model_forward_calls']==loaded['new_optimizer_updates']==0 and loaded['original_complete_loader_used'] is True and
                loaded['input_Pose_used'] is False and loaded['model_parameters_frozen'] is True and loaded['validation_or_test_read'] is False,'原R/RS完整加载器/身份/FP32证明不同')
            paths={key:checked(recording[key]) for key in ('environment','source','RNG_before','RNG_after')}
            require(all(path==fit_path.parent/(key+('.pt' if key.startswith('RNG_') else '.json')) for key,path in paths.items()),
                    '新环境/来源/完整RNG不能指向旧checkpoint')
            env=read(paths['environment']);require(env['device']=='cpu' and env['torch_threads']==1 and env['CUDA_VISIBLE_DEVICES']=='-1' and
                env['dtype']=='FP32_native_per_window' and env['optimizer_updates']==0 and env['augmentation'] is False,'实际CPU/FP32/无SGD环境不同')
            source=read(paths['source']);require(source==dict(model_spec=spec,inventory=cfg['inventory'],protocol=ref(config)),'记录模型来源不一致')
            result.update(fit=reference,window_records=recording['window_records'],RNG_before=recording['RNG_before'],RNG_after=recording['RNG_after'],
                RNG_payloads_hash_bound_not_unpickled=True,RNG_equality_source='producer_unchanged_attestation_only',
                model_weights_reopened_by_terminal=False,raw_input_features_rebuilt=False)
            checks.append(result)
        totals=check_matrix(checks,inventory);same(manifest['totals'],totals,'manifest.totals')
        final_exit=processes_absent(state)
        receipt=dict(schema='trainR_intercept_fits_independent_verification_v1',status=STATUS,implementation=ref(__file__),protocol=ref(config),
            inventory=cfg['inventory'],manifest=ref(control/'manifest.json'),state=ref(control/'state.json'),numeric_admission=cfg['numeric_admission'],
            runtime=runtime_ref,inputs=inputs_ref,totals=totals,model_checks=checks,worker_closure=closure,initial_exit=initial_exit,final_exit=final_exit,
            producer_processes_absent=True,all1000_window_and_unknown_denominators_preserved=True,
            all_saved_logit_points_objective_derivative_bracket_and_FP32_application_independently_checked=True,
            fitting_reexecuted=False,model_forward_calls=0,old_weights_cache_GT_coordinate_or_media_opened=False,
            raw_feature_values_rebuilt=False,saved_feature_digests_equal_across_six_models_per_fold=True,
            new_RNG_payloads_hash_bound_not_unpickled=True,RNG_semantic_equality_independently_proven=False,
            diagnostic_model_window_evaluations_separate=384,new_optimizer_updates=0,scalar_fits_in_source=18,
            additional_supervised_calibration_budget=True,new_independent_real_data_claim=False,strict_same_total_supervision_budget_claim=False,
            fitting_NLL_improvement_not_tracking_effectiveness=True,performance_pass_flag=None,equivalence_or_noninferiority=False,test_read=False)
        write_new(output,receipt);return receipt
    except BaseException as error:
        write_new(output.parent/'failed.json',dict(status='failed_intercept_fit_verification_partial_preserved_no_replay',
            error=repr(error),traceback=traceback.format_exc(),source_modified=False,model_forward_calls=0,optimizer_updates=0,test_read=False));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('config','control','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if args.execute:
        result=verify(args.config,args.control,args.output);print(canonical(dict(status=result['status'],totals=result['totals'],model_forward_calls=0)))
    else:print(canonical(dict(status='readonly_trainR_fit_terminal_candidate_no_verification_or_output',protocol=ref(args.config),
        expected_models=18,expected_model_windows=18000,model_forward_calls=0,optimizer_updates=0)))
