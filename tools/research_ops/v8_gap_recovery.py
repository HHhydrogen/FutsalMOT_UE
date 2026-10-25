"""固定输入的可信检测断档proxy注册与端点身份恢复评价；不代表物理遮挡。"""
import argparse
from collections import Counter,defaultdict
import configparser
import hashlib
import json
import math
from pathlib import Path
import re
SCOPE={'SNMOT-060':'game4','SNMOT-097':'game6','SNMOT-151':'game9'}
RESEARCH=Path('D:/projects/FutsalMOT_Research')
def require(ok,message):
    if not ok:raise ValueError(message)
def safe(path):
    path=Path(path).absolute();require(not any(re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',p.lower()) or p.lower()=='test' for p in path.parts),'封存测试禁止读取');return path
def sha(path):return hashlib.sha256(safe(path).read_bytes()).hexdigest()
def read(path):return json.loads(safe(path).read_text(encoding='utf-8-sig'))
def checked(ref):
    p=safe(ref['path']);require(p.is_file() and sha(p)==ref['sha256'],'绑定元数据变化:'+str(p));return p
def valid_box(box):return len(box)==4 and all(isinstance(v,(int,float)) and math.isfinite(v) for v in box) and min(box[2:])>0
def iou(a,b):
    x,y,w,h=a;u,v,s,t=b;intersection=max(0,min(x+w,u+s)-max(x,u))*max(0,min(y+h,v+t)-max(y,v));union=w*h+s*t-intersection;return intersection/union if union>0 else 0.
def trusted(detections,gt):
    """返回GT身份到唯一预测的匹配；任一方向多候选均保持歧义。"""
    edges=[[j for j,g in enumerate(gt) if iou(d['bbox_xywh_px'],g['bbox_xywh_px'])>=.5] for d in detections];degrees=Counter(j for row in edges for j in row);matches={};states={g['gt_id']:'missing' for g in gt}
    for i,row in enumerate(edges):
        for j in row:states[gt[j]['gt_id']]='ambiguous'
        if len(row)==1 and degrees[row[0]]==1:identity=gt[row[0]]['gt_id'];matches[identity]=detections[i];states[identity]='matched'
    return matches,states
def build_events(sequence,frames,gt):
    """只在相邻可信端点间建事件，GT连续有效限定在查看学习结果前固定。"""
    histories=defaultdict(list);audit=Counter();events=[];endpoint_gt={}
    for frame in sorted(frames):
        good=[g for g in gt.get(frame,[]) if valid_box(g['bbox_xywh_px'])];matches,_=trusted(frames[frame],good)
        for identity,det in matches.items():histories[identity].append((frame,det['uid']))
    for identity,observations in sorted(histories.items()):
        for (start,start_uid),(end,end_uid) in zip(observations,observations[1:]):
            audit['total_consecutive_trusted_endpoint_intervals']+=1
            missing=end-start-1
            if missing<2:audit['excluded_fewer_than_2_missing']+=1;continue
            audit['candidate_trusted_endpoint_intervals']+=1
            if end-start>30:audit['excluded_endpoint_interval_over_30_frames']+=1;continue
            if not all(any(g['gt_id']==identity and valid_box(g['bbox_xywh_px']) for g in gt.get(frame,[])) for frame in range(start,end+1)):
                audit['excluded_not_continuously_annotated']+=1;continue
            stratum='2-4' if missing<=4 else ('5-9' if missing<=9 else '10-29')
            event=dict(sequence=sequence,gt_id=identity,start_frame_number=start,end_frame_number=end,missing_frames=missing,stratum=stratum,start_raw_uid=start_uid,end_raw_uid=end_uid)
            event['event_uid']=hashlib.sha256(json.dumps(event,sort_keys=True,separators=(',',':')).encode()).hexdigest();events.append(event);audit['included_events']+=1;audit['included_missing_'+stratum]+=1
            for frame in (start,end):endpoint_gt[str(frame)]=[g for g in gt[frame] if valid_box(g['bbox_xywh_px'])]
    return events,dict(audit),endpoint_gt
def load_source(source):
    sequence=source['sequence'];require(sequence in SCOPE and SCOPE[sequence]==source['game'] and source['first_frame']==0 and source['last_frame']==749 and source['fps']==25,'仅三比赛固定750帧train源')
    game=configparser.ConfigParser();game.read(checked(source['gameinfo']),encoding='utf-8-sig');seq=configparser.ConfigParser();seq.read(checked(source['seqinfo']),encoding='utf-8-sig')
    require('game'+game['Sequence']['gameID']==source['game'] and seq['Sequence']['name']==sequence and float(seq['Sequence']['frameRate'])==25,'真实比赛/序列身份不符')
    players={str(int(k.split('_')[-1])) for k,v in game['Sequence'].items() if k.startswith('trackletid_') and (v.strip().lower().startswith('player ') or v.strip().lower().startswith('goalkeeper'))};require(players,'player/keeper roster缺失');gt=defaultdict(list)
    for line in checked(source['gt']).read_text(encoding='utf-8-sig').splitlines():
        a=line.split(',');frame,identity=int(a[0]),str(int(a[1]));box=list(map(float,a[2:6]))
        if 1<=frame<=750 and identity in players and int(float(a[6]))==1 and valid_box(box):gt[frame].append(dict(gt_id=identity,bbox_xywh_px=box))
    frames={}
    for line in checked(source['cache']).read_text(encoding='utf-8-sig').splitlines():
        if not line.strip():continue
        f=json.loads(line);index=f['frame_index'];require(f['sequence']==sequence and f['game']==source['game'] and f['frame_number']==index+1 and 0<=index<750 and index+1 not in frames and f['fps']==25 and abs(f['timestamp_sec']-index/25)<1e-9,'raw帧身份/范围变化')
        require(all(valid_box(d['bbox_xywh_px']) for d in f['detections']),'raw正面积框无效');frames[index+1]=f['detections']
    require(set(frames)==set(range(1,751)),'必须含全部750帧（含空检测帧）');return frames,gt
def write(path,value):
    path=Path(path).resolve();require(RESEARCH in path.parents and not path.exists(),'输出必须新建DResearch文件，不覆盖');path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
def register(config,output):
    cfg=read(config);sources=[s for s in cfg['sources'] if s['domain']=='real'];require(sorted(s['sequence'] for s in sources)==sorted(SCOPE),'固定三比赛必须齐全');sequences={};events=[]
    for source in sources:
        frames,gt=load_source(source);selected,audit,endpoints=build_events(source['sequence'],frames,gt);events.extend(selected);sequences[source['sequence']]=dict(game=source['game'],frames=750,audit=audit,endpoint_GT=endpoints,bindings={k:source[k] for k in ('cache','gt','gameinfo','seqinfo')})
    value=dict(schema='v8_trusted_detection_gap_proxy_registry',status='complete_predeclared_detection_gap_registry',source_config=dict(path=str(safe(config)),sha256=sha(config)),implementation_sha256=sha(__file__),sequences=sequences,events=events,event_count=len(events),rules=dict(raw_endpoint='bidirectional_unique_IoU>=0.5',missing='no trusted raw match between consecutive trusted endpoints of same GT ID',missing_min=2,endpoint_interval_max_frames=30,strata=['2-4','5-9','10-29'],continuous_annotation='same player/keeper GT with valid positive-area bbox in every interval frame; missing annotation excluded before learning results',prediction_endpoint='bidirectional_unique_IoU>=0.5 against all endpoint player/keeper GT',denominator='all registered events in evaluated sequence, including missing/ambiguous/wrong-ID failures',meaning='detection-gap proxy, not physical occlusion'),test_read=False,GPU_used=False)
    write(output,value);return dict(status=value['status'],event_count=len(events),registry_sha256=sha(output))
def evaluate_events(events,endpoint_gt,predictions):
    counts=Counter(total_events=len(events));strata={key:Counter(total_events=sum(e['stratum']==key for e in events)) for key in ('2-4','5-9','10-29')};details=[];matched={}
    for frame,gt in endpoint_gt.items():matched[int(frame)]=trusted(predictions.get(int(frame),[]),gt)
    for e in events:
        a,sa=matched[e['start_frame_number']];b,sb=matched[e['end_frame_number']];identity=e['gt_id'];states=[sa.get(identity,'missing'),sb.get(identity,'missing')]
        if 'ambiguous' in states:reason='ambiguous_endpoint'
        elif 'missing' in states:reason='missing_prediction_endpoint'
        elif a[identity]['uid']!=b[identity]['uid']:reason='different_prediction_ID'
        else:reason='same_prediction_ID_recovered'
        for counter in (counts,strata[e['stratum']]):
            counter[reason]+=1;counter['events_with_missing_endpoint']+=int('missing' in states);counter['events_with_ambiguous_endpoint']+=int('ambiguous' in states)
        details.append(dict(event_uid=e['event_uid'],reason=reason,endpoint_states=states,start_prediction_ID=a.get(identity,{}).get('uid'),end_prediction_ID=b.get(identity,{}).get('uid')))
    def result(c):return dict(c,recovery_rate=c['same_prediction_ID_recovered']/c['total_events'] if c['total_events'] else None)
    return dict(overall=result(counts),strata={k:result(v) for k,v in strata.items()},events=details)
def evaluate(registry,tracking,output):
    registry_value=read(registry);require(registry_value['schema']=='v8_trusted_detection_gap_proxy_registry' and registry_value['status']=='complete_predeclared_detection_gap_registry' and registry_value['implementation_sha256']==sha(__file__),'registry身份/冻结实现不符');checked(registry_value['source_config']);tracking=safe(tracking);receipt=read(tracking/'receipt.json') if (tracking/'receipt.json').is_file() else None
    selected=[receipt['sequence']] if receipt else list(SCOPE);require(set(selected)<=set(SCOPE),'不准扩展scope');reports={}
    for sequence in selected:
        entry=registry_value['sequences'][sequence]
        for ref in entry['bindings'].values():checked(ref)
        file=tracking/'data'/(sequence+'.txt');text=safe(file).read_text(encoding='utf-8');predictions=defaultdict(list);seen=set()
        if receipt:require(receipt['status']=='complete' and receipt['frames']==750 and receipt['sequence']==sequence and receipt['mot_sha256']==sha(file),'tracking收据/MOT身份不符')
        for line in text.splitlines():
            if not line.strip():continue
            a=list(map(float,line.split(',')));require(len(a)==10 and all(math.isfinite(v) for v in a) and a[0].is_integer() and 1<=a[0]<=750 and a[1].is_integer() and a[1]>0 and valid_box(a[2:6]),'预测行非法，不自动过滤');frame,identity=int(a[0]),str(int(a[1]));require((frame,identity) not in seen,'重复预测同帧ID');seen.add((frame,identity));predictions[frame].append(dict(uid=identity,bbox_xywh_px=a[2:6]))
        events=[e for e in registry_value['events'] if e['sequence']==sequence];reports[sequence]=dict(evaluate_events(events,entry['endpoint_GT'],predictions),prediction_sha256=sha(file),prediction_rows=len(seen))
    result=dict(schema='v8_gap_proxy_recovery_evaluation',registry=dict(path=str(safe(registry)),sha256=sha(registry)),implementation_sha256=sha(__file__),sequences=reports,predictions_GT_filtered=False,denominator='all preregistered events within selected complete sequence',scope_selection='complete tracking receipt sequence, or all three when no receipt',interpretation='endpoint identity recovery on trusted detection-gap proxy; not physical occlusion recovery',GT_used_only_for_metric=True,test_read=False,GPU_used=False);write(output,result);return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-config',type=Path);p.add_argument('--registry-output',type=Path);p.add_argument('--registry',type=Path);p.add_argument('--tracking',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    require(bool(a.source_config and a.registry_output)!=bool(a.registry and a.tracking and a.output),'二选一：注册固定输入，或评价已注册事件');print(json.dumps(register(a.source_config,a.registry_output) if a.source_config else evaluate(a.registry,a.tracking,a.output),ensure_ascii=False))
