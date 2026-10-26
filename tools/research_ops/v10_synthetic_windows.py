"""v10四运动的平衡/困难合成窗口；只读共享预测，GT仅用于身份标签与事件诊断。"""
import argparse
from collections import Counter, defaultdict
import hashlib
import heapq
import importlib.util
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
import v8_pairs as pairs
from v10_prediction_inputs import WINDOWS, CAMERAS

RESEARCH=Path('D:/projects/FutsalMOT_Research')
DATASET=Path('G:/FutsalMOT_Dataset')
read=pairs.read; sha=pairs.sha; require=pairs.require


def synthetic_labels(source, annotation_path, expected_sha):
    require(source['domain']=='synthetic' and source['role']=='train' and source['seed'] in WINDOWS
            and source['camera'] in CAMERAS and source['fps']==10
            and source['first_frame']==0 and source['last_frame']==299, '不是四运动合成训练来源')
    result=defaultdict(list); seen=set(); digest=hashlib.sha256()
    with Path(annotation_path).open('rb') as stream:
        for line in stream:
            digest.update(line); row=json.loads(line); key=(row['frame_index'],row['entity_id'])
            require(key not in seen and key[0] in range(300)
                    and key[1] in {s+str(i) for s in 'LR' for i in range(5)}
                    and row['source_frame_index']==WINDOWS[source['seed']][0]+key[0], 'GT人物重复或源帧错位')
            seen.add(key)
            # 不提取uv_px/world/可见性作为网络输入；这里只使用实例可见框和身份。
            box=row['bbox_visible_xywh']; area=row['visible_mask_area']
            if area<=0:continue
            require(isinstance(box,list) and len(box)==4 and all(math.isfinite(v) for v in box)
                    and min(box[2:])>0, 'GT实例框非有限或退化')
            result[key[0]].append(dict(gt_id=key[1],bbox_xywh_px=box))
    require(len(seen)==3000 and digest.hexdigest()==expected_sha,'实际标注记录或SHA不符')
    return dict(result)


def load_predictions(source, gt):
    frames={}; audit=Counter(); seen=set()
    for frame in pairs.rows(pairs.bound(source['cache'])):
        index=frame['frame_index']
        require(index not in frames and index in range(300) and frame['sequence']==source['sequence']
                and frame['game']==source['game'] and frame['frame_number']==index+1
                and frame['source_frame_index']==WINDOWS[source['seed']][0]+index
                and frame['timestamp_sec']==index/10 and frame['fps']==10
                and [frame['width'],frame['height']]==[3840,2160]
                and frame['GT_used_for_predictions'] is False, '共享预测身份/时序或来源不同')
        detections=[]
        for original in frame['detections']:
            record={k:original[k] for k in pairs.PRED_FIELDS}
            require(record['uid'] not in seen and record['timestamp_sec']==frame['timestamp_sec']
                    and record['image_wh']==[3840,2160] and len(record['bbox_xywh_px'])==4
                    and min(record['bbox_xywh_px'][2:])>0 and 0<=record['score']<=1
                    and all(math.isfinite(v) for v in record['bbox_xywh_px'])
                    and len(record['xy_px'])==len(record['geometry_valid'])==17
                    and all(type(v) is bool for v in record['geometry_valid'])
                    and all(len(p)==2 and all(math.isfinite(v) for v in p) for p in record['xy_px']), '预测格式或UID重复')
            seen.add(record['uid']);detections.append(record)
        labels=pairs.match_labels(detections,gt.get(index,[]));audit.update(v['state'] for v in labels.values())
        frames[index]=dict(frame_index=index,frame_number=index+1,timestamp_sec=index/10,
                           detections=detections,labels=labels)
    require(set(frames)==set(range(300)),'预测必须完整300帧，包括零检测帧')
    return frames,dict(audit)


def gap_events(frames, gt):
    """连续有效GT中间2..29帧没有任何IoU>=.5检测；冲突匹配不冒称漏检。"""
    boxes={i:{g['gt_id']:g['bbox_xywh_px'] for g in rows} for i,rows in gt.items()}
    entities=sorted({g for rows in boxes.values() for g in rows});events=[]
    for entity in entities:
        valid={i for i,rows in boxes.items() if entity in rows}
        detected=sorted(i for i in valid if any(pairs.iou(d['bbox_xywh_px'],boxes[i][entity])>=.5
                                               for d in frames[i]['detections']))
        for before,after in zip(detected,detected[1:]):
            missing=after-before-1
            if 2<=missing<=29 and all(i in valid for i in range(before,after+1)):
                events.append(dict(gt_id=entity,before_frame=before,after_frame=after,missing_frames=missing,
                    definition='continuous_valid_mask_GT_and_no_raw_box_IoU_ge.5_between_endpoints',physical_occlusion_claim=False))
    return events,boxes


