"""v5关联独立依赖与明确文件relocation；不修改旧协议/缓存/数值源码。"""
import ast
from collections import Counter
import configparser
import hashlib
import importlib
import inspect
import json
import math
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace

RESEARCH=Path('D:/projects/FutsalMOT_Research')
PROJECT=Path('D:/projects/FutsalMOT_UEDataset')
SEQUENCES=('SNMOT-151','SNMOT-152','SNMOT-153')
CACHE_SHA='3028fa8cf73737ae459afda4226bad33b55c6ef34cd817efb548ae417e6c462d'
RAW_SHA='6268addda27fe636e94434aa7e61580d5409accdabe73f0b7c82613afc2f581e'
RULE_SHA='52133eb43be96c96782bbc92abc0a7659d21442b817199c8e7c1ff1767e988db'
CONFIG_SHA='49916c92e1362655a7e21944e1be44d315bc99863d877b65f5da3b1e743b6e16'
BASELINE_SHA='bc433af5ba617ec8b0a94a3aea43318ec68e79d7f7a4c2ce242fe4439926bf23'

def require(ok,message):
    if not ok:raise ValueError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def bound(ref):
    path=Path(ref['path']).resolve();require(path.is_file() and sha(path)==ref['sha256'],'绑定SHA变化:'+str(path));return path

