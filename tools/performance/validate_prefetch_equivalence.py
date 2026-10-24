"""仅两个真实G PNG的CPU输出等价检查；不加载模型、不基准GPU或正式训练。"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import threading
from ordered_prefetch import OrderedPrefetch

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-jsonl',type=Path,default=Path('D:/projects/FutsalMOT_Research/pose/poseonly_v5/candidate_a04/train.sport_blue_v1.virtual_location.jsonl'))
    parser.add_argument('--bundle',type=Path,default=Path('D:/projects/FutsalMOT_Research/code/7e5b7a7500919a0088bb443b0d002560a2d47ef104276aee285dede052237c28'))
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    root=Path('D:/projects/FutsalMOT_Research/pose/poseonly_v5');output=args.output.resolve()
    if root not in output.parents or output.exists():raise ValueError('仅全新DResearch/v5 CPU证据目录')
    # 所有运行数据都是新元数据；原JSONL与G PNG保持不变。
    records=[]
    with args.dataset_jsonl.open(encoding='utf-8') as stream:
        for line in stream:
            if line.strip():records.append(json.loads(line))
            if len(records)==2:break
    if len(records)!=2:raise ValueError('需两个实际记录')
    image_paths=[Path(row['image_file']).resolve() for row in records]
    if len(set(image_paths))!=2 or any(Path('G:/FutsalMOT_Dataset') not in path.parents or path.suffix.lower()!='.png' for path in image_paths):raise ValueError('只允许两个不同实际GDataset PNG')
    output.mkdir(parents=True);subset=output/'two_records.virtual_location.jsonl'
    subset.write_text(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in records),encoding='utf-8')
    sys.path[:0]=[str(args.bundle/'tools/research_ops'),str(args.bundle/'python/src')]
    import torch
    import numpy as np
    import cv2
    torch.set_num_threads(1);cv2.setNumThreads(1)
    from v5_virtual_crop import VirtualCropDataset
    dataset=VirtualCropDataset(subset)
    states=(random.getstate(),np.random.get_state(),torch.get_rng_state().clone())
    synchronous=[dataset[index] for index in (0,1)]
    def tensor_bytes(value):
        if isinstance(value,torch.Tensor):return value.numel()*value.element_size()
        if isinstance(value,dict):return sum(tensor_bytes(item) for item in value.values())
        if isinstance(value,(list,tuple)):return sum(tensor_bytes(item) for item in value)
        return 0
    limit=max(tensor_bytes(value) for value in synchronous);producer_threads=[]
    def load(index):producer_threads.append(threading.get_ident());return dataset[index]
    with OrderedPrefetch(load,(0,1),capacity=2,resource=dataset,max_item_bytes=limit,measure_bytes=tensor_bytes) as prefetched:
        asynchronous=list(prefetched)
    def equal(left,right):
        if type(left) is not type(right):raise AssertionError('返回类型改变')
        if isinstance(left,torch.Tensor):
            if left.is_cuda or right.is_cuda or left.dtype!=right.dtype or left.shape!=right.shape or not torch.equal(left,right):raise AssertionError('CPU tensor非逐值一致')
        elif isinstance(left,dict):
            if list(left)!=list(right):raise AssertionError('metadata键/顺序改变')
            for key in left:equal(left[key],right[key])
        elif isinstance(left,(list,tuple)):
            if len(left)!=len(right):raise AssertionError('metadata长度改变')
            for a,b in zip(left,right):equal(a,b)
        elif left!=right:raise AssertionError('metadata值改变')
    equal(synchronous,asynchronous)
    current_np=np.random.get_state()
    rng_equal=dict(python=random.getstate()==states[0],numpy=current_np[0]==states[1][0] and np.array_equal(current_np[1],states[1][1]) and current_np[2:]==states[1][2:],torch_CPU=torch.equal(torch.get_rng_state(),states[2]))
    if not all(rng_equal.values()) or prefetched.worker_alive or len(set(producer_threads))!=1:raise AssertionError('随机状态或线程生命周期改变')
    receipt=dict(schema='ordered_CPU_prefetch_twoPNG_equivalence_candidate_v1',status='passed_data_equivalence_only_not_train_speed',distinct_G_PNG=2,PNG_decode_calls=4,
        samples=2,all_tensor_and_metadata_exact_equal=True,random_states_unchanged=rng_equal,producer_threads=1,capacity=2,torch_CPU_threads=torch.get_num_threads(),OpenCV_threads=cv2.getNumThreads(),
        models_loaded=False,GPU_used=False,optimizer_updates=0,media_copied=False,media_hashed=False,stats=prefetched.stats,
        input_record_images=[str(path) for path in image_paths],source_jsonl=str(args.dataset_jsonl),
        source_module=dict(path=str(Path(sys.modules['v5_virtual_crop'].__file__)),sha256=hashlib.sha256(Path(sys.modules['v5_virtual_crop'].__file__).read_bytes()).hexdigest()),
        bounded_memory=dict(max_sample_tensor_payload_bytes=limit,prefetched_tensor_payload_bound_queue2=3*limit,prefetched_tensor_payload_bound_queue4=5*limit,
            max_one_inflight_source_BRG_uint8_bytes=3840*2160*3,one_inflight_640_RGB_and_resized_BRG_estimate_bytes=2*640*640*3,
            excluded=['consumer-owned outputs','Dataset existing LRU/cache','Python metadata and library allocator overhead','loader-specific temporary objects'],whole_process_RSS_bound_claimed=False),
        contract=['one deterministic loader producer only','same CachedDataset exclusive resource until close','no RNG/state/sampler changes','close waits in-flight loader; timeout is explicit failure','no optimizer update submission/replay/retry'],
        limitations=['CPU equality on only two PNG; not an end-to-end speed result','future GPU efficiency validation requires independent protocol','noncooperative blocking loader cannot be force-killed safely'])
    (output/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt,ensure_ascii=False))
if __name__=='__main__':main()