def describe_window(window, events, boxes):
    identity=window['supervision']['query_gt_id'];before=window['history_frame_indices'][-1]
    after=window['candidate_frame_index']
    natural=any(e['gt_id']==identity and e['before_frame']==before and e['after_frame']==after for e in events)
    overlap_frames=0
    for index in range(before,after+1):
        current=boxes.get(index,{})
        if identity in current and any(other!=identity and pairs.iou(current[identity],box)>=.1 for other,box in current.items()):
            overlap_frames+=1
    result=dict(window)
    result['difficulty']=dict(window['difficulty'],natural_detection_gap_proxy=natural,
        image_mask_box_overlap_proxy=overlap_frames>0,overlap_frames=overlap_frames,
        ranking_features='bbox_and_raw_detection_availability_only_no_Pose_quality_or_model_result',
        physical_occlusion_claim=False)
    return result


class HardPool(pairs.BalancedPool):
    """与平衡组相同camera×gap配额，在每格内按固定困难顺序取唯一窗口。"""
    def add(self,window):
        stratum=tuple(window['stratum']);require(stratum in self.heaps,'未知stratum')
        self.available[stratum]+=1;d=window['difficulty']
        score=(int(d['natural_detection_gap_proxy']),int(d['image_mask_box_overlap_proxy']),
               d['candidate_count'],-int(window['window_uid'],16))
        entry=(score,window['window_uid'],window);heap=self.heaps[stratum]
        if len(heap)<self.quotas[stratum]:heapq.heappush(heap,entry)
        elif entry>heap[0]:heapq.heapreplace(heap,entry)


def choose_pools(source_frames, gate):
    strata=[(camera,gap) for camera in CAMERAS for gap in pairs.GAPS]
    balanced={seed:pairs.BalancedPool(strata,count=250) for seed in WINDOWS}
    hard={seed:HardPool(strata,count=250) for seed in WINDOWS}
    audit=[];ledger=[];seen=set()
    for source,frames,gt,label_audit in source_frames:
        events,boxes=gap_events(frames,gt);ledger.extend(dict(e,sequence=source['sequence'],seed=source['seed']) for e in events)
        counts=Counter()
        for window in pairs.enumerate_windows(source,frames,gate,counts):
            require(window['window_uid'] not in seen,'实际观测窗口UID重复，不充配额');seen.add(window['window_uid'])
            window=describe_window(window,events,boxes);window['synthetic_seed']=source['seed']
            counts['eligible_windows']+=1
            counts['natural_gap_windows']+=int(window['difficulty']['natural_detection_gap_proxy'])
            counts['overlap_windows']+=int(window['difficulty']['image_mask_box_overlap_proxy'])
            balanced[source['seed']].add(window);hard[source['seed']].add(window)
        audit.append(dict(sequence=source['sequence'],seed=source['seed'],camera=source['camera'],
                          natural_gap_events=len(events),label_states=label_audit,**dict(counts)))
    result={name:sorted([w for seed in sorted(WINDOWS) for w in pools[seed].finish()],key=lambda w:w['window_uid'])
            for name,pools in (('balanced',balanced),('hard_enriched',hard))}
    for windows in result.values():
        require(len(windows)==len({w['window_uid'] for w in windows})==1000
                and Counter(w['synthetic_seed'] for w in windows)=={s:250 for s in WINDOWS}, '四seed配额不完整')
    summary={name:dict(windows=len(w),seed_counts=dict(Counter(x['synthetic_seed'] for x in w)),
                natural_gap_windows=sum(x['difficulty']['natural_detection_gap_proxy'] for x in w),
                image_overlap_windows=sum(x['difficulty']['image_mask_box_overlap_proxy'] for x in w),
                candidate_pairs=sum(len(x['candidates']) for x in w),known_pairs=sum(c['label'] is not None for x in w for c in x['candidates']))
             for name,w in result.items()}
    return result,dict(source_audit=audit,event_ledger=ledger,selected=summary,
                      pool_UID_overlap=len({w['window_uid'] for w in result['balanced']}&{w['window_uid'] for w in result['hard_enriched']}))


