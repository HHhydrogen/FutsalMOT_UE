import unittest
from unittest.mock import patch
import io
import substitution_validation_inputs as entry
class Tests(unittest.TestCase):
    def test_truncated_JPEG_is_retried_before_any_destination_write(self):
        from PIL import Image
        out=io.BytesIO();Image.new('RGB',(2,2)).save(out,format='JPEG');good=out.getvalue()
        s=dict(split='train',role='external_validation_only',sequence='v_ITo3sCnpw_k_c007',width=2,height=2)
        with patch.object(entry,'fetch',side_effect=[good[:-10],good]),patch.object(entry.time,'sleep'):
            raw,attempts=entry.fetch_jpeg(s,414);self.assertEqual(raw,good);self.assertEqual(attempts,2)
    def test_original_split_and_role_whitelist(self):
        s=dict(split='train',role='external_validation_only',sequence='v_ITo3sCnpw_k_c007')
        self.assertIn('/train/',entry.source_url(s,'img1/000002.jpg'))
        for changes in (dict(split='test'),dict(role='training')):
            with self.assertRaises(ValueError):entry.source_url(dict(s,**changes),'gt/gt.txt')
    def test_no_official_det_or_traversal(self):
        s=dict(split='val',role='external_validation_only',sequence='v_ITo3sCnpw_k_c007')
        for name in ('det/det.txt','../test/foo','img1/../../test.jpg'):
            with self.assertRaises(ValueError):entry.source_url(s,name)
if __name__=='__main__':unittest.main()
