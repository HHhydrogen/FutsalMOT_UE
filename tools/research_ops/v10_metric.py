"""v10五场独立TrackEval/断档评价；ID0合法，DO_PREPROC=False，不筛预测。"""
import argparse
from contextlib import redirect_stdout
from collections import defaultdict
import inspect
import io
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import v10_tracking_runtime as rt
from v10_gap_registry import gap_numeric


def plain(v):
    if isinstance(v,dict):return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [plain(x) for x in v]
    if hasattr(v,'tolist'):return plain(v.tolist())
    if hasattr(v,'item'):return v.item()
    return v


def prediction_rows(text,frames):
    predictions=defaultdict(list);seen=set()
    for line in text.splitlines():
        if not line:continue
        a=list(map(float,line.split(',')))
        rt.require(len(a)==10 and all(math.isfinite(x) for x in a) and a[0].is_integer()
            and 1<=a[0]<=frames and a[1].is_integer() and a[1]>0 and min(a[4:6])>0,'预测行非法，不静默过滤')
        key=(int(a[0]),int(a[1]));rt.require(key not in seen,'预测同帧身份重复');seen.add(key)
        predictions[key[0]].append(dict(uid=str(key[1]),bbox_xywh_px=a[2:6]))
    return dict(predictions),len(seen)


def validate_count(name,value,predicted,gt,sequence,frames):
    rt.require(value['Dets']==predicted and value['GT_Dets']==gt,'评价丢弃了预测/GT行')
    if name==sequence:rt.require(value['Frames']==frames,'实际单序列帧数改变')
    else:rt.require(name=='COMBINED_SEQ','未知汇总域')


def trackeval_numeric(source,gt,prediction_directory,output):
    """保持原MOT适配和HOTA/CLEAR/Identity口径；SportsMOT不伪造gameinfo。"""
    import trackeval
    rt.require(trackeval.__version__=='1.3.0','固定TrackEval1.3.0')
    sequence=source['sequence'];frames=source['frames'];prediction_directory=Path(prediction_directory)
    root=output/'derived_player_gt';folder=root/sequence/'gt';folder.mkdir(parents=True)
    (folder/'gt.txt').write_text('\n'.join(gt)+'\n',encoding='utf-8')
    (root/sequence/'seqinfo.ini').write_text('[Sequence]\nname='+sequence+'\nimDir=img1\nframeRate=25\nseqLength='+str(frames)+
        '\nimWidth='+str(source['width'])+'\nimHeight='+str(source['height'])+'\nimExt=.jpg\n',encoding='utf-8')
    capture=io.StringIO()
    dataset_config=dict(GT_FOLDER=str(root),TRACKERS_FOLDER=str(prediction_directory.parent),OUTPUT_FOLDER=str(output/'trackeval'),
        TRACKERS_TO_EVAL=[prediction_directory.name],SKIP_SPLIT_FOL=True,SEQ_INFO={sequence:frames},DO_PREPROC=False,
        BENCHMARK='MOT17',SPLIT_TO_EVAL='train',PRINT_CONFIG=False,CLASSES_TO_EVAL=['pedestrian'],TRACKER_SUB_FOLDER='data',INPUT_AS_ZIP=False)
    settings=dict(USE_PARALLEL=False,PRINT_CONFIG=False,PRINT_RESULTS=False,PLOT_CURVES=False,TIME_PROGRESS=False,
        OUTPUT_SUMMARY=True,OUTPUT_DETAILED=True,BREAK_ON_ERROR=True,LOG_ON_ERROR=str(output/'errors.txt'))
    with redirect_stdout(capture):
        evaluator=trackeval.Evaluator(settings);dataset=trackeval.datasets.MotChallenge2DBox(dataset_config)
        rt.require(dataset.do_preproc is False,'不得按GT预处理/过滤预测')
        metrics=[trackeval.metrics.HOTA(),trackeval.metrics.CLEAR(dict(PRINT_CONFIG=False)),trackeval.metrics.Identity(dict(PRINT_CONFIG=False))]
        results,messages=evaluator.evaluate([dataset],metrics)
    rt.require(messages['MotChallenge2DBox'][prediction_directory.name]=='Success','TrackEval未成功')
    raw=plain(results['MotChallenge2DBox'][prediction_directory.name]);rt.require(set(raw)=={sequence,'COMBINED_SEQ'},'评价scope扩大')
    (output/'stdout.txt').write_text(capture.getvalue(),encoding='utf-8')
    source_sha={str(Path(inspect.getfile(type(x)))):rt.sha(inspect.getfile(type(x))) for x in [evaluator,dataset]+metrics}
    return raw,source_sha


