"""有界Pose变化候选的独立CPU输入合同；不加载模型、不训练或拟合标准化。"""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import inspect
import json
import math
from pathlib import Path
import re
import sys

from pose_velocity_feature_candidate import bounded_velocity_features
from pose_temporal_feature_candidate import CHANGED_COLUMNS

R = Path('D:/projects/FutsalMOT_Research')
W = Path('D:/projects/FutsalMOT_UEDataset')
E = R / 'pose/pose_information_a01'
FOLDS = ('game4', 'game6', 'game9')
FIELDS = ('uid', 'bbox_xywh_px', 'score', 'xy_px', 'geometry_valid', 'timestamp_sec', 'image_wh')
SOURCE_STATUS = 'complete_three_actual_base_R_input_contracts_zero_updates_candidate_not_trained'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def safe_path(value):
    """先检查逻辑路径各段，不跟随junction或封存测试路径。"""
    p = Path(value)
    require(p.is_absolute(), '必须使用绝对物理路径')
    require('..' not in p.parts, '不接受可能越出物理根的上级路径段')
    require(not any(x.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', x.lower())
                    or x.lower().startswith('test_') for x in p.parts), '封存测试路径禁止读取')
    for component in reversed((p, *p.parents)):
        if component.exists():
            info = component.lstat()
            require(not component.is_symlink() and not (getattr(info, 'st_file_attributes', 0) & 0x400),
                    '禁止通过junction或符号链接访问')
    return p


