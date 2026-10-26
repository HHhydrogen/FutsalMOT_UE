"""v10五场可信检测断档proxy事前登记；复用v8端点规则，不是物理遮挡。"""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import v10_tracking_runtime as rt


def gap_numeric(old):return rt.load_file('v10_reference_gap_numeric',Path(old['bundle'])/'tools/research_ops/v8_gap_recovery.py')


def register(training_protocol,output):
    runtime,train,numeric,base,old=rt.training(training_protocol)
    sources=rt.sources_from(train,rt.read(rt.checked(train['prediction_manifest'])))
    gap=gap_numeric(old);events=[];registered={}
    output=runtime.storage().physical_child(output,rt.V);rt.require(not output.exists(),'断档注册输出已存在，不覆盖')
    for seq,source in sources.items():
        frames=rt.rows(rt.checked(source['cache']));rt.require(len(frames)==source['frames'],'完整输入帧不足')
        for frame in frames:rt.validate_frame(frame,sources)
        rt.require([f['frame_number'] for f in frames]==list(range(1,source['frames']+1)),'帧顺序/空检测帧不完整')
        gt,_=rt.load_gt(source)
        selected,audit,endpoints=gap.build_events(seq,{f['frame_number']:f['detections'] for f in frames},gt)
        events.extend(selected);registered[seq]=dict(frames=source['frames'],game=source['game'],audit=audit,
            endpoint_GT=endpoints,cache=source['cache'],evaluation_domain=source['evaluation_domain'])
    result=dict(schema='v10_five_match_trusted_gap_registry_v1',status='complete_five_matches_gap_registry_before_tracking',
        registered_utc=datetime.now(timezone.utc).isoformat(),training_protocol=dict(path=str(training_protocol),sha256=rt.sha(training_protocol)),
        sources=sources,sequences=registered,events=events,event_count=len(events),
        old_event_count=sum(e['sequence'] in rt.OLD for e in events),external_event_count=sum(e['sequence'] in rt.EXTERNAL for e in events),
        original_gap_implementation=dict(path=gap.__file__,sha256=rt.sha(gap.__file__)),
        rules=dict(raw_endpoint='bidirectional unique IoU>=.5',missing='no trusted match between consecutive trusted same-ID endpoints',
            missing_min=2,endpoint_interval_max_frames=30,continuous_annotation=True,
            prediction_endpoint='same bidirectional unique IoU>=.5 against all endpoint player GT',
            denominator='all registered events in complete evaluated sequence including missing/ambiguous/different-ID failures'),
        distinction='trusted detection-gap proxy can include ambiguous raw matches; not the synthetic no-any-raw-box gap rule or physical occlusion',
        tracking_results_read=False,test_read=False,GPU_used=False,new_R_training_exposure=0)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:stream.write(rt.canonical(result)+'\n')
    return dict(status=result['status'],event_count=len(events),old=result['old_event_count'],external=result['external_event_count'],sha256=rt.sha(output))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--training-protocol',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    print(rt.canonical(register(a.training_protocol,a.output) if a.execute else dict(status='readonly_registry_plan_no_GT_read')))
