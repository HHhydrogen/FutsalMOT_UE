"""冻结七比赛方案的区间精度敏感度；只读旧开发结果，零训练。"""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import stdev
import sys
ROOT=Path(__file__).resolve().parents[2];R=Path('D:/projects/FutsalMOT_Research')
sys.path.insert(0,str(ROOT/'tools/research_ops'))
from substitution_paired_analysis import precision_scenarios
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def ref(p):return dict(path=str(p),sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest())
def execute(config):
    cfg=read(config);assert cfg['schema']=='substitution_precision_config_v1' and Path(cfg['bundle'])==ROOT and ROOT.parent==R/'code'
    for f in cfg['code_files']:assert ref(ROOT/f['path'])['sha256']==f['sha256']
    for k in ('analysis_plan','old_development_report'):assert ref(cfg[k]['path'])==cfg[k]
    plan=read(cfg['analysis_plan']['path']);assert plan['formal_equivalence_test'] is False and plan['formal_noninferiority_test'] is False
    registry=read(plan['matches']['path']);assert ref(plan['matches']['path'])==plan['matches'] and len(registry['sources'])==7
    old=read(cfg['old_development_report']['path']);assert old['status']=='complete_all253_tracking_comparisons'
    prior={}
    for domain in ('external','old_heldout'):
        for method in ('motion','gated'):
            c=old['comparisons'][f'{domain}/balanced/{method}-minus-R']['match_delta_pp'];values=[v['AssA'] for v in c.values()]
            prior[f'{domain}/{method}/B-A']=dict(match_AssA_deltas={s:v['AssA'] for s,v in c.items()},matches=len(values),sample_SD_pp=stdev(values),not_B_minus_C_variance=True)
    import scipy,numpy
    output=Path(cfg['output']);assert output==R/'pose/real_substitution_a01/precision_a01' and not output.exists()
    for p in output.parents:
        if p.exists():assert not p.is_symlink() and not(getattr(p.lstat(),'st_file_attributes',0)&0x400)
    output.mkdir()
    value=dict(schema='seven_match_precision_sensitivity_v1',status='complete_old_development_and_assumption_only_precision_no_C_results',config=ref(config),
        analysis_plan=cfg['analysis_plan'],prior_observed_development=prior,precision_scenarios=precision_scenarios(7),
        scipy_version=scipy.__version__,numpy_version=numpy.__version__,python_version=sys.version,margin=None,
        equivalence_or_noninferiority_test=False,optimizer_updates=0,test_read=False,
        limitations=['old B-A variance is not future B-C variance','two prior external matches give unstable variance estimate',
                    'selected short-match panel and fixed training panel; interval assumptions must be reported','no loss-margin or pass/fail criterion selected'])
    with (output/'report.json').open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
    print(json.dumps(dict(status=value['status'],precision_scenarios=value['precision_scenarios']),ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if a.execute:execute(a.config)
    else:print('readonly_precision_plan_no_training')
