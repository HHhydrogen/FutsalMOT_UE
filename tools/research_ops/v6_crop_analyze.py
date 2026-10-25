"""v6完成后的独立结果整理；默认只读gate，不推理/重跑TrackEval/读取媒体或GT。"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics

RESEARCH=Path('D:/projects/FutsalMOT_Research')
BASE=RESEARCH/'pose/association_dev_a01'
CONTROL=BASE/'v6_crop/control_a01'
SEEDS=(20261024,20261025,20261026)
FLOORS=('R3S_blue','R3S_terracotta')
MODELS=['pretrained']+[f'{arm}_seed{seed}' for seed in SEEDS for arm in ('R3',*FLOORS)]
SEQUENCES=('SNMOT-151','SNMOT-152','SNMOT-153')


def require(ok,message):
    if not ok:raise ValueError(message)
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def small_json_sha(path):
    """只核验已有小JSON收据的SHA，绝不读取媒体/权重/GT或JSONL做hash扫描。"""
    path=Path(path);require(path.suffix.lower()=='.json' and path.stat().st_size<4*1024*1024,'只允许小JSON完整性核验')
    return hashlib.sha256(path.read_bytes()).hexdigest()
def same_path(actual,expected):return Path(actual).resolve()==Path(expected).resolve()
def difference(a,b):
    return {sequence:dict(delta_pp={key:a[sequence]['metrics_percent'][key]-b[sequence]['metrics_percent'][key] for key in ('AssA','HOTA','IDF1')},IDSW_delta_count=a[sequence]['IDSW_count']-b[sequence]['IDSW_count']) for sequence in a}

def gate(control):
    control=Path(control).resolve();require(BASE/'v6_crop' in control.parents,'control须实际DResearch/v6_crop下')
    path=control/'driver_state.json'
    if not path.is_file():return dict(status='waiting',reason='driver_state_not_present',analysis_started=False),None
    state=read(path)
    if state.get('status')!='complete_all_ten_models_crop_tracking':
        return dict(status='waiting',driver_status=state.get('status'),completed_models=len(state.get('completed',[])),expected_models=10,analysis_started=False),None
    require(state.get('completed')==MODELS and state.get('child_pid') is None,'终态十模型顺序/子任务未完整')
    reference=state.get('summary',{});summary_path=control/'paired_summary.json'
    require(same_path(reference.get('path',''),summary_path) and small_json_sha(summary_path)==reference.get('sha256'),'终态summary路径或已有SHA不一致')
    summary=read(summary_path)
    require(summary.get('schema')=='futsalmot_ten_model_crop_pose_exploratory_summary_v6' and summary.get('status')=='complete_all_ten_models','summary不是实际十模型完成结果')
    require(list(summary.get('models',{}))==MODELS and summary.get('new_formal_optimizer_updates')==0,'模型清单或0新训练事实不符')
    reports={};fullframe={}
    for key in MODELS:
        entry=summary['models'][key];path=control/key/'metrics/report.json';ref=entry['metrics']
        require(same_path(ref['path'],path) and small_json_sha(path)==ref['sha256'],'模型实际指标报告与summary不同:'+key)
        report=read(path)
        require(report.get('v6_model_key')==key and report.get('v6_protocol_sha256')==state['config_sha256'] and report.get('summary')==entry['summary'],'v6模型/协议/数值summary不一致:'+key)
        require(report['DO_PREPROC'] is False and report['predictions_filtered'] is False and report['frames']==450 and report['test_read'] is False,'现有TrackEval口径不同')
        reports[key]=report
        expected=BASE/'metrics_pretrained_pose_lambda01/report.json' if key=='pretrained' else BASE/'v5_association_a01'/key/'metrics/report.json'
        ref=entry['full_frame_reference'];require(same_path(ref['path'],expected) and small_json_sha(expected)==ref['sha256'],'原fullframe参考身份变化:'+key)
        fullframe[key]=read(expected)
        require(difference(report['summary'],fullframe[key]['summary'])==entry['crop_vs_same_model_full_frame'],'crop-fullframe汇总数值不一致:'+key)
    return dict(status='complete_inputs_consistent_ready_no_analysis',analysis_started=False,models=10),dict(state=state,summary=summary,reports=reports,fullframe=fullframe,control=control)

def coverage_by_sequence(control,key):
    manifest=read(control/key/'attachment/crop_attachment_manifest.json')
    require(manifest['status']=='complete_crop_pose_attachment_not_tracking' and manifest['model_key']==key and manifest['counts']['frames']==450,'不是完整实际crop附件')
    source=control/key/'attachment/crop_attachments.jsonl'
    require(same_path(manifest['attachments']['path'],source),'附件不能指向其他路径/媒体')
    result={sequence:dict(frames=0,raw_UID_crop_attempts=0,geometry_valid=0,bbox_fallback=0,rejections=Counter()) for sequence in SEQUENCES}
    seen_frames=set()
    with source.open(encoding='utf-8') as stream:
        for line in stream:
            if not line.strip():continue
            frame=json.loads(line);sequence=frame['sequence_id'];require(sequence in SEQUENCES,'附件包含未登记片段')
            require(frame['schema']=='futsalmot_fixed_detection_crop_pose_frame_v6','不能把fullframe附件当crop')
            require((sequence,frame['frame_index']) not in seen_frames,'重复源帧');seen_frames.add((sequence,frame['frame_index']))
            require(0<=frame['frame_index']<150 and len(frame['attachments'])==frame['crop_attempts']==frame['fixed_detection_count'],'帧/UID计数不符')
            item=result[sequence];item['frames']+=1;item['raw_UID_crop_attempts']+=frame['crop_attempts'];uids=set()
            for row in frame['attachments']:
                require(row['detection_id'] not in uids and row['visibility_state']==['unknown']*17,'UID重复或可见性发生升级');uids.add(row['detection_id'])
                require(type(row['prediction_valid']) is bool,'geometry valid须bool')
                if row['prediction_valid']:item['geometry_valid']+=1
                else:item['bbox_fallback']+=1;item['rejections'][row['prediction_rejection']]+=1
    for item in result.values():
        require(item['frames']==150,'每片段应完整150帧')
        item['geometry_fraction']=item['geometry_valid']/item['raw_UID_crop_attempts'] if item['raw_UID_crop_attempts'] else None
        item['rejections']=dict(item['rejections'])
    total={name:sum(item[name] for item in result.values()) for name in ('frames','raw_UID_crop_attempts','geometry_valid','bbox_fallback')}
    require(total['raw_UID_crop_attempts']==6901 and total['geometry_valid']+total['bbox_fallback']==6901,'尝试/几何成功/fallback不能混淆')
    total['geometry_fraction']=total['geometry_valid']/6901
    require(total['geometry_valid']==manifest['counts'].get('geometry_valid',0) and total['bbox_fallback']==manifest['counts'].get('bbox_fallback',0),'逐行统计与已发布小报告不一致')
    return dict(by_sequence=result,total=total)

def tracker_activity(control,key):
    receipt=read(control/key/'tracking/receipt.json');require(receipt['GT_read'] is False and receipt['pose_lambda']==.1,'不是原固定开发关联收据')
    per={};total=Counter()
    for sequence in SEQUENCES:
        audit=receipt['sequences'][sequence]['audit'];counts={name:audit.get(name,0) for name in ('pose_pairs_used','bbox_fallback_pairs','bbox_gated_out_pairs')}
        require(all(type(value) is int and value>=0 for value in counts.values()),'tracker audit计数非法')
        total.update(counts);denominator=counts['pose_pairs_used']+counts['bbox_fallback_pairs']
        per[sequence]=dict(counts,pose_use_fraction_among_pose_eligible_or_fallback_pairs=counts['pose_pairs_used']/denominator if denominator else None,original_audit=audit)
    denominator=total['pose_pairs_used']+total['bbox_fallback_pairs']
    return dict(by_sequence=per,total=dict(total),pose_use_fraction_among_pose_eligible_or_fallback_pairs=total['pose_pairs_used']/denominator if denominator else None,
        units='association_pair_comparisons_not_detections_or_unique_people',low_score_stage='original_upstream_bbox_only_unchanged')

def mean_differences(rows):
    return {sequence:dict(mean_delta_pp={key:statistics.mean(row[sequence]['delta_pp'][key] for row in rows) for key in ('AssA','HOTA','IDF1')},mean_IDSW_delta_count=statistics.mean(row[sequence]['IDSW_delta_count'] for row in rows)) for sequence in (*SEQUENCES,'COMBINED_SEQ')}

def analyze(context):
    control=context['control'];source=context['summary'];models={}
    for key in MODELS:
        coverage=coverage_by_sequence(control,key);expected=source['models'][key]['coverage']
        require(coverage['total']['geometry_valid']==expected['geometry_valid'] and coverage['total']['bbox_fallback']==expected['bbox_fallback'],'JSONL覆盖率与最终summary不一致')
        models[key]=dict(coverage=coverage,tracker=tracker_activity(control,key),metrics=context['reports'][key]['summary'],crop_vs_same_model_fullframe=difference(context['reports'][key]['summary'],context['fullframe'][key]['summary']))
    paired={}
    for seed in SEEDS:
        paired[str(seed)]={}
        for floor in FLOORS:
            current=models[f'{floor}_seed{seed}']['metrics'];real=models[f'R3_seed{seed}']['metrics'];pt=models['pretrained']['metrics']
            paired[str(seed)][floor]=dict(vs_same3000R_crop_R3=difference(current,real),vs_crop_pretrained=difference(current,pt))
    require(paired==source['paired'],'原driver配对结果与各小报告数值不一致')
    means={floor:{comparison:mean_differences([paired[str(seed)][floor][comparison] for seed in SEEDS]) for comparison in ('vs_same3000R_crop_R3','vs_crop_pretrained')} for floor in FLOORS}
    means_fullframe={arm:mean_differences([models[f'{arm}_seed{seed}']['crop_vs_same_model_fullframe'] for seed in SEEDS]) for arm in ('R3',*FLOORS)}
    return dict(schema='futsalmot_v6_crop_report_only_analysis_v1',status='complete_analysis_of_existing_ten_model_results',models=models,paired_by_seed=paired,three_training_seed_means=means,
        three_training_seed_mean_crop_minus_fullframe=means_fullframe,pretrained_crop_minus_fullframe=models['pretrained']['crop_vs_same_model_fullframe'],
        original_descriptive_progress=source['descriptive_progress'],new_formal_training_updates=0,images_or_GT_read=False,models_loaded=False,GPU_used=False,TrackEval_rerun=False,
        input_binding=dict(driver_config_sha256=context['state']['config_sha256'],driver_summary=context['state']['summary']),
        limitations=['coverage is prediction geometry admission, not keypoint accuracy or physical visibility','pose_pairs_used is a tracker pair-comparison count, not unique player count',
            'three training seeds are not three independent matches; all real clips share game9','existing v5 weights reused; zero new formal optimizer updates','crop+batch16 is an exploratory inference-interface change',
            'unknown visibility remains unknown; final116/187 stay sealed','small JSON receipt SHA only; no image/model/GT/JSONL hash scan'])

def markdown(report):
    lines=['# v6 crop接入结果整理','', '仅整理既有结果；0次新正式训练更新，未重跑推理或TrackEval。覆盖率表示几何准入，不等于Pose准确率或可见性。','',
        '| 模型 | 几何有效/原raw | 覆盖率 | tracker pose pairs | tracker bbox fallback pairs | AssA | HOTA | IDF1 | IDSW |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for key in MODELS:
        item=report['models'][key];coverage=item['coverage']['total'];activity=item['tracker']['total'];metric=item['metrics']['COMBINED_SEQ']
        lines.append(f"| {key} | {coverage['geometry_valid']}/6901 | {coverage['geometry_fraction']*100:.2f}% | {activity['pose_pairs_used']} | {activity['bbox_fallback_pairs']} | {metric['metrics_percent']['AssA']:.4f} | {metric['metrics_percent']['HOTA']:.4f} | {metric['metrics_percent']['IDF1']:.4f} | {metric['IDSW_count']} |")
    lines+=['','## mixed配对：每seed与均值','', '| floor / seed | 比较 | AssA Δpp | HOTA Δpp | IDF1 Δpp | IDSW Δcount |','|---|---|---:|---:|---:|---:|']
    for floor in FLOORS:
        for comparison in ('vs_same3000R_crop_R3','vs_crop_pretrained'):
            for seed in SEEDS:
                row=report['paired_by_seed'][str(seed)][floor][comparison]['COMBINED_SEQ'];d=row['delta_pp'];lines.append(f"| {floor}/{seed} | {comparison} | {d['AssA']:+.4f} | {d['HOTA']:+.4f} | {d['IDF1']:+.4f} | {row['IDSW_delta_count']:+d} |")
            row=report['three_training_seed_means'][floor][comparison]['COMBINED_SEQ'];d=row['mean_delta_pp'];lines.append(f"| {floor}/mean | {comparison} | {d['AssA']:+.4f} | {d['HOTA']:+.4f} | {d['IDF1']:+.4f} | {row['mean_IDSW_delta_count']:+.4f} |")
    lines+=['','## 同一模型crop − 原fullframe','', '| 模型 | AssA Δpp | HOTA Δpp | IDF1 Δpp | IDSW Δcount |','|---|---:|---:|---:|---:|']
    for key in MODELS:
        row=report['models'][key]['crop_vs_same_model_fullframe']['COMBINED_SEQ'];d=row['delta_pp'];lines.append(f"| {key} | {d['AssA']:+.4f} | {d['HOTA']:+.4f} | {d['IDF1']:+.4f} | {row['IDSW_delta_count']:+d} |")
    lines+=['','全部model/sequence覆盖率、fallback原因、原tracker审计及片段配对保存在report.json。','',
        '三个真实片段来自同game9；三个训练seed不是三个独立比赛。结果属于接入方式的探索性对照，不能据覆盖率或均值直接宣称准确率、跨比赛或真实五人制泛化提升。最终116/187保持封存。','']
    return '\n'.join(lines)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--control',type=Path,default=CONTROL);parser.add_argument('--output',type=Path);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    status,context=gate(args.control)
    if context is None or not args.execute:print(json.dumps(status,ensure_ascii=False));return
    require(args.output is not None,'实际整理需明确独立analysis目录');output=args.output.resolve()
    require(BASE/'v6_crop' in output.parents and not (context['control']==output or context['control'] in output.parents) and output.name.startswith('analysis_') and not output.exists(),'输出须独立全新analysis_*，不修改正式control结果')
    result=analyze(context);output.mkdir(parents=True)
    (output/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(output/'report.md').write_text(markdown(result),encoding='utf-8')
    print(json.dumps(dict(status=result['status'],output=str(output),new_formal_training_updates=0,media_read=False,TrackEval_rerun=False),ensure_ascii=False))
if __name__=='__main__':main()
