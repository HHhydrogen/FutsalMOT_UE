"""既有记录三轴诊断的有界只读驱动；不导入模型/追踪器或打开GT。"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime,timezone
import ctypes,gzip,hashlib,json,multiprocessing as mp,os,re,subprocess,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from record_reuse_windows import analyse_windows
from record_reuse_gap import analyse_gap
from record_reuse_history import analyse_history

R=Path('D:/projects/FutsalMOT_Research');E=R/'pose/record_reuse_diagnosis_a01';ROOT=Path(__file__).resolve().parents[2]
DONE='complete_record_reuse_weak_labels_reachability_history_no_training'
ZERO=('new_optimizer_updates','new_model_forwards','new_image_predictions','new_tracking','new_solver_calls','new_TrackEval','GT_coordinate_reads')

def require(value,message):
 if not value:raise ValueError(message)

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)

def safe(value):
 p=Path(os.path.abspath(value));require(R in p.parents,'仅物理研究根')
 require(not any(x.lower() in ('test','gt') or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',x.lower()) for x in p.parts),'GT/测试封存')
 require(p.suffix.lower() not in ('.pt','.pth','.ckpt','.png','.jpg','.jpeg','.exr','.mp4') and p.name!='gap_registry.json','模型媒体完整GTregistry禁读')
 for q in (p,*p.parents):
  if q.exists() or q.is_symlink():require(not q.is_symlink() and not getattr(q.lstat(),'st_file_attributes',0)&0x400,'拒绝链接/junction')
 return p

def sha(path):
 h=hashlib.sha256()
 with safe(path).open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()

def ref(path):return dict(path=str(safe(path)),sha256=sha(path))

def read_raw(path):return json.loads(safe(path).read_text(encoding='utf-8-sig'))

def write(path,value):
 p=safe(path);require(E in p.parents,'仅本次新输出');p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:f.write(canonical(value)+'\n')

class Reader:
 def __init__(self,cfg):
  self.allowed={};self.checked=set();self.rows_read={};self.bytes_hashed=0
  for x in cfg['source_refs'].values():self.add(x)
  for item in cfg['metric_sources']:
   self.add(item['report']);self.add(item['tracking_receipt'])
  for item in cfg['window_units']:
   for k in ('receipt','selected_windows','selected_candidates'):self.add(item[k])
  state=self(cfg['source_refs']['history_state'])
  for x in state['observe'].values():self.add(x)
  for x in state['observe'].values():
   receipt=self(x)
   if receipt['job']['regime']=='RS':self.add(receipt['frames_log'])
 def add(self,value):
  p=safe(value['path']);key=str(p)
  require(p.is_file() and p.stat().st_size<=536870912,'来源不存在或超过512MiB，先停在预飞')
  require(key not in self.allowed or self.allowed[key]['sha256']==value['sha256'],'同path多SHA')
  self.allowed[key]=value
 def __call__(self,value):
  p=safe(value['path']);key=str(p);require(key in self.allowed and self.allowed[key]['sha256']==value['sha256'],'不在冻结白名单')
  if key not in self.checked:
   require(p.stat().st_size<=536870912,'单来源超过512MiB边界');require(sha(p)==value['sha256'],'来源SHA改变：'+key)
   self.checked.add(key);self.bytes_hashed+=p.stat().st_size
  if p.suffix=='.json':return read_raw(p)
  require(p.name in ('selected_windows.jsonl','selected_candidates.jsonl.gz','frames.jsonl.gz'),'只准绑定的三类派生流')
  return self.rows(p)
 def rows(self,p):
  opener=gzip.open if p.suffix=='.gz' else open;key=str(p);limit=750 if p.name=='frames.jsonl.gz' else 500 if p.name=='selected_windows.jsonl' else 8000
  with opener(p,'rt',encoding='utf-8') as f:
   for line in f:
    self.rows_read[key]=self.rows_read.get(key,0)+1;require(self.rows_read[key]<=limit,'单来源行预算越界')
    yield json.loads(line)
 def evidence(self):return dict(files_SHA_checked=len(self.checked),source_bytes_hashed=self.bytes_hashed,rows_read=dict(self.rows_read),GT_coordinates_or_weights_or_media_opened=False)

def memory():
 import psutil
 v=psutil.virtual_memory();require(os.name=='nt','本协议只准已登记Windows主机')
 class Info(ctypes.Structure):
  _fields_=[('cb',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in ('CommitTotal','CommitLimit','CommitPeak','PhysicalTotal','PhysicalAvailable','SystemCache','KernelTotal','KernelPaged','KernelNonpaged','PageSize')]+[(n,ctypes.c_ulong) for n in ('HandleCount','ProcessCount','ThreadCount')]
 info=Info();info.cb=ctypes.sizeof(info);require(ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(info),info.cb),'Windows commit读取失败')
 return dict(available_RAM_bytes=v.available,available_commit_bytes=(info.CommitLimit-info.CommitTotal)*info.PageSize)

def process_identity(rows,current_pid,script):
 by={x['ProcessId']:x for x in rows};own={current_pid};node=by.get(current_pid);identity=str(script).replace('\\','/').lower()
 while node and node['ParentProcessId'] in by:
  parent=by[node['ParentProcessId']];cmd=(parent.get('CommandLine') or '').replace('\\','/').lower()
  if not (parent.get('Name') or '').lower().startswith('python') or identity not in cmd:break
  require(parent['ProcessId'] not in own,'CIM父链循环');own.add(parent['ProcessId']);node=parent
 pattern=re.compile(r'(?:^|[\\/\s"\x27])(?:record_reuse_diagnosis|control_r_eligibility_training|r_eligibility_train|r_eligibility_tracking_control|state_gap_control|state_aligned_tracking_control|r_set_tracking_control)[.]py(?=$|[\s"\x27])',re.I)
 blocked=[x for x in rows if x['ProcessId'] not in own and ((x['Name'] or '').lower().startswith('unrealeditor') or pattern.search(x.get('CommandLine') or ''))]
 require(not blocked,'已有相关producer/UE，不重复启动：'+canonical(blocked));return dict(actual_Name_CommandLine_checked=True,no_related_producer=True,own_exact_script_launcher_chain=sorted(own))

def producers_absent():
 value=subprocess.run(['powershell.exe','-NoProfile','-Command',"Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^python|^UnrealEditor'} | Select-Object Name,ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress"],check=True,capture_output=True,text=True,encoding='utf-8').stdout
 rows=json.loads(value) if value.strip() else [];rows=[rows] if isinstance(rows,dict) else rows
 return process_identity(rows,os.getpid(),__file__)

def enough(snapshot,inflight):return snapshot['available_RAM_bytes']>=8589934592+3221225472*inflight and snapshot['available_commit_bytes']>=6442450944+3221225472*inflight

def task(kind,cfg):
 reader=Reader(cfg);started=time.perf_counter()
 if kind=='windows':value=analyse_windows(cfg['window_units'],reader)
 elif kind=='gap':value=analyse_gap(cfg['metric_sources'],reader,cfg['panels'])
 else:value=analyse_history(reader(cfg['source_refs']['history_selection']),reader(cfg['source_refs']['history_state']),reader)
 return dict(value=value,reader=reader.evidence(),worker_pid=os.getpid(),wall_seconds=time.perf_counter()-started)

def validate(path):
 cfg=read_raw(path)
 require(cfg['schema']=='record_reuse_diagnosis_protocol_v1' and cfg['approved_by']=='root' and cfg['test_sealed'] is True,'独立协议/授权不同')
 require(all(cfg[k]==0 for k in ZERO) and cfg['main_reference']=='original_uncalibrated_strongmotion_RS','零实验/主参照边界不同')
 require(Path(cfg['bundle'])==ROOT and ROOT.parent==R/'code','只执行冻结源码')
 manifest=read_raw(cfg['bundle_manifest']['path']);require(sha(cfg['bundle_manifest']['path'])==cfg['bundle_manifest']['sha256'],'bundle manifest改变')
 for item in manifest['files']:require(sha(ROOT/item['path'])==item['sha256'],'执行源码变化')
 output=Path(cfg['output']);require(len(cfg['metric_sources'])==540 and len(cfg['window_units'])==6 and output.parent==E and re.fullmatch('control_a[0-9]{2}',output.name),'输入/输出边界不同')
 if output!=E/'control_a01':
  previous=cfg['recovery']['previous_failure'];require(sha(previous['path'])==previous['sha256'],'恢复失败证据SHA不同');failure=read_raw(previous['path'])
  require(failure['diagnosis_data_tasks_started']==0 and failure['diagnosis_rows_read']==0 and cfg['recovery']['completed_data_tasks_inherited']==0,'不允许隐式重放成功数据任务')
 reader=Reader(cfg)
 root=reader(cfg['source_refs']['mask_complete']);require(root['status']=='complete_R_candidate_eligibility18_training180_tracking_independent_verification_and_all_intervals' and root['test_read'] is False,'前轮未闭合')
 require(root['tracking_analysis']==cfg['source_refs']['mask_analysis'],'前轮完整分析来源不同')
 require(len({(x['condition'],x['sequence'],x['fold'],x['seed']) for x in cfg['metric_sources']})==540,'540单元重复')
 return cfg

def execute(path):
 cfg=validate(path);processes=producers_absent();out=safe(cfg['output']);require(not out.exists(),'成功/partial拒绝覆盖')
 snap=memory();workers=2 if enough(snap,2) else 1;require(enough(snap,workers),'RAM/commit保留不足，不启动');out.mkdir()
 state=dict(schema='record_reuse_diagnosis_control_v1',status='started_not_committed',protocol=ref(path),pid=os.getpid(),active=[],worker_exits=[],resources=snap,process_preflight=processes,worker_count=workers,test_read=False)
 def save():
  state['updated_utc']=datetime.now(timezone.utc).isoformat();p=out/'state.pending.json';p.write_text(canonical(state),encoding='utf-8');os.replace(p,out/'driver_state.json')
 save();started=time.perf_counter();outputs={};io={}
 try:
  with ProcessPoolExecutor(max_workers=workers,mp_context=mp.get_context('spawn')) as pool:
   pending={kind:pool.submit(task,kind,cfg) for kind in ('windows','gap')};processes=list(pool._processes.values())
   for kind in ('windows','gap'):
    state['active']=[kind];save();result=pending.pop(kind).result();value=result.pop('value');io[kind]=result
    if kind=='windows':
     write(out/'window_summary.json',value['summary']);write(out/'window_cases.json',value['casebook'])
     target=out/'window_records.jsonl'
    else:write(out/'gap_summary.json',value['summary']);target=out/'gap_pairs.jsonl'
    with target.open('x',encoding='utf-8') as f:
     for row in value['records']:f.write(canonical(row)+'\n')
    outputs[kind]=dict(summary=ref(out/('window_summary.json' if kind=='windows' else 'gap_summary.json')),records=ref(target))
    if kind=='windows':outputs[kind]['casebook']=ref(out/'window_cases.json')
    del value,result
  require(all(not p.is_alive() and p.exitcode==0 for p in processes),'只读worker未实际退出')
  state['worker_exits']=[dict(pid=p.pid,exit_code=p.exitcode,process_exited=not p.is_alive()) for p in processes];state['active']=['history'];save()
  require(enough(memory(),1),'history读取前资源不足');result=task('history',cfg);write(out/'history.json',result.pop('value'));outputs['history']=ref(out/'history.json');io['history']=result
  report=dict(schema='record_reuse_diagnosis_v1',status=DONE,protocol=ref(path),sources=cfg['source_refs'],outputs=outputs,IO=io,
   actual_worker_exits=state['worker_exits'],main_reference=cfg['main_reference'],new_confidence_intervals=0,existing_90_intervals_source=cfg['source_refs']['mask_analysis'],
   all_negative_unknown_exclusions_retained=True,factor_selected=False,training_authorized=False,test_read=False,wall_seconds=time.perf_counter()-started,**{k:0 for k in ZERO})
  write(out/'report.json',report);state.update(status=DONE,active=[],report=ref(out/'report.json'));save();return report
 except BaseException:
  state.update(status='failed_preserved_no_implicit_replay',traceback=traceback.format_exc());save();write(out/'failed.json',state);raise

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
 if a.execute:result=execute(a.config)
 else:
  cfg=validate(a.config);result=dict(status='readonly_record_reuse_preflight',reports=len(cfg['metric_sources']),R_units=len(cfg['window_units']))
 print(canonical(dict(status=result['status'])))
