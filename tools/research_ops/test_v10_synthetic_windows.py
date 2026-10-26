"""v10困难采样必要CPU检查；请求跳帧、自然检测缺失和配额必须区分。"""
import unittest
from unittest.mock import patch

import v10_synthetic_windows as w


def observations(missing=()):
    frames={i:dict(detections=[] if i in missing else [dict(bbox_xywh_px=[0,0,20,30])]) for i in range(8)}
    gt={i:[dict(gt_id='L1',bbox_xywh_px=[0,0,20,30])] for i in range(8)}
    return frames,gt


def window(uid='1',natural=False,overlap=False,count=2):
    return dict(window_uid=uid,stratum=['camera',0.],history_frame_indices=[0,1,2],candidate_frame_index=6,
                candidates=[dict(label=1) for _ in range(count)],supervision=dict(query_gt_id='L1'),
                difficulty=dict(candidate_count=count,natural_detection_gap_proxy=natural,image_mask_box_overlap_proxy=overlap))


class WindowTests(unittest.TestCase):
    def test_natural_gap_requires_no_raw_overlap_and_continuous_valid_GT(self):
        frames,gt=observations(missing=(2,3,4))
        events,_=w.gap_events(frames,gt)
        self.assertEqual([(e['before_frame'],e['after_frame'],e['missing_frames']) for e in events],[(1,5,3)])
        # 有raw框但GT匹配冲突不是检测缺失。
        frames[3]['detections']=[dict(bbox_xywh_px=[0,0,20,30])]*2
        self.assertEqual(w.gap_events(frames,gt)[0],[])
        frames,gt=observations(missing=(2,3,4));gt.pop(3)
        self.assertEqual(w.gap_events(frames,gt)[0],[])

    def test_requested_gap_is_not_natural_and_overlap_is_only_proxy(self):
        frames,gt=observations();events,boxes=w.gap_events(frames,gt)
        value=w.describe_window(window(),events,boxes)
        self.assertFalse(value['difficulty']['natural_detection_gap_proxy'])
        boxes[4]['R2']=[5,0,20,30]
        value=w.describe_window(window(),events,boxes)
        self.assertTrue(value['difficulty']['image_mask_box_overlap_proxy'])
        self.assertFalse(value['difficulty']['physical_occlusion_claim'])

    def test_hard_rank_preserves_quota_without_Pose_or_loss(self):
        pool=w.HardPool([('camera',0.)],count=2)
        for value in (window('1',count=100),window('2',natural=True),window('3',overlap=True)):
            pool.add(value)
        self.assertEqual({x['window_uid'] for x in pool.finish()},{'2','3'})
        insufficient=w.HardPool([('camera',0.)],count=2);insufficient.add(window())
        with self.assertRaisesRegex(ValueError,'不足'):insufficient.finish()

    def test_each_seed_exactly250_same_camera_gap_quotas(self):
        source_frames=[]
        for seed in w.WINDOWS:
            for camera in w.CAMERAS:
                source_frames.append((dict(seed=seed,camera=camera,sequence='%s_%s'%(seed,camera)),{}, {}, {}))
        def generated(source,frames,gate,audit):
            for gap in w.pairs.GAPS:
                for number in range(15):
                    uid=w.pairs.key([source['seed'],source['camera'],gap,number])
                    value=window(uid);value['stratum']=[source['camera'],gap]
                    yield value
        with patch.object(w.pairs,'enumerate_windows',generated):
            pools,audit=w.choose_pools(source_frames,lambda *a:None)
        for values in pools.values():
            self.assertEqual(len(values),1000)
            self.assertEqual(w.Counter(x['synthetic_seed'] for x in values),{s:250 for s in w.WINDOWS})
        self.assertEqual(audit['selected']['balanced']['windows'],1000)
        self.assertEqual(audit['selected']['hard_enriched']['natural_gap_windows'],0)


if __name__=='__main__':unittest.main()
