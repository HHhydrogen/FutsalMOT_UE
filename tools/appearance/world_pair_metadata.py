"""提取既有逐行world配对检查；保留数值与SHA语义，不改动任何点。"""
import hashlib
from itertools import zip_longest
import json
import math
from pathlib import Path
from run_seeded_kit_short_a01 import require


def compare_world(a,b,expected_sha_a,expected_sha_b,expected_records=3000):
    hashes=[hashlib.sha256(),hashlib.sha256()];pairs=0;points=0;exact=True;maximum=0.0
    with Path(a).open('rb') as fa,Path(b).open('rb') as fb:
        for ra,rb in zip_longest(fa,fb):
            require(ra is not None and rb is not None,'A/B世界记录行数不同')
            hashes[0].update(ra);hashes[1].update(rb)
            x,y=json.loads(ra),json.loads(rb)
            require(all(x[k]==y[k] for k in ('frame_index','source_frame_index','entity_id','track_id','mesh_identity','manifest_sha256')),'A/B源帧/角色/校准不同')
            require(len(x['world_m'])==len(y['world_m'])==17,'不是COCO17世界记录')
            pairs+=1
            for p,q in zip(x['world_m'],y['world_m']):
                require(len(p)==len(q)==3 and all(math.isfinite(v) for v in (*p,*q)),'世界点非有限')
                points+=1;exact &= p==q;maximum=max(maximum,math.dist(p,q))
    require(pairs==expected_records and [h.hexdigest() for h in hashes]==[expected_sha_a,expected_sha_b],'世界文本SHA或完整记录数不符')
    return dict(record_pairs=pairs,keypoint_pairs=points,all_world_exact=exact,max_world_delta_m=maximum,world_values_modified=False)
