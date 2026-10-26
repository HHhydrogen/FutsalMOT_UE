"""v10共享检测/Pose的来源与时间契约；纯CPU规划，不运行模型或读取GT内容。"""
from pathlib import Path

CAMERAS = tuple('CineCam_%02d' % n for n in range(1, 5))
WINDOWS = {1042: (152, 452), 1044: (383, 683), 1048: (0, 300), 1131: (565, 865)}
EXTERNAL = {'v_2QhNRucNC7E_c017': 450, 'v_G-vNjfx1GGc_c004': 675}


def require(ok, message):
    if not ok: raise ValueError(message)


def relative_ref(folder, reference):
    relative = Path(reference)
    require(not relative.is_absolute() and not relative.drive and '..' not in relative.parts
            and len(relative.parts) > 0, '来源相对引用越界')
    return Path(folder) / relative


def synthetic_sources(group, group_path):
    """每个实际绿色B组四机位均重做原图检测；不继承蓝框或旧检测UID。"""
    seed = group.get('seed'); folder = Path(group_path).parent
    expected_schema = ('futsalmot_pose17_green_seeded_kit_paired_group_v1' if seed == 1048
                       else 'futsalmot_v10_multiseed_group_v1')
    require(seed in WINDOWS and group.get('schema') == expected_schema
            and group.get('variant') == 'B' and group.get('split') == 'train'
            and group.get('source_frame_range') == list(WINDOWS[seed]) and group.get('fps') == 10
            and group.get('not_training') is True and group.get('MRQ_sync_verified') is False
            and group.get('world_values_modified') is False
            and set(group.get('cameras', {})) == set(CAMERAS), '不是已登记四运动绿色B训练来源')
    require(group['green_floor']['id'].startswith('grass_'), '不能用旧蓝/红图代替绿色图')
    result = []
    for camera in CAMERAS:
        ref = group['cameras'][camera]
        require(ref.get('frames') == 300 and ref.get('record_layout') == 'one_person_per_line', '机位不完整')
        directory = relative_ref(folder, ref['rgb_directory_ref'])
        annotation = relative_ref(folder, ref['pose2d_ref'])
        # 新序列名与真实物理图像绑定；原1048_blue缓存的UID不在此沿用。
        sequence = 'v10_S%08d_green_B_%s' % (seed, camera)
        frames = [dict(frame_index=i, frame_number=i+1, timestamp_sec=i/10,
                       source_frame_index=WINDOWS[seed][0]+i,
                       source_timestamp_sec=(WINDOWS[seed][0]+i)/10,
                       image_file=str(directory / ('%06d.png' % i))) for i in range(300)]
        result.append(dict(domain='synthetic', sequence=sequence, sequence_id=sequence,
            game='synthetic%08d' % seed, role='train', seed=seed, camera=camera,
            floor=group['green_floor']['id'], fps=10, width=3840, height=2160,
            first_frame=0, last_frame=299, source_frame_range=list(WINDOWS[seed]), frames=frames,
            annotation_path=str(annotation), annotation_usage='identity_and_mask_labels_after_prediction_only',
            capture_group_path=str(group_path), raw_detection_reuse=False,
            source_flags=dict(diagnostic_only=True, not_training=True, visibility='unknown', MRQ_sync_verified=False)))
    return result


def external_sources(initial, decode, root):
    require(initial.get('schema') == 'v10_external_val_initial_acquisition_v1'
            and decode.get('status') == 'complete_inputs_decoded_GT_validated_no_model'
            and decode.get('frames') == 1125 and decode.get('test_requested') is False
            and decode.get('new_R_training_exposure') == 0, '新比赛输入尚未验收或用途改变')
    registered = {r['sequence']: r for r in initial['sequences']}
    require(len(initial['sequences']) == len(registered) == 2 and set(registered) == set(EXTERNAL),
            '不是结果前登记的两场val；禁止替换比赛或读test')
    result = []
    for sequence, count in EXTERNAL.items():
        row = registered[sequence]; meta = row['seqinfo']
        require(meta['name'] == sequence and int(meta['seqlength']) == count
                and row['frames_for_registered_evaluation'] == count and meta['imdir'] == 'img1'
                and meta['imext'] == '.jpg' and int(meta['framerate']) == 25
                and (int(meta['imwidth']), int(meta['imheight'])) == (1280, 720), '实际val时序/尺寸改变')
        proof = next((r for r in decode['sequences'] if r['sequence'] == sequence), None)
        require(proof is not None and proof['decoded_RGB_JPEG'] == proof['frames'] == count,
                '该比赛未完整解码验收')
        folder = Path(root) / sequence
        require(Path(row['files']['gt/gt.txt']['path']) == folder/'gt/gt.txt', 'GT只允许该登记比赛的独立评价引用')
        frames = [dict(frame_index=i, frame_number=i+1, timestamp_sec=i/25,
                       source_frame_index=i, source_timestamp_sec=i/25,
                       image_file=str(folder/'img1'/('%06d.jpg' % (i+1)))) for i in range(count)]
        result.append(dict(domain='real', sequence=sequence, sequence_id=sequence,
            game='SportsMOT_' + sequence.rsplit('_c', 1)[0], role='external_validation_only',
            fps=25, width=1280, height=720, first_frame=0, last_frame=count-1, frames=frames,
            gt_reference=row['files']['gt/gt.txt'], seqinfo_reference=row['files']['seqinfo.ini'],
            GT_usage='evaluation_only_no_prediction_filter', new_R_training_exposure=0,
            fabricated_soccerNet_gameinfo=False, raw_detection_reuse=False))
    return result


def assemble(groups, initial, decode, external_root):
    require(len(groups) == 4 and {g['group']['seed'] for g in groups} == set(WINDOWS),
            '必须四个不同运动seed，不复制UID填额')
    sources = [source for entry in sorted(groups, key=lambda g:g['group']['seed'])
               for source in synthetic_sources(entry['group'], entry['path'])]
    sources += external_sources(initial, decode, external_root)
    require(len(sources) == 18 and len({s['sequence'] for s in sources}) == 18
            and sum(len(s['frames']) for s in sources) == 5925, '完整共享输入矩阵不符')
    return sources


def inference_frame(source, frame):
    """进入模型的帧元数据没有GT身份/框/Pose；GT引用仅保留在输出来源索引。"""
    index = frame['frame_index']
    require(type(index) is int and source['first_frame'] <= index <= source['last_frame']
            and frame['frame_number'] == index+1 and frame['timestamp_sec'] == index/source['fps'],
            '预测帧编号或局部时间错位')
    return dict(schema='futsalmot_v10_shared_prediction_frame_v1',
        sequence=source['sequence'], sequence_id=source['sequence_id'], game=source['game'],
        role=source['role'], domain=source['domain'], fps=source['fps'], width=source['width'], height=source['height'],
        frame_index=index, frame_number=index+1, timestamp_sec=frame['timestamp_sec'],
        source_frame_index=frame['source_frame_index'], source_timestamp_sec=frame['source_timestamp_sec'],
        image_file=frame['image_file'], GT_used_for_predictions=False)
