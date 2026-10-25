"""v7独立receipt评价适配；仅复用原TrackEval数值入口，不伪装旧implementation。"""
import json
from pathlib import Path
from grf_ue_bridge import pose_association_trackeval_v1 as old

def evaluate(tracking,output,config,config_sha,base_identity,v7_sources):
    tracking=Path(tracking);output=Path(output);receipt=old.read(tracking/'receipt.json');baseline=old.read(config['lambda0_receipt']['path'])
    old.require(receipt['schema']=='futsalmot_temporal_pose_tracking_receipt_v7' and receipt['protocol_sha256']==config_sha and receipt['base_identity']==base_identity==baseline['identity'] and receipt['v7_sources']==v7_sources,'缺独立v7来源/原base identity')
    old.require(receipt['GT_read'] is False and receipt['GPU_used'] is False and receipt['pose_lambda']==.1,'非预定义v7纯CPU输入')
    rule=old.read(config['original_rule']['path']);source=old.read(old.bound(rule['source_manifest']));gt_info={};pred_info={}
    old.require([entry['sequence_id'] for entry in source['sequences']]==list(old.SEQUENCES) and source['frames']==450,'只限原450开发域')
    for entry in source['sequences']:
        sequence=entry['sequence_id'];expected=old.GT_ROOT/sequence/'gt/gt.txt';old.require(old.safe_path(entry['derived_gt_file'])==old.safe_path(expected),'不是原GT来源')
        references=[ref for ref in entry['text_sources'] if old.safe_path(ref['path'])==old.safe_path(expected)];old.require(len(references)==1,'原GT SHA缺失')
        path=old.bound(references[0]);gt=old.parse_mot(path.read_text(encoding='utf-8'),150,ground_truth=True);old.require(len(gt)==entry['selected_player_gt_rows'],'原GT数量变化')
        pred=tracking/'data'/(sequence+'.txt');rows=old.parse_mot(pred.read_text(encoding='utf-8'),150);old.require(old.sha(pred)==receipt['sequences'][sequence]['mot_sha256'] and len(rows)==receipt['sequences'][sequence]['tracked_rows'],'新预测不得筛行/变更')
        gt_info[sequence]=dict(path=str(path),sha256=references[0]['sha256'],rows=len(gt));pred_info[sequence]=dict(path=str(pred),sha256=old.sha(pred),rows=len(rows))
    old.require(not output.exists(),'评价输出必须全新');output.mkdir(parents=True)
    result,log=old.run_trackeval(old.GT_ROOT,tracking,{sequence:150 for sequence in old.SEQUENCES},output/'trackeval')
    for sequence in old.SEQUENCES:
        count=result['raw_results'][sequence]['pedestrian']['Count'];old.require(count['Frames']==150 and count['Dets']==pred_info[sequence]['rows'] and count['GT_Dets']==gt_info[sequence]['rows'],'TrackEval丢行/隐式过滤')
    result.update(schema='futsalmot_temporal_pose_TrackEval_v7',status='complete_v7_existing_development_evaluation',protocol_sha256=config_sha,base_identity=base_identity,v7_sources=v7_sources,
        GT=gt_info,predictions=pred_info,DO_PREPROC=False,predictions_filtered=False,test_read=False,frames=450,new_training_updates=0,
        note='base_identity describes unchanged fallback/upstream only; full temporal numeric identity is v7_sources plus protocol',units='metrics_percent differences are pp; IDSW_count is unscaled integer')
    (output/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(output/'stdout.txt').write_text(log,encoding='utf-8');return result
