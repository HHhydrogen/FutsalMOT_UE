"""一次真实CPU虚拟crop反向传播与冻结检测核验；不启动GPU/正式arm。"""
import argparse
from copy import copy
import hashlib
import json
from pathlib import Path
import sys

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--candidate',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    require=lambda ok,msg:None if ok else (_ for _ in ()).throw(ValueError(msg))
    bundle=args.bundle.resolve();output=args.output.resolve();root=Path('D:/projects/FutsalMOT_Research')
    require(root/'pose/poseonly_v5' in output.parents and not output.exists(),'CPU检查仅全新DResearch/v5目录')
    sys.path[:0]=[str(bundle/'python/src'),str(bundle/'tools/research_ops')]
    from train_longpair_v5 import configure_runtime
    configure_runtime()
    import torch
    from ultralytics.utils import DEFAULT_CFG
    from ultralytics.utils.torch_utils import ModelEMA
    from grf_ue_bridge.pose_location_dataset_v2 import LocationPoseDataset
    from grf_ue_bridge.pose_location_supervision_v4 import SeparateDomainLocationObjective
    from grf_ue_bridge.pose_only_calibration_v3 import configure_pose_only
    from grf_ue_bridge.pose_xy_head_transfer import map_pose_xy
    from v5_virtual_crop import VirtualCropDataset
    from v5_numeric_loader import numeric_helpers
    torch.set_num_threads(4);torch.manual_seed(20261024)
    output.mkdir(parents=True)
    (output/'transaction').mkdir()
    real=root/'pose/coco2017_location_a01/subset/train2017.location.jsonl'
    records=real.read_text(encoding='utf-8').splitlines()[:3]
    # 仅检查3条真实记录；绝对路径派生不改源JSONL，不复制媒体。
    fixed=[]
    for line in records:
        row=json.loads(line);path=Path(row['image_file']);row['image_file']=str((real.parent/path).resolve() if not path.is_absolute() else path);fixed.append(json.dumps(row))
    (output/'real_three.jsonl').write_text('\n'.join(fixed)+'\n',encoding='utf-8')
    virtual=args.candidate/'train.sport_blue_v1.virtual_location.jsonl'
    (output/'synthetic_one.jsonl').write_text(virtual.open(encoding='utf-8').readline(),encoding='utf-8')
    real_dataset=LocationPoseDataset(output/'real_three.jsonl',640,verify_image_sha256=True)
    synthetic_dataset=VirtualCropDataset(output/'synthetic_one.jsonl')
    real_batch=LocationPoseDataset.collate_fn([real_dataset[i] for i in range(3)]);syn_batch=LocationPoseDataset.collate_fn([synthetic_dataset[0]])
    for batch in (real_batch,syn_batch):batch['img']=batch['img'].float()/255.
    checkpoint=root/'weights/yolo11n-pose_xy_location_exact_a01.pt'
    require(hashlib.sha256(checkpoint.read_bytes()).hexdigest()=='c41fee957f91da4657f5b4f8822e22d53c6c527074c102e0a8c7490cf97736ec','初始化SHA变化')
    loaded=torch.load(checkpoint,map_location='cpu',weights_only=False);model=map_pose_xy(loaded['model'].float()).cpu();model.args=copy(DEFAULT_CFG);model.args.pose=12.
    guard=configure_pose_only(model);objective=SeparateDomainLocationObjective(model,freeze_guard=guard)
    optimizer=torch.optim.SGD((p for p in model.parameters() if p.requires_grad),lr=.0001,momentum=.9,weight_decay=0.)
    ema=ModelEMA(model,decay=.9999,tau=2000.)
    def detections(m):
        with torch.no_grad():value=m(real_batch['img'])
        value=value[0] if isinstance(value,(tuple,list)) else value
        return value[:,:5].detach().clone()
    before=detections(model);before_ema=detections(ema.ema)
    numeric,identities=numeric_helpers(bundle)
    context=dict(arm='R3S1',seed=20261024,bindings=dict(scope='isolated_CPU_validation_not_formal_arm'))
    schedule=[dict(update_index=i,real_indices=[0,1,2],synthetic_index=0) for i in range(1000)]
    context['schedule']=schedule
    result=numeric.train_loop(model,objective,optimizer,ema,guard,real_dataset,synthetic_dataset,schedule,context,output/'transaction',stop_after=1)
    gradients=sum(int(p.grad is not None and bool(p.grad.abs().sum())) for p in model.parameters() if p.requires_grad);require(gradients>0,'未产生位置梯度')
    saved=torch.load(output/'transaction/last.pt',map_location='cpu',weights_only=False)
    committed=numeric.reconcile_resume(output/'transaction',saved,context)
    require(committed==1 and result['completed_updates']==1,'CPU事务未真实提交一次')
    exposure=json.loads((output/'transaction/exposures.jsonl').read_text(encoding='utf-8'))
    actual_equal=torch.equal(before,detections(model));ema_equal=torch.equal(before_ema,detections(ema.ema));require(actual_equal and ema_equal,'检测输出发生改变')
    state=guard.assert_unchanged();objective.close();guard.close()
    receipt=dict(schema='futsalmot_v5_actual_cpu_crop_backward_receipt_v1',status='passed',device='cpu',GPU_used=False,formal_optimizer_budget_updates=0,toy_validation_optimizer_updates=1,
        actual_images_read=dict(real=3,synthetic=1),image_copy=False,loss=exposure['total_location_loss'],checkpoint_and_exposure_committed_updates=committed,optimizer_replayed_updates=0,trainable_parameters_with_nonzero_gradients=gradients,
        actual_detector_output_exact_equal=actual_equal,EMA_detector_output_exact_equal=ema_equal,freeze_guard=state,
        valid_points=dict(real=int(real_batch['location_valid'].sum()),synthetic=int(syn_batch['location_valid'].sum())),numeric_functions=len(identities),
        bundle=str(bundle),source_checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),limitations=['one_CPU_validation_update_not_formal_arm','no_dynamic_visibility_upgrade','no_claim_of_training_benefit'])
    (output/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt,ensure_ascii=False))
if __name__=='__main__':main()
