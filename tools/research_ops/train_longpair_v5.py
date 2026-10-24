"""v5独立候选执行入口；默认只读，必须新root准入与明确--execute才训练。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import signal
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from v5_numeric_loader import numeric_helpers

RESEARCH=Path('D:/projects/FutsalMOT_Research')
GDATA=Path('G:/FutsalMOT_Dataset')
ARMS=('R3','R3S_blue','R3S_terracotta')

def require(ok,message):
    if not ok:raise ValueError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def checked(ref):
    path=Path(ref['path']).resolve();require(path.is_file() and sha(path)==ref['sha256'],'绑定SHA缺失/变化:'+str(path));return path

def preflight(context_path,protocol_path,admission_path,seed,arm):
    runtime=read(context_path);protocol=read(protocol_path);admission=read(admission_path)
    require(runtime.get('schema')=='futsalmot_v5_explicit_runtime_context_v1','缺显式v5运行布局')
    bundle=Path(runtime['code_bundle']).resolve();research=Path(runtime['research_root']).resolve();source=Path(runtime['source_project_root']).resolve()
    require(research==RESEARCH and bundle.parent==research/'code' and len(bundle.name)==64,'执行bundle须DResearch/code/<SHA>')
    require(Path(__file__).resolve()==bundle/'tools/research_ops/train_longpair_v5.py','真实执行入口必须来自不可变DResearch bundle')
    require((source/'.git').exists() and source!=bundle,'canonical Git项目与执行bundle分离；不建新Git')
    manifest=read(checked(runtime['bundle_manifest']))
    canonical=json.dumps(manifest['files'],sort_keys=True,separators=(',',':')).encode()
    require(hashlib.sha256(canonical).hexdigest()==bundle.name,'bundle内容地址身份变化')
    for item in manifest['files']:
        path=bundle/item['path'];require(bundle in path.resolve().parents and sha(path)==item['sha256'],'bundle文件变化')
    require(protocol.get('schema')=='futsalmot_longpair_training_protocol_v5' and protocol.get('status')=='frozen_location_research_v5' and protocol.get('training_authorized') is True and protocol.get('updates')==1000
        and protocol.get('seeds')==[20261024,20261025,20261026] and protocol.get('arms')==list(ARMS),'新v5协议/固定预算不符')
    require(admission.get('schema')=='futsalmot_longpair_training_admission_v5' and admission.get('approved_by')=='root'
        and admission.get('training_authorized') is True and admission.get('location_only') is True
        and admission.get('visibility_supervision') is False and admission.get('protocol_sha256')==sha(protocol_path)
        and admission.get('runtime_context_sha256')==sha(context_path),'尚无独立root准入或绑定不同')
    shutdown=read(checked(admission['shutdown_receipt']))
    require(admission.get('all_rendering_finished') is True,'所有渲染结束后才准入')
    require(shutdown.get('normal_exit_confirmed') is True and shutdown.get('process_absent') is True,'本轮UE安全退出证据缺失')
    sys.path.insert(0,str(bundle/'python/src'))
    numerical,identities=numeric_helpers(bundle)
    require(protocol.get('numeric_function_bindings')==identities,'新v5须绑定所复用原函数逐字SHA')
    require(not numerical.BASE.editor_running(),'当前仍存在UnrealEditor')
    require(seed in protocol['seeds'] and arm in ARMS,'arm/seed越界')
    schedule=read(checked(protocol['schedules'][str(seed)]));require(len(schedule)==1000,'必须1000次实际更新')
    synthetic=checked(protocol['synthetic_jsonl']['sport_blue_v1' if arm!='R3S_terracotta' else 'sport_terracotta_v1'])
    real=checked(protocol['real_jsonl']);require(RESEARCH in real.parents and RESEARCH in synthetic.parents,'训练JSONL/元数据实际DResearch')
    for index,row in enumerate(schedule):
        require(row['update_index']==index and len(row['real_indices'])==3 and all(type(i) is int and 0<=i<1000 for i in row['real_indices'])
            and type(row['synthetic_index']) is int and 0<=row['synthetic_index']<1200,'调度身份/边界改变')
    require(all(sorted(r['real_indices'][slot] for r in schedule)==list(range(1000)) for slot in range(3)),'同3000R须每槽各完整1000次')
    require(len(set(r['synthetic_index'] for r in schedule))==1000,'混合恰1000个不同S，同表双地板')
    for path,is_synthetic in [(real,False),(synthetic,True)]:
        for line in path.read_text(encoding='utf-8').splitlines():
            record=json.loads(line);image=Path(record['image_file']);image=(path.parent/image).resolve() if not image.is_absolute() else image.resolve()
            require((GDATA in image.parents) if is_synthetic else (RESEARCH in image.parents or GDATA in image.parents),'媒体实际位置违反策略')
    initialization=checked(protocol['initialization']);require(RESEARCH in initialization.parents,'初始化实际DResearch')
    return numerical,dict(arm='R3' if arm=='R3' else 'R3S1',seed=seed,schedule=schedule,real_jsonl=real,synthetic_jsonl=synthetic,
        bindings=dict(v5_protocol_sha256=sha(protocol_path),v5_admission_sha256=sha(admission_path),v5_runtime_sha256=sha(context_path),external_arm=arm,
            schedule_sha256=sha(checked(protocol['schedules'][str(seed)])),bundle_manifest_sha256=runtime['bundle_manifest']['sha256']),initialization=initialization,external_arm=arm)

def execute(numeric,context,output,resume=False,device='cuda:0',stop_after=None):
    import numpy as np
    import torch
    import ultralytics
    from copy import copy
    from ultralytics.utils import DEFAULT_CFG
    from ultralytics.utils.torch_utils import ModelEMA
    from grf_ue_bridge.pose_location_dataset_v2 import LocationPoseDataset
    from grf_ue_bridge.pose_location_supervision_v4 import SeparateDomainLocationObjective
    from grf_ue_bridge.pose_xy_head_transfer import map_pose_xy
    from grf_ue_bridge.pose_only_calibration_v3 import configure_pose_only
    from v5_virtual_crop import VirtualCropDataset
    require(ultralytics.__version__=='8.4.60' and torch.__version__=='2.6.0+cu124','候选仅当前已验版本')
    output=Path(output).resolve();require(RESEARCH/'pose/poseonly_v5' in output.parents,'输出仅DResearch独立v5')
    require((output/'last.pt').is_file() if resume else not output.exists(),'拒绝覆盖partial；续跑须明确last')
    output.mkdir(parents=True,exist_ok=resume);seed=context['seed'];random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    if device=='cuda:0':torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.use_deterministic_algorithms(True)
    loaded=torch.load(output/'last.pt' if resume else context['initialization'],map_location='cpu',weights_only=False)
    completed=numeric.reconcile_resume(output,loaded,context) if resume else 0;require(completed<1000,'完成臂不能再训练')
    model=map_pose_xy(loaded['model'].float()).to(device);model.args=copy(DEFAULT_CFG);model.args.pose=12.
    guard=configure_pose_only(model);objective=SeparateDomainLocationObjective(model,freeze_guard=guard)
    optimizer=torch.optim.SGD((p for p in model.parameters() if p.requires_grad),lr=.0001,momentum=.9,weight_decay=0.)
    ema=ModelEMA(model,decay=.9999,tau=2000.)
    if resume:
        optimizer.load_state_dict(loaded['optimizer']);ema.ema.load_state_dict(loaded['ema'].state_dict());ema.updates=loaded['ema_updates']
        random.setstate(loaded['rng']['python']);np.random.set_state(loaded['rng']['numpy']);torch.set_rng_state(loaded['rng']['torch'])
        if loaded['rng']['cuda'] is not None:torch.cuda.set_rng_state_all(loaded['rng']['cuda'])
    mixed=context['arm']=='R3S1';limit=3*1024**3
    real=numeric.BASE.CachedDataset(LocationPoseDataset(context['real_jsonl'],640,verify_image_sha256=True),limit//2 if mixed else limit)
    synthetic=numeric.BASE.CachedDataset(VirtualCropDataset(context['synthetic_jsonl']),limit//2 if mixed else 0)
    stop=[False];previous=signal.signal(signal.SIGINT,lambda *args:stop.__setitem__(0,True))
    try:
        result=numeric.train_loop(model,objective,optimizer,ema,guard,real,synthetic,context['schedule'],context,output,
            completed=completed,chain=loaded['exposure_chain_sha256'] if resume else '0'*64,initial_hash=loaded['initial_state_sha256'] if resume else None,
            last_exposure=loaded.get('last_exposure') if resume else None,stop_after=stop_after,stop_requested=lambda:stop[0])
    finally:signal.signal(signal.SIGINT,previous);objective.close();guard.close()
    result.update(schema='futsalmot_longpair_training_run_v5',bindings=context['bindings'],external_arm=context['external_arm'],seed=seed,
        actual_exposures=dict(real=result['completed_updates']*3,synthetic=result['completed_updates']*int(mixed)),visibility_supervised=False,
        numerical_loop='verbatim_v4_AST_functions_new_v5_checkpoint_identity',source_not_training_flags_preserved=True)
    numeric.atomic_json(output/'run_receipt.json',result)

def configure_runtime():
    runtime=RESEARCH/'pose/poseonly_v5/_runtime'
    for key,folder in [('TORCH_HOME','torch'),('YOLO_CONFIG_DIR','ultralytics'),('MPLCONFIGDIR','matplotlib'),('XDG_CACHE_HOME','cache'),('TMP','tmp'),('TEMP','tmp')]:
        path=runtime/folder;path.mkdir(parents=True,exist_ok=True);os.environ[key]=str(path)
    os.environ.update(YOLO_AUTOINSTALL='false',YOLO_OFFLINE='true',WANDB_MODE='disabled',COMET_MODE='DISABLED',CUBLAS_WORKSPACE_CONFIG=':4096:8')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime-context','protocol','admission','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--seed',type=int,required=True);parser.add_argument('--arm',choices=ARMS,required=True);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--resume',action='store_true');parser.add_argument('--device',choices=('cpu','cuda:0'),default='cuda:0');parser.add_argument('--stop-after',type=int)
    args=parser.parse_args();require(args.stop_after is None or 1<=args.stop_after<=1000,'安全暂停步仅1..1000');numeric,context=preflight(args.runtime_context,args.protocol,args.admission,args.seed,args.arm)
    if not args.execute:print(json.dumps(dict(status='approved_readonly_preflight_no_training',bindings=context['bindings'])));return
    configure_runtime()
    execute(numeric,context,args.output,args.resume,args.device,args.stop_after)
if __name__=='__main__':main()
