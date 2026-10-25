"""v6显式crop来源→原ByteTrack/TrackEval数值桥；不改raw/原协议常量。"""
import argparse
import inspect
import json
import os
from pathlib import Path
import sys
from v6_crop_runtime import load,configure_runtime,read,sha,require,RESEARCH

def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def tracking(config_path,key,attachment_manifest,output):
    config,bundle,base,legacy,core=load(config_path);require(config.get('execution_authorized') is True and config.get('approved_by')=='root','v6未root启用')
    legacy.training_complete(base.config,require_absent=True);configure_runtime();os.environ['CUDA_VISIBLE_DEVICES']='-1'
    sys.path.append(str(RESEARCH/'runtime_dependencies'))
    from grf_ue_bridge import pose_bytetrack_v2 as tracker
    from ultralytics.utils import YAML
    from ultralytics.trackers.byte_tracker import BYTETracker
    import ultralytics
    import lap
    manifest=read(attachment_manifest);require(manifest['schema']=='futsalmot_fixed_detection_crop_pose_manifest_v6' and manifest['status']=='complete_crop_pose_attachment_not_tracking' and manifest['model_key']==key and manifest['config_sha256']==sha(config_path),'禁止借用smoke/fullframe/他模型附件')
    require(manifest['checkpoint']['sha256']==config['models'][key]['checkpoint']['sha256'],'v5实际权重身份改变')
    attachment_path=Path(manifest['attachments']['path']);require(sha(attachment_path)==manifest['attachments']['sha256'],'v6附件字节改变')
    cached,frames=base.fixed.load_fixed_cache(base.config['cache']['path'],base.config['cache']['sha256'])
    records=[json.loads(line) for line in attachment_path.read_text(encoding='utf-8').splitlines() if line]
    require(len(records)==len(frames)==450,'必须全450帧，不能以小样冒充')
    poses={};model_sha=manifest['checkpoint']['sha256']
    for frame,record in zip(frames,records):
        values=core.tracker_records(frame,record,model_sha256=model_sha,fixed_detection_set_sha256=base.config['cache']['sha256'],config=config['crop_configuration'])
        poses.setdefault(frame['sequence_id'],{})[frame['frame_index']]=values
    protocol=read(base.config['association_protocol']['path']);cost=protocol['pose_cost_candidate'];yaml=base.canonical(protocol['tracking']['tracker_config']['path'])
    require(YAML.load(yaml)==dict(tracker_type='bytetrack',**tracker.FIXED_ARGS),'原ByteTrack配置变化')
    identity=dict(fixed_detection_set_sha256=base.config['cache']['sha256'],implementation_sha256=sha(tracker.__file__),upstream_bytetrack_sha256=sha(inspect.getfile(BYTETracker)),tracker_config_sha256=sha(yaml),ultralytics=ultralytics.__version__,lap=lap.__version__)
    baseline=read(base.config['lambda0']['path']);require(identity==baseline['identity'],'原lambda0数值/依赖身份不符')
    output=Path(output).resolve();require(RESEARCH/'pose/association_dev_a01/v6_crop' in output.parents and not output.exists(),'全新v6 CPU输出，不覆盖partial')
    output.mkdir(parents=True);(output/'data').mkdir()
    report=dict(schema='futsalmot_fixed_pose_association_candidate_v1',status='candidate_cpu_tracking_complete_not_metric_evaluated',identity=identity,protocol_sha256=base.config['association_protocol']['sha256'],pose_lambda=.1,pose_model_sha256=model_sha,
        attachment_manifest_sha256=sha(attachment_manifest),sequences={},GT_read=False,test_read=False,physical_visibility_used=False,gpu_used=False,metrics_evaluated=False,
        v6_protocol_sha256=sha(config_path),pose_source_schema=core.FRAME_SCHEMA,pose_source_transform=core.STRATEGY,
        explicit_adapter='v6 pixel/geometry records consumed unchanged by original pose_pair_cost and ByteTrack; no fullframe schema rename',new_formal_training_updates=0)
    for sequence in legacy.SEQUENCES:
        selected=[frame for frame in frames if frame['sequence_id']==sequence]
        outputs,_,audit=tracker.run_sequence(selected,fixed_sha=base.config['cache']['sha256'],pose_lambda=.1,model_sha=model_sha,poses_by_frame=poses[sequence],
            bbox_margin_fraction=config['crop_configuration']['geometry_config']['bbox_margin_fraction'],joint_indices=cost['joint_indices'],min_joints=cost['min_common_geometry_joints'],sigma=cost['sigma'],max_frame_gap=cost['max_frame_gap'])
        lines=[]
        for frame,values in zip(selected,outputs):
            for row in values:
                x,y,r,b,track_id,score,_,_=map(float,row);lines.append(','.join([str(frame['frame_number']),str(int(track_id))]+[format(value,'.17g') for value in (x,y,r-x,b-y,score)]+['-1']*3))
        path=output/'data'/(sequence+'.txt');path.write_text('\n'.join(lines)+('\n' if lines else ''),encoding='utf-8')
        report['sequences'][sequence]=dict(frames=len(selected),tracked_rows=len(lines),audit=audit,lambda0_equivalence=None,mot_file_sha256=sha(path))
    write(output/'receipt.json',report)

def metrics(config_path,key,tracking_dir,output):
    config,bundle,base,legacy,core=load(config_path);require(config.get('execution_authorized') is True and config.get('approved_by')=='root','v6未root启用')
    legacy.training_complete(base.config,require_absent=True);configure_runtime();os.environ['CUDA_VISIBLE_DEVICES']='-1';sys.path.append(str(RESEARCH/'runtime_dependencies'))
    current=read(Path(tracking_dir)/'receipt.json');require(current.get('v6_protocol_sha256')==sha(config_path) and current.get('pose_source_schema')==core.FRAME_SCHEMA,'v6显式数值桥缺失')
    # 原TrackEval仍以原ruleSHA/lambda0做数值检查；新v6协议SHA另外绑定，不硬改旧常量。
    result=base.metrics(Path(tracking_dir),Path(output));result.update(v6_protocol_sha256=sha(config_path),v6_model_key=key,pose_source_schema=core.FRAME_SCHEMA,exploratory=True,new_formal_training_updates=0)
    write(Path(output)/'report.json',result)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=('tracking','metrics'));parser.add_argument('--config',type=Path,required=True);parser.add_argument('--model',required=True);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    require(args.execute,'本入口只显式CPU执行')
    if args.stage=='tracking':tracking(args.config,args.model,args.input,args.output)
    else:metrics(args.config,args.model,args.input,args.output)
if __name__=='__main__':main()
