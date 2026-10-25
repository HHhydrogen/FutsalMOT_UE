"""已知框定位评价的定向数学检查，不加载媒体、模型或GPU。"""
import math
import unittest
from v7_pose_quality import quality, aggregate, SIGMAS

class QualityTest(unittest.TestCase):
    def annotation(self):
        return dict(area=10000., keypoints=[v for _ in range(17) for v in (20., 30., 2)])
    def test_exact_and_missing(self):
        annotation = self.annotation()
        exact = aggregate([dict(points=quality(annotation, [[20., 30.]]*17))])
        self.assertEqual(exact['limbs']['mean_person_OKS'], 1.)
        missing = aggregate([dict(points=quality(annotation, None))])
        self.assertEqual(missing['all']['mean_person_OKS'], 0.)
        self.assertEqual(missing['all']['PCK_sqrt_segmentation_area']['0.1'], 0.)
    def test_coco_sigma_and_threshold(self):
        points = quality(self.annotation(), [[30., 30.]]*17)
        self.assertAlmostEqual(points[0]['oks'], math.exp(-100/(2*(2*SIGMAS[0])**2*10000)))
        report = aggregate([dict(points=points)])
        self.assertEqual(report['all']['PCK_sqrt_segmentation_area']['0.1'], 1.)
        self.assertEqual(report['all']['PCK_sqrt_segmentation_area']['0.05'], 0.)
    def test_visibility_only_evaluation_groups(self):
        annotation = self.annotation(); annotation['keypoints'][2] = 0; annotation['keypoints'][5] = 1
        report = aggregate([dict(points=quality(annotation, [[20., 30.]]*17))])
        self.assertEqual(report['all']['labeled_joints'], 16)
        self.assertEqual(report['GT_v1']['labeled_joints'], 1)
        self.assertEqual(report['GT_v2']['labeled_joints'], 15)
    def test_actual_runtime_sigma_argument_is_used(self):
        sigmas = [value/2 for value in SIGMAS]
        result = quality(self.annotation(), [[30., 30.]]*17, sigmas)
        self.assertAlmostEqual(result[0]['oks'], math.exp(-100/(2*(2*sigmas[0])**2*10000)))
        self.assertLess(result[0]['oks'], quality(self.annotation(), [[30., 30.]]*17)[0]['oks'])

if __name__ == '__main__': unittest.main()