def evaluate(config,tracking,output):
    cfg,runtime,train,numeric,base,old=rt.validate_config(config);tracking=Path(tracking)
    receipt=rt.read(tracking/'receipt.json');job=receipt['job'];sequence=job['sequence'];source=cfg['sources'][sequence]
    rt.require(receipt['schema']=='v10_independent_free_tracking_v1' and receipt['status']=='complete'
        and receipt['protocol_sha256']==rt.sha(config) and receipt['GT_read'] is False
        and job in cfg['tracking_matrix'] and receipt['cache']==source['cache'] and receipt['frames']==source['frames'],'独立追踪身份不符')
    mot=tracking/'data'/(sequence+'.txt');rt.require(rt.sha(mot)==receipt['mot_sha256'],'预测MOT变化')
    predictions,count=prediction_rows(mot.read_text(encoding='utf-8'),source['frames']);rt.require(count==receipt['tracked_rows'],'预测行数改变')
    gt_dict,gt=rt.load_gt(source)
    output=runtime.storage().physical_child(output,rt.V);rt.require(not output.exists(),'新评价输出，partial不覆盖');output.mkdir(parents=True)
    raw,numerical_sha=trackeval_numeric(source,gt,tracking,output);summary={}
    for name,classes in raw.items():
        value=classes['pedestrian'];validate_count(name,value['Count'],count,len(gt),sequence,source['frames']);fraction={}
        for group,keys in [('HOTA',('HOTA','AssA','DetA')),('Identity',('IDF1',)),('CLEAR',('MOTA',))]:
            for key in keys:
                v=value[group][key];fraction[key]=sum(v)/len(v) if isinstance(v,list) else float(v)
        summary[name]=dict(metrics_fraction=fraction,metrics_percent={k:100*v for k,v in fraction.items()},IDSW_count=int(value['CLEAR']['IDSW']))
    registry=rt.read(rt.checked(cfg['registry']));rt.require(registry['sources']==cfg['sources'],'断档注册来源不同')
    selected=[e for e in registry['events'] if e['sequence']==sequence]
    gap=gap_numeric(old);recovery=gap.evaluate_events(selected,registry['sequences'][sequence]['endpoint_GT'],predictions)
    rt.require(recovery['overall']['total_events']==len(selected),'必须全部注册事件为分母')
    result=dict(schema='v10_independent_trackeval_gap_v1',status='complete',protocol_sha256=rt.sha(config),job=job,
        sequence=sequence,frames=source['frames'],summary=summary,raw_results=raw,recovery=recovery,
        registry_sha256=cfg['registry']['sha256'],tracking_receipt_sha256=rt.sha(tracking/'receipt.json'),GT_rows=len(gt),
        GT_selection=source['GT_selection'],GT_identity0_preserved=True,DO_PREPROC=False,predictions_GT_filtered=False,
        GT_used_only_for_metric=True,test_read=False,numerical_source_sha256=numerical_sha)
    (output/'report.json').write_text(rt.canonical(result)+'\n',encoding='utf-8');return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','tracking','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--execute',action='store_true');a=p.parse_args()
    print(rt.canonical(evaluate(a.config,a.tracking,a.output) if a.execute else dict(status='readonly_v10_metric_candidate_no_GT_read')))
