"""v8完整三比赛三seed四单元分析；保留负结果及两项预训练参考。"""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/research_ops'))
from v8_train import read,sha,checked,require,atomic,GAMES,ARMS
SEEDS=(20261024,20261025,20261026)
METRICS=('AssA','HOTA','IDF1','DetA','MOTA')
def mean(values):return sum(values)/len(values)
def differences(left,right):return {key:left[key]-right[key] for key in METRICS}
def average(items):return {key:mean([item[key] for item in items]) for key in METRICS}
def recovery_counts(reports):
    values=[next(iter(report['sequences'].values()))['overall'] for report in reports]
    total=sum(v['total_events'] for v in values);success=sum(v.get('same_prediction_ID_recovered',0) for v in values)
    return dict(registered_events=total,recovered_events=success,recovery_rate=success/total if total else None,missing_endpoint=sum(v.get('events_with_missing_endpoint',0) for v in values),ambiguous_endpoint=sum(v.get('events_with_ambiguous_endpoint',0) for v in values))
def analyze(config,control,output):
    cfg=read(config);control=Path(control);output=Path(output);state=read(control/'driver_state.json')
    require(Path(__file__).resolve()==Path(cfg['bundle'])/'tools/research_ops/v8_analyze.py','必须bundle执行')
    require(state['protocol_sha256']==sha(config) and len(state['completed_train'])==36 and len(state['completed_tracking'])==42,'只有完整36训练/42追踪可作终态分析')
    train={};values={};recovery={};audits={}
    def metric(directory):
        report=read(directory/'metric/report.json');require(report['status']=='complete' and report['protocol_sha256']==sha(config) and report['DO_PREPROC'] is False and report['test_read'] is False,'评价来源不符')
        return report['summary'][report['sequence']]['metrics_percent']
    baselines={game:{mode:metric(control/'baselines'/game/mode) for mode in ('PT_bbox','PT_static_pose')} for game in GAMES}
    for game in GAMES:
        for seed in SEEDS:
            identity=None
            for arm in ARMS:
                key=(game,seed,arm);directory=control/'runs'/game/str(seed)/arm;receipt=read(directory/'training/run_receipt.json');binding=receipt['binding']
                require(receipt['status']=='complete' and receipt['completed_updates']==1000 and receipt['real_window_exposures']==3000 and receipt['synthetic_window_exposures']==(1000 if arm.endswith('_RS') else 0),'预算未完成')
                actual=(binding['initialization_sha256'],binding['R_window_UID_chain_sha256'])
                if identity is None:identity=actual
                require(identity==actual,'组间真实曝光或初始化不一致')
                train[key]=receipt;values[key]=metric(directory);recovery[key]=read(directory/'recovery.json');audits[key]=read(directory/'tracking/receipt.json')['audit']
    comparisons={}
    for group,left,right in [('motion_RS_minus_motion_R','motion_RS','motion_R'),('pose_RS_minus_pose_R','pose_RS','pose_R'),('pose_RS_minus_motion_RS','pose_RS','motion_RS'),('pose_R_minus_motion_R','pose_R','motion_R')]:
        by_seed={str(seed):average([differences(values[(g,seed,left)],values[(g,seed,right)]) for g in GAMES]) for seed in SEEDS}
        by_game={game:average([differences(values[(game,s,left)],values[(game,s,right)]) for s in SEEDS]) for game in GAMES}
        comparisons[group]=dict(macro_mean_pp=average(list(by_seed.values())),per_seed_macro_pp=by_seed,per_heldout_game_mean_pp=by_game)
    baseline_comparisons={}
    for arm in ARMS:
        baseline_comparisons[arm]={mode:dict(macro_mean_pp=average([differences(values[(g,s,arm)],baselines[g][mode]) for g in GAMES for s in SEEDS]),per_seed_macro_pp={str(s):average([differences(values[(g,s,arm)],baselines[g][mode]) for g in GAMES]) for s in SEEDS}) for mode in ('PT_bbox','PT_static_pose')}
    primary=comparisons['pose_RS_minus_pose_R'];delta=primary['macro_mean_pp'];positive_seed=sum(v['AssA']>0 for v in primary['per_seed_macro_pp'].values());nonnegative_game=sum(v['AssA']>=0 for v in primary['per_heldout_game_mean_pp'].values())
    decision=dict(AssA_mean_at_least_0_5pp=delta['AssA']>=.5,at_least_two_seeds_positive=positive_seed>=2,at_least_two_games_nonnegative=nonnegative_game>=2,HOTA_mean_nonnegative=delta['HOTA']>=0,IDF1_mean_drop_at_most_0_5pp=delta['IDF1']>=-.5)
    did=differences(comparisons['pose_RS_minus_pose_R']['macro_mean_pp'],comparisons['motion_RS_minus_motion_R']['macro_mean_pp'])
    recovery_summary={arm:{str(seed):recovery_counts([recovery[(g,seed,arm)] for g in GAMES]) for seed in SEEDS} for arm in ARMS}
    recovery_baselines={mode:recovery_counts([read(control/'baselines'/g/mode/'recovery.json') for g in GAMES]) for mode in ('PT_bbox','PT_static_pose')}
    rows=[]
    for game in GAMES:
        for seed in SEEDS:
            for arm in ARMS:
                key=(game,seed,arm);receipt=train[key];rows.append(dict(heldout_game=game,seed=seed,arm=arm,metrics_percent=values[key],recovery=recovery[key],tracker_audit=audits[key],real_windows=3000,synthetic_windows=receipt['synthetic_window_exposures'],wall_seconds=receipt['wall_seconds_including_validation_and_checkpoint'],prefetch=receipt['prefetch']))
    require(not output.exists(),'分析输出必须全新');output.mkdir(parents=True)
    result=dict(schema='v8_complete_cross_game_analysis',status='complete',protocol_sha256=sha(config),all_rows=rows,pretrained_fixed_baselines=baselines,paired_comparisons=comparisons,mixed_minus_pretrained=baseline_comparisons,Pose_difference_in_differences_pp=did,predeclared_primary_checks=decision,primary_progress_passed=all(decision.values()),formal_updates=sum(x['completed_updates'] for x in train.values()),real_window_exposures=sum(x['real_window_exposures'] for x in train.values()),synthetic_window_exposures=sum(x['synthetic_window_exposures'] for x in train.values()),budget_unit='supervised association window, not image/independent event',full_training_wall_seconds=sum(x['wall_seconds_including_validation_and_checkpoint'] for x in train.values()),test116187_read=False,limitations=['three short official-train matches; cross-validation is development, not final test','teacher-forced matched training histories; free-running heldout histories','one synthetic motion seed and four correlated cameras','fixed pretrained predictions, not newly trained Pose heads','additional S is not matched FLOPs or known-pair count','detection-gap proxy is not physical occlusion GT','no best/seed/lambda filtering; all arms and negative outcomes retained'])
    result['gap_proxy_recovery']=dict(per_arm_per_seed=recovery_summary,pretrained=recovery_baselines,denominator='same fixed events for every arm; repeated seeds do not create independent events')
    atomic(output/'report.json',result)
    lines=['# v8完整对照结果','',f"主登记门槛：{'达到' if result['primary_progress_passed'] else '未达到'}。下表均为跨比赛宏平均差，单位为百分点。",'','| 比较 | AssA | HOTA | IDF1 |','| --- | ---: | ---: | ---: |']
    for name,value in comparisons.items():v=value['macro_mean_pp'];lines.append(f"| {name} | {v['AssA']:+.4f} | {v['HOTA']:+.4f} | {v['IDF1']:+.4f} |")
    for arm,refs in baseline_comparisons.items():
        for mode,value in refs.items():v=value['macro_mean_pp'];lines.append(f"| {arm} − {mode} | {v['AssA']:+.4f} | {v['HOTA']:+.4f} | {v['IDF1']:+.4f} |")
    lines+=['',f"完成{result['formal_updates']}次更新、{result['real_window_exposures']}R窗口与{result['synthetic_window_exposures']}S窗口。",'','三场比赛各750帧的留一比赛开发验证，最终测试116/187封存；窗口不是图像，断档代理不是物理遮挡真值。完整逐折/seed/臂、恢复计数、介入次数与耗时保留于report.json。']
    (output/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','control','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();result=analyze(a.config,a.control,a.output);print(json.dumps(dict(status=result['status'],primary_progress_passed=result['primary_progress_passed'])))
