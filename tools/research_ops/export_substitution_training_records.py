"""从C十八臂已验实际记录导出论文CSV；不补造字段、不训练/预测或改原文件。"""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/real_substitution_a01'
def require(ok,msg):
    if not ok:raise ValueError(msg)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p))
def checked(v):
    p=Path(v['path']);require(p.is_file() and sha(p)==v['sha256'],'原记录来源改变');return p

def export(protocol,budget,output):
    cfg=read(protocol);audit=read(budget)
    require(cfg['schema']=='substitution_C4000R_training_v1' and cfg['test116187_sealed'] is True
        and audit['status']=='complete18_C_actual_budget_full_records_and_exit_verified' and audit['protocol']==ref(protocol)
        and audit['actual_totals']['updates']==18000 and audit['actual_totals']['R_windows']==72000
        and audit['complete_checkpoints_read_back']==378,'C实际完整预算未闭合')
    bundle=Path(cfg['bundle']);require(bundle.parent==R/'code','必须实际D训练bundle')
    for entry in read(checked(cfg['bundle_manifest']))['files']:require(sha(bundle/entry['path'])==entry['sha256'],'原冻结记录源码变化')
    spec=importlib.util.spec_from_file_location('C_archive_storage',bundle/'python/src/grf_ue_bridge/storage_policy.py')
    st=importlib.util.module_from_spec(spec);spec.loader.exec_module(st)
    output=st.physical_child(output,EXP);require(not output.exists(),'归档已存在/partial，不覆盖');output.mkdir(parents=True)
    fields=['fold','seed','method','actual_update','loss','real_loss','base_real_loss','extra_real_loss','synthetic_loss','learning_rates','grad_l2',
        'step_wall_seconds','R_windows','base_R_windows','extra_R_windows','S_windows','R_pairs','base_R_pairs','extra_R_pairs',
        'R_known_pairs','base_R_known_pairs','extra_R_known_pairs','S_pairs','S_known_pairs','real','synthetic','chain_sha256']
    sources=[];n=0
    with (output/'steps.csv').open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for item in audit['runs']:
            directory=Path(item['last']['path']).parents[1];done=read(directory/'training_complete.json');receipt=read(directory/'run_receipt.json')
            require(sha(directory/'run_receipt.json')==item['run_receipt_sha256'] and receipt['full_training_record']==sha(directory/'training_complete.json')
                and done['schema']=='full_training_process_complete_v2_real_groups','C成功收据来源不同')
            logs=directory/'steps.jsonl';require(sha(logs)==done['steps_sha256'],'原逐步日志变化')
            rows=[json.loads(x) for x in logs.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
            require(len(rows)==1000 and [x['actual_update'] for x in rows]==list(range(1,1001)),'逐步记录不能筛选或缺失')
            for row in rows:
                out={k:row[k] for k in fields if k not in ('fold','seed','method')};out.update({k:item[k] for k in ('fold','seed','method')})
                for key in ('learning_rates','real','synthetic'):out[key]=json.dumps(out[key],separators=(',',':'),ensure_ascii=False)
                writer.writerow(out);n+=1
            sources.append(dict(fold=item['fold'],seed=item['seed'],method=item['method'],steps=ref(logs),
                run_manifest=ref(directory/'run_manifest.json'),training_complete=ref(directory/'training_complete.json'),
                last_checkpoint_manifest=ref(directory/'last_checkpoint.json'),all378_checkpoints_remain_original=True,raw_files_modified=False))
    require(n==18000 and len(sources)==18,'全18臂18000行未齐')
    with (output/'runs.csv').open('x',encoding='utf-8-sig',newline='') as f:
        count_fields=list(audit['runs'][0]['counts']);writer=csv.DictWriter(f,fieldnames=['fold','seed','method','updates',*count_fields]);writer.writeheader()
        for item in audit['runs']:writer.writerow(dict({k:item[k] for k in ('fold','seed','method')},updates=item['actual_updates'],**item['counts']))
    result=dict(schema='C18_training_paper_records_archive_v1',status='complete18_C_raw_training_records_export',
        protocol=ref(protocol),actual_budget=ref(budget),steps=ref(output/'steps.csv'),runs=ref(output/'runs.csv'),sources=sources,
        raw_steps=18000,training_runs=18,raw_data_not_smoothed=True,missing_fields_fabricated=False,models_modified=False,
        new_optimizer_updates=0,new_validation_metrics_read=False,test_read=False)
    with (output/'complete.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    return {k:result[k] for k in ('status','raw_steps','training_runs','new_optimizer_updates')}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('protocol','budget','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--execute',action='store_true');a=p.parse_args()
    print(json.dumps(export(a.protocol,a.budget,a.output) if a.execute else dict(status='readonly_C_archive_plan',new_updates=0),ensure_ascii=False))
