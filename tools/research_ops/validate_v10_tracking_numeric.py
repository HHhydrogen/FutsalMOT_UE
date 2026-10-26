"""原750帧上逐输出核对新scope适配；CPU零优化更新，不读取新比赛追踪结果。"""
import argparse
from copy import deepcopy
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import v10_tracking_runtime as rt


def validate(config,run,output):
    os.environ['CUDA_VISIBLE_DEVICES']='-1'
    runtime,train,numeric,base,old=rt.training(config)
    import torch
    torch.set_num_threads(1)
    sources=rt.sources_from(train,rt.read(rt.checked(train['prediction_manifest'])))
    source=sources['SNMOT-060'];frames=rt.rows(rt.checked(source['cache']))
    _,_,model,adapter,binding=runtime.complete_model(config,run)
    rt.require(binding['method']=='gated' and binding['fold']=='game4','固定首seed gated模型验证')
    from grf_ue_bridge.learned_association_tracker_v8 import tracker_class
    original=tracker_class();adapted,scope=rt.scoped_tracker(old['bundle'],sources);checks=[]
    for mode in ('PT_bbox','PT_static_pose','learned'):
        values=[]
        for cls in (original,adapted):
            tracker=cls(mode=mode,model=model if mode=='learned' else None,normalizer=adapter if mode=='learned' else None,
                use_pose=True,pose_source_sha256=train['pose_checkpoint_sha256'],fixed_detection_sha256=source['cache']['sha256'])
            mot=[]
            for f in frames:
                for row in tracker.update_frame(f):
                    mot.append([f['frame_number']]+[float(x) for x in row[:6]])
            values.append(dict(mot=mot,audit=deepcopy(tracker.audit)))
        rt.require(values[0]==values[1],'显式新scope改变原750帧实际输出/数值')
        import hashlib
        checks.append(dict(mode=mode,frames=len(frames),rows=len(values[0]['mot']),
            output_sha256=hashlib.sha256(rt.canonical(values[0]).encode()).hexdigest(),all_rows_and_audit_equal=True))
    output=runtime.storage().physical_child(output,rt.V);rt.require(not output.exists(),'验收输出已存在，不覆盖')
    output.parent.mkdir(parents=True,exist_ok=True)
    result=dict(status='complete_original750_three_modes_scope_equivalent',training_protocol_sha256=rt.sha(config),
        run_receipt_sha256=rt.sha(Path(run)/'run_receipt.json'),checks=checks,scope=scope,GT_read=False,
        new_match_tracking_results_read=False,new_optimizer_updates=0,GPU_used=False,test_read=False)
    with output.open('x',encoding='utf-8') as stream:stream.write(rt.canonical(result)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','run','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(rt.canonical(validate(a.config,a.run,a.output)))
