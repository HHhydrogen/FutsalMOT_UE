"""验收人工声明与独立复核契约；无人标注时明确pending，不计算准确率。"""
import argparse
from pathlib import Path

from pose_manual_quality_contract import canonical, require, validate_document
from pose_manual_quality_prepare import physical, read, ref, sha, write_new


def validate(manifest_path, annotations_path, output=None, execute=False):
    manifest_path, annotations_path = physical(manifest_path), physical(annotations_path)
    manifest = read(manifest_path)
    require(manifest['schema'] == 'manual_coco17_quality_fixed_scope_v1' and manifest['sample_count'] == 120,
            '必须先固定120源输入')
    plan_ref = manifest['source_plan']; require(sha(plan_ref['path']) == plan_ref['sha256'], '原质量计划SHA改变')
    plan = read(plan_ref['path']); document = read(annotations_path)
    result = validate_document(document, manifest, sha(manifest_path), plan['rows'])
    result.update(manifest=ref(manifest_path), annotations=ref(annotations_path),
        source_plan=plan_ref, original_records_modified=False, media_read=False,
        training_inputs_changed=False, tracking_inputs_changed=False,
        root_must_verify_actual_human_provenance=True)
    if execute:
        require(output is not None, '实际验收记录必须指定新输出路径')
        output = physical(output); require(not output.exists(), '已有验收/partial，不覆盖')
        output.parent.mkdir(parents=True, exist_ok=True); write_new(output, result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--annotations', type=Path, required=True)
    parser.add_argument('--output', type=Path); parser.add_argument('--execute', action='store_true'); args = parser.parse_args()
    print(canonical(validate(args.manifest, args.annotations, args.output, args.execute)))
