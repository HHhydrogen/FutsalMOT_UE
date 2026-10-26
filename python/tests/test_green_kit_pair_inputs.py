"""A/B可改变Pose但不能改变监督/运动输入，也不能混入dev或缺预测回填。"""
from copy import deepcopy
import pytest

from grf_ue_bridge.green_kit_pair_inputs import replace_synthetic_pose


def fixture():
    a=dict(uid="S1048_blue_CineCam_01:000000:000000", bbox_xywh_px=[10., 20., 30., 40.],
           score=.9, image_wh=[3840, 2160], timestamp_sec=0., xy_px=[[12., 24.]]*17,
           geometry_valid=[True]*17)
    b=deepcopy(a);b.update(uid="S1048_blue_CineCam_01:000001:000000", timestamp_sec=.1)
    windows=[dict(window_uid="window_%04d" % i, domain="synthetic", game="synthetic1048",
                  sequence="S1048_blue_CineCam_01", fps=10, history=[deepcopy(a)],
                  candidates=[dict(prediction=deepcopy(b), label=1, label_reason="fixed_GT_identity"),
                              dict(prediction=deepcopy(a), label=None, label_reason="unknown_preserved")])
             for i in range(1000)]
    return windows, {a["uid"]: deepcopy(a), b["uid"]: deepcopy(b)}


def test_only_pose_changes_and_originals_labels_UID_order_remain():
    windows, observations=fixture();original=deepcopy(windows)
    key=next(iter(observations));observations[key]["xy_px"][0]=[13., 25.]
    output, proof=replace_synthetic_pose(windows,observations)
    assert windows==original and output!=windows
    assert proof["unique_windows"]==1000 and proof["candidate_pairs"]==2000 and proof["known_pairs"]==1000
    assert proof["changed_pose_observations"]==1 and proof["runtime_authorized"] is False
    assert output[0]["candidates"][1]["label"] is None


def test_missing_observation_or_changed_bbox_refuse():
    windows, observations=fixture();missing=deepcopy(observations);missing.pop(next(iter(missing)))
    with pytest.raises(ValueError,match="缺新Pose"):replace_synthetic_pose(windows,missing)
    changed=deepcopy(observations);changed[next(iter(changed))]["bbox_xywh_px"][0]+=1
    with pytest.raises(ValueError,match="固定bbox"):replace_synthetic_pose(windows,changed)


def test_dev_and_shortened_budget_refuse():
    windows, observations=fixture()
    with pytest.raises(ValueError,match="1000"):replace_synthetic_pose(windows[:-1],observations)
    windows[0]["game"]="synthetic1102"
    with pytest.raises(ValueError,match="来源越界"):replace_synthetic_pose(windows,observations)


def test_invalid_keypoint_or_fake_geometry_bool_refuse():
    windows, observations=fixture();key=next(iter(observations))
    bad=deepcopy(observations);bad[key]["xy_px"][0]=[float('nan'),0.]
    with pytest.raises(ValueError,match="COCO17"):replace_synthetic_pose(windows,bad)
    bad=deepcopy(observations);bad[key]["geometry_valid"][0]=1
    with pytest.raises(ValueError,match="COCO17"):replace_synthetic_pose(windows,bad)


def test_shared_input_object_does_not_mutate_or_confuse_old_UID_checks():
    windows, observations=fixture();shared=windows[0]["history"][0]
    for row in windows:
        row["history"][0]=shared
        row["candidates"][1]["prediction"]=shared
    observations[shared["uid"]]["xy_px"][0]=[14., 26.]
    output, proof=replace_synthetic_pose(windows,observations)
    assert shared["xy_px"][0]==[12.,24.]
    assert all(w["history"][0]["xy_px"][0]==[14.,26.] for w in output)
    assert proof["changed_pose_observations"]==1
