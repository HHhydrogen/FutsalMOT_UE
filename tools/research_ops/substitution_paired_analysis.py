"""比赛等权的配对差值/描述性区间；不执行等效或非劣效判定。"""
from collections import defaultdict
from statistics import mean,stdev
import math

FOLDS=('game4','game6','game9');SEEDS=(20261024,20261025,20261026)
def require(ok,msg):
    if not ok:raise ValueError(msg)
def paired_match_differences(rows,matches,method,target='B',reference='C',metric='AssA'):
    """先在同比赛内平均9个匹配训练单元，禁止将seed/fold冒充比赛。"""
    require(len(matches)==len(set(matches))>=2,'至少两个唯一比赛')
    indexed={}
    for row in rows:
        if row['method']!=method or row['group'] not in (target,reference):continue
        key=(row['match'],row['group'],row['fold'],row['seed'])
        require(key not in indexed,'比较单元重复');indexed[key]=row
    expected={(m,g,f,s) for m in matches for g in (target,reference) for f in FOLDS for s in SEEDS}
    require(set(indexed)==expected,'实际矩阵缺失或含未登记比赛，不筛seed/fold')
    return {m:mean(float(indexed[m,target,f,s][metric])-float(indexed[m,reference,f,s][metric]) for f in FOLDS for s in SEEDS) for m in matches}
def effect_intervals(match_deltas,*,confidence=.95,resamples=10000,bootstrap_seed=20261027):
    import numpy as np
    from scipy.stats import t
    values=list(match_deltas.values());n=len(values)
    require(n>=2 and all(math.isfinite(x) for x in values),'比赛差值缺失/非有限')
    require(confidence==.95 and resamples==10000 and bootstrap_seed==20261027,'已登记区间规则不可结果后修改')
    avg=mean(values);sd=stdev(values);half=float(t.ppf(.975,n-1))*sd/math.sqrt(n)
    draws=np.random.default_rng(bootstrap_seed).integers(0,n,size=(resamples,n));boot=np.asarray(values)[draws].mean(axis=1)
    limits=np.quantile(boot,[.025,.975]).tolist()
    return dict(n_independent_matches=n,match_deltas_pp=match_deltas,mean_delta_pp=avg,match_sample_SD_pp=sd,
        Student_t_95CI=[avg-half,avg+half],percentile_match_bootstrap_95CI=limits,
        leave_one_match_out_mean={key:mean(v for k,v in match_deltas.items() if k!=key) for key in match_deltas},
        formal_equivalence_or_noninferiority_test=False,margin=None,
        interpretation='conditional on fixed training panel; small convenience sample and independence/normality assumptions; no equivalence from interval including zero')
def precision_scenarios(n):
    from scipy.stats import t
    require(n>=2,'至少两场才能形成t区间')
    factor=float(t.ppf(.975,n-1))/math.sqrt(n)
    return [dict(matches=n,assumed_match_difference_SD_pp=sd,Student_t_95CI_halfwidth_pp=factor*sd,
        assumption_only_not_observed_C_variance=True) for sd in (.25,.5,1.,2.,5.)]
