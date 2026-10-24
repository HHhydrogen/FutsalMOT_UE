"""v5实际EMA附件/原数值关联/TrackEval阶段；只在九训练结束后显式执行。"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from v5_association_runtime import load,check_fixed,training_complete,require,read,sha,CACHE_SHA,CONFIG_SHA

def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def attachment(runtime,seed,arm,output):
    from train_longpair_v5 import configure_runtime
    configure_runtime()
    import cv2
    import numpy as np
    import torch
    import ultralytics
    config=runtime.config;manifest,frames,configuration=check_fixed(runtime)
    protocol=Path(config['training_protocol']);admission=Path(config['training_admission']);context=Path(config['training_runtime_context'])
    numerical,training,metric,dev_context=runtime.evaluation.load_context(protocol,admission,context,seed,arm)
    trainroot=Path(config['training_root'])/f'{arm}_seed{seed}'/'train';checkpoint=trainroot/'last.pt';run=trainroot/'run_receipt.json'
    report=read(trainroot.parent/'coco_dev/report.json');expected=report['checkpoint']
    require(expected['role']=='last_ema' and Path(expected['path'])==checkpoint and expected['run_receipt_sha256']==sha(run),'官方v5 dev没有绑定该实际lastEMA')
    model,identity=runtime.evaluation.load_model(checkpoint,expected['sha256'],'last_ema',numerical,training,metric,dev_context,run,sha(run))
    model=model.to('cuda:0').float().eval();torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.use_deterministic_algorithms(True)
    output=runtime.fixed.output_path(output);output.mkdir(parents=True);write(output/'started.json',dict(status='started_not_complete',schema='v5_actual_EMA_pose_attachment_stage',model_identity=identity,test_read=False))
    counts=Counter();partial=output/'attachments.partial.jsonl'
    with partial.open('x',encoding='utf-8') as handle:
        for frame in frames:
            raw=runtime.canonical(frame['image_file']).read_bytes();image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
            require(image is not None and image.shape[:2]==(frame['height'],frame['width']),'固定开发原图尺寸变化')
            predictions=runtime.attachment.infer_image(image,model,'cuda:0',configuration)
            row=runtime.attachment.attach_frame(frame,predictions,model_sha256=identity['sha256'],fixed_detection_set_sha256=CACHE_SHA,config=configuration)
            runtime.attachment.validate_attachment_frame(frame,row,model_sha256=identity['sha256'],fixed_detection_set_sha256=CACHE_SHA,config=configuration)
            row['image_content_sha256']=hashlib.sha256(raw).hexdigest();handle.write(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n')
            counts['frames']+=1;counts['fixed_detections']+=len(frame['detections'])
            for item in row['attachments']:
                counts['prediction_valid' if item['prediction_valid'] else 'bbox_fallback']+=1
                if item['prediction_rejection']:counts['reason:'+item['prediction_rejection']]+=1
    final=output/'attachments.jsonl';partial.rename(final)
    result=dict(schema='futsalmot_fixed_detection_pose_attachment_manifest_v1',status='complete_pose_attachment_not_tracking',
        fixed_detection_cache=dict(path=config['cache']['path'],sha256=CACHE_SHA),fixed_detection_set_sha256=CACHE_SHA,source_manifest=manifest['source_manifest'],checkpoint=dict(identity,member='ema'),
        configuration=dict(path=config['configuration']['path'],sha256=CONFIG_SHA,values=configuration),attachments_jsonl=dict(path=str(final),sha256=sha(final),frames=450),counts=dict(counts),
        independent_v5_identity=dict(training_bindings=training['bindings'],dev_report_sha256=sha(trainroot.parent/'coco_dev/report.json'),checkpoint_schema='futsalmot_longpair_location_checkpoint_v5'),
        detections_modified=False,fixed_boxes_used_for_crops=False,GT_used_for_selection=False,physical_visibility='unknown',test_read=False,
        runtime=dict(device='cuda:0',torch=torch.__version__,ultralytics=ultralytics.__version__,opencv=cv2.__version__))
    write(output/'attachment_manifest.json',result)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=('attachment','tracking','metrics'))
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--seed',type=int,required=True);parser.add_argument('--arm',required=True);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    runtime=load(args.config);require(args.execute and runtime.config.get('execution_authorized') is True and runtime.config.get('approved_by')=='root','root未授权关联执行')
    require(training_complete(runtime.config,require_absent=True) is not None,'九训练未真正完成退出')
    require(args.seed in (20261024,20261025,20261026) and args.arm in ('R3','R3S_blue','R3S_terracotta'),'非法arm/seed')
    from train_longpair_v5 import configure_runtime
    configure_runtime()
    check_fixed(runtime);root=runtime.root/f'{args.arm}_seed{args.seed}'
    if args.stage=='attachment':attachment(runtime,args.seed,args.arm,root/'attachment')
    else:
        import os
        os.environ.update(CUDA_VISIBLE_DEVICES='-1',YOLO_AUTOINSTALL='false')
        sys.path.append('D:/projects/FutsalMOT_Research/runtime_dependencies')
        if args.stage=='tracking':runtime.tracking(root/'tracking',root/'attachment/attachment_manifest.json')
        else:runtime.metrics(root/'tracking',root/'metrics')
if __name__=='__main__':main()
