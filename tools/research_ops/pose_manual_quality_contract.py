"""固定120分母的人工COCO17契约；校验记录可审计性，不证明标注人身份真实性。"""
from collections import Counter
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

JOINTS = ('nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear', 'left_shoulder', 'right_shoulder',
    'left_elbow', 'right_elbow', 'left_wrist', 'right_wrist', 'left_hip', 'right_hip',
    'left_knee', 'right_knee', 'left_ankle', 'right_ankle')
SEQUENCES = ('SNMOT-060', 'SNMOT-097', 'SNMOT-151', 'v_2QhNRucNC7E_c017', 'v_G-vNjfx1GGc_c004')
POINT_STATES = ('pending', 'visible', 'occluded_localizable', 'out_of_frame', 'unjudgeable')
REASONS = ('too_small', 'blur', 'occluded_not_localizable', 'landmark_ambiguous',
    'not_a_person', 'target_ambiguous', 'outside_full_image', 'other')
SCHEMA = 'manual_coco17_quality_annotation_v1'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sample_id(plan_sha, row):
    return hashlib.sha256((plan_sha+'|'+row['uid']).encode()).hexdigest()[:24]


def annotation_digest(sample):
    return digest({k: sample[k] for k in ('sample_id', 'source', 'target_state', 'joints', 'annotation')})


def empty_sample(item):
    return dict(sample_id=item['sample_id'], source=deepcopy(item['source']), target_state='pending',
        joints=[dict(joint_id=i, name=name, status='pending', xy_image_px=None, coco_v=None, reason='', note='')
                for i, name in enumerate(JOINTS)],
        annotation=dict(status='pending', annotator_id='', declared_human=False,
            origin='manual_from_image', model_predictions_viewed=None, prediction_copy=None,
            started_at_utc=None, submitted_at_utc=None),
        review=dict(status='pending', reviewer_id='', declared_human=False, independent_of_annotator=None,
            model_predictions_viewed=None, prediction_copy=None, reviewed_at_utc=None,
            annotation_digest=None, points_checked=[]))


def empty_document(manifest, manifest_sha):
    return dict(schema=SCHEMA, source_manifest_sha256=manifest_sha, sample_count=120,
        coco17=list(JOINTS), model_predictions_included=False, model_predictions_prefilled=False,
        claimed_complete=False, samples=[empty_sample(item) for item in manifest['samples']], interaction_log=[])


def timestamp(value):
    require(isinstance(value, str), '人工操作缺明确UTC时间')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0, '操作时间必须有UTC时区')
    return parsed


def joint_contract(point, image_wh, target_state):
    require(set(point) == {'joint_id', 'name', 'status', 'xy_image_px', 'coco_v', 'reason', 'note'},
            '关键点字段严格固定，不能塞入模型预测来源或额外GT字段')
    joint = point['joint_id']
    require(type(joint) is int and 0 <= joint < 17 and point['name'] == JOINTS[joint]
            and point['status'] in POINT_STATES and isinstance(point['note'], str), 'COCO17顺序/名称/状态不符')
    state, xy = point['status'], point['xy_image_px']
    if state in ('visible', 'occluded_localizable'):
        require(target_state == 'person_confirmed' and isinstance(xy, list) and len(xy) == 2
                and all(type(x) in (int, float) and math.isfinite(x) for x in xy)
                and 0 <= xy[0] < image_wh[0] and 0 <= xy[1] < image_wh[1]
                and point['coco_v'] == (2 if state == 'visible' else 1) and point['reason'] == '',
                '可定位点必须来自原图坐标/可确认人体，不能超视野或伪造visibility')
    else:
        require(xy is None and point['coco_v'] == (None if state == 'pending' else 0),
                '不可判定/图外点不能造坐标；pending不能冒充COCO已标注')
        if state != 'pending':
            require(point['reason'] in REASONS and (point['reason'] != 'other' or point['note'].strip()),
                    '不可判定必须保留明确原因')
        if state == 'out_of_frame':
            require(point['reason'] == 'outside_full_image', '图外指完整原图，不是超出裁剪框')
    if target_state in ('not_a_person', 'target_ambiguous'):
        require(state == 'unjudgeable' and point['reason'] == target_state, '非人体/目标不明也须保留全部17点不可判定记录')
    elif point['reason'] in ('not_a_person', 'target_ambiguous'):
        raise ValueError('人体目标判断与不可判定原因相互矛盾')


def manual_claim(value, identity_key):
    require(isinstance(value[identity_key], str) and value[identity_key].strip()
            and value[identity_key] == value[identity_key].strip()
            and value['declared_human'] is True and value['model_predictions_viewed'] is False
            and value['prediction_copy'] is False, '缺人工身份/盲标/未拷贝预测声明，不接受人工完成声明')


