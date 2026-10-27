"""固定120样本的盲人工空模板；只引用原图，不复制/解码媒体，不预填预测。"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from pose_manual_quality_contract import (SEQUENCES, canonical, empty_document, require, sample_id)

RESEARCH = Path('D:/projects/FutsalMOT_Research')


def physical(path):
    path = Path(os.path.abspath(path))
    require(RESEARCH in path.parents, '人工质量输入/输出必须是实际DResearch路径')
    require(not any(p.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', p.lower()) for p in path.parts), '最终测试封存')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            value = part.lstat()
            require(not stat.S_ISLNK(value.st_mode) and not getattr(value, 'st_file_attributes', 0) & 0x400, '拒绝junction/重解析点')
    return path


def read(path): return json.loads(physical(path).read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(physical(path).read_bytes()).hexdigest()
def ref(path): return dict(path=str(path), sha256=sha(path))


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(canonical(value)+'\n')


def scope(plan, plan_sha):
    require(plan['status'] == 'complete120_raw_person_crop_indices_manual_keypoint_review_pending'
            and plan['sample_size'] == 120 and len(plan['rows']) == 120
            and len({r['uid'] for r in plan['rows']}) == 120
            and Counter(r['sequence'] for r in plan['rows']) == {s: 24 for s in SEQUENCES},
            '只使用已固定120/五场各24样本，不重新选样或丢难例')
    require(plan['actual_manual_reviews'] == 0 and plan['manual_keypoint_truth_available'] is False
            and all(r['manual_keypoints'] is None and r['manual_review_status'] == 'pending' for r in plan['rows']),
            '原固定计划已有非空人工字段，停止避免重复/覆盖')
    return {r['uid']: dict(row_index=i, sample_id=sample_id(plan_sha, r)) for i, r in enumerate(plan['rows'])}


def make_manifest(plan_path, plan_sha256=None):
    plan_path = physical(plan_path); plan_sha = sha(plan_path)
    require(plan_sha256 is None or plan_sha == plan_sha256, '固定质量计划SHA不同')
    plan = read(plan_path); chosen = scope(plan, plan_sha); found = {}; path_differences = 0
    for sequence in SEQUENCES:
        source = plan['sources'][sequence]; path = physical(source['path']); hasher = hashlib.sha256()
        wanted = {r['uid']: r for r in plan['rows'] if r['sequence'] == sequence}
        with path.open('rb') as stream:
            for line in stream:
                hasher.update(line)
                if not line.strip(): continue
                frame = json.loads(line)
                for prediction in frame['detections']:
                    uid = prediction['uid']
                    if uid not in wanted: continue
                    row = wanted[uid]
                    require(uid not in found and frame['sequence'] == row['sequence']
                        and frame['frame_index'] == row['frame_index'] and frame['frame_number'] == row['frame_number']
                        and row['frame_number'] == row['frame_index']+1
                        and prediction['bbox_xywh_px'] == row['bbox_xywh_px']
                        and prediction['xy_px'] == row['xy_px'] and prediction['geometry_valid'] == row['geometry_valid'],
                        '固定UID、帧、预测选框来源不对应')
                    image = physical(row['image_file']); require(image.is_file(), '固定原图不存在，不猜目录/下载/跳过')
                    wh = [frame['width'], frame['height']]
                    require(prediction['image_wh'] == wh and all(type(x) is int and x > 0 for x in wh), '原图尺寸元数据不一致')
                    path_differences += str(frame['image_file']) != str(row['image_file'])
                    found[uid] = dict(chosen[uid], source=dict(sequence=sequence, frame_number=row['frame_number'],
                        frame_index=row['frame_index'], image_file=str(image), image_file_url=image.as_uri(),
                        image_wh=wh, roi_bbox_xywh_px=row['bbox_xywh_px']),
                        original_cache=source, original_cache_image_path=frame['image_file'],
                        image_path_binding='explicit_frozen_quality_plan_not_inferred_from_UID', stratum=row['stratum'])
        require(hasher.hexdigest() == source['sha256'], '固定模型cache来源SHA改变')
    require(len(found) == 120, '固定120来源未全部对应，不丢缺失/难例')
    ordered = [found[r['uid']] for r in plan['rows']]
    return dict(schema='manual_coco17_quality_fixed_scope_v1', source_plan=ref(plan_path),
        samples=ordered, sample_count=120, per_sequence=24, original_source_caches=plan['sources'],
        role='diagnostic_manual_quality_only_no_training_or_tracking_input',
        model_predictions_excluded_from_public_template=True, coordinate_system='full_original_image_pixel_xy',
        original_cache_vs_explicit_image_path_differences=path_differences,
        source_images_stat_only=True, image_pixels_decoded=0, image_media_hashed=False,
        new_optimizer_updates=0, test_read=False)


INSTRUCTIONS = """# 固定120人物的人工COCO17质量复核

