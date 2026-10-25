"""v8独立train域750帧TrackEval适配；GT只评价，不改旧scope守卫。"""
import argparse
import configparser
from contextlib import redirect_stdout
import inspect
import io
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tools/research_ops'),str(Path('D:/projects/FutsalMOT_Research/runtime_dependencies'))]
from v8_train import read,checked,require,sha
from v8_track import SEQUENCE,RESEARCH
def plain(v):
    if isinstance(v,dict):return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [plain(x) for x in v]
    if hasattr(v,'tolist'):return plain(v.tolist())
    if hasattr(v,'item'):return v.item()
    return v
def evaluate(config,tracking,output):
    cfg=read(config);require(cfg.get('tracking_authorized') is True and cfg.get('approved_by')=='root','需root真实评价授权')
    require(Path(__file__).resolve()==Path(cfg['bundle'])/'tools/research_ops/v8_metric.py','需bundle入口')
    for f in read(checked(cfg['bundle_manifest']))['files']:require(sha(Path(cfg['bundle'])/f['path'])==f['sha256'],'source变化')
    tracking=Path(tracking);receipt=read(tracking/'receipt.json');require(receipt['schema']=='v8_independent_tracking' and receipt['status']=='complete' and receipt['protocol_sha256']==sha(config) and receipt['frames']==750 and receipt['GT_read'] is False,'独立v8预测身份缺失')
    fold=receipt['fold'];sequence=SEQUENCE[fold];require(sequence==receipt['sequence'],'heldout身份不符')
    source_config=read(checked(cfg['source_config']));source=next(s for s in source_config['sources'] if s['domain']=='real' and s['game']==fold);require(source['cache']==receipt['cache'],'cache身份不符')
    info=configparser.ConfigParser();info.read(checked(source['gameinfo']),encoding='utf-8-sig');q=configparser.ConfigParser();q.read(checked(source['seqinfo']),encoding='utf-8-sig')
    require('game'+info['Sequence']['gameID']==fold and q['Sequence']['name']==sequence and float(q['Sequence']['frameRate'])==25,'实际gameinfo/seqinfo不是登记域')
    players={int(k.split('_')[-1]) for k,v in info['Sequence'].items() if k.startswith('trackletid_') and (v.strip().lower().startswith('player ') or v.strip().lower().startswith('goalkeeper'))};require(players,'真实player roster缺失')
    gt=[]
    for line in checked(source['gt']).read_text(encoding='utf-8-sig').splitlines():
        row=line.split(',');frame,identity=int(row[0]),int(row[1])
        if 1<=frame<=750 and identity in players and int(float(row[6]))==1:gt.append(','.join(row[:6]+['1','1','1']))
    pred=tracking/'data'/(sequence+'.txt');require(sha(pred)==receipt['mot_sha256'],'预测变更')
    predicted=[line for line in pred.read_text(encoding='utf-8').splitlines() if line];require(len(predicted)==receipt['tracked_rows'],'预测不准筛行')
    output=Path(output).resolve();require(RESEARCH/'pose/learned_association_v8' in output.parents and not output.exists(),'全新v8评价目录')
    output.mkdir(parents=True);gtroot=output/'derived_player_gt';folder=gtroot/sequence/'gt';folder.mkdir(parents=True);(folder/'gt.txt').write_text('\n'.join(gt)+'\n',encoding='utf-8')
    (gtroot/sequence/'seqinfo.ini').write_text('[Sequence]\nname='+sequence+'\nimDir=img1\nframeRate=25\nseqLength=750\nimWidth='+q['Sequence']['imWidth']+'\nimHeight='+q['Sequence']['imHeight']+'\nimExt=.jpg\n',encoding='utf-8')
    import trackeval
    require(trackeval.__version__=='1.3.0','固定TrackEval1.3.0');capture=io.StringIO()
    dataset_config=dict(GT_FOLDER=str(gtroot),TRACKERS_FOLDER=str(tracking.parent),OUTPUT_FOLDER=str(output/'trackeval'),TRACKERS_TO_EVAL=[tracking.name],SKIP_SPLIT_FOL=True,SEQ_INFO={sequence:750},DO_PREPROC=False,BENCHMARK='MOT17',SPLIT_TO_EVAL='train',PRINT_CONFIG=False,CLASSES_TO_EVAL=['pedestrian'],TRACKER_SUB_FOLDER='data',INPUT_AS_ZIP=False)
    evaluation_config=dict(USE_PARALLEL=False,PRINT_CONFIG=False,PRINT_RESULTS=False,PLOT_CURVES=False,TIME_PROGRESS=False,OUTPUT_SUMMARY=True,OUTPUT_DETAILED=True,BREAK_ON_ERROR=True,LOG_ON_ERROR=str(output/'errors.txt'))
    with redirect_stdout(capture):
        evaluator=trackeval.Evaluator(evaluation_config);dataset=trackeval.datasets.MotChallenge2DBox(dataset_config);require(dataset.do_preproc is False,'不得隐式过滤')
        metrics=[trackeval.metrics.HOTA(),trackeval.metrics.CLEAR(dict(PRINT_CONFIG=False)),trackeval.metrics.Identity(dict(PRINT_CONFIG=False))];results,messages=evaluator.evaluate([dataset],metrics)
    require(messages['MotChallenge2DBox'][tracking.name]=='Success','评价失败');raw=plain(results['MotChallenge2DBox'][tracking.name]);require(set(raw)=={sequence,'COMBINED_SEQ'},'不可扩大scope')
    summary={}
    for name,classes in raw.items():
        value=classes['pedestrian'];count=value['Count'];require(count['Frames']==750 and count['Dets']==len(predicted) and count['GT_Dets']==len(gt),'评价丢行/帧')
        fraction={}
        for group,keys in [('HOTA',('HOTA','AssA','DetA')),('Identity',('IDF1',)),('CLEAR',('MOTA',))]:
            for key in keys:v=value[group][key];fraction[key]=sum(v)/len(v) if isinstance(v,list) else float(v)
        summary[name]=dict(metrics_fraction=fraction,metrics_percent={k:100*v for k,v in fraction.items()},IDSW_count=int(value['CLEAR']['IDSW']))
    result=dict(schema='v8_train_domain_trackeval',status='complete',protocol_sha256=sha(config),tracking_receipt_sha256=sha(tracking/'receipt.json'),fold=fold,sequence=sequence,mode=receipt['mode'],binding=receipt['binding'],frames=750,GT=dict(source=source['gt'],gameinfo=source['gameinfo'],seqinfo=source['seqinfo'],derived_sha256=sha(folder/'gt.txt'),rows=len(gt),selection='gameinfo player and goalkeeper, mark1, first750; predictions never GT filtered'),summary=summary,raw_results=raw,DO_PREPROC=False,test_read=False,GT_used_only_for_metric=True,numerical_source_sha256={str(Path(inspect.getfile(type(x)))):sha(inspect.getfile(type(x))) for x in [evaluator,dataset]+metrics})
    (output/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(output/'stdout.txt').write_text(capture.getvalue(),encoding='utf-8');return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--tracking',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    print(json.dumps(evaluate(a.config,a.tracking,a.output) if a.execute else dict(status='readonly_v8_metric_candidate_no_GT_read'),ensure_ascii=False))
