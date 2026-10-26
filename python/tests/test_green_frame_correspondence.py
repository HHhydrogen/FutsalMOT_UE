"""旧检测UID以frame_number计，新PNG以frame_index计，必须避免一帧偏移。"""
from copy import deepcopy
import pytest
from grf_ue_bridge.green_kit_pair_inputs import plan_green_frames


def fixture():
    source=dict(domain='synthetic',seed=1048,game='synthetic1048',sequence='S1048_blue_CineCam_01',
                role='train',fps=10,first_frame=0,last_frame=299,width=3840,height=2160,camera='CineCam_01')
    frames=[]
    for i in range(300):
        uid=source['sequence']+':%06d:000000'%(i+1)
        detection=dict(uid=uid,detection_id=uid,bbox_xywh_px=[1.,2.,3.,4.],score=.9,class_id=0,
                       image_wh=[3840,2160],timestamp_sec=i/10,xy_px=[[1.,1.]]*17,geometry_valid=[True]*17)
        frames.append(dict(sequence=source['sequence'],sequence_id=source['sequence'],domain='synthetic',
            game='synthetic1048',role='train',fps=10,width=3840,height=2160,frame_index=i,frame_number=i+1,
            timestamp_sec=i/10,image_file='old/%06d.png'%i,detections=[detection]))
    group=dict(schema='futsalmot_pose17_green_seeded_kit_paired_group_v1',seed=1048,split='train',variant='A',fps=10,
        source_frame_range=[0,300],not_training=True,MRQ_sync_verified=False,
        cameras={'CineCam_%02d'%c:dict(rgb_directory_ref='views/CineCam_%02d/cameras/CineCam_%02d/rgb'%(c,c),
                 frames=300,record_layout='one_person_per_line') for c in range(1,5)})
    return source,frames,group


def test_uid_number_does_not_shift_image_or_reuse_old_Pose():
    source,frames,group=fixture();before=deepcopy(frames)
    planned,proof=plan_green_frames(source,frames,group)
    assert planned[0]['detections'][0]['uid'].endswith(':000001:000000')
    assert planned[0]['new_image_ref'].endswith('/000000.png')
    assert planned[-1]['new_image_ref'].endswith('/000299.png')
    assert 'xy_px' not in planned[0]['detections'][0] and 'geometry_valid' not in planned[0]['detections'][0]
    assert frames==before and proof['published_files_validated'] is False
    group['variant']='B';_,b=plan_green_frames(source,frames,group)
    assert proof['raw_detection_order_sha256']==b['raw_detection_order_sha256']


def test_dev_and_incomplete_or_wrong_time_frame_refuse():
    source,frames,group=fixture();bad=deepcopy(group);bad.update(seed=1102,split='synthetic_dev')
    with pytest.raises(ValueError):plan_green_frames(source,frames,bad)
    with pytest.raises(ValueError):plan_green_frames(source,frames[:-1],group)
    frames[0]['frame_index']=1
    with pytest.raises(ValueError):plan_green_frames(source,frames,group)


def test_unsafe_RGB_reference_refuses():
    source,frames,group=fixture()
    for ref in ('../other','G:/outside','/absolute','views\\other'):
        group['cameras']['CineCam_01']['rgb_directory_ref']=ref
        with pytest.raises(ValueError):plan_green_frames(source,frames,group)
