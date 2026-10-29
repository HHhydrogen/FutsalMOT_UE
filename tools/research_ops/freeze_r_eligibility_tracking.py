"""训练独立审计完成后冻结新180追踪矩阵；安装代码与元数据，不执行追踪。"""
from copy import deepcopy
import argparse,hashlib,importlib.util,json,os,re,shutil,sys
from pathlib import Path
P=Path(__file__).resolve().parents[2];R=Path('D:/projects/FutsalMOT_Research');E=R/'pose/r_candidate_eligibility_a01'
FILES=['tools/research_ops/r_eligibility_tracking_'+n+'.py' for n in ('runtime','workers','control','analysis')]
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p))
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def read_ref(value):
 p=safe(value['path']);assert sha(p)==value['sha256'],'闭合来源SHA改变';return read(p)

def resolve_training_refs(complete_ref):
 """只按完成根和独立预算双链定位实际执行态，不猜科学协议里的旧a01目录。"""
 complete=read_ref(complete_ref)
 assert complete['schema']=='r_candidate_eligibility_training_complete_root_v1'
 assert complete['status']=='complete18_R_candidate_eligibility_training_and_independent_budget_verified'
 assert complete['actual_training_and_audit_processes_absent'] is True and complete['test_read'] is False
 budget_ref=complete['budget_audit'];audit=read_ref(budget_ref)
 assert audit['schema']=='independent_R_candidate_eligibility18_budget_audit_v1'
 assert audit['status']=='complete18_R_candidate_eligibility_actual_budget_effective_supervision_full_records_and_exit_verified'
 assert audit['protocol']==complete['protocol']
 assert complete['protocol']['sha256']=='d5880b07e97e1252852c7c70ee5b1961b04f5825838063f8e84b462559388daf'
 assert Path(complete['protocol']['path'])==E/'training_frozen_a01/protocol.json'
 control_ref=complete['control_state'];assert control_ref==audit['control_state'],'完成根与预算实际state引用不同'
 control_path=Path(control_ref['path']);assert E in control_path.parents and control_path.name=='driver_state.json'
 state=read_ref(control_ref)
 assert state['status']=='complete18_R_candidate_eligibility_training_wait_independent_audit_tracking' and state['active'] is None
 assert state['protocol_sha256']==complete['protocol']['sha256'] and len(state['completed_train'])==18
 return dict(budget_audit=budget_ref,control_state=control_ref,state=state)
def safe(p):
 p=Path(os.path.abspath(p));assert R in p.parents
 for q in (p,*p.parents):
  if q.exists() or q.is_symlink():assert not q.is_symlink() and not getattr(q.lstat(),'st_file_attributes',0)&0x400
 return p
def write(p,v):
 p=safe(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:f.write(canonical(v)+'\n')
def install(attempt='a01'):
 assert re.fullmatch(r'a\d{2}',attempt),'独立attempt命名不同'
 closure=resolve_training_refs(ref(E/'training_complete_root_a01.json'))
 freeze=E/('tracking_numeric_frozen_'+attempt);assert not freeze.exists(),'已有冻结/partial，不覆盖'
 files=[dict(path=p,sha256=sha(P/p)) for p in FILES];identity=hashlib.sha256(canonical(files).encode()).hexdigest();bundle=R/'code'/identity
 for row in files:
  target=safe(bundle/row['path']);target.parent.mkdir(parents=True,exist_ok=True)
  if target.exists():assert sha(target)==row['sha256']
  else:shutil.copyfile(P/row['path'],target)
 manifest=freeze/'bundle_manifest.json';write(manifest,dict(files=files,source_project=str(P)))
 spec=importlib.util.spec_from_file_location('freeze_R_eligibility_runtime',bundle/FILES[0]);rt=importlib.util.module_from_spec(spec);sys.modules[spec.name]=rt;spec.loader.exec_module(rt)
 oldpath=R/'pose/state_aligned_training_a01/tracking_frozen_a01/config.json';old=read(oldpath);cfg=deepcopy(old)
 aligned_analysis=R/'pose/state_aligned_training_a01/tracking_control_a01/analysis_a01/report.json'
 old_protocol_ref=read(aligned_analysis)['protocol']
 assert Path(old_protocol_ref['path'])==oldpath and old_protocol_ref['sha256']==sha(oldpath), '旧报告协议不是实际同文件同SHA'
 learning=E/'training_frozen_a01/protocol.json';complete=E/'training_complete_root_a01.json'
 learning_data=read(learning);admission=read(learning_data['learning_admission_root_path'])
 assert admission['protocol']==ref(learning) and admission['status']=='complete_R_candidate_eligibility_training_numeric_full_record_admission'
 numeric=read_ref(admission['numeric_validation']);assert numeric['all_groups_equal'] is True and numeric['actual_diagnostic_optimizer_updates']==20 and numeric['diagnostic_R_windows']==60 and numeric['diagnostic_S_windows']==8
 controller_spec=importlib.util.spec_from_file_location('freeze_eligibility_control',bundle/FILES[2]);controller=importlib.util.module_from_spec(controller_spec);controller_spec.loader.exec_module(controller)
 cfg.update(schema='r_eligibility_tracking_protocol_v1',bundle=str(bundle),bundle_manifest=ref(manifest),output_root=str(E),
  learning_protocol=ref(learning),training_budget=closure['budget_audit'],training_complete=ref(complete),training_control_state=closure['control_state'],
  aligned_inventory=old['inventory'],aligned_learning_protocol=old['learning_protocol'],aligned_tracking_protocol=old_protocol_ref,
  aligned_tracking_manifest=ref(R/'pose/state_aligned_training_a01/tracking_control_a01/manifest.json'),
  aligned_analysis=ref(aligned_analysis),
  source_state_aligned_runtime=rt.BASE_REFERENCE,analysis_plan=read(learning)['analysis_plan'],
  worker_profile=dict(controller.PROFILE),worker_service=ref(controller.BASE),
  source_numeric_validation=admission['numeric_validation'],phase='numeric_admission',numeric_authorized=True,tracking_authorized=False,
  numeric_output=str(E/('tracking_numeric_'+attempt)),control_root=str(E/'tracking_control_a01'))
 models=rt.model_specs(cfg['learning_protocol'],closure['state'],rt.read_ref(cfg['aligned_inventory']),rt.read_ref(cfg['source_inventory']))
 inventory=dict(schema=rt.SCHEMA,models=models,sources=cfg['sources'],panels=cfg['panels'])
 invpath=E/('tracking_inventory_'+attempt)/'manifest.json';write(invpath,inventory);cfg['inventory']=ref(invpath)
 cfg['jobs']=rt.tracking_matrix(models,cfg['sources'],cfg['panels'])
 gates=[j for j in old['jobs'] if j['job_id'] in old['gate_job_ids']]
 cfg['gate_job_ids']=[next(n['job_id'] for n in cfg['jobs'] if all(n[k]==g[k] for k in ('fold','seed','regime','sequence'))) for g in gates]
 cfg.pop('numeric_admission',None);rt.validate_jobs(cfg,inventory);rt.training_closure(cfg);rt.source_bindings(cfg)
 path=freeze/'config.json';write(path,cfg)
 return dict(status='frozen_R_eligibility180_tracking_numeric_protocol_not_executed',config=ref(path),bundle=str(bundle),inventory=ref(invpath),jobs=len(cfg['jobs']),new_optimizer_updates=0,test_read=False)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--attempt',default='a01');args=parser.parse_args()
 print(canonical(install(args.attempt)))
