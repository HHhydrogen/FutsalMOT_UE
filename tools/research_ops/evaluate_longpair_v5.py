"""v5独立官方COCO200dev身份适配，保留既有数值评价代码。"""
import argparse
import json
from pathlib import Path
import sys
from train_longpair_v5 import preflight,checked,read,sha,require,RESEARCH

def load_context(protocol_path,admission_path,runtime_context,seed,arm):
    numerical,training=preflight(runtime_context,protocol_path,admission_path,seed,arm)
    protocol=read(protocol_path);runtime=read(runtime_context)
    from grf_ue_bridge import coco_pose_dev_eval as metric
    require(sha(metric.__file__)==protocol['evaluation']['numerical_source_sha256'],'官方COCO数值源变化')
    source=read(checked(protocol['evaluation']['dev_manifest']))
    gt=read(checked(source['ground_truth']));ids=source['image_ids'];metric.validate_ground_truth(gt,ids)
    require(len(ids)==len(set(ids))==200 and source['role']=='public_pose_development_only_not_final_test','必须固定原200公开dev')
    images={int(row['image_id']):row for row in source['images']}
    require(set(images)==set(ids),'dev媒体清单不完整')
    for entry in images.values():
        path=Path(entry['path']).resolve();require(RESEARCH in path.parents,'真实dev媒体仅实际DResearch')
    context=dict(protocol=protocol,protocol_sha256=sha(protocol_path),gt=gt,image_ids=ids,images=images,
        binding=dict(v5_protocol_sha256=sha(protocol_path),v5_admission_sha256=sha(admission_path),dev_manifest_sha256=protocol['evaluation']['dev_manifest']['sha256']))
    return numerical,training,metric,context

def load_model(checkpoint_path,checkpoint_sha,role,numerical,training,metric,context,run_path=None,run_sha=None):
    import torch
    from grf_ue_bridge.pose_xy_head_transfer import map_pose_xy,_validate
    checkpoint_path=Path(checkpoint_path).resolve();require(RESEARCH in checkpoint_path.parents and sha(checkpoint_path)==checkpoint_sha,'checkpoint位置/SHA变化')
    checkpoint=torch.load(checkpoint_path,map_location='cpu',weights_only=False)
    if role=='pretrained_reference':
        require(checkpoint_sha==context['protocol']['initialization']['sha256'],'参考权重必须相同严格xy初始化')
        model=checkpoint.get('ema') if isinstance(checkpoint.get('ema'),torch.nn.Module) else checkpoint.get('model')
        model=map_pose_xy(model.float())
    else:
        require(checkpoint_path.name=='last.pt' and run_path is not None and sha(run_path)==run_sha,'last/run绑定缺失')
        run=read(run_path);require(run.get('schema')=='futsalmot_longpair_training_run_v5' and run.get('complete') is True
            and run.get('completed_updates')==run.get('planned_updates')==1000,'v5必须实际完成last1000')
        require(run.get('bindings')==checkpoint.get('bindings')==training['bindings'] and run.get('external_arm')==training['external_arm'],'九臂身份链不符')
        require(run.get('actual_exposures')==dict(real=3000,synthetic=0 if training['arm']=='R3' else 1000),'真实曝光预算变化')
        require(checkpoint.get('completed_updates')==checkpoint.get('planned_updates')==checkpoint.get('ema_updates')==1000,'checkpoint实际更新/EMA不符')
        numerical.reconcile_resume(checkpoint_path.parent,checkpoint,training)
        require(isinstance(checkpoint.get('ema'),torch.nn.Module),'缺真实EMA；禁止回退model')
        for name in ('model','ema'):
            require(all(not t.is_floating_point() or t.dtype==torch.float32 for t in checkpoint[name].state_dict().values()),'实际模型/EMA必须FP32')
        model=checkpoint['ema']
    head=_validate(model);require(tuple(head.kpt_shape)==(17,2) and head.nc==1,'必须COCO17xy单类头')
    return model.float().eval(),dict(role=role,path=str(checkpoint_path),sha256=checkpoint_sha,run_receipt_sha256=run_sha,actual_ema_fp32=role=='last_ema')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime-context','protocol','admission','checkpoint','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--checkpoint-sha256',required=True);parser.add_argument('--seed',type=int,required=True)
    parser.add_argument('--arm',required=True);parser.add_argument('--role',choices=('last_ema','pretrained_reference'),default='last_ema')
    parser.add_argument('--run-receipt',type=Path);parser.add_argument('--run-receipt-sha256');parser.add_argument('--device',choices=('cpu','cuda:0'),default='cuda:0')
    args=parser.parse_args();numerical,training,metric,context=load_context(args.protocol,args.admission,args.runtime_context,args.seed,args.arm)
    output=args.output.resolve();require(RESEARCH/'pose/poseonly_v5' in output.parents and not output.exists(),'评价输出须独立DResearch新目录')
    # 与训练一致，第三方配置不写用户目录。
    from train_longpair_v5 import configure_runtime
    configure_runtime()
    model,metadata=load_model(args.checkpoint,args.checkpoint_sha256,args.role,numerical,training,metric,context,args.run_receipt,args.run_receipt_sha256)
    output.mkdir(parents=True)
    try:
        predictions,processed,runtime=metric.inference(context,model,args.device)
        metric.validate_predictions(predictions,processed,context['image_ids'])
        report,log=metric.evaluate(context,predictions,processed)
        report.update(schema='futsalmot_coco_pose_dev_evaluation_v5',checkpoint=metadata,numerical_source_sha256=sha(metric.__file__))
        for name,value in [('predictions.json',predictions),('report.json',report),('predictions_receipt.json',dict(schema='futsalmot_coco_pose_dev_predictions_v5',binding=context['binding'],checkpoint=metadata,
            processed_image_ids=processed,runtime=runtime,postprocess=metric.POSTPROCESS,score_policy=metric.SCORE_POLICY,physical_visibility='unknown_not_predicted',test_read=False))]:
            (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (output/'official_COCOeval.txt').write_text(log,encoding='utf-8')
    except Exception as error:
        (output/'failure.json').write_text(json.dumps(dict(status='failed_preserved_no_claim',error=str(error)))+'\n',encoding='utf-8');raise
if __name__=='__main__':main()
