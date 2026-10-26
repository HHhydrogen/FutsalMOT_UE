"""额外R的独立预测输入契约；仅接收完成的三源manifest，GT不进入模型帧。"""
from pathlib import Path
import re

SEQUENCES={'SNMOT-061':'game4','SNMOT-098':'game6','SNMOT-154':'game9'}
STATUS='complete2250_extra_real_train_frames_decoded_not_prediction_or_training_authorized'
ROOT=Path('D:/projects/FutsalMOT_Research/public/real_substitution_train_a01')


def require(ok,message):
    if not ok:raise ValueError(message)


def sources(manifest,root):
    """只读来源元数据；逐图物理边界/解码与模型SHA由后续独立运行准入核验。"""
    root=Path(root)
    require(root==ROOT,'只允许已登记额外R物理目录，不别名旧真实或合成输入')
    require(manifest.get('schema')=='extra_real_train_input_manifest_v1' and manifest.get('status')==STATUS
        and manifest.get('images')==2250 and manifest.get('optimizer_updates')==0
        and manifest.get('training_authorized') is False and manifest.get('models_inferred') is False
        and manifest.get('test_requested') is False and manifest.get('det_file_extracted_or_used') is False,
        '获取尚未完成或来源/用途改变，不能把候选当实际输入')
    registered=manifest['sequences'];by_seq={s['sequence']:s for s in registered}
    require(len(registered)==len(by_seq)==3 and set(by_seq)==set(SEQUENCES),'只允许三段train，不引入heldout/val/test或重复序列')
    result=[]
    for seq,game in SEQUENCES.items():
        source=by_seq[seq]
        require(str(source['game_id'])==game[4:] and source['frames']==750 and source['fps']==25
            and (source['width'],source['height'])==(1920,1080),'实际比赛/帧数/时序或尺寸改变')
        files=source['files'];members={f['official_member']:f for f in files}
        prefix=f'train/{seq}/';images=[f'{prefix}img1/{n:06d}.jpg' for n in range(1,751)]
        expected=set(images+[prefix+'gt/gt.txt',prefix+'gameinfo.ini',prefix+'seqinfo.ini'])
        require(len(members)==len(files)==753 and set(members)==expected,'成员缺失/重复/含det或越界')
        for name,value in members.items():
            relative=Path(name).relative_to('train')
            require(Path(value['path'])==root/relative and value['bytes']>0
                and re.fullmatch('[0-9a-f]{64}',value['sha256']) is not None,'成员物理对象或下载身份不符')
        def reference(name):
            r=members[prefix+name];return dict(path=r['path'],sha256=r['sha256'])
        frames=[dict(frame_index=i,frame_number=i+1,timestamp_sec=i/25,
            source_frame_index=i,source_timestamp_sec=i/25,image_file=members[name]['path'],
            image_sha256_from_acquisition=members[name]['sha256']) for i,name in enumerate(images)]
        result.append(dict(schema='extra_real_source_for_prediction_v1',domain='real',sequence=seq,sequence_id=seq,
            game=game,role='extra_R_training_input_only_C',fps=25,width=1920,height=1080,first_frame=0,last_frame=749,
            frames=frames,gt_reference=reference('gt/gt.txt'),gameinfo_reference=reference('gameinfo.ini'),seqinfo_reference=reference('seqinfo.ini'),
            game_time_start=source['game_time_start'],game_time_stop=source['game_time_stop'],
            GT_usage='future_train_labels_only_never_prediction_filter',source_index_scope='official_clip_local_not_full_match_frames',
            new_R_training_exposure=0,model_inference_authorized=False))
    return result


def inference_frame(source,frame):
    """显式白名单；不复制GT、身份、框、Pose或其它意外字段。"""
    seq=source['sequence'];i=frame['frame_index']
    require(seq in SEQUENCES and source['game']==SEQUENCES[seq]
        and source['role']=='extra_R_training_input_only_C' and source['domain']=='real','预测角色或比赛身份改变')
    require(type(i) is int and 0<=i<750 and frame['frame_number']==i+1 and frame['timestamp_sec']==i/25
        and frame['source_frame_index']==i and frame['source_timestamp_sec']==i/25
        and frame['image_file']==source['frames'][i]['image_file'],'零基/一基/局部时间或图像对应改变')
    return dict(schema='extra_real_shared_prediction_frame_v1',sequence=seq,sequence_id=seq,game=source['game'],
        role=source['role'],domain='real',fps=25,width=1920,height=1080,frame_index=i,frame_number=i+1,timestamp_sec=i/25,
        source_frame_index=i,source_timestamp_sec=i/25,image_file=frame['image_file'],GT_used_for_predictions=False)