def validate_document(document, manifest, manifest_sha, plan_rows):
    require(set(document) == {'schema', 'source_manifest_sha256', 'sample_count', 'coco17',
        'model_predictions_included', 'model_predictions_prefilled', 'claimed_complete', 'samples', 'interaction_log'}
        and document['schema'] == SCHEMA and document['source_manifest_sha256'] == manifest_sha
        and document['sample_count'] == 120 and document['coco17'] == list(JOINTS)
        and document['model_predictions_included'] is False and document['model_predictions_prefilled'] is False,
        '人工空模板身份/来源不符，不能使用带预测预填的记录')
    require(type(document['claimed_complete']) is bool, '完成声明必须是明确bool')
    expected = manifest['samples']
    require(len(expected) == len(document['samples']) == 120
            and [s['sample_id'] for s in document['samples']] == [s['sample_id'] for s in expected]
            and len({s['sample_id'] for s in expected}) == 120, '固定120分母不许删难例、补样或重复')
    require(len(plan_rows) == 120 and Counter(r['sequence'] for r in plan_rows) == {s: 24 for s in SEQUENCES},
            '私有原计划分母或五场比例改变')
    for i, (item, row) in enumerate(zip(expected, plan_rows)):
        source = item['source']
        require(item['row_index'] == i and item['sample_id'] == sample_id(manifest['source_plan']['sha256'], row)
                and source['sequence'] == row['sequence'] and source['frame_number'] == row['frame_number']
                and source['frame_index'] == row['frame_index']
                and Path(source['image_file']) == Path(row['image_file'])
                and source['roi_bbox_xywh_px'] == row['bbox_xywh_px'],
                '人工manifest并非固定原计划逐条对应，不能换图/换目标')
    events = document['interaction_log']; require(isinstance(events, list), '缺完整人工操作日志')
    by_sample = {}
    for i, event in enumerate(events):
        require(type(event['event_id']) is int and event['event_id'] == i+1
                and event['kind'] in ('set_point', 'set_status', 'set_target', 'annotator_declaration',
                    'submit_annotation', 'review_decision', 'review_declaration', 'submit_review')
                and event['sample_id'] in {s['sample_id'] for s in expected}
                and isinstance(event['actor_id'], str) and event['actor_id'].strip(), '操作日志步序/样本/人员缺失')
        timestamp(event['time_utc']); by_sample.setdefault(event['sample_id'], []).append(event)
    states = Counter(); joint_states = Counter(); submitted = reviewed = coordinate_points = 0
    for actual, item, prediction in zip(document['samples'], expected, plan_rows):
        require(set(actual) == {'sample_id', 'source', 'target_state', 'joints', 'annotation', 'review'}
                and actual['source'] == item['source'], '原图/ROI/帧源引用被替换或缺失')
        require(actual['target_state'] in ('pending', 'person_confirmed', 'not_a_person', 'target_ambiguous')
                and len(actual['joints']) == 17
                and [p['joint_id'] for p in actual['joints']] == list(range(17)), '必须完整17点，不能丢未知点')
        for point in actual['joints']:
            joint_contract(point, item['source']['image_wh'], actual['target_state']); joint_states[point['status']] += 1
        annotation, review = actual['annotation'], actual['review']
        require(set(annotation) == {'status', 'annotator_id', 'declared_human', 'origin', 'model_predictions_viewed',
                    'prediction_copy', 'started_at_utc', 'submitted_at_utc'}
                and set(review) == {'status', 'reviewer_id', 'declared_human', 'independent_of_annotator',
                    'model_predictions_viewed', 'prediction_copy', 'reviewed_at_utc', 'annotation_digest', 'points_checked'},
                '人工标注/复核字段严格固定，不接受额外来源或自动审核字段')
        require(annotation['status'] in ('pending', 'in_progress', 'submitted')
                and review['status'] in ('pending', 'needs_revision', 'reviewed'), '人工标注/独立复核状态未知')
        require(annotation.get('origin') == 'manual_from_image' and annotation.get('prediction_copy') is not True
                and annotation.get('model_predictions_viewed') is not True
                and review.get('prediction_copy') is not True and review.get('model_predictions_viewed') is not True,
                '预测拷贝/看过预测不得冒充独立盲人工GT')
        local = by_sample.get(actual['sample_id'], [])
        if annotation['status'] == 'submitted':
            submitted += 1; manual_claim(annotation, 'annotator_id')
            start, finish = timestamp(annotation['started_at_utc']), timestamp(annotation['submitted_at_utc'])
            require(start <= finish and actual['target_state'] != 'pending'
                    and all(p['status'] != 'pending' for p in actual['joints']), '未标完只能pending，不能提交完成')
            author = annotation['annotator_id']
            targets = [e for e in local if e['kind'] == 'set_target' and e['actor_id'] == author]
            declarations = [e for e in local if e['kind'] == 'annotator_declaration' and e['actor_id'] == author]
            require(targets and targets[-1]['target_state'] == actual['target_state']
                    and start <= timestamp(targets[-1]['time_utc']) <= finish
                    and declarations and declarations[-1]['declaration'] == dict(declared_human=True,
                        model_predictions_viewed=False, prediction_copy=False)
                    and start <= timestamp(declarations[-1]['time_utc']) <= finish,
                    '缺实际目标判断或人工盲标声明操作')
            for point in actual['joints']:
                actions = [e for e in local if e['kind'] in ('set_point', 'set_status')
                    and e.get('joint_id') == point['joint_id'] and e['actor_id'] == author]
                require(actions and actions[-1]['joint'] == point and start <= timestamp(actions[-1]['time_utc']) <= finish,
                        '每个点必须有对应人工点击/不可判定选择日志，不能仅填完成字段')
                require(actions[-1]['image_displayed'] is True
                        and actions[-1]['image_natural_wh'] == item['source']['image_wh'],
                        '逐点操作缺实际原图载入/尺寸声明')
                if point['xy_image_px'] is not None:
                    require(actions[-1]['kind'] == 'set_point' and actions[-1].get('input_method') == 'pointer',
                            '有坐标点缺实际人工指针操作声明')
                    coordinate_points += 1
                else:
                    require(actions[-1]['kind'] == 'set_status' and actions[-1].get('input_method') == 'status_selection',
                            '无坐标点必须是明确不可判定/图外状态选择，不能造点击')
            submit = [e for e in local if e['kind'] == 'submit_annotation' and e['actor_id'] == author]
            require(submit and submit[-1]['time_utc'] == annotation['submitted_at_utc'], '缺实际人工提交事件')
            placed = [p for p in actual['joints'] if p['xy_image_px'] is not None]
            require(not (len(placed) >= 3 and all(p['xy_image_px'] == prediction['xy_px'][p['joint_id']] for p in placed)),
                    '已知预测整向量精确拷贝，不可作为独立人工GT')
        if review['status'] == 'reviewed':
            require(annotation['status'] == 'submitted', '未提交标注不能伪造复核完成')
            manual_claim(review, 'reviewer_id')
            require(review['independent_of_annotator'] is True
                    and review['reviewer_id'].casefold() != annotation['annotator_id'].casefold()
                    and review['annotation_digest'] == annotation_digest(actual)
                    and timestamp(review['reviewed_at_utc']) >= timestamp(annotation['submitted_at_utc']),
                    '独立复核必须不同人员且绑定实际最终标注，不能自审或改后沿用旧审核')
            decisions = review['points_checked']
            require(len(decisions) == 17 and {d['joint_id'] for d in decisions} == set(range(17))
                    and all(d['decision'] == 'accepted' for d in decisions), '缺逐点独立复核或仍需修订')
            for point in actual['joints']:
                actions = [e for e in local if e['kind'] == 'review_decision' and e['actor_id'] == review['reviewer_id']
                    and e.get('joint_id') == point['joint_id']]
                require(actions and actions[-1]['decision'] == 'accepted' and actions[-1]['joint'] == point
                        and actions[-1]['annotation_submitted_at_utc'] == annotation['submitted_at_utc']
                        and actions[-1]['image_displayed'] is True
                        and actions[-1]['image_natural_wh'] == item['source']['image_wh']
                        and timestamp(annotation['submitted_at_utc']) <= timestamp(actions[-1]['time_utc'])
                            <= timestamp(review['reviewed_at_utc']),
                        '复核不能只填签名，缺绑定最终点的逐点操作记录')
            actions = [e for e in local if e['kind'] == 'submit_review' and e['actor_id'] == review['reviewer_id']]
            declarations = [e for e in local if e['kind'] == 'review_declaration' and e['actor_id'] == review['reviewer_id']]
            require(actions and actions[-1]['annotation_digest'] == review['annotation_digest']
                    and actions[-1]['time_utc'] == review['reviewed_at_utc']
                    and declarations and declarations[-1]['declaration'] == dict(declared_human=True,
                        independent_of_annotator=True, model_predictions_viewed=False, prediction_copy=False)
                    and timestamp(annotation['submitted_at_utc']) <= timestamp(declarations[-1]['time_utc'])
                        <= timestamp(review['reviewed_at_utc']),
                    '缺绑定内容的独立复核提交/声明日志')
            reviewed += 1
        states[annotation['status']] += 1
    require(sum(joint_states.values()) == 2040, '120×17点完整分母不齐')
    if document['claimed_complete']:
        require(submitted == reviewed == 120, '缺人工标注或独立审核，不能宣称全部完成')
    return dict(status='complete120_manual_annotation_review_contract_not_accuracy' if reviewed == 120
        else 'pending_manual_annotation_or_independent_review', samples=120, joint_denominator=2040,
        annotation_states=dict(states), joint_states=dict(joint_states), submitted_annotation_claims=submitted,
        independently_reviewed_claims=reviewed, coordinate_bearing_submitted_points=coordinate_points,
        accuracy_metrics_generated=False, test_read=False, model_predictions_displayed=False,
        human_authenticity_proven_by_JSON=False,
        limitations='来源/操作/不同人员声明是可审计契约；JSON或点击日志不能证明真人身份、独立性或排除蓄意抄写。未计算PCK/OKS。')