def build(config_path):
    config=read(config_path);bundle=ROOT
    require(config['schema']=='v10_synthetic_pool_config_v1' and config['approved_by']=='root'
            and config['pool_build_authorized'] is True and config['training_authorized'] is False,
            '缺独立窗口构建准入')
    require(bundle==Path(config['bundle']) and bundle.parent==RESEARCH/'code','只执行独立D代码bundle')
    for entry in config['code_files']:
        relative=Path(entry['path'])
        require(not relative.is_absolute() and not relative.drive and '..' not in relative.parts
                and sha(bundle/relative)==entry['sha256'],'源代码绑定改变')
    require(sha(Path(pairs.__file__))==config['pairs_source_sha256'],'原窗口/标签/间隔数值源改变')
    storage_path=bundle/'python/src/grf_ue_bridge/storage_policy.py'
    spec=importlib.util.spec_from_file_location('v10_pool_storage',storage_path);storage=importlib.util.module_from_spec(spec);spec.loader.exec_module(storage)
    storage.physical_child(bundle,RESEARCH/'code')
    for entry in config['code_files']:storage.physical_child(bundle/entry['path'],bundle)
    prediction_path=pairs.bound(config['prediction_manifest']);manifest=read(prediction_path)
    require(manifest['schema']=='v10_shared_prediction_cache_manifest_v1'
            and manifest['status']=='complete_18_sources_not_training_authorized'
            and manifest['synthetic_frames']==4800 and manifest['external_validation_frames']==1125
            and manifest['all_raw_detections_new_same_pipeline'] is True and manifest['old_blue_boxes_reused'] is False
            and manifest['GT_used_for_predictions'] is False and manifest['final116187_read'] is False,'共享预测未完整或来源改变')
    sources=[s for s in manifest['sources'] if s['domain']=='synthetic']
    require(len(sources)==16 and {(s['seed'],s['camera']) for s in sources}=={(s,c) for s in WINDOWS for c in CAMERAS},'必须四seed四机位；val不入训练')
    group_refs={}
    for field in ('dataset','old_dataset'):
        data_path=storage.physical_child(pairs.bound(manifest[field]),DATASET);data=read(data_path)
        for seed in WINDOWS:
            if (seed==1048)!=(field=='old_dataset'):continue
            entry=data['groups']['1048/B'] if seed==1048 else data['groups'][str(seed)]
            path=storage.physical_child(data_path.parent/entry['group_ref'],data_path.parent)
            require(sha(path)==entry['sha256'],'实际发布组SHA改变')
            group_refs[seed]=path
    require(set(config['source_annotations'])=={s['sequence'] for s in sources},'标注来源绑定未完整登记')
    feature_path=bundle/'python/src/grf_ue_bridge/learned_association_features_v8.py'
    require(sha(feature_path)==config['gate_source_sha256'],'原motion候选门槛改变')
    spec=importlib.util.spec_from_file_location('v10_same_candidate_gate',feature_path);features=importlib.util.module_from_spec(spec);spec.loader.exec_module(features)
    output=storage.physical_child(config['output'],RESEARCH/'pose/multiseed_v10_a01')
    require(not output.exists(),'已有或partial窗口输出不覆盖')
    output.mkdir(parents=True);pairs.dump(output/'intent.json',dict(status='started_not_complete',config_sha256=sha(config_path)))
    def inputs():
        for source in sources:
            group_path=storage.physical_child(source['capture_group_path'],DATASET)
            require(group_path==group_refs[source['seed']],'原始发布组路径重定向')
            group=read(group_path)
            camera=source['camera'];unit=storage.physical_child(group_path.parent/group['cameras'][camera]['capture_unit_ref'],DATASET)
            post=read(unit.parent/'postprocess_complete.json');require(len(post['views'])==1,'原单位不是单机位')
            annotation=storage.physical_child(source['annotation_path'],DATASET)
            require(annotation==group_path.parent/group['cameras'][camera]['pose2d_ref'],'实际GT引用重定向')
            declared=config['source_annotations'][source['sequence']]
            require(Path(declared['path'])==annotation and declared['sha256']==post['views'][0]['pose_jsonl']['sha256'],'冻结标注链不同')
            gt=synthetic_labels(source,annotation,declared['sha256'])
            frames,audit=load_predictions(source,gt)
            yield source,frames,gt,audit
    try:
        pools,audit=choose_pools(inputs(),features.candidate_gate)
        for regime,windows in pools.items():pairs.dump_rows(output/(regime+'.jsonl'),windows)
        pairs.dump(output/'audit.json',audit)
        result=dict(schema='v10_synthetic_pool_complete_v1',status='complete_two_pools_not_training_authorized',
            config_sha256=sha(config_path),prediction_manifest=config['prediction_manifest'],
            pools={name:dict(path=str(output/(name+'.jsonl')),sha256=sha(output/(name+'.jsonl'))) for name in pools},
            selection='same_seed250_camera_gap_quota; hard lexicographic natural_gap/image_overlap/candidate_count/SHA',
            fallback='within_same_stratum_rank_all_eligible; report_actual_event_counts_no_UID_duplication',
            natural_gap_denominator=sum(x['natural_gap_events'] for x in audit['source_audit']),
            external_validation_used_for_training=False,new_optimizer_updates=0,test_read=False)
        pairs.dump(output/'complete.json',result);return result
    except BaseException as error:
        pairs.dump(output/'failed.json',dict(status='failed_preserved_no_replay',error=repr(error)));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if args.execute:print(json.dumps(build(args.config),ensure_ascii=False))
    else:print(json.dumps(dict(status='CPU_candidate_plan_only',unique_windows_per_pool=1000,per_seed=250,
                              no_model_inference=True,new_optimizer_updates=0)))
