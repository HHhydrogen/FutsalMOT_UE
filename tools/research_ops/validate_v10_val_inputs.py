"""下载闭合后一次解码两个已登记val输入；不执行模型或读取测试集。"""
import argparse
from collections import Counter
import configparser
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from training_journal import physical, require, sha, write_new
from v10_validation_inputs import SEQUENCES, checked, read


def validate(root, output):
    from PIL import Image
    root = physical(root); output = physical(output)
    require(output.parent == root and not output.exists(), '只写本次独立验证收据，不覆盖')
    complete = read(root/'download_a01/complete.json')
    require(complete['status'] == 'complete_two_registered_val_inputs_no_model'
            and complete['frames'] == 1125 and complete['test_requested'] is False, '下载未完整闭合')
    journal = root/'download_a01/files.jsonl'
    require(sha(journal) == complete['files_journal_sha256'], '下载索引发生变化')
    refs = [json.loads(line) for line in journal.read_text(encoding='utf-8').splitlines()]
    initial = read(root/'initial_manifest.json')
    require([v['sequence'] for v in initial['sequences']] == list(SEQUENCES), '只允许登记val片段')
    results = []
    for source, expected_count in zip(initial['sequences'], (450, 675)):
        sequence = source['sequence']; folder = physical(root/sequence)
        ini = configparser.ConfigParser(); ini.read(checked(source['files']['seqinfo.ini']), encoding='utf-8')
        cfg = ini['Sequence']
        require(cfg['name'] == sequence and int(cfg['seqLength']) == expected_count
                and int(cfg['frameRate']) == 25 and int(cfg['imWidth']) == 1280
                and int(cfg['imHeight']) == 720 and cfg['imDir'] == 'img1' and cfg['imExt'] == '.jpg', '元数据不符')
        rows = [r for r in refs if r['sequence'] == sequence]
        require(sorted(r['frame_number'] for r in rows) == list(range(1, expected_count+1)), '下载帧集合重复或遗漏')
        for row in rows:
            path = physical(row['path'])
            require(path == folder/'img1'/f"{row['frame_number']:06d}.jpg"
                    and path.stat().st_size == row['bytes'], '图像路径或大小改变')
            with Image.open(path) as image:
                image.load()
                require(image.size == (1280, 720) and image.format == 'JPEG' and image.mode == 'RGB', '真实解码规格不符')
        seen = set(); identities = set(); gt_frames = Counter(); values = Counter(); boundary = 0
        for line in checked(source['files']['gt/gt.txt']).read_text(encoding='utf-8').splitlines():
            v = [float(s.strip()) for s in line.split(',')]
            require(len(v) == 9 and all(math.isfinite(x) for x in v), 'GT须9列有限值')
            frame, identity = v[:2]
            require(frame.is_integer() and identity.is_integer() and 1 <= frame <= expected_count
                    and identity >= 0 and (frame, identity) not in seen, 'GT帧/身份/重复错误，ID0合法')
            x, y, width, height = v[2:6]
            require(width > 0 and height > 0 and v[6] in (0, 1) and v[7] == 1 and 0 <= v[8] <= 1,
                    'GT球员class/有效标志/可见比例或框异常')
            boundary += int(x < 0 or y < 0 or x+width > 1280 or y+height > 720)
            seen.add((frame, identity)); identities.add(int(identity)); gt_frames[int(frame)] += 1
            values[str(tuple(v[6:]))] += 1
        require(set(gt_frames) == set(range(1, expected_count+1)), 'GT未覆盖全部评价帧')
        results.append(dict(sequence=sequence, frames=expected_count, decoded_RGB_JPEG=expected_count,
            gt_rows=len(seen), identities=sorted(identities), id_zero_present=0 in identities,
            gt_flag_class_visibility_counts=dict(values), boxes_outside_image_preserved=boundary,
            gt_usage='evaluation_only_no_prediction_filter', official_pixel_SHA_available=False))
    value = dict(schema='v10_external_val_decode_validation_v1', status='complete_inputs_decoded_GT_validated_no_model',
        download_complete_sha256=sha(root/'download_a01/complete.json'), files_journal_sha256=sha(journal),
        source_identity=complete['source_identity'], sequences=results, frames=1125,
        model_inference=False, new_R_training_exposure=0, test_requested=False,
        note='只验证输入，不裁剪GT、不用GT筛预测、不伪造SoccerNet比赛元数据；下载时已有逐文件SHA，不重复媒体哈希')
    write_new(output, value)
    return value


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); result = validate(a.root, a.output)
    print(json.dumps(dict(status=result['status'], frames=result['frames'], sequences=result['sequences']), ensure_ascii=True))
