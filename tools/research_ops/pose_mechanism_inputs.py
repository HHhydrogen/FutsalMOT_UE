"""准备五场raw库存/GT后验标签与无GT形状交换；无模型执行或优化更新。"""
import argparse
from collections import Counter
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import pose_mechanism_core as core


def prepare(protocol,output):
    rt,old,runtime,train,numeric,base,numbers=core.reference(protocol)
    pairs=rt.load_file('mechanism_v8_pairs',Path('D:/projects/FutsalMOT_Research/code/1ddcf191b3f33c3d350cdab64011721ae99854680b1b1d2f3eef4c2592a69806/tools/research_ops/v8_pairs.py'))
    core.require(core.sha(pairs.__file__)=='522d00e3767fe4413d44a90510088407bbfa66b444e6e2e6b473764a020208ef','原匹配标签数值改变')
    output=runtime.storage().physical_child(output,core.V);core.require(not output.exists(),'新输入目录，partial不覆盖');output.mkdir(parents=True)
    sources={};all_inventory={}
    for seq,source in old['sources'].items():
        frames=core.rows(core.checked(source['cache']));index={d['uid']:d for f in frames for d in f['detections']}
        bank=core.make_swaps(frames);gt,_=rt.load_gt(source);labels={};inventory=Counter();strata=Counter()
        for frame in frames:
            number=frame['frame_number'];dets=frame['detections'];targets=gt.get(number,[])
            matched=pairs.match_labels(dets,targets)
            labels.update({u:dict(v,frame_number=number) for u,v in matched.items()});inventory['raw_detections']+=len(dets);inventory['GT_person_frames']+=len(targets)
            for g in targets:
                overlaps=[d for d in dets if pairs.iou(d['bbox_xywh_px'],g['bbox_xywh_px'])>=.5]
                trusted=[d for d in overlaps if matched[d['uid']]['state']=='matched' and matched[d['uid']]['gt_id']==g['gt_id']]
                if not overlaps:inventory['GT_person_frames_no_any_raw_IoU05']+=1
                elif not trusted:inventory['GT_person_frames_raw_match_ambiguous']+=1
                else:
                    d=trusted[0];limbs=sum(d['geometry_valid'][5:]);inventory['GT_person_frames_trusted_raw']+=1
                    inventory['trusted_raw_with_at_least6_valid_limbs']+=int(limbs>=6)
                    inventory['trusted_raw_with_fewer6_valid_limbs']+=int(limbs<6)
                    strata[str(core.bin_index(d['bbox_xywh_px'][3]/d['image_wh'][1],core.PARAMETERS['height_edges']))]+=1
        folder=output/seq;folder.mkdir()
        def save(name,value):
            p=folder/name
            with p.open('x',encoding='utf-8') as stream:stream.write(core.canonical(value)+'\n')
            return core.ref(p)
        b=save('shape_swaps.json',bank);l=save('posthoc_GT_labels.json',dict(labels=labels,GT_input_to_models=False))
        sources[seq]=dict(source=source,bank=b,labels=l)
        all_inventory[seq]=dict(counts=dict(inventory),height_strata=dict(strata),shuffle_observations=bank['shuffled_observations'],
            all_observations=len(index),unchanged_reasons=dict(Counter(bank['unchanged_reasons'].values())),
            interpretation='geometric validity and IoU matching coverage, not keypoint accuracy or physical visibility')
    value=dict(schema='pose_mechanism_prepared_inputs_v1',status='complete_raw_inputs_labels_and_shape_swaps_no_inference',
        v10_protocol=core.ref(protocol),sources=sources,inventory=all_inventory,parameters=core.PARAMETERS,new_optimizer_updates=0,
        inference=False,GT_used_only_for_posthoc_labels=True,test_read=False)
    with (output/'complete.json').open('x',encoding='utf-8') as stream:stream.write(core.canonical(value)+'\n')
    return dict(status=value['status'],inventory=all_inventory)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--v10-protocol',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--execute',action='store_true');a=p.parse_args()
    print(core.canonical(prepare(a.v10_protocol,a.output) if a.execute else dict(status='readonly_mechanism_input_plan')))
