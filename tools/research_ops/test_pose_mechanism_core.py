"""固定权重诊断的交换/身份/预算边界；不执行训练。"""
from copy import deepcopy
import unittest
import pose_mechanism_core as core


def record(uid,offset=0):
    return dict(uid=uid,bbox_xywh_px=[20.,20.,40.,80.],score=.8,timestamp_sec=0.,image_wh=[200,200],
        geometry_valid=[True]*12+[False]*5,xy_px=[[35.+offset,40.+j] if j<12 else [0.,0.] for j in range(17)])


class Tests(unittest.TestCase):
    def test_deterministic_bijective_swaps_ignore_GT_and_preserve_metadata(self):
        dets=[record(str(i),i) for i in range(8)];frames=[dict(timestamp_sec=0.,detections=dets)]
        before=deepcopy(frames);bank=core.make_swaps(frames);self.assertEqual(frames,before)
        self.assertEqual(bank,core.make_swaps(frames));self.assertEqual(len(bank['mapping']),8)
        gt=deepcopy(frames)
        for d in gt[0]['detections']:d['gt_id']='sensitive_not_used'
        self.assertEqual(bank,core.make_swaps(gt))
        index={d['uid']:d for d in dets}
        for d in dets:
            changed=core.transform(d,bank,index)
            self.assertEqual({k:v for k,v in d.items() if k!='xy_px'},{k:v for k,v in changed.items() if k!='xy_px'})
            self.assertEqual(changed['geometry_valid'],d['geometry_valid']);self.assertNotEqual(changed['xy_px'],d['xy_px'])

    def test_no_mask_upgrading_and_incompatible_donor_rejected(self):
        a=record('a');b=record('b');b['geometry_valid'][0]=False
        self.assertIsNone(core.mapped_shape(a,b))
        bank=core.make_swaps([dict(timestamp_sec=0.,detections=[a,b])]);self.assertEqual(bank['shuffled_observations'],0)
        self.assertEqual(core.transform(a,bank,{'a':a,'b':b}),a)

    def test_no_valid_pose_is_explicitly_not_shuffled(self):
        d=record('a');d['geometry_valid']=[False]*17;d['xy_px']=[[0.,0.]]*17
        b=core.make_swaps([dict(timestamp_sec=0.,detections=[d])]);self.assertEqual(b['unchanged_reasons']['a'],'no_valid_pose')

    def test_exact54_common_and108_counterfactual_jobs(self):
        original=[]
        for pool in ('balanced','hard_enriched'):
            for fold in ('game4','game6','game9'):
                for seed in (20261024,20261025,20261026):
                    for sequence in (fold,'new1','new2'):
                        for method in ('motion','gated'):
                            original.append(dict(kind='new_RS',pool=pool,fold=fold,seed=seed,sequence=sequence,method=method))
        jobs=core.job_matrix(dict(tracking_matrix=original));self.assertEqual(len(jobs),162)
        self.assertEqual(sum(j['kind']=='common_state' for j in jobs),54)
        self.assertEqual(sum(j.get('condition')=='pose_off' for j in jobs),54)
        self.assertEqual(sum(j.get('condition')=='shape_shuffle' for j in jobs),54)

    def test_sealed_test_guard(self):
        for path in ('D:/public/test/gt.txt','D:/public/SNMOT-116/cache.json','D:/public/test_zip_index.json'):
            with self.assertRaises(ValueError):core.safe(path)

    def test_off_wrapper_is_actual_same_network_motion_branch_no_updates(self):
        import torch
        class Model(torch.nn.Module):
            def __init__(self):super().__init__();self.base=torch.nn.Linear(194,1)
        m=Model().eval();before={k:v.clone() for k,v in m.state_dict().items()};x=torch.arange(390,dtype=torch.float32).reshape(2,195)
        actual=core.off_model(m)(x);expected=m.base(torch.cat([x[:,:24],torch.zeros_like(x[:,24:194])],dim=1))
        self.assertTrue(torch.equal(actual,expected));self.assertTrue(all(torch.equal(before[k],v) for k,v in m.state_dict().items()))


if __name__=='__main__':unittest.main()