def read(path):
    return json.loads(safe_path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    h = hashlib.sha256()
    with safe_path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def ref(path):
    return dict(path=str(path), sha256=sha(path))


def checked(reference):
    require(isinstance(reference, dict) and {'path', 'sha256'} <= set(reference), '缺少来源路径/SHA')
    require(re.fullmatch('[0-9a-f]{64}', reference['sha256']) is not None, '来源SHA格式无效')
    p = safe_path(reference['path'])
    require(p.is_relative_to(R) or p.is_relative_to(W), '来源必须位于实际研究或项目根')
    require(sha(p) == reference['sha256'], '来源字节变化：' + str(p))
    return p


def all_refs(value):
    if isinstance(value, dict):
        if {'path', 'sha256'} <= set(value):
            yield value
        else:
            for child in value.values():
                yield from all_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_refs(child)


def validate_contract_shape(contract):
    require(contract.get('status') == SOURCE_STATUS and contract.get('new_optimizer_updates') == 0
            and contract.get('model_loaded') is False and contract.get('normalizer_fitted') is False
            and contract.get('external_inputs_read') is False and contract.get('test_read') is False,
            '只接受已完成的零更新、无外部输入基础R合同')
    require(contract.get('changed_columns') == list(CHANGED_COLUMNS), '只能替换34个原历史均值通道')
    require(set(contract.get('folds', {})) == set(FOLDS), '必须三个固定fold，不得遗漏或增加')
    for fold, entry in contract['folds'].items():
        clip = entry.get('velocity_clip_99')
        require(entry.get('window_entries') == 1000 and isinstance(clip, (int, float))
                and not isinstance(clip, bool) and math.isfinite(clip) and clip > 0,
                '每fold须1000R及有限正的trainR速度界限：' + fold)


def validate_window_scope(window, fold):
    require(fold in FOLDS and window.get('domain') == 'real' and window.get('game') in FOLDS
            and window['game'] != fold, '训练窗口含heldout、外部或非真实来源')
    require(isinstance(window.get('window_uid'), str) and window['window_uid'], '窗口UID缺失')
    require(isinstance(window.get('history'), list) and len(window['history']) == 3
            and isinstance(window.get('candidates'), list) and window['candidates'], '固定三条实际历史/候选缺失')
    for record in window['history'] + [x['prediction'] for x in window['candidates']]:
        require(set(FIELDS) <= set(record), '原预测白名单字段缺失')
        require(re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', str(record['uid']).lower()) is None,
                '记录UID触及封存测试')


def public(record):
    """候选标签、GT身份等不传给数值特征函数。"""
    return {key: record[key] for key in FIELDS}


def validate_pair(raw, changed, gate_source, history, quality, scale):
    require(len(raw) == len(changed) == len(gate_source) == 194, '必须194维')
    require(all(isinstance(x, (int, float)) and math.isfinite(x) for x in (*raw, *changed, *gate_source)),
            '原/新特征或gate源含非有限值')
    require(gate_source == raw, 'gate必须使用未改变的原raw')
    require(all(changed[k] == raw[k] for k in range(194) if k not in CHANGED_COLUMNS),
            '改变了motion、当前坐标、mask或其他通道')
    require(quality.quality_gate(raw, scale) == quality.quality_gate(gate_source, scale), '原gate不相同')
    missing = 0
    maximum = 0.
    for joint in range(17):
        i = 24 + 10 * joint + 4
        speed = math.hypot(changed[i], changed[i + 1])
        # 此容差只用于浮点单位范数核验，不是性能等效界限。
        require(speed <= 1. + 1e-12, '有界变化描述超过单位范数')
        maximum = max(maximum, speed)
        available = history[-1]['geometry_valid'][joint] and sum(x['geometry_valid'][joint] for x in history) >= 2
        if not available:
            missing += 1
            require(changed[i] == changed[i + 1] == 0., '缺历史速度必须显式为零，不补造')
    return missing, maximum


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def context(source_contract):
    source_contract = safe_path(source_contract)
    require(source_contract == E / 'temporal_candidate_CPU_a01.json', '只接受已闭合阶段的明确基础R合同')
    contract = read(source_contract)
    validate_contract_shape(contract)
    completion = read(E / 'complete_root_a03.json')
    require(completion.get('status') == 'complete_zero_update_numeric_Pose_information_chain_manual_quality_pending'
            and completion.get('temporal_candidate_CPU') == ref(source_contract)
            and completion.get('test_read') is False, '阶段完成根没有绑定此合同')
    references = list(all_refs(contract))
    for reference in references:
        checked(reference)
    training = read(checked(contract['source_training_protocol']))
    feature_path = checked(contract['source_feature'])
    quality_path = checked(contract['source_quality'])
    require(feature_path.is_relative_to(R / 'code') and quality_path.is_relative_to(R / 'code')
            and feature_path.name == 'learned_association_features_v8.py'
            and quality_path.name == 'pose_quality_features_v9.py', '必须原冻结独立纯函数')
    scales = {}
    for fold in FOLDS:
        entry = contract['folds'][fold]
        expected = R / 'pose/learned_association_v8/pairs_a01' / ('heldout_' + fold) / 'real_pool.jsonl'
        require(Path(entry['base_R_pool']['path']) == expected
                and entry['base_R_pool'] == training['folds'][fold]['real_pool'], '原基础R池来源不对应')
        scale_ref = training['folds'][fold]['quality_scale']
        scale = read(checked(scale_ref))
        require(scale.get('fit_scope') == 'positive known-label train_R only'
                and scale.get('train_pool') == entry['base_R_pool'], 'gate尺度不是同一基础trainR拟合')
        scales[fold] = dict(value=scale['shape_change_scale'], source=scale_ref)
    here = Path(__file__).resolve().parent
    require(Path(inspect.getfile(bounded_velocity_features)).resolve() == here / 'pose_velocity_feature_candidate.py'
            and Path(sys.modules['pose_temporal_feature_candidate'].__file__).resolve() == here / 'pose_temporal_feature_candidate.py',
            '候选必须从入口同一最小bundle加载，不能漂移到工作区')
    local_sources = [ref(here / name) for name in ('validate_pose_velocity_candidate_cpu.py',
        'pose_velocity_feature_candidate.py', 'pose_temporal_feature_candidate.py')]
    return contract, scales, feature_path, quality_path, local_sources


def output_paths(output):
    output = safe_path(output)
    require(output.is_relative_to(E) and output.suffix == '.json', '只写本研究阶段内独立JSON')
    paths = (output, output.with_suffix('.intent.json'), output.with_suffix('.failed.json'))
    require(not any(p.exists() for p in paths), '已有输出或partial，不覆盖、不隐式重放')
    require(output.parent.is_dir(), '输出父目录必须已经存在')
    return paths


def execute(source_contract, output, *, dry_run=True):
    contract, scales, feature_path, quality_path, local_sources = context(source_contract)
    output, intent, failed = output_paths(output)
    source_ref = ref(Path(source_contract))
    if dry_run:
        return dict(status='readonly_bounded_velocity_three_fold_CPU_plan', source_contract=source_ref,
                    folds=list(FOLDS), declared_base_R_window_entries=3000, new_optimizer_updates=0,
                    model_loaded=False, normalizer_fitted=False, test_read=False)
    with intent.open('x', encoding='utf-8') as stream:
        json.dump(dict(status='started_not_complete', source_contract=source_ref, sources=local_sources,
                       new_optimizer_updates=0, test_read=False), stream, ensure_ascii=False, indent=2)
    try:
        feature = load_module('bounded_velocity_original_feature', feature_path)
        quality = load_module('bounded_velocity_original_quality', quality_path)
        results = {}
        for fold in FOLDS:
            entry = contract['folds'][fold]
            pool_path = checked(entry['base_R_pool'])
            count = changed_count = missing_count = 0
            maximum = 0.
            seen = set()
            with pool_path.open(encoding='utf-8-sig') as stream:
                for line in stream:
                    window = json.loads(line)
                    validate_window_scope(window, fold)
                    require(window['window_uid'] not in seen, '原R窗口UID重复')
                    seen.add(window['window_uid'])
                    history = [public(x) for x in window['history']]
                    for candidate in window['candidates']:
                        # label可以unknown，所有候选都核验，但label不进入特征函数。
                        prediction = public(candidate['prediction'])
                        raw = feature.features(history, prediction)
                        changed, gate_source = bounded_velocity_features(raw, history, prediction, entry['velocity_clip_99'])
                        missing, norm = validate_pair(raw, changed, gate_source, history, quality, scales[fold]['value'])
                        count += 1
                        changed_count += int(changed != raw)
                        missing_count += missing
                        maximum = max(maximum, norm)
            require(len(seen) == 1000 and count == entry['all_candidate_pairs'], '真实池窗口/全部pair数量不符')
            results[fold] = dict(base_R_pool=entry['base_R_pool'], window_entries=len(seen), all_candidate_pairs=count,
                changed_pairs=changed_count, missing_speed_joint_descriptors=missing_count, max_velocity_descriptor_norm=maximum,
                velocity_clip_99=entry['velocity_clip_99'], original_gate_source_preserved=True,
                quality_scale=scales[fold]['source'], unknown_candidate_labels_retained=True)
        result = dict(status='complete_three_base_R_bounded_velocity_CPU_contract_candidate_not_trained',
            completed_local=datetime.now().astimezone().isoformat(), source_contract=source_ref,
            source_feature=contract['source_feature'], source_quality=contract['source_quality'],
            source_training_protocol=contract['source_training_protocol'], candidate_sources=local_sources,
            changed_columns=list(CHANGED_COLUMNS), folds=results, new_optimizer_updates=0, model_loaded=False,
            normalizer_fitted=False, external_inputs_read=False, test_read=False,
            interpretation='有界历史速度描述不是新关键点或准确率；本收据不等于训练/追踪有效')
        with output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        return result
    except BaseException as error:
        with failed.open('x', encoding='utf-8') as stream:
            json.dump(dict(status='failed_preserved_no_replay', error=repr(error), source_contract=source_ref,
                           new_optimizer_updates=0, test_read=False), stream, ensure_ascii=False, indent=2)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-contract', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    value = execute(args.source_contract, args.output, dry_run=not args.execute)
    print(json.dumps(value, ensure_ascii=False))
