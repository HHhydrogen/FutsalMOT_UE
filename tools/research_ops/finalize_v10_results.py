"""v10结果闭合核验：253项来源/MOT/指标/分母及全部配对，不重训或重评。"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import stat
from statistics import mean

V=Path('D:/projects/FutsalMOT_Research/pose/multiseed_v10_a01')
EXTERNAL={'v_2QhNRucNC7E_c017':450,'v_G-vNjfx1GGc_c004':675}
OLD={'game4':'SNMOT-060','game6':'SNMOT-097','game9':'SNMOT-151'}
METRICS=('AssA','HOTA','IDF1','DetA','MOTA')


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def ref(path):return dict(path=str(path),sha256=sha(path))
def checked(value):
    p=Path(value['path']);require(p.is_file() and sha(p)==value['sha256'],'来源变化：'+str(p));return p
def close(a,b):return math.isclose(a,b,rel_tol=0,abs_tol=1e-10)


def verify(config,control,analysis,process_exit):
    cfg=read(config);state=read(Path(control)/'driver_state.json');result=read(analysis);exit_receipt=read(process_exit)
    require(exit_receipt['all_related_absent'] is True and exit_receipt['query_failed'] is False
        and exit_receipt['related_processes']==[],'实际进程退出未确认')
    require(cfg['schema']=='v10_independent_tracking_protocol_v1' and cfg['test116187_sealed'] is True
        and state['status']=='complete253_tracking_and_analysis' and state['active'] is None
        and result['status']=='complete_all253_tracking_comparisons' and result['test_read'] is False
        and result['protocol_sha256']==state['protocol_sha256']==sha(config),'独立终态/协议链未闭合')
    for entry in read(checked(cfg['bundle_manifest']))['files']:
        require(sha(Path(cfg['bundle'])/entry['path'])==entry['sha256'],'追踪数值源码变化')
    train=read(checked(cfg['training_protocol']));budget=read(checked(cfg['actual_budget']))
    require(budget['status']=='complete54_actual_budget_and_full_records_verified' and len(budget['runs'])==54
        and budget['totals']['updates']==54000 and budget['totals']['R_windows']==162000
        and budget['totals']['S_windows']==54000 and budget['complete_checkpoints_verified']==1134,
        '已经完成的独立训练预算不完整')
    registry=read(checked(cfg['registry']));require(registry['sources']==cfg['sources'] and registry['event_count']==1353
        and registry['old_event_count']==956 and registry['external_event_count']==397,'事前断档全事件分母不同')
    events=Counter(e['sequence'] for e in registry['events']);matrix=cfg['tracking_matrix'];jobs={j['job_id']:j for j in matrix}
    completed={x['job']['job_id']:x for x in state['completed_tracking']}
    indexed={x['job']['job_id']:x for x in result['all_results']}
    require(len(matrix)==len(jobs)==len(state['completed_tracking'])==len(completed)==len(result['all_results'])==len(indexed)==253
        and set(jobs)==set(completed)==set(indexed),'253项矩阵/结果存在缺失或重复')
    require(Counter(j['kind'] for j in matrix)=={'PT':10,'new_RS':162,'pure_R':81},'对照类型数量不同')
    gt_hashes={};source_metric={};recovery_counts={}
    for identity,job in jobs.items():
        folder=Path(control)/'runs'/identity;path=folder/'metric/report.json';report=read(path)
        require(sha(path)==completed[identity]['report_sha256']==indexed[identity]['report']['sha256']
            and report['job']==job==completed[identity]['job']==indexed[identity]['job']
            and report['status']=='complete' and report['protocol_sha256']==sha(config),'评价来源/身份变化')
        tracking=read(folder/'tracking/receipt.json');sequence=job['sequence'];source=cfg['sources'][sequence]
        require(sha(folder/'tracking/receipt.json')==report['tracking_receipt_sha256']
            and tracking['job']==job and tracking['GT_read'] is False and tracking['GPU_used'] is False
            and tracking['cache']==source['cache'] and tracking['schema']=='v10_independent_free_tracking_v1',
            '自由追踪身份/无GT输入声明不完整')
        mot=folder/'tracking/data'/(sequence+'.txt');require(sha(mot)==tracking['mot_sha256'],'MOT改变')
        count=sum(bool(x) for x in mot.read_text(encoding='utf-8').splitlines())
        require(count==tracking['tracked_rows'] and tracking['frames']==report['frames']==source['frames']
            and report['predictions_GT_filtered'] is False and report['DO_PREPROC'] is False
            and report['GT_used_only_for_metric'] is True and report['test_read'] is False,'预测行/用途改变')
        gt=folder/'metric/derived_player_gt'/sequence/'gt/gt.txt';gt_hash=sha(gt)
        if sequence not in gt_hashes:gt_hashes[sequence]=gt_hash
        require(gt_hashes[sequence]==gt_hash,'各模型实际评价GT不相同')
        for scope,classes in report['raw_results'].items():
            c=classes['pedestrian']['Count'];require(c['Dets']==count and c['GT_Dets']==report['GT_rows'],'评价丢弃了行')
            if scope==sequence:require(c['Frames']==source['frames'],'实际帧数不符')
            else:require(scope=='COMBINED_SEQ','未知评价域')
        if sequence in EXTERNAL:
            require(report['GT_rows']==(6622 if sequence=='v_2QhNRucNC7E_c017' else 8137)
                and report['raw_results'][sequence]['pedestrian']['Count']['GT_IDs']==(21 if sequence=='v_2QhNRucNC7E_c017' else 20)
                and report['GT_identity0_preserved'] is True,'新比赛GT roster/ID0不符')
        actual=report['summary'][sequence]['metrics_percent'];require(actual==indexed[identity]['metrics'],'分析指标未引用原评价')
        require(set(report['summary'])=={sequence,'COMBINED_SEQ'},'评价范围改变');source_metric[identity]=actual
        recovery=report['recovery']['overall'];require(recovery==indexed[identity]['recovery'] and recovery['total_events']==events[sequence]
            and report['registry_sha256']==cfg['registry']['sha256'],'恢复率未使用事前全部分母')
        successes=recovery.get('same_prediction_ID_recovered',0)
        require(sum(recovery.get(k,0) for k in ('same_prediction_ID_recovered','different_prediction_ID','ambiguous_endpoint','missing_prediction_endpoint'))==events[sequence]
            and (recovery['recovery_rate'] is None if not events[sequence] else close(recovery['recovery_rate'],successes/events[sequence])),
            '恢复事件原因或分母不完整')
        recovery_counts[identity]=dict(successes=successes,events=events[sequence])
    # 全部配对从原评价逐一重算；比较身份和18/9格覆盖另核对，避免只信宏均值。
    for key,comparison in result['comparisons'].items():
        domain,pool,contrast=key.split('/');pairs=comparison['pairs'];seen=set()
        require(len(pairs)==(18 if domain=='external' else 9),'对照单元数不完整')
        for pair in pairs:
            a,b=jobs[pair['target']],jobs[pair['reference']];fold,seed,seq=(pair[k] for k in ('fold','seed','sequence'))
            require(a['kind']=='new_RS' and all(a[k]==pair[k] for k in ('fold','seed','sequence')) and b['sequence']==seq,'配对身份不一致')
            require(seq in EXTERNAL if domain=='external' else seq==OLD[fold],'比赛分层不符')
            if pool=='hard-minus-balanced':
                require(a['pool']=='hard_enriched' and b['pool']=='balanced' and a['method']==b['method']==contrast and b['kind']=='new_RS','池间配对不符')
            else:
                method,reference=contrast.split('-minus-');require(a['pool']==pool and a['method']==method,'方法名称与目标模型不同')
                if reference=='R':require(b['kind']=='pure_R' and b['method']==method,'纯R对照身份不符')
                elif reference.startswith('PT_'):require(b['kind']=='PT' and b['mode']==reference,'预训练参考不符')
                else:require(b['kind']=='new_RS' and b['pool']==pool and b['method']==reference,'同池motion对照不符')
            if b['kind']!='PT':require(b['fold']==fold and b['seed']==seed,'对照模型fold/seed不同')
            cell=(fold,seed,seq);require(cell not in seen,'重复配对格');seen.add(cell)
            for metric in METRICS:require(close(pair['delta_pp'][metric],source_metric[a['job_id']][metric]-source_metric[b['job_id']][metric]),'配对差值错误')
        for metric in METRICS:require(close(comparison['mean_delta_pp'][metric],mean(p['delta_pp'][metric] for p in pairs)),'宏均值错误')
        for seed in ('20261024','20261025','20261026'):
            require(close(comparison['seed_AssA_delta_pp'][seed],mean(p['delta_pp']['AssA'] for p in pairs if str(p['seed'])==seed)),'seed均值错误')
        for seq,metrics in comparison['match_delta_pp'].items():
            for metric in METRICS:require(close(metrics[metric],mean(p['delta_pp'][metric] for p in pairs if p['sequence']==seq)),'比赛均值错误')
        require(comparison['negative_AssA_cells']==sum(p['delta_pp']['AssA']<0 for p in pairs),'负结果数量不符')
    for pool,gate in result['primary_gates'].items():
        item=result['comparisons']['external/'+pool+'/gated-minus-motion'];d=item['mean_delta_pp']
        criteria=dict(AssA_mean_at_least_half_pp=d['AssA']>=.5,HOTA_nonnegative=d['HOTA']>=0,
            IDF1_drop_at_most_half_pp=d['IDF1']>=-.5,at_least_two_seeds_positive=sum(x>0 for x in item['seed_AssA_delta_pp'].values())>=2,
            both_external_matches_nonnegative=all(x['AssA']>=0 for x in item['match_delta_pp'].values()))
        require(gate['conditions']==criteria and gate['passed']==all(criteria.values()),'事前主门槛判定错误')
    archive=read(V/'paper_training_archive_a01/complete.json')
    require(archive['status']=='complete54_raw_training_records_export' and archive['step_rows']==54000
        and len(archive['source_runs'])==54 and len(archive['figures'])==12,'论文训练归档不完整')
    return dict(schema='v10_final_closed_result_verification_v1',status='complete_all_data54_train253_tracking_budget_records_and_analysis',
        verified_utc=datetime.now(timezone.utc).isoformat(),tracking_config=ref(config),tracking_state=ref(Path(control)/'driver_state.json'),
        analysis=ref(analysis),actual_budget=cfg['actual_budget'],training_protocol=cfg['training_protocol'],process_exit=ref(process_exit),
        paper_training_archive=ref(V/'paper_training_archive_a01/complete.json'),registry=cfg['registry'],
        verified_tracking_jobs=253,verified_paired_comparisons=len(result['comparisons']),event_counts=dict(events),
        actual_derived_GT_sha256=gt_hashes,primary_gates=result['primary_gates'],optimizer_updates_replayed=0,
        new_optimizer_updates=0,test_read=False,media_read=False,models_reloaded=False,metrics_rerun=False)


def write(path,value):
    path=Path(path).absolute();require(V in path.parents and not path.exists(),'新D研究结果收据，不覆盖')
    for part in (path,*path.parents):
        if part.exists() or part.is_symlink():
            info=part.lstat();require(not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400,'拒绝联接')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','control','analysis','process-exit','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--execute',action='store_true');a=p.parse_args()
    if a.execute:
        value=verify(a.config,a.control,a.analysis,a.process_exit);write(a.output,value)
        print(json.dumps(dict(status=value['status'],tracking_jobs=253,paired_comparisons=value['verified_paired_comparisons'],primary_gates=value['primary_gates']),ensure_ascii=False))
    else:print(json.dumps(dict(status='readonly_v10_final_verification_plan_no_files_changed')))
