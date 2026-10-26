"""只获取事前固定的两个SportsMOT val足球片段；禁止test和新增训练曝光。"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
from training_journal import atomic, canonical, physical, require, sha, write_new

SEQUENCES = ('v_2QhNRucNC7E_c017', 'v_G-vNjfx1GGc_c004')
REVISION = '2993b47d4369fa70ea70afc8bc63b5964e556a81'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def checked(ref):
    path = Path(ref['path']); require(path.is_file() and sha(path) == ref['sha256'], '来源变化')
    return path


def preflight(config, output):
    cfg = read(config); require(cfg.get('schema') == 'v10_external_val_download_config_v1'
        and cfg.get('mirror_revision') == REVISION and cfg.get('sequences') == list(SEQUENCES)
        and cfg.get('evaluate_only') is True and cfg.get('test_sealed') is True,
        '只接受已登记两个val序列，禁止test或训练用途')
    original = read(checked(cfg['initial_manifest'])); identity = read(checked(cfg['identity_receipt']))
    require(identity['status'] == 'root_visual_identity_verified_before_model'
            and identity['model_metrics_seen'] is False and original['test_requested'] is False,
            '比赛身份或结果前登记不完整')
    root = physical(cfg['input_root']); output = physical(output)
    require(output.parent == root and not output.exists(), '新下载状态目录，已有partial不隐式重放')
    require([s['sequence'] for s in original['sequences']] == list(SEQUENCES), '来源顺序不符')
    for source in original['sequences']:
        require(300 <= source['frames_for_registered_evaluation'] <= 750, '不填帧或不足300帧')
        for item in source['files'].values():
            path = checked(item); require(root in path.parents and path.resolve() == path.absolute(), '来源不得联接或越界')
    return cfg, original, root, output


def acquire(config, output):
    cfg, original, root, output = preflight(config, output)
    output.mkdir(); write_new(output/'intent.json', dict(config_path=str(config), config_sha256=sha(config),
        input_root=str(root), media='real_validation_JPEG_not_generated_media', models_run=False, test_requested=False))
    jobs = [(source['sequence'], index) for source in original['sequences']
            for index in range(2, source['frames_for_registered_evaluation']+1)]
    refs = [{**source['files']['img1/000001.jpg'], 'sequence':source['sequence'], 'frame_number':1,
             'reused_initial_acquisition':True} for source in original['sequences']]
    state = dict(status='downloading_registered_val_only', completed=len(refs), target=len(jobs)+len(refs),
                 config_sha256=sha(config), test_requested=False, model_inference=False, optimizer_updates=0)
    atomic(output/'state.json', state)

    def one(job):
        sequence, number = job
        url = f'https://huggingface.co/datasets/Lekim89/sportsmot/resolve/{REVISION}/val/{sequence}/img1/{number:06d}.jpg?download=true'
        target = physical(root/sequence/'img1'/f'{number:06d}.jpg')
        require(not target.exists(), '已有非首帧图，保留partial不覆盖')
        raw = None
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, headers={'User-Agent':'FutsalMOT-academic-val/1.0'})
                with urllib.request.urlopen(request, timeout=30) as response:
                    raw = response.read(5_000_001)
                require(4 < len(raw) <= 5_000_000 and raw[:2] == b'\xff\xd8' and raw[-2:] == b'\xff\xd9', 'JPEG格式/大小异常')
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(attempt+1)
        with target.open('xb') as stream:
            stream.write(raw)
        return dict(sequence=sequence, frame_number=number, path=str(target), bytes=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest(), url=url, reused_initial_acquisition=False)

    try:
        # 沿用已有输入下载的四路I/O；不是渲染/导出或GPU性能实验。
        with (output/'files.jsonl').open('x', encoding='utf-8') as journal:
            for item in refs:
                journal.write(canonical(item)+'\n')
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                for item in pool.map(one, jobs):
                    refs.append(item); journal.write(canonical(item)+'\n'); journal.flush()
                    if len(refs) % 25 == 0:
                        atomic(output/'state.json', dict(state, completed=len(refs)))
        require(len(refs) == state['target'] == 1125, '实际两片段450/675帧不完整')
        write_new(output/'complete.json', dict(schema='v10_external_validation_images_v1',
            status='complete_two_registered_val_inputs_no_model', frames=len(refs),
            source_config_sha256=sha(config), files_journal_sha256=sha(output/'files.jsonl'),
            source_identity=cfg['identity_receipt'], GT_usage='evaluation_only_no_GT_predictor_filter',
            new_R_training_exposure=0, model_inference=False, test_requested=False,
            limitations='public transport mirror pinned; official split names checked, no official image SHA available'))
        atomic(output/'state.json', dict(state, status='complete_two_registered_val_inputs_no_model', completed=len(refs)))
    except Exception as error:
        atomic(output/'state.json', dict(state, status='failed_preserved_no_replay',
            completed=len(refs), error=repr(error)))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute', action='store_true'); parser.add_argument('--config-sha256')
    args = parser.parse_args()
    if args.execute:
        require(args.config_sha256 == sha(args.config), '明确固定配置SHA才能下载')
        acquire(args.config, args.output)
    else:
        preflight(args.config, args.output)
        print(canonical(dict(status='readonly_val_input_preflight', test_requested=False, model_inference=False)))