def plain(path,relocations=()):
    raw=Path(path).absolute()
    require('..' not in raw.parts and not any(part.lower() in ('test','test2017','test2014') or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',part.lower()) for part in raw.parts),'stat前拒绝封存域/逃逸')
    for old,new in relocations:
        if raw==Path(old):raw=Path(new).absolute();break
    for part in (raw,*raw.parents):
        if part.exists():require(not part.is_symlink() and not getattr(part.lstat(),'st_file_attributes',0)&0x400,'禁止联接/G别名:'+str(part))
    require(raw.resolve()==raw,'未登记重定向')
    return raw

def output_path(path,root):
    path=plain(path);require(root in path.parents and not path.exists(),'保留partial；仅全新v5关联输出');return path

def load(config_path):
    config=read(config_path);bundle=Path(config['association_bundle']).resolve();training_bundle=Path(config['training_bundle']).resolve()
    require(bundle.parent==RESEARCH/'code' and Path(__file__).resolve()==bundle/'tools/research_ops/v5_association_runtime.py','关联执行必须来自独立DResearch SHA bundle')
    manifest=read(bound(config['association_bundle_manifest']))
    identity=hashlib.sha256(json.dumps(manifest['files'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    require(bundle.name==identity,'关联bundle内容地址不符')
    for item in manifest['files']:require(sha(bundle/item['path'])==item['sha256'],'关联bundle源变化')
    require(sha(config['training_protocol'])==config['training_protocol_sha256'] and sha(config['training_admission'])==config['training_admission_sha256'],'冻结v5训练输入变化')
    sys.path[:0]=[str(bundle/'python/src'),str(training_bundle/'python/src'),str(training_bundle/'tools/research_ops')]
    import grf_ue_bridge
    for directory in (bundle/'python/src/grf_ue_bridge',training_bundle/'python/src/grf_ue_bridge'):
        if str(directory) not in grf_ue_bridge.__path__:grf_ue_bridge.__path__.append(str(directory))
    from grf_ue_bridge import fixed_detection_pose_attach_v2 as attachment
    from grf_ue_bridge import pose_association_trackeval_v1 as metric
    # v5 load_model仅在真正训练终态后调用，绝不别名成v4身份。
    evaluation=importlib.import_module('evaluate_longpair_v5')
    relocations=[(row['legacy'],row['actual']) for row in config['literal_file_relocations']]
    canonical=lambda path:plain(path,relocations)
    metric.safe_path=canonical
    root=Path(config['output_root']).resolve()
    fixed=dict(Path=Path,math=math,json=json,hashlib=hashlib,require=require,sha=sha,read=read,plain=canonical,
        output_path=lambda path:output_path(path,root),SEQUENCES=SEQUENCES,FRAME_SCHEMA='futsalmot_fixed_detection_frame_v1',RESEARCH=RESEARCH,
        INFERENCE=dict(conf=.1))
    def extract(relative,names,namespace):
        path=bundle/relative;tree=ast.parse(path.read_text(encoding='utf-8-sig'));selected=[]
        for name in names:
            nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name];require(len(nodes)==1,'原函数缺失:'+name);selected+=nodes
        namespace['__file__']=str(path);exec(compile(ast.Module(body=selected,type_ignores=[]),str(path),'exec'),namespace)
    extract('experiments/sim2real/prepare_pose_association_dev.py',['source_paths','frame_record','load_fixed_cache'],fixed)
    model_ns=dict(fixed_cache=SimpleNamespace(**fixed),attachment=attachment,safe=canonical,Path=Path)
    extract('experiments/sim2real/attach_fixed_detection_pose.py',['check_file','validate_cache_source'],model_ns)
    # 原run函数只数值关联，不读图/GT。延迟导入tracker以免交接等待期载入Torch。
    def tracking(output,attachment_manifest):
        from grf_ue_bridge import pose_bytetrack_v2 as tracker
        namespace=dict(Path=Path,hashlib=hashlib,inspect=inspect,json=json,tracker=tracker,SEQUENCES=SEQUENCES,
            load_fixed_cache=fixed['load_fixed_cache'],output_path=fixed['output_path'],plain=canonical,
            validate_attachment_frame=attachment.validate_attachment_frame,validate_configuration=attachment.validate_configuration)
        extract('experiments/sim2real/run_pose_association_dev.py',['read','sha','checked','run'],namespace)
        return namespace['run'](config['cache']['path'],CACHE_SHA,config['association_protocol']['path'],RULE_SHA,output,.1,
            attachment_manifest,sha(attachment_manifest),config['lambda0']['path'])
    def metrics(tracking_dir,output):
        namespace=dict(Path=Path,json=json,metric=metric)
        extract('experiments/sim2real/evaluate_pose_association_dev.py',['write','evaluate'],namespace)
        return namespace['evaluate'](tracking_dir,config['cache']['path'],CACHE_SHA,config['association_protocol']['path'],RULE_SHA,config['lambda0']['path'],output)
    return SimpleNamespace(config=config,bundle=bundle,training_bundle=training_bundle,root=root,attachment=attachment,metric=metric,evaluation=evaluation,
        fixed=SimpleNamespace(**fixed),validate_cache_source=model_ns['validate_cache_source'],tracking=tracking,metrics=metrics,canonical=canonical)

def check_fixed(runtime):
    config=runtime.config
    for key,expected in [('cache',CACHE_SHA),('association_protocol',RULE_SHA),('configuration',CONFIG_SHA),('lambda0',BASELINE_SHA)]:
        require(config[key]['sha256']==expected and sha(bound(config[key]))==expected,'原唯一关联输入变化:'+key)
    manifest,frames=runtime.fixed.load_fixed_cache(config['cache']['path'],CACHE_SHA)
    require(sha(runtime.canonical(manifest['detections_jsonl']['path']))==RAW_SHA,'6901raw原始字节变化')
    runtime.validate_cache_source(manifest,frames)
    configuration=read(config['configuration']['path']);runtime.attachment.validate_configuration(configuration)
    protocol=read(config['association_protocol']['path']);require(protocol['frozen_by']=='root' and protocol['pose_cost_candidate']['lambda_candidates']==[0,.1],'不得修改lambda范围')
    baseline=read(config['lambda0']['path']);require(baseline['pose_lambda']==0 and all(row['lambda0_equivalence']['passed'] and row['lambda0_equivalence']['output_arrays_exact'] and row['lambda0_equivalence']['track_states_exact'] for row in baseline['sequences'].values()),'原lambda0等价失败')
    require(len(frames)==450 and sum(len(frame['detections']) for frame in frames)==6901,'原450帧/6901检测范围变化')
    for key in ('bbox_metrics','pretrained_metrics'):
        report=read(bound(config[key]));require(report['test_read'] is False and report['DO_PREPROC'] is False and report['predictions_filtered'] is False,'旧参考口径不同')
    return manifest,frames,configuration

def training_complete(config,require_absent=False):
    state=read(config['training_state']);expected={f'{arm}_seed{seed}' for seed in (20261024,20261025,20261026) for arm in ('R3','R3S_blue','R3S_terracotta')}
    if state.get('status')!='complete_all_nine_train_and_dev':return None
    require(set(state['completed'])==expected and len(state['completed'])==9,'九臂终态身份不完整')
    summary_path=bound(state['summary']);summary=read(summary_path);require(set(summary['reports'])==expected,'九臂汇总缺失')
    for item in summary['reports'].values():bound(item)
    if require_absent:
        import psutil
        driver=Path(config['training_driver']).name.lower()
        for process in psutil.process_iter(['pid','name']):
            if (process.info['name'] or '').lower() not in ('python.exe','pythonw.exe','unrealeditor.exe'):continue
            if (process.info['name'] or '').lower()=='unrealeditor.exe':raise ValueError('UE仍在')
            try:command=' '.join(process.cmdline()).lower()
            except psutil.NoSuchProcess:continue
            except psutil.AccessDenied:raise RuntimeError('Python进程用途无法确认')
            require(not any(token in command for token in (driver,'train_longpair_v5.py','evaluate_longpair_v5.py')),'训练/评价/launcher仍未真实退出')
    return dict(state=state,summary=summary,summary_path=str(summary_path),summary_sha256=sha(summary_path))
