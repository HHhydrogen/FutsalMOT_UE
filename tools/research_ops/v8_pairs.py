"""v8固定预测输入的身份窗口：GT只标注，比赛隔离，实际观测与固定窗口曝光。"""
import argparse
from collections import Counter, defaultdict
import configparser
import hashlib
import heapq
import json
import math
from pathlib import Path
import sys

PROJECT=Path(__file__).resolve().parents[2]
RESEARCH=Path('D:/projects/FutsalMOT_Research')
GAMES=('game4','game6','game9')
GAPS=(0.,.2,.4,.8,1.2)
SEEDS=(20261024,20261025,20261026)
PRED_FIELDS=('uid','bbox_xywh_px','score','xy_px','geometry_valid','image_wh','timestamp_sec')


def require(ok,msg):
    if not ok:raise ValueError(msg)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()


def key(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def rows(path):
    with Path(path).open(encoding='utf-8-sig') as f:
        for line in f:
            if line.strip():yield json.loads(line)


def bound(binding):
    path=Path(binding['path']).absolute()
    require(path.suffix.lower() in ('.json','.jsonl','.txt','.ini'),f'只读元数据: {path}')
    require(path.is_file() and sha(path)==binding['sha256'],f'绑定变化/缺失: {path}')
    require('SNMOT-116' not in str(path) and 'SNMOT-187' not in str(path),'最终test封存')
    return path


def iou(a,b):
    ax,ay,aw,ah=a;bx,by,bw,bh=b
    inter=max(0,min(ax+aw,bx+bw)-max(ax,bx))*max(0,min(ay+ah,by+bh)-max(ay,by))
    union=aw*ah+bw*bh-inter
    return inter/union if union>0 else 0.


def match_labels(detections,gt):
    """双向唯一IoU>=.5；低重叠与竞争保留unknown，避免框风格差异冒充硬负例。"""
    overlaps=[[iou(d['bbox_xywh_px'],g['bbox_xywh_px']) for g in gt] for d in detections]
    edges=[[j for j,v in enumerate(values) if v>=.5] for values in overlaps]
    degrees=Counter(j for matches in edges for j in matches)
    output={}
    for det,matches,values in zip(detections,edges,overlaps):
        if len(matches)==1 and degrees[matches[0]]==1:
            output[det['uid']]={'state':'matched','gt_id':gt[matches[0]]['gt_id']}
        elif matches:output[det['uid']]={'state':'unknown_conflict','gt_id':None}
        elif any(v>=.1 for v in values):output[det['uid']]={'state':'unknown_low_overlap','gt_id':None}
        else:output[det['uid']]={'state':'unmatched','gt_id':None}
    return output


def real_gt(source):
    info=configparser.ConfigParser();info.read(bound(source['gameinfo']),encoding='utf-8-sig')
    sequence=configparser.ConfigParser();sequence.read(bound(source['seqinfo']),encoding='utf-8-sig')
    s=info['Sequence'];q=sequence['Sequence']
    require('game'+s['gameID']==source['game'] and q['name']==source['sequence'],'实际比赛/sequence不匹配')
    require(float(q['frameRate'])==source['fps'],'实际fps不同')
    players={int(k.split('_')[-1]) for k,v in s.items() if k.startswith('trackletid_')
             and (v.strip().lower().startswith('player ') or v.strip().lower().startswith('goalkeeper'))}
    require(players,'gameinfo没有player/goalkeeper')
    result=defaultdict(list)
    for line in bound(source['gt']).read_text(encoding='utf-8-sig').splitlines():
        x=line.split(',');frame,identity=int(x[0]),int(x[1])
        if identity in players and int(float(x[6]))==1:
            result[frame].append(dict(gt_id=str(identity),bbox_xywh_px=list(map(float,x[2:6]))))
    return result


def synthetic_gt(source):
    require(source['seed']==1048 and source['floor']=='sport_blue_v1','S仅1048蓝地板，1102不入训练')
    path=bound(source['annotations'])
    require(Path('G:/FutsalMOT_Dataset') in path.parents,'S标注仅G成品')
    result={}
    for record in rows(path):
        # GT姿态字段刻意不读取；实体身份/visible框仅用于训练标签。
        result[record['frame_index']]=[dict(gt_id=str(o['entity_id']),bbox_xywh_px=o['bbox_visible_xywh'])
                                      for o in record['objects'] if o['bbox_visible_xywh'] is not None]
    return result


def load_source(source):
    require(source['domain'] in ('real','synthetic'),'domain错误')
    if source['domain']=='real':
        require(source['game'] in GAMES and source['sequence'] in ('SNMOT-060','SNMOT-097','SNMOT-151'),'真实源越界')
    gt=real_gt(source) if source['domain']=='real' else synthetic_gt(source)
    frames={};audit=Counter();seen=set()
    for frame in rows(bound(source['cache'])):
        index=frame['frame_index']
        require(frame['frame_number']==index+1,'frame_number必须显式为1-based index+1，GT禁止用index直接连接')
        require(index not in frames and frame['sequence']==source['sequence'] and frame['game']==source['game'],'cache身份/帧重复')
        require(float(frame['fps'])==source['fps'],'cache fps不匹配')
        require(abs(frame['timestamp_sec']-index/source['fps'])<=1e-9,'缓存timestamp必须index/fps')
        require(source['first_frame']<=index<=source['last_frame'],'cache帧超配置范围')
        detections=[]
        for original in frame['detections']:
            det={k:original[k] for k in PRED_FIELDS}
            require(det['uid'] not in seen,'预测uid必须全sequence唯一');seen.add(det['uid'])
            require(det['timestamp_sec']==frame['timestamp_sec'],'预测/frame时间不一致')
            require(det['image_wh']==[frame['width'],frame['height']],'预测/frame尺寸不一致')
            require(len(det['bbox_xywh_px'])==4 and min(det['bbox_xywh_px'][2:])>0,'预测框无效')
            require(len(det['xy_px'])==17,'预测必须COCO17，不能用GT Pose替代')
            require(len(det['geometry_valid'])==17 and all(type(v) is bool for v in det['geometry_valid']),
                    'geometry_valid必须17个逐关节bool')
            require(all(isinstance(xy,list) and len(xy)==2 and all(isinstance(v,(float,int)) and math.isfinite(v) for v in xy)
                        for xy in det['xy_px']), 'xy_px必须17×2有限值，无Pose用零+False')
            detections.append(det)
        gt_frame=frame['frame_number'] if source['domain']=='real' else index
        labels=match_labels(detections,gt.get(gt_frame,[]));audit.update(x['state'] for x in labels.values())
        frames[index]=dict(frame_index=index,frame_number=frame['frame_number'],timestamp_sec=frame['timestamp_sec'],detections=detections,labels=labels)
    require(len(frames)==source['last_frame']-source['first_frame']+1,'cache必须含完整声明连续帧，包括零检测帧')
    ordered=sorted(frames)
    require(all(frames[b]['timestamp_sec']>frames[a]['timestamp_sec'] for a,b in zip(ordered,ordered[1:])),'cache时间不递增')
    return frames,dict(audit)


def enumerate_windows(source,frames,gate,audit=None):
    fps=source['fps']
    matched={}
    for index,frame in frames.items():
        matched[index]={frame['labels'][d['uid']]['gt_id']:d for d in frame['detections']
                        if frame['labels'][d['uid']]['state']=='matched'}
    for current in sorted(frames):
        for gap in GAPS:
            last=current-max(1,math.floor(gap*fps+.5));history_frames=(last-2,last-1,last)
            if any(i not in matched for i in history_frames):continue
            common=set(matched[history_frames[0]])&set(matched[history_frames[1]])&set(matched[history_frames[2]])
            for identity in sorted(common):
                history=[matched[i][identity] for i in history_frames]
                candidates=[]
                for prediction in frames[current]['detections']:
                    if not gate(history,prediction)['accepted']:continue
                    label=frames[current]['labels'][prediction['uid']]
                    value=None if label['state'].startswith('unknown') else int(label['state']=='matched' and label['gt_id']==identity)
                    candidates.append(dict(prediction=prediction,label=value,label_reason=label['state']))
                dt=frames[current]['timestamp_sec']-history[-1]['timestamp_sec']
                if not candidates or (len(candidates)<2 and dt<.12-1e-9):continue
                if audit is not None:audit['difficult_windows_before_known_filter']+=1
                if not any(c['label'] is not None for c in candidates):
                    if audit is not None:audit['filtered_all_unknown_windows']+=1
                    continue
                # UID只由实际观测身份定义，不能靠请求gap标签伪造unique。
                uid=key([source['domain'],source['sequence'],current,identity,history_frames])
                yield dict(window_uid=uid,domain=source['domain'],sequence=source['sequence'],game=source['game'],
                    fps=fps,gap_requested_sec=gap,gap_mode='native_next_frame' if gap==0 else 'requested_seconds',
                    gap_actual_sec=dt,history=history,
                    history_frame_indices=list(history_frames),candidate_frame_index=current,
                    candidate_frame_number=current+1,candidates=candidates,
                    supervision=dict(query_gt_id=identity,teacher_forced_history=True,
                        positives=sum(c['label']==1 for c in candidates),unknown=sum(c['label'] is None for c in candidates)),
                    difficulty=dict(candidate_count=len(candidates),long_observation_gap=dt>=.12-1e-9,
                        definition='candidate_count>=2 OR actual observation gap>=.12s; not physical occlusion GT'),
                    stratum=[source['camera'] if source['domain']=='synthetic' else source['game'],gap])


class BalancedPool:
    """每stratum只保留固定配额的最小SHA窗口，内存有界，不按模型结果挑样。"""
    def __init__(self,strata,count=1000):
        strata=sorted(strata);self.quotas={s:count//len(strata)+(i<count%len(strata)) for i,s in enumerate(strata)}
        self.heaps={s:[] for s in strata};self.available=Counter()
    def add(self,window):
        s=tuple(window['stratum']);require(s in self.heaps,'未知stratum')
        self.available[s]+=1;h=self.heaps[s];entry=(-int(window['window_uid'],16),window['window_uid'],window)
        if len(h)<self.quotas[s]:heapq.heappush(h,entry)
        elif entry>h[0]:heapq.heapreplace(h,entry)
    def finish(self):
        for s,q in self.quotas.items():require(len(self.heaps[s])==q,f'窗口池不足，不重复补足: {s},available={self.available[s]},need={q}')
        result=sorted((entry[2] for heap in self.heaps.values() for entry in heap),key=lambda w:w['window_uid'])
        require(len({w['window_uid'] for w in result})==len(result),'窗口池有重复')
        return result


def exposures(real,synthetic,seed):
    r=[]
    for epoch in range(3):
        ordered=sorted(real,key=lambda w:key(['R',seed,epoch,w['window_uid']]))
        r.extend(dict(window_uid=w['window_uid'],domain='real',epoch=epoch,
                      candidate_pairs=len(w['candidates']),labelled_pairs=sum(c['label'] is not None for c in w['candidates'])) for w in ordered)
    s=[dict(window_uid=w['window_uid'],domain='synthetic',epoch=0,candidate_pairs=len(w['candidates']),
            labelled_pairs=sum(c['label'] is not None for c in w['candidates']))
       for w in sorted(synthetic,key=lambda w:key(['S',seed,w['window_uid']]))]
    return dict(real=r,synthetic=s,accounting=dict(real_window_exposures=len(r),synthetic_window_exposures=len(s),
                real_candidate_pair_exposures=sum(x['candidate_pairs'] for x in r),
                synthetic_candidate_pair_exposures=sum(x['candidate_pairs'] for x in s)),
                reuse='all four arms share R order; both RS arms share S order; windows are not source image exposures')


def dump(path,obj):
    with path.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')


def dump_rows(path,items):
    with path.open('x',encoding='utf-8') as f:
        for item in items:f.write(json.dumps(item,ensure_ascii=False,separators=(',',':'))+'\n')


def build(config_path,output):
    config=read(config_path);output=Path(output).absolute()
    require(config['schema']=='v8_pair_build_config_v1','config schema错误')
    require(RESEARCH in output.parents and not output.exists(),'输出必须全新DResearch目录；partial拒绝覆盖')
    sys.path.insert(0,str(PROJECT/'python/src'))
    from grf_ue_bridge.learned_association_features_v8 import candidate_gate
    import grf_ue_bridge.learned_association_features_v8 as module
    require(sha(module.__file__)==config['gate_source_sha256'],'gate源绑定变化')
    real_sources=[s for s in config['sources'] if s['domain']=='real']
    synthetic=[s for s in config['sources'] if s['domain']=='synthetic']
    require(sorted(s['game'] for s in real_sources)==list(GAMES),'必须3个独立真实比赛')
    require(len(synthetic)==4 and len({s['camera'] for s in synthetic})==4,'必须1048蓝四相机')
    require(len({s['sequence'] for s in config['sources']})==len(config['sources']),'每源sequence必须唯一，四cam不可同名')
    require(all(s['first_frame']==0 and s['last_frame']==749 and s['fps']==25 for s in real_sources),'真实必须index0..749完整750帧@25fps')
    require(all(s['first_frame']==0 and s['last_frame']==299 and s['fps']==10 for s in synthetic),'合成必须300帧@10fps')
    real_pools={g:BalancedPool([(other,gap) for other in GAMES if other!=g for gap in GAPS]) for g in GAMES}
    s_pool=BalancedPool([(s['camera'],gap) for s in synthetic for gap in GAPS]);audit=[]
    for source in config['sources']:
        frames,labels=load_source(source);counts=Counter(filtered_all_unknown_windows=0,difficult_windows_before_known_filter=0,eligible_windows=0)
        for window in enumerate_windows(source,frames,candidate_gate,counts):
            counts['eligible_windows']+=1
            if source['domain']=='synthetic':s_pool.add(window)
            else:
                for heldout,pool in real_pools.items():
                    if heldout!=source['game']:pool.add(window)
        audit.append(dict(sequence=source['sequence'],game=source['game'],domain=source['domain'],
                          frames=len(frames),labelled_detection_states=labels,**dict(counts)))
    selected_s=s_pool.finish();selected_r={g:pool.finish() for g,pool in real_pools.items()}
    output.mkdir(parents=True)
    dump(output/'build_intent.json',dict(config_path=str(config_path),config_sha256=sha(config_path),status='writing'))
    dump_rows(output/'synthetic_pool.jsonl',selected_s)
    for heldout,r in selected_r.items():
        fold=output/('heldout_'+heldout);fold.mkdir()
        dump_rows(fold/'real_pool.jsonl',r)
        for seed in SEEDS:dump(fold/f'exposures_{seed}.json',exposures(r,selected_s,seed))
    receipt=dict(schema='v8_pairs_build_receipt_v1',status='complete_candidate_not_training_authorized',
        config_sha256=sha(config_path),gate_source_sha256=config['gate_source_sha256'],
        real_pool_unique_per_fold=1000,synthetic_pool_unique_shared=1000,source_audit=audit,
        pretraining_amendment='history uses last three consecutive actual prediction frames, matching free tracker cadence; no model-result-driven amendment',
        history_cadence='one original source frame, not .12 seconds; missing any required actual observation skips window',
        gap_requests_sec=list(GAPS),native_gap='0 means next source frame, actual max(1,round_half_up(gap*fps)) / fps',
        temporal_grid_amendment='before any v8 training/evaluation: .12 at10fps aliases native1frame, so final grid 0/.2/.4/.8/1.2 uses distinct integral frame gaps at25/10fps',
        unique_window_rule='UID uses actual history/current/query/sequence/domain only; no requested-gap labels; duplicate UID fails closed',
        source_frames_per_fold=dict(real_train=1500,heldout=750),
        GT_usage='training labels and teacher-forced history membership only; never model features/GT pose',
        heldout_usage='free-running whole sequence tracker evaluation; no GT teacher forcing',
        matching='bidirectional unique IoU>=.5; conflicts unknown; unmatched with max IoU>=.1 unknown_low_overlap; far unmatched can be query-specific negative',
        supervision_filter='exclude all-unknown windows before balanced pool; count per-source; valid-label availability, not model success',
        recovery_name='detection-gap proxy, not physical occlusion recovery',
        pool_selection='stable SHA balanced by train game/camera and requested time-gap; no model outcome selection')
    dump(output/'complete.json',receipt);return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    print(json.dumps(build(a.config,a.output),ensure_ascii=False))
