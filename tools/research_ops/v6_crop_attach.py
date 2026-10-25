"""root显式GPU小样/正式crop附件入口；默认仅只读，不写裁剪媒体。"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from v6_crop_runtime import load,configure_runtime,model,read,sha,require,RESEARCH

def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def attach(config_path,key,output,smoke=False):
    config,bundle,base,legacy,core=load(config_path)
    require(config.get('approved_by')=='root' and config.get('gpu_smoke_authorized' if smoke else 'execution_authorized') is True,'root尚未签本次v6探索准入')
    legacy.training_complete(base.config,require_absent=True)
    output=Path(output).resolve();require(RESEARCH/'pose/association_dev_a01/v6_crop' in output.parents and not output.exists(),'仅全新DResearch/v6输出；保留partial')
    configure_runtime()
    import cv2
    import numpy as np
    import torch
    import ultralytics
    require(torch.__version__=='2.6.0+cu124' and ultralytics.__version__=='8.4.60','仅已登记运行环境')
    loaded,identity=model(config,base,key);loaded=loaded.to('cuda:0').float().eval()
    require(all(not t.is_floating_point() or t.dtype==torch.float32 for t in loaded.state_dict().values()),'不得偷偷AMP/FP16')
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.use_deterministic_algorithms(True)
    torch.cuda.reset_peak_memory_stats();manifest,frames=base.fixed.load_fixed_cache(base.config['cache']['path'],base.config['cache']['sha256']);frames=frames[:2] if smoke else frames
    output.mkdir(parents=True);write(output/'started.json',dict(status='started_not_complete',exploratory=True,model=identity,crop_configuration=config['crop_configuration'],smoke=smoke))
    counts=Counter();partial=output/'crop_attachments.partial.jsonl'
    with partial.open('x',encoding='utf-8') as stream:
        for frame in frames:
            raw=base.canonical(frame['image_file']).read_bytes();image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
            predictions=core.infer_frame(image,frame,loaded,'cuda:0',config['crop_configuration'])
            record=core.attach_frame(frame,predictions,model_sha256=identity['sha256'],fixed_detection_set_sha256=base.config['cache']['sha256'],config=config['crop_configuration'])
            core.validate_frame(frame,record,model_sha256=identity['sha256'],fixed_detection_set_sha256=base.config['cache']['sha256'],config=config['crop_configuration'])
            record['image_content_sha256']=hashlib.sha256(raw).hexdigest();stream.write(json.dumps(record,separators=(',',':'),allow_nan=False)+'\n')
            counts['frames']+=1;counts['raw_UID_crop_attempts']+=len(frame['detections'])
            for row in record['attachments']:
                counts['geometry_valid' if row['prediction_valid'] else 'bbox_fallback']+=1
                if row['prediction_rejection']:counts['reason:'+row['prediction_rejection']]+=1
    final=output/'crop_attachments.jsonl';partial.rename(final)
    result=dict(schema='futsalmot_fixed_detection_crop_pose_manifest_v6',status='smoke_complete_not_full_tracking_input' if smoke else 'complete_crop_pose_attachment_not_tracking',
        exploratory=True,model_key=key,checkpoint=identity,configuration=config['crop_configuration'],config_sha256=sha(config_path),
        fixed_cache=base.config['cache'],raw_jsonl=base.config['raw_jsonl'],attachments=dict(path=str(final),sha256=sha(final),frames=len(frames)),counts=dict(counts),
        frozen_geometry_source=config['original_geometry_configuration'],batch_size=16,dtype='float32',autocast=False,crops_written=False,physical_visibility='unknown',GT_read=False,test_read=False,new_formal_optimizer_updates=0,
        cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(),cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved(),
        backend=dict(torch=torch.__version__,ultralytics=ultralytics.__version__,cudnn_allow_tf32=torch.backends.cudnn.allow_tf32,matmul_allow_tf32=torch.backends.cuda.matmul.allow_tf32),
        limitations=['each_raw_UID_attempt_is_not_geometry_success','geometric_candidate_dedup_is_not_verified_physical_person_identity','different_crop_inference_interface_from_full_frame','single_game9_development_only'])
    write(output/'crop_attachment_manifest.json',result);print(json.dumps(dict(status=result['status'],counts=result['counts'],cuda_peak_allocated_bytes=result['cuda_peak_allocated_bytes']),ensure_ascii=False))

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--model',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--gpu-smoke',action='store_true');args=parser.parse_args()
    config,bundle,base,legacy,core=load(args.config);require(args.model in config['models'],'不得筛选额外模型/seed')
    if not args.execute:print(json.dumps(dict(status='readonly_v6_crop_candidate_no_GPU',models=len(config['models']),model=args.model,batch_size=16,frame_scope='first_two_fixed_frames' if args.gpu_smoke else 'all450',new_formal_training_updates=0)));return
    attach(args.config,args.model,args.output,args.gpu_smoke)
if __name__=='__main__':main()
