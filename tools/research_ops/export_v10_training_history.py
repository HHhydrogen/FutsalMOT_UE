"""从已验54臂原始记录导出论文CSV/曲线；不补造历史、不修改模型或训练日志。"""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path

R=Path('D:/projects/FutsalMOT_Research');V=R/'pose/multiseed_v10_a01'


def require(ok,message):
    if not ok:raise ValueError(message)


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def checked(ref):
    p=Path(ref['path']);require(p.is_file() and sha(p)==ref['sha256'],'来源变化：'+str(p));return p
def ref(path):return dict(path=str(path),sha256=sha(path))


def export(protocol,budget,output,plots=False):
    cfg=read(protocol);audit=read(budget)
    require(cfg['schema']=='v10_recorded_association_training_v1' and cfg['test116187_sealed'] is True
        and audit['status']=='complete54_actual_budget_and_full_records_verified'
        and audit['protocol_sha256']==sha(protocol) and audit['totals']['updates']==54000,'54臂真实预算核对缺失')
    bundle=Path(cfg['bundle']);require(bundle.parent==R/'code','实际D研究bundle缺失')
    for entry in read(checked(cfg['bundle_manifest']))['files']:require(sha(bundle/entry['path'])==entry['sha256'],'冻结记录源码变化')
    module=importlib.util.spec_from_file_location('v10_paper_storage',bundle/'python/src/grf_ue_bridge/storage_policy.py')
    storage=importlib.util.module_from_spec(module);module.loader.exec_module(storage)
    output=storage.physical_child(output,V);require(not output.exists(),'论文导出partial不覆盖/重放');output.mkdir(parents=True)
    fields=['fold','seed','pool','method','actual_update','loss','real_loss','synthetic_loss','learning_rates','grad_l2',
        'step_wall_seconds','R_windows','S_windows','R_pairs','S_pairs','R_known_pairs','S_known_pairs','real','synthetic','chain_sha256']
    manifest=[];curves={};count=0
    with (output/'steps.csv').open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for item in audit['runs']:
            job=item['job'];directory=Path(item['last']['path']).parents[1]
            path=checked(dict(path=str(directory/'steps.jsonl'),sha256=item['steps_sha256']))
            rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]
            require(len(rows)==1000,'完整1000步缺失');curves[(job['pool'],job['fold'],job['method'],job['seed'])]=[x['loss'] for x in rows]
            for row in rows:
                value={k:row[k] for k in fields if k in row};value.update(job)
                for key in ('learning_rates','real','synthetic'):value[key]=json.dumps(value[key],ensure_ascii=False,separators=(',',':'))
                writer.writerow(value);count+=1
            manifest.append(dict(job=job,steps=ref(path),run_manifest=ref(directory/'run_manifest.json'),
                training_complete=ref(directory/'training_complete.json'),last_checkpoint=ref(directory/'last_checkpoint.json'),
                checkpoints_preserved_in_original_directory=True,raw_files_modified=False))
    require(count==54000,'不能导出缺失步或筛seed')
    with (output/'runs.csv').open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['fold','seed','pool','method','updates','R_windows','S_windows','R_pairs','S_pairs','R_known_pairs','S_known_pairs'])
        writer.writeheader()
        for item in audit['runs']:writer.writerow(dict(item['job'],updates=item['updates'],**item['totals']))
    figures=[]
    if plots:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        for pool in ('balanced','hard_enriched'):
            for fold in ('game4','game6','game9'):
                fig,axes=plt.subplots(1,3,figsize=(12,3.2),sharex=True,sharey=True)
                for ax,method in zip(axes,('motion','motion_residual','gated')):
                    for seed in (20261024,20261025,20261026):
                        y=curves[(pool,fold,method,seed)]
                        smooth=[sum(y[max(0,i-49):i+1])/len(y[max(0,i-49):i+1]) for i in range(len(y))]
                        line,=ax.plot(range(1,1001),smooth,label=str(seed),linewidth=1)
                        ax.plot(range(1,1001),y,color=line.get_color(),alpha=.1,linewidth=.35)
                    ax.set_title(method);ax.set_xlabel('Actual optimizer update');ax.grid(alpha=.2)
                axes[0].set_ylabel('R loss + S loss / 3');axes[-1].legend(fontsize=7)
                fig.suptitle(f'v10 {pool} / {fold} | raw + trailing 50-update mean');fig.tight_layout()
                for suffix in ('png','pdf'):
                    p=output/(pool+'_'+fold+'.'+suffix);fig.savefig(p,dpi=180);figures.append(ref(p))
                plt.close(fig)
    result=dict(schema='v10_paper_training_archive_v1',status='complete54_raw_training_records_export',
        generated_utc=datetime.now(timezone.utc).isoformat(),protocol=ref(protocol),actual_budget=ref(budget),source_runs=manifest,
        step_rows=count,steps=ref(output/'steps.csv'),runs=ref(output/'runs.csv'),figures=figures,
        smoothing='trailing 50 updates for display only; all unsmoothed steps in CSV',
        model_selection='last1000 only; no checkpoint selection',new_optimizer_updates=0,media_read=False,test_read=False,
        fields_unavailable=[],diagnostic_updates_excluded=6,tracking_results_not_read=True)
    with (output/'complete.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2);stream.write('\n')
    return dict(status=result['status'],step_rows=count,figures=len(figures),new_updates=0)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','budget','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--plots',action='store_true');p.add_argument('--execute',action='store_true');a=p.parse_args()
    print(json.dumps(export(a.protocol,a.budget,a.output,a.plots) if a.execute else dict(status='readonly_v10_paper_archive_plan'),ensure_ascii=False))
