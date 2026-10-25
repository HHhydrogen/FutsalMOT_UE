"""v9全量主对照/首seed消融汇总；以同容量运动分支和v8 motion_RS为双参考。"""
import argparse,json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/research_ops'))
from v9_train import read,sha,checked,require,atomic
METRICS=('AssA','HOTA','IDF1');GAMES=('game4','game6','game9');SEEDS=(20261024,20261025,20261026)
def avg(values):return {m:statistics.mean(v[m] for v in values) for m in METRICS}
def diff(a,b):return {m:a[m]-b[m] for m in METRICS}
def evaluate_pair(values,variant='gated',regime='RS',reference='motion_residual',ref_regime='RS',external=None):
    pair={(g,s):diff(values[(g,s,variant,regime)],external[(g,s)] if external else values[(g,s,reference,ref_regime)]) for g in GAMES for s in SEEDS};seed={str(s):avg([pair[(g,s)] for g in GAMES]) for s in SEEDS};game={g:avg([pair[(g,s)] for s in SEEDS]) for g in GAMES};macro=avg(list(pair.values()))
    passed=dict(AssA_at_least_0_5pp=macro['AssA']>=.5,at_least_two_seed_macro_positive=sum(x['AssA']>0 for x in seed.values())>=2,at_least_two_game_mean_nonnegative=sum(x['AssA']>=0 for x in game.values())>=2,HOTA_nonnegative=macro['HOTA']>=0,IDF1_drop_at_most_0_5pp=macro['IDF1']>=-.5)
    return dict(macro_mean_pp=macro,per_seed_macro_pp=seed,per_game_mean_pp=game,all_cells=[dict(game=g,seed=s,delta_pp=v) for (g,s),v in pair.items()],checks=passed,passed=all(passed.values()))
def analyze(config,control,output):
    cfg=read(config);control=Path(control);state=read(control/'driver_state.json');require(state['protocol_sha256']==sha(config) and len(state['completed_train'])==len(state['completed_tracking'])==78,'必须完整78组，不按部分组选结果')
    values={};rows=[]
    for job in cfg['training_matrix']:
        directory=control/'runs'/job['fold']/str(job['seed'])/job['variant']/job['regime'];metric=read(directory/'metric/report.json');receipt=read(directory/'training/run_receipt.json');tracking=read(directory/'tracking/receipt.json');require(metric['status']=='complete' and metric['protocol_sha256']==sha(config) and receipt['completed_updates']==1000,'收据不完整')
        val=metric['summary'][metric['sequence']]['metrics_percent'];key=(job['fold'],job['seed'],job['variant'],job['regime']);values[key]=val;rows.append(dict(**job,metrics_percent=val,train_receipt=receipt,tracker_audit=tracking['audit'],recovery=read(directory/'recovery.json')))
    old=read(checked(cfg['v8_analysis']));baseline={(r['heldout_game'],r['seed'],r['arm']):r['metrics_percent'] for r in old['all_rows']}
    comparisons=dict(gated_RS_minus_capacity_matched_motion_RS=evaluate_pair(values),gated_RS_minus_v8_motion_RS=evaluate_pair(values,external={(g,s):baseline[(g,s,'motion_RS')] for g in GAMES for s in SEEDS}),gated_RS_minus_gated_R=evaluate_pair(values,reference='gated',ref_regime='R'),gated_RS_minus_robust_RS=evaluate_pair(values,reference='robust'))
    references={}
    for variant in ('motion_residual','robust','gated'):
        references[variant]={}
        for regime in ('R','RS'):
            references[variant][regime]={mode:avg([diff(values[(g,s,variant,regime)],old['pretrained_fixed_baselines'][g][mode]) for g in GAMES for s in SEEDS]) for mode in ('PT_bbox','PT_static_pose')}
    ablations={}
    for variant in ('motion_residual','mask','raw','drop','jitter','robust','gated'):
        ablations[variant]={regime:avg([values[(g,20261024,variant,regime)] for g in GAMES]) for regime in ('R','RS')}
    output=Path(output);require(not output.exists(),'全新分析输出');output.mkdir(parents=True)
    result=dict(schema='v9_complete_residual_ablation_analysis',status='complete',protocol_sha256=sha(config),all_rows=rows,main_comparisons=comparisons,main_minus_pretrained_pp=references,exploratory_matched_seed20261024=ablations,main_groups_macro={v:{regime:avg([values[(g,s,v,regime)] for g in GAMES for s in SEEDS]) for regime in ('R','RS')} for v in ('motion_residual','robust','gated')},Pose_increment_both_motion_references_passed=comparisons['gated_RS_minus_capacity_matched_motion_RS']['passed'] and comparisons['gated_RS_minus_v8_motion_RS']['passed'],all_formal_updates=78000,R_window_exposures=234000,S_window_exposures=39000,total_train_wall_seconds=sum(r['train_receipt']['wall_seconds'] for r in rows),v8_references=cfg['v8_analysis'],test116187_read=False,limitations=['same three already observed short official-train matches, development not final blind test','teacher-forced training histories vs free tracking','geometric quality proxy is not visibility or ground-truth noise','main3 variants have3seeds; four exploratory variants use predeclared firstseed only','jointly trained motion branch, not frozen previous motion_RS','extra S not equal FLOPs or total pair budget','one synthetic motion seed, unknown physical visibility retained'])
    atomic(output/'report.json',result);lines=['# v9完整对照','',f"同时超越两运动参考的登记门槛：{'达到' if result['Pose_increment_both_motion_references_passed'] else '未达到'}。",'','| 比较 | AssA差 | HOTA差 | IDF1差 |','| --- | ---: | ---: | ---: |']
    for name,value in comparisons.items():v=value['macro_mean_pp'];lines.append(f"| {name} | {v['AssA']:+.4f} | {v['HOTA']:+.4f} | {v['IDF1']:+.4f} |")
    lines+=['','单位：百分点，三比赛等权宏均。完整每折/seed/负结果、纯真实及两预训练参考、断档proxy和耗时见report.json。最终116/187封存。'];(output/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','control','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();r=analyze(a.config,a.control,a.output);print(__import__('json').dumps(dict(status=r['status'],Pose_increment_both_motion_references_passed=r['Pose_increment_both_motion_references_passed'])))