这是待人工完成的质量输入，不是人工GT已完成。五个已观察比赛各24，所有120样本及17点都保留；无法判断也须记录原因，不删除难例。原选样框来自固定检测，仅用于指定目标，不是人体真值框。重叠和断档只是选样代理，不证明物理遮挡。

1. 直接用本地浏览器打开annotate.html（file://），不要作为HTTP页面托管。若本地图片访问受限则停止并由root处理，不换图、不复制图片或绕过访问限制。标注人不得查看源计划内预测点、模型overlay或模型输出；页面不展示、不预填这些内容。左右按人物解剖方向，非画面左右。源图只引用，不上传/复制。
2. 先判断目标为可确认人体、非人体或目标不明。后两种全部点标不可判定并保留原因。
3. 完整原图坐标：visible对应COCO v2；occluded_localizable仅当可以有把握定位，对应v1；out_of_frame指完整原图以外，v0且无坐标；unjudgeable也v0/无坐标，并区分过小、模糊、遮挡不可定位、部位不明等。超出ROI不等于超出原图。不要猜点或拿模型坐标填空。
4. 每个可定位点点击、每个不可判定选择都记实际人员/UTC/状态日志。输入人工ID并逐样本声明人工操作、未看/抄模型预测；导出JSON保留日志，不只填完成字段。
5. 另一位真实人员逐点独立复核。复核人须不同，声明未看预测，17点分别接受或要求修订；通过的复核绑定最终标注SHA。改点后旧审核失效。未审核只报告pending，不能宣称GT或准确率完成。
6. 工具可检查来源、坐标、声明与日志的一致性，也能拒绝已知预测向量精确复制等明显违规；无法凭JSON证明真人身份/独立性或排除蓄意抄写。root须依据实际人工过程核验来源，再另立统计准入。此工具不计算PCK、OKS或模型准确率。

目前所有模板点都是pending/null。初始模板必须通过验证且结果为pending，不得称120图已经人工标注。模型预测、完整人工点误差和人工不可判定分母后续分开报告。
"""


def prepare(plan, output, plan_sha256=None, execute=False):
    output = physical(output); require(not output.exists(), '人工输入目录/partial已存在，不覆盖')
    if not execute:
        value = read(plan); current_sha = sha(plan)
        require(plan_sha256 is None or current_sha == plan_sha256, '固定质量计划SHA不同')
        scope(value, current_sha)
        return dict(status='readonly_manual_quality_input_plan', samples=120,
            actual_manual_reviews=0, image_pixels_decoded=0, model_loaded=False, new_optimizer_updates=0)
    manifest = make_manifest(plan, plan_sha256)
    output.mkdir(parents=True); write_new(output/'manifest.json', manifest)
    template = empty_document(manifest, sha(output/'manifest.json'))
    write_new(output/'annotations_pending.json', template)
    with (output/'INSTRUCTIONS.md').open('x', encoding='utf-8') as stream: stream.write(INSTRUCTIONS)
    from pose_manual_quality_page import page
    with (output/'annotate.html').open('x', encoding='utf-8') as stream: stream.write(page(template))
    complete = dict(status='complete120_blind_manual_annotation_inputs_not_labels',
        manifest=ref(output/'manifest.json'), template=ref(output/'annotations_pending.json'),
        page=ref(output/'annotate.html'), instructions=ref(output/'INSTRUCTIONS.md'),
        samples=120, actual_manual_reviews=0, manual_keypoint_truth_available=False,
        image_pixels_decoded_by_prepare=0, images_copied=False, test_read=False)
    write_new(output/'complete.json', complete); return complete


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--plan-sha256'); parser.add_argument('--execute', action='store_true'); args = parser.parse_args()
    print(canonical(prepare(args.plan, args.output, args.plan_sha256, args.execute)))
