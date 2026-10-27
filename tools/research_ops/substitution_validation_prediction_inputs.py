"""七比赛预测输入契约：严格使用获取ledger，不猜目录，不向模型暴露GT。"""
from pathlib import Path
import re

R=Path('D:/projects/FutsalMOT_Research')
EXPECTED={'v_1yHWGw8DH4A_c029':725,'v_HdiyOtliFiw_c003':775,'v_ITo3sCnpw_k_c007':701,
    'v_dw7LOz17Omg_c053':550,'v_gQNyhv8y0QY_c003':700,'v_i2_L4qquVg0_c006':888,'v_iIxMOsCGH58_c013':451}
STATUS='complete4790_validation_frames_decoded_not_prediction_or_training_authorized'

def require(ok,msg):
    if not ok:raise ValueError(msg)

def image_boundary(path):
    """继承图保留实际来源，只有明确登记的四公共根和一张诊断图允许使用。"""
    p=Path(path)
    require(p.is_absolute() and '..' not in p.parts,'图像路径必须明确绝对且无父目录跳转')
    for name in ('substitution_validation_a01','substitution_validation_a02','substitution_match_identity_a01','substitution_match_identity_a02'):
        root=R/'public'/name
        if root in p.parents:return root
    require(p==R/'pose/real_substitution_a01/input_diagnostic_a01/000414_response.jpg','图像不在获取账本允许的物理范围')
    return R/'pose/real_substitution_a01/input_diagnostic_a01'

def sources(manifest,registry,ledger):
    require(manifest.get('schema')=='seven_match_validation_inputs_v1' and manifest.get('status')==STATUS
        and manifest.get('frames')==4790 and manifest.get('new_R_training_exposure')==manifest.get('optimizer_updates')==0
        and manifest.get('test_read') is False and manifest.get('models_run') is False,'七比赛输入尚未闭合或用途变化')
    entries=manifest['sequences'];by={x['sequence']:x for x in entries};identity={x['sequence']:x for x in registry['sources']}
    require(len(entries)==len(by)==len(identity)==7 and set(by)==set(identity)==set(EXPECTED)
        and len({s['video_id'] for s in entries})==7,'固定七独立视频/序列矩阵改变')
    images={}
    for f in ledger:
        key=(f['sequence'],f['frame_number'])
        require(key not in images and key[0] in EXPECTED and type(key[1]) is int and 1<=key[1]<=EXPECTED[key[0]]
            and f['bytes']>0 and re.fullmatch('[a-f0-9]{64}',f['sha256']) is not None,'获取ledger重复/越界/缺持久来源')
        image_boundary(f['path']);images[key]=f
    require(len(images)==4790,'缺少实际获取帧，不复制或旧图回填')
    result=[]
    for seq,count in EXPECTED.items():
        source=by[seq];ident=identity[seq]
        require(source['frames']==ident['full_clip_frames']==count and source['video_id']==ident['video_id']
            and source['original_split']==ident['split'] and source['role']=='external_validation_only'
            and source['fps']==25 and (source['width'],source['height'])==(1280,720),'比赛来源/尺寸/帧数/角色改变')
        frames=[]
        for i in range(count):
            f=images[(seq,i+1)]
            frames.append(dict(frame_index=i,frame_number=i+1,timestamp_sec=i/25,source_frame_index=i,
                source_timestamp_sec=i/25,image_file=f['path'],image_sha256_from_acquisition=f['sha256'],image_bytes=f['bytes']))
        result.append(dict(schema='seven_match_shared_source_v1',domain='real',sequence=seq,sequence_id=seq,
            game='external:'+source['video_id'],role='external_validation_only',video_id=source['video_id'],original_split=source['original_split'],
            match_identity=source['match_identity'],fps=25,width=1280,height=720,first_frame=0,last_frame=count-1,frames=frames,
            gt=source['gt'],seqinfo=source['seqinfo'],GT_usage='metrics_only_never_prediction_filter',new_R_training_exposure=0))
    return result

def inference_frame(source,frame):
    seq=source['sequence'];i=frame['frame_index']
    require(seq in EXPECTED and source['role']=='external_validation_only' and source['game']=='external:'+source['video_id']
        and type(i) is int and 0<=i<EXPECTED[seq] and frame['frame_number']==i+1 and frame['timestamp_sec']==i/25
        and frame['source_frame_index']==i and frame['source_timestamp_sec']==i/25
        and frame['image_file']==source['frames'][i]['image_file'],'明确图像/零基一基/时序关系改变')
    return dict(schema='seven_match_PT_prediction_frame_v1',sequence=seq,sequence_id=seq,domain='real',game=source['game'],
        role='external_validation_only',fps=25,width=1280,height=720,frame_index=i,frame_number=i+1,timestamp_sec=i/25,
        source_frame_index=i,source_timestamp_sec=i/25,image_file=frame['image_file'],GT_used_for_predictions=False)
