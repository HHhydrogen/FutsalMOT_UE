"""已有trace的残差幅度可达性诊断；不是新模型、GT Pose或性能上界。"""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys


def capacity(base, gates, positive, negative, bound=.5):
    margin=max(base[k] for k in positive)-max(base[k] for k in negative)
    optimistic=max(base[k]+bound*gates[k] for k in positive)-max(base[k]-bound*gates[k] for k in negative)
    return dict(base_margin=margin,optimistic_margin=optimistic,
                base_wrong_or_tied=margin<=0,not_correctable_at_fixed_gate=margin<=0 and optimistic<=0)


def execute(config,control,output):
    cfg=json.loads(config.read_text(encoding='utf-8'));bundle=Path(cfg['bundle'])
    if bundle.parent!=Path('D:/projects/FutsalMOT_Research/code'):raise ValueError('必须已有冻结诊断bundle')
    sys.path.insert(0,str(bundle/'tools/research_ops'))
    import pose_mechanism_analyze as analyzer
    core=analyzer.core;_,rt,old,runtime,train,numeric,base,numbers=core.validate(config)
    core.require(numbers['parameters']['delta_logit_bound']==.5,'原残差幅度契约变化')
    state=core.read(control/'driver_state.json');done={r['job']['job_id'] for r in state['completed']};inputs=core.read(core.checked(cfg['inputs']))
    jobs=[j for j in cfg['jobs'] if j['kind']=='common_state'];core.require(len(jobs)==54 and all(j['job_id'] in done for j in jobs),'共同54项未完成')
    details=[];groups={}
    for job in jobs:
        seq=job['original']['sequence'];labels=core.read(core.checked(inputs['sources'][seq]['labels']))['labels']
        receipt=core.read(control/'runs'/job['job_id']/'tracking/receipt.json');trace=core.checked(receipt['trace']);count=Counter()
        with gzip.open(trace,'rt',encoding='utf-8') as stream:
            for line in stream:
                e=json.loads(line);locations={tuple(v):k for k,v in enumerate(e['scored_locations'])}
                for i,history in enumerate(e['history_UIDs']):
                    if not e['active_rows'][i] or not e['enough_history'][i]:continue
                    identity,_=analyzer.query_identity(history,labels)
                    if identity is None:continue
                    known={locations[(i,j)]:analyzer.pair_label(identity,labels[u]) for j,u in enumerate(e['candidate_UIDs']) if (i,j) in locations and e['enabled'][i][j]}
                    pos=[k for k,v in known.items() if v==1];neg=[k for k,v in known.items() if v==0]
                    if not pos or not neg:continue
                    off=e['logits']['pose_off'];pose=e['logits']['pose'];gate=e['quality_gates']['pose']
                    for k in known:
                        core.require(0<=gate[k]<=1 and abs(pose[k]-off[k])<=.5*gate[k]+1e-5,'实际Pose输出不满足原固定门控/残差界限')
                    result=capacity(off,gate,pos,neg);count['active_both_known_classes']+=1
                    if result['base_wrong_or_tied']:
                        count['base_wrong_or_tied']+=1
                        count['fixed_gate_bound_cannot_correct' if result['not_correctable_at_fixed_gate'] else 'fixed_gate_bound_might_correct']+=1
        details.append(dict(job=job,counts=dict(count),trace=receipt['trace']))
        key=job['original']['pool']+'/'+('external' if seq in rt.EXTERNAL else 'old_heldout')
        groups.setdefault(key,Counter()).update(count)
    output=runtime.storage().physical_child(output,core.V);core.require(not output.exists(),'独立幅度诊断partial不覆盖');output.mkdir(parents=True)
    result=dict(schema='pose_fixed_gate_residual_capacity_v1',status='complete54_fixed_gate_bound_diagnosis_no_inference',protocol=core.ref(config),source_code=core.ref(__file__),
        groups={k:dict(v) for k,v in groups.items()},details=details,delta_logit_bound=.5,optimizer_updates=0,GT_only_posthoc=True,test_read=False,
        limitations=['fixed already-trained motion branch and current quality gates; not a perfect-Pose/system performance bound',
                     'arbitrary independent per-edge residual extremes are only optimistic feasibility, not an attainable trained model',
                     'rows repeat states/models/stages; only trusted histories and known positive/negative subsets'])
    with (output/'report.json').open('x',encoding='utf-8') as f:f.write(core.canonical(result)+'\n')
    return dict(status=result['status'],groups=result['groups'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','control','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(execute(a.config,a.control,a.output),ensure_ascii=False))
