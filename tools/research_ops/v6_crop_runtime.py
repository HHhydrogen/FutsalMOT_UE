"""v6明确依赖冻结v5身份链；不修改旧bundle、raw或full-frame缓存。"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

RESEARCH=Path('D:/projects/FutsalMOT_Research')

def require(ok,message):
    if not ok:raise ValueError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def bound(ref):
    path=Path(ref['path']).resolve();require(path.is_file() and sha(path)==ref['sha256'],'绑定改变:'+str(path));return path

def load(config_path):
    config=read(config_path);bundle=Path(config['v6_bundle']).resolve();manifest=read(bound(config['bundle_manifest']))
    require(Path(__file__).resolve()==bundle/'tools/research_ops/v6_crop_runtime.py' and bundle.parent==RESEARCH/'code','必须从DResearch独立v6 bundle执行')
    require(bundle.name==hashlib.sha256(json.dumps(manifest['files'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),'v6 bundle身份不符')
    for entry in manifest['files']:require(sha(bundle/entry['path'])==entry['sha256'],'v6代码字节变化')
    old_config=bound(config['frozen_v5_association_config']);old=read(old_config);old_bundle=Path(old['association_bundle'])
    spec=importlib.util.spec_from_file_location('v6_explicit_frozen_v5_runtime',old_bundle/'tools/research_ops/v5_association_runtime.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    base=module.load(old_config);module.check_fixed(base);require(module.training_complete(old,require_absent=False) is not None,'必须复用完整九臂，不重训')
    import grf_ue_bridge
    directory=str(bundle/'python/src/grf_ue_bridge')
    if directory not in grf_ue_bridge.__path__:grf_ue_bridge.__path__.append(directory)
    from grf_ue_bridge import fixed_detection_crop_pose_v6 as core
    require(Path(core.__file__).resolve()==bundle/'python/src/grf_ue_bridge/fixed_detection_crop_pose_v6.py','禁止误导入源码区未冻结core')
    core.validate_configuration(config['crop_configuration']);require(config['crop_configuration']['geometry_config']==read(bound(config['original_geometry_configuration'])),'旧几何门槛改变')
    return config,bundle,base,module,core

def configure_runtime():
    root=RESEARCH/'pose/association_dev_a01/v6_crop/_runtime'
    for key,folder in [('TORCH_HOME','torch'),('YOLO_CONFIG_DIR','ultralytics'),('MPLCONFIGDIR','matplotlib'),('XDG_CACHE_HOME','cache'),('TMP','tmp'),('TEMP','tmp')]:
        path=root/folder;path.mkdir(parents=True,exist_ok=True);os.environ[key]=str(path)
    os.environ.update(YOLO_AUTOINSTALL='false',YOLO_OFFLINE='true',WANDB_MODE='disabled',COMET_MODE='DISABLED',CUBLAS_WORKSPACE_CONFIG=':4096:8')

def model(config,base,key):
    entry=config['models'][key]
    numerical,training,metric,context=base.evaluation.load_context(Path(base.config['training_protocol']),Path(base.config['training_admission']),Path(base.config['training_runtime_context']),entry['seed'],entry['arm'])
    if entry['role']=='last_ema':
        report=read(bound(entry['dev_report']));require(report['checkpoint']['sha256']==entry['checkpoint']['sha256'],'模型并非既有实际last EMA')
        run=bound(entry['run_receipt'])
    else:run=None
    loaded,identity=base.evaluation.load_model(bound(entry['checkpoint']),entry['checkpoint']['sha256'],entry['role'],numerical,training,metric,context,run,entry.get('run_receipt',{}).get('sha256'))
    return loaded,dict(identity,v5_bindings=training['bindings'],new_formal_training_updates=0)
