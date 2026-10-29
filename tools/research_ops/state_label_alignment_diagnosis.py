"""既有资格/弱标签账本的有界流式诊断；不加载模型、GT坐标或追踪器。"""
import argparse
import ast
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
from itertools import zip_longest
import json
import multiprocessing as mp
import os
from pathlib import Path
import re
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).parent))
import state_label_alignment_core as core

R = Path('D:/projects/FutsalMOT_Research')
EXP = R/'pose/state_label_alignment_diagnosis_a01'
ROOT = Path(__file__).resolve().parents[2]
STATUS = 'complete3000_R_windows180118_existing_rows_state_label_alignment_diagnosis_no_factor_executed'
ZERO_KEYS = ('new_optimizer_updates', 'new_model_forwards', 'new_image_predictions', 'new_tracking', 'new_solver_calls', 'new_TrackEval')
FOLDS = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
WEIGHTS = ('window_known_mass','R_step_known_mass','excluded_known_window_mass','excluded_known_R_step_mass',
           'unresolved_known_window_mass','unresolved_known_R_step_mass')
EXPOSURE_CELLS = {(f,s) for f in FOLDS.values() for s in (20261024,20261025,20261026)}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def safe(value, output=False):
    p = Path(os.path.abspath(value))
    require(R in p.parents, '只准DResearch实际文件')
    require(not any(x.lower() in ('test','gt') or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', x.lower()) for x in p.parts), '测试/GT坐标封存')
    require(p.suffix.lower() not in ('.pt','.pth','.ckpt','.jpg','.jpeg','.png','.exr','.mp4') and p.name not in ('gap_registry.json','posthoc_GT_labels.json'), '模型/媒体/GT坐标禁止读取')
    if output:
        require(EXP in p.parents, '仅新诊断独立目录可写')
    for x in (p, *p.parents):
        if x.exists() or x.is_symlink():
            require(not x.is_symlink() and not getattr(x.lstat(), 'st_file_attributes', 0) & 0x400, '不跟随junction')
    return p


def sha(path):
    h = hashlib.sha256()
    with safe(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def ref(path):
    return dict(path=str(safe(path)), sha256=sha(path))


def checked(value):
    p = safe(value['path'])
    require(sha(p) == value['sha256'], '来源SHA变化：'+str(p))
    return p


def read(value):
    p = safe(value['path'])
    require(p.suffix == '.json', '只准绑定小JSON')
    checked(value)
    return json.loads(p.read_text(encoding='utf-8-sig'))


def write(path, value):
    p = safe(path, output=True)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8') as f:
        f.write(canonical(value)+'\n')


def json_rows(value):
    p = safe(value['path'])
    require((p.name == 'rows.jsonl.gz' and 'decision_opportunity_a01' in p.parts)
            or (p.name == 'all_rows.jsonl.gz' and 'state_gap_diagnosis_a01' in p.parts)
            or (p.name == 'windows.jsonl' and 'teacher_anchor_bank_a01' in p.parts), '禁止frames/cache/GT/权重/原池等新增读取')
    checked(value)
    opener = gzip.open if p.suffix == '.gz' else open
    count = 0
    with opener(p, 'rt', encoding='utf-8') as f:
        for line in f:
            count += 1
            yield json.loads(line)
    if 'rows' in value:
        require(count == value['rows'], '源逐行分母变化')


def coordinate(row):
    return tuple(row[k] for k in ('frame_number', 'stage', 'row_index', 'track_id'))


def metadata_key(row):
    return (row['source_job_id'], row['candidate_frame_number'], row['source_stage'], row['source_row_index'], row['source_track_id'])


def joined_rows(ledger, annotations):
    """一次只保留同坐标的两行；不读旧frames、raw或GT坐标。"""
    for row, annotation in zip_longest(ledger, annotations):
        require(row is not None and annotation is not None, '后验/机会行数不齐')
        require(coordinate(row) == coordinate(annotation), '逐行坐标或次序不同')
        require(row['job']['job_id'] == annotation['job_id'], '跨job后验join')
        require(row['history_UIDs'] == annotation['history_UIDs']
                and row['query_GT_id'] == annotation['query_GT_id']
                and [p['uid'] for p in row['pose_candidates']] == annotation['candidate_UIDs']
                and [p['label'] for p in row['pose_candidates']] == annotation['pair_labels'], '原历史/query/候选UID/标签不一致')
        yield row, annotation


def selected_metadata(cfg):
    selected = {}
    for row in json_rows(cfg['selected_windows']):
        key = metadata_key(row)
        require(key not in selected, '选中源坐标重复')
        require(row['fold'] != FOLDS[row['sequence']] and row['source_stage'] == 'high_score', '允许train来源或stage不同')
        selected[key] = row
    require(len(selected) == 3000 and len({v['window_uid'] for v in selected.values()}) == 3000, '原3000唯一窗不同')
    return selected


def validate(path):
    path = safe(path)
    cfg = json.loads(path.read_text(encoding='utf-8-sig'))
    require(cfg['schema'] == 'state_label_alignment_diagnosis_protocol_v1' and cfg['approved_by'] == 'root', '协议未冻结授权')
    require(cfg['test_sealed'] is True and cfg['GT_coordinates_read'] is False and all(cfg[k] == 0 for k in ZERO_KEYS), '零实验边界不同')
    require(cfg['main_reference'] == 'original_uncalibrated_strongmotion_RS' and cfg['factor_selected'] is False, '不得事前执行训练因素')
    require(Path(cfg['bundle']) == ROOT and ROOT.parent == R/'code', '只准冻结最小闭包')
    manifest=read(cfg['bundle_manifest'])
    require({x['path'] for x in manifest['files']}=={'tools/research_ops/state_label_alignment_core.py','tools/research_ops/state_label_alignment_diagnosis.py'} and len(manifest['files'])==2, '最小执行闭包不符')
    for item in manifest['files']:
        require(sha(ROOT/item['path']) == item['sha256'], '冻结源码变化')
    require(set(cfg['static_sources'])=={'tracker','features','model','instrumentation'}, '静态来源不齐')
    source={k:checked(v).read_text(encoding='utf-8') for k,v in cfg['static_sources'].items()}
    mask=next(n for n in ast.parse(source['tracker']).body if isinstance(n,ast.FunctionDef) and n.name=='intervention_mask')
    require('enabled[i] = gates[i]' in ast.unparse(mask), '原preprob资格定义不同')
    dists=next(n for n in ast.walk(ast.parse(source['tracker'])) if isinstance(n,ast.FunctionDef) and n.name=='get_dists')
    calls=list(ast.walk(dists))
    mask_line=min(n.lineno for n in calls if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='intervention_mask')
    sigmoid_line=min(n.lineno for n in calls if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='sigmoid')
    require(mask_line<sigmoid_line, 'enabled不在概率前，拒绝资格推断')
    old = read(cfg['anchor_complete'])
    require(old['status'] == 'complete3000_selected_R_bank_anchor_crosscheck_independently_verified'
            and old['selected_windows'] == 3000 and old['all_pairs'] == 42465, '已验teacher来源不齐')
    anchor = read(cfg['anchor_report'])
    require(old['analysis'] == cfg['anchor_report'] and anchor['windows_jsonl'] == cfg['selected_windows'], '必须引用已验原窗口')
    opportunity = read(cfg['opportunity_report'])
    require(opportunity['status'] == 'complete12_existing_log_decision_opportunity_counts_and_source_intervals'
            and opportunity['rows'] == 180118, '原全部机会来源不同')
    source_units = [read(x) for x in opportunity['units']]
    require(len(cfg['source_units']) == 12, '完整12来源必须齐全')
    for index, (u, old_u) in enumerate(zip(cfg['source_units'], source_units)):
        require(u['job'] == old_u['job'] and u['ledger'] == old_u['ledger'] and u['source_unit'] == opportunity['units'][index], '原机会来源不一致')
        ann = read(old_u['posthoc'])
        require(u['annotation'] == ann['all_rows'] and u['annotation']['rows'] == u['ledger']['rows'], '只准既有无坐标后验原行')
    matrix = {(u['job']['fold'], u['job']['regime'], u['job']['sequence'], u['job']['seed']) for u in cfg['source_units']}
    require(matrix == {(f, reg, seq, 20261024) for seq, held in FOLDS.items() for f in FOLDS.values() if f != held for reg in ('R','RS')}, '矩阵不完整/混测试')
    require((cfg['worker_count'], cfg['reserve_RAM_bytes'], cfg['reserve_commit_bytes'], cfg['inflight_reserve_bytes']) == (2,8589934592,6442450944,3221225472), '资源边界不同')
    require(cfg['bootstrap_seed'] == 20261029 and cfg['bootstrap_repeats'] == 10000, '统计预登记不同')
    training = read(cfg['exposure_protocol'])
    require(len(cfg['exposure_tables']) == 9 and {(x['fold'],x['seed']) for x in cfg['exposure_tables']} == EXPOSURE_CELLS, '九曝光表fold/seed矩阵不齐或重复')
    for table in cfg['exposure_tables']:
        require(training['exposures'][table['fold']][str(table['seed'])] == table['table'], '曝光表来源不是原训练')
    if cfg['phase'] == 'formal':
        admission = read(cfg['admission'])
        require(admission['status'] == 'complete_one_source_existing_rows_streaming_admission'
                and admission['all_workers_joined'] is True and cfg['inherit_completed'] == {cfg['source_units'][0]['job']['job_id']: admission['unit']}, '只准继承一次成功实际准入')
        original = read(admission['protocol'])
        for k in ('bundle','bundle_manifest','source_units','selected_windows','exposure_tables','exposure_protocol','anchor_complete','anchor_report','opportunity_report','resource_source',
                  'worker_count','reserve_RAM_bytes','reserve_commit_bytes','inflight_reserve_bytes','bootstrap_seed','bootstrap_repeats','static_sources'):
            require(cfg[k] == original[k], '准入后改变来源/源码：'+k)
    else:
        require(cfg['phase'] == 'admission' and not cfg['inherit_completed'], '阶段无效')
    cfg['_protocol'] = ref(path)
    return cfg


def unit_run(cfg, unit, selected):
    import psutil
    started = time.perf_counter()
    process=psutil.Process();peak_rss=process.memory_info().rss
    job = unit['job']
    require(all(k[0] == job['job_id'] for k in selected), '选窗必须预分配至正确job')
    out = safe(Path(cfg['unit_output_root'])/job['job_id'], output=True)
    require(not out.exists(), 'partial/成功输出不可覆盖或隐式重放')
    out.mkdir(parents=True)
    counts = Counter()
    classes = Counter()
    overlap = defaultdict(Counter)
    flags = defaultdict(Counter)
    bins = {k:defaultdict(Counter) for k in ('history_bin','gap_bin','candidate_bin')}
    selected_counts = Counter()
    scoring = {g:Counter() for g in core.LABEL_GROUPS}
    probability = {g:Counter() for g in core.LABEL_GROUPS}
    found = set()
    all_rows = out/'rows.jsonl.gz'
    windows = out/'selected_windows.jsonl'
    candidates = out/'selected_candidates.jsonl.gz'
    with gzip.open(all_rows,'xt',encoding='utf-8',compresslevel=2) as sink, windows.open('x',encoding='utf-8') as win, gzip.open(candidates,'xt',encoding='utf-8',compresslevel=2) as cand:
        for row, annotation in joined_rows(json_rows(unit['ledger']), json_rows(unit['annotation'])):
            key = (job['job_id'], *coordinate(row))
            metadata = selected.get(key)
            summary, pairs = core.classify_row(row, annotation, metadata)
            sink.write(canonical(summary)+'\n')
            counts.update(summary['counts'])
            counts['rows'] += 1
            if counts['rows'] % 256 == 0:peak_rss=max(peak_rss,process.memory_info().rss)
            classes[summary['B_class']] += 1
            for g in core.LABEL_GROUPS:
                scoring[g].update(summary['scoring_counts'][g])
                probability[g].update(summary['probability_counts'][g])
            for k,v in summary['primary_flags'].items():
                flags[k]['null' if v is None else str(v).lower()] += 1
            for k,v in summary['overlap_flags'].items():
                overlap[k]['null' if v is None else str(v).lower()] += 1
            for name, table in bins.items():
                table[summary[name]]['rows'] += 1
                table[summary[name]][summary['B_class']] += 1
            if metadata is not None:
                require(key not in found, '同窗重复join')
                found.add(key)
                win.write(canonical(summary)+'\n')
                selected_counts.update(summary['counts'])
                selected_counts['windows'] += 1
                for pair in pairs:
                    cand.write(canonical(dict(window_uid=metadata['window_uid'], job_id=job['job_id'], **pair))+'\n')
            del row, annotation, summary, pairs
    require(found == set(selected) and counts['rows'] == unit['ledger']['rows'], '完整行/选窗join缺失')
    result = dict(status='complete', protocol=cfg['_protocol'], job=job, source=unit,
                  rows=dict(**ref(all_rows), rows=counts['rows']), selected_windows=dict(**ref(windows), rows=len(found)),
                  selected_candidates=dict(**ref(candidates), rows=selected_counts['all_pairs']), counts=dict(counts),
                  selected_counts=dict(selected_counts), B_classes=dict(classes), primary_flags={k:dict(v) for k,v in flags.items()},
                  scoring_counts={k:dict(v) for k,v in scoring.items()}, probability_counts={k:dict(v) for k,v in probability.items()},
                  overlap_flags={k:dict(v) for k,v in overlap.items()}, bins={k:{b:dict(v) for b,v in table.items()} for k,table in bins.items()},
                  worker_pid=os.getpid(), peak_RSS_bytes=max(peak_rss,process.memory_info().rss),wall_seconds=time.perf_counter()-started, test_read=False, GT_coordinates_read=False,
                  **{k:0 for k in ZERO_KEYS})
    write(out/'receipt.json', result)
    return ref(out/'receipt.json')


def read_output_rows(value):
    p = safe(value['path'])
    require(EXP in p.parents and p.name in ('selected_windows.jsonl','rows.jsonl.gz','selected_candidates.jsonl.gz'), '只准本轮输出')
    checked(value)
    opener = gzip.open if p.suffix == '.gz' else open
    n=0
    with opener(p,'rt',encoding='utf-8') as f:
        for line in f:
            n+=1
            yield json.loads(line)
    require(n == value['rows'], '输出行数不符')


def exposure_summary(cfg, windows):
    index={w['window_uid']:w for w in windows}
    require(len(cfg['exposure_tables'])==9 and {(x['fold'],x['seed']) for x in cfg['exposure_tables']}==EXPOSURE_CELLS, '曝光表矩阵缺失或重复')
    result=[]
    for bound in cfg['exposure_tables']:
        table=read(bound['table']); entries=table['real']; counts=Counter(); mass=Counter(); seen=Counter()
        require(len(entries)==3000 and table['fold']==bound['fold'] and table['seed']==bound['seed'], '原曝光表标识不同')
        for entry in entries:
            w=index[entry['window_uid']]
            require(w['fold']==bound['fold'] and entry['candidate_pairs']==w['counts']['all_pairs'] and entry['labelled_pairs']==w['counts']['known_pairs'], '曝光UID/原pair数不同')
            seen[w['window_uid']]+=1; counts.update(w['counts']); counts['window_exposures']+=1
            mass.update({k:w['bce_weights'][k] for k in WEIGHTS})
        require(len(seen)==1000 and set(seen.values())=={3}, '原1000唯一窗每表三次曝光不符')
        result.append(dict(**bound, counts=dict(counts), BCE_weight_masses=dict(mass), UID_exposure_counts=dict(seen),
                           table_shared_by_R_RS=True, not_doubled_to_18_run_consumption=True, new_training=False))
    require(sum(x['counts']['window_exposures'] for x in result)==27000, '九R表27000读取边界不同')
    return result


def summarize(cfg, completed):
    units=[read(completed[u['job']['job_id']]) for u in cfg['source_units']]
    windows=[r for u in units for r in read_output_rows(u['selected_windows'])]
    require(sum(u['counts']['rows'] for u in units)==180118 and len(windows)==3000
            and sum(u['selected_candidates']['rows'] for u in units)==42465, '原180118/3000/42465分母不同')
    total=Counter(); selected=Counter()
    for u in units:
        total.update(u['counts']); selected.update(u['selected_counts'])
    require((selected['known_pairs'],selected['unknown_pairs'],selected['positive_pairs'],selected['known_negative_pairs'])==(35240,7225,1115,34125), '原known/unknown/正负不符')
    cells={}
    for fold in FOLDS.values():
        for seq,heldout in FOLDS.items():
            if fold==heldout:continue
            group=[w for w in windows if w['fold']==fold and w['sequence']==seq]
            cc=Counter();bw=Counter();sc={g:Counter() for g in core.LABEL_GROUPS};pc={g:Counter() for g in core.LABEL_GROUPS}
            for w in group:
                cc.update(w['counts']);bw.update({k:w['bce_weights'][k] for k in WEIGHTS})
                for g in core.LABEL_GROUPS:sc[g].update(w['scoring_counts'][g]);pc[g].update(w['probability_counts'][g])
            cells[fold+':'+seq]=dict(windows=len(group),counts=dict(cc),B_classes=dict(Counter(w['B_class'] for w in group)),
                scoring_counts={g:dict(v) for g,v in sc.items()},probability_counts={g:dict(v) for g,v in pc.items()},BCE_weight_masses=dict(bw),
                bins={name:dict(Counter(w[name] for w in group)) for name in ('history_bin','gap_bin','candidate_bin')},
                anchor_drift=dict(Counter('null' if w['anchor_drift'] is None else str(w['anchor_drift']).lower() for w in group)))
    require(all(w['primary_flags']['eligible_trusted_correct_without_known_positive'] is not True for w in windows), '恒等一致性检查发现冲突；先诊断join/标签来源，不选训练因素')
    return dict(schema='state_label_alignment_diagnosis_report_v1', status=STATUS, protocol=cfg['_protocol'],
                units=[dict(job=u['job'],receipt=completed[u['job']['job_id']]) for u in units], primary=core.summarize_selected(windows),
                absolute_counts=dict(total), selected_counts=dict(selected), exposures=exposure_summary(cfg,windows),
                selected_fold_source_cells=cells,
                free_state_sensitivity_by_regime={reg:[dict(job=u['job'],counts=u['counts'],B_classes=u['B_classes'],flags=u['primary_flags'],bins=u['bins']) for u in units if u['job']['regime']==reg] for reg in ('R','RS')},
                primary_interval_count=4, logical_existing_frames=9000, unique_existing_frames=2250, stages=27000,
                ledger_rows_read=180118, public_annotation_rows_read=180118, raw_GT_weights_cache_frames_or_media_opened=False,
                CE_current_model_internal_state_available=False, teacher_state_is_not_current_model_state=True,
                labels_changed=False, window_selection_changed=False, factor_selected=False, test_read=False, GT_coordinates_read=False,
                **{k:0 for k in ZERO_KEYS})


def resource_module(cfg):
    spec=importlib.util.spec_from_file_location('state_label_existing_resources',checked(cfg['resource_source']))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def execute(path, cfg):
    out=safe(cfg['control_root'],output=True)
    require(not out.exists(),'控制目录已有成功/partial，不隐式恢复')
    out.mkdir(parents=True)
    completed=dict(cfg['inherit_completed'])
    state=dict(status='started_not_committed',protocol=cfg['_protocol'],controller_pid=os.getpid(),active=[],completed=completed,
               inherited_completed=dict(completed),worker_pids=[],resource_samples=[],started_utc=datetime.now(timezone.utc).isoformat(),
               test_read=False,GT_coordinates_read=False,**{k:0 for k in ZERO_KEYS})
    def save():
        p=out/'state.pending';p.write_text(canonical(state)+'\n',encoding='utf-8');os.replace(p,out/'driver_state.json')
    start=time.perf_counter(); resources=resource_module(cfg); active={}; metadata=selected_metadata(cfg)
    pending=[cfg['source_units'][0]] if cfg['phase']=='admission' else [u for u in cfg['source_units'] if u['job']['job_id'] not in completed]
    try:
        for jid, v in completed.items():
            old=read(v); unit=next(u for u in cfg['source_units'] if u['job']['job_id']==jid)
            require(old['status']=='complete' and old['source']==unit, '只继承已绑定完整成功任务')
            for k in ('rows','selected_windows','selected_candidates'):checked(old[k])
        save()
        with ProcessPoolExecutor(max_workers=1 if cfg['phase']=='admission' else 2,mp_context=mp.get_context('spawn')) as pool:
            while pending or active:
                require(not(out/'STOP').exists(),'用户停止，保留partial')
                snap=resources.resource_snapshot();state['resource_samples'].append(snap)
                while pending and len(active)<(1 if cfg['phase']=='admission' else 2) and snap['available_RAM_bytes']>=cfg['reserve_RAM_bytes']+(len(active)+1)*cfg['inflight_reserve_bytes'] and snap['commit_available_bytes']>=cfg['reserve_commit_bytes']+(len(active)+1)*cfg['inflight_reserve_bytes']:
                    unit=pending.pop(0);selected={k:v for k,v in metadata.items() if k[0]==unit['job']['job_id']}
                    active[pool.submit(unit_run,cfg,unit,selected)]=unit['job']['job_id']
                state['active']=list(active.values());save()
                if not active:
                    time.sleep(1);continue
                done,_=wait(active,timeout=1,return_when=FIRST_COMPLETED)
                for future in done:
                    jid=active.pop(future);v=future.result();state['completed'][jid]=v
                    pid=read(v)['worker_pid']
                    if pid not in state['worker_pids']:state['worker_pids'].append(pid)
            processes=list(pool._processes.values())
        state['worker_exits']=[dict(worker_pid=p.pid,joined=True,process_exited=not p.is_alive(),exit_code=p.exitcode) for p in processes]
        require(all(x['process_exited'] and x['exit_code']==0 for x in state['worker_exits']), 'worker未真实正常退出')
        state.update(all_workers_joined=True,active=[])
        if cfg['phase']=='admission':
            result=dict(status='complete_one_source_existing_rows_streaming_admission',protocol=cfg['_protocol'],
                        unit=state['completed'][cfg['source_units'][0]['job']['job_id']],all_workers_joined=True,
                        worker_exits=state['worker_exits'],resources=state['resource_samples'],wall_seconds=time.perf_counter()-start,
                        test_read=False,GT_coordinates_read=False,**{k:0 for k in ZERO_KEYS})
            write(out/'receipt.json',result);state['status']=result['status']
        else:
            require(len(state['completed'])==12,'12任务未齐')
            report=summarize(cfg,state['completed']);write(out/'report.json',report);state.update(status=STATUS,report=ref(out/'report.json'))
        state['wall_seconds']=time.perf_counter()-start;save();return state
    except BaseException:
        state.update(status='failed_preserved_no_implicit_replay',traceback=traceback.format_exc(),active=list(active.values()));save();raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True);parser.add_argument('--execute',action='store_true')
    args=parser.parse_args();cfg=validate(args.config)
    result=execute(args.config,cfg) if args.execute else dict(status='readonly_frozen_state_label_alignment_preflight')
    print(canonical(dict(status=result['status'])))
