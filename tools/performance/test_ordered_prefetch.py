"""预取器少量定向CPU检查，无模型、图像或训练更新。"""
import threading
import unittest
from ordered_prefetch import OrderedPrefetch

class PrefetchTests(unittest.TestCase):
    def test_order_and_one_producer(self):
        identities=[]
        def load(index):identities.append(threading.get_ident());return index*2
        with OrderedPrefetch(load,range(20)) as stream:self.assertEqual(list(stream),list(range(0,40,2)))
        self.assertEqual(len(set(identities)),1);self.assertFalse(stream.worker_alive);self.assertLessEqual(stream.stats['queue_peak'],2)
    def test_first_and_middle_error_preserve_order_stop(self):
        for failure_index in (0,2):
            calls=[];error=ValueError('original-'+str(failure_index));seen=[]
            def load(index):
                calls.append(index)
                if index==failure_index:raise error
                return index
            stream=OrderedPrefetch(load,range(100))
            with self.assertRaises(ValueError) as raised:
                with stream:
                    for item in stream:seen.append(item)
            self.assertIs(raised.exception,error);self.assertEqual(seen,list(range(failure_index)))
            self.assertEqual(calls,list(range(failure_index+1)));self.assertFalse(stream.worker_alive)
    def test_backpressure_close_does_not_start_more_tasks(self):
        third=threading.Event();calls=[]
        def load(index):
            calls.append(index)
            if index==2:third.set()
            return index
        stream=OrderedPrefetch(load,range(100));stream.start();self.assertTrue(third.wait(2));stream.close()
        self.assertEqual(calls,[0,1,2]);self.assertFalse(stream.worker_alive);self.assertEqual(stream.stats['yielded'],0)
        self.assertEqual(list(stream),[])
    def test_shared_cached_owner_exclusive(self):
        class Cache:
            def __getitem__(self,index):return index
        cache=Cache();first=OrderedPrefetch(cache.__getitem__,range(100));second=OrderedPrefetch(cache.__getitem__,range(2))
        first.start()
        try:
            with self.assertRaises(RuntimeError):second.start()
        finally:first.close();second.close()
        self.assertFalse(first.worker_alive)
    def test_timeout_must_not_claim_thread_closed(self):
        entered=threading.Event();release=threading.Event()
        def load(index):entered.set();release.wait();return index
        stream=OrderedPrefetch(load,range(1));stream.start();self.assertTrue(entered.wait(2))
        try:
            with self.assertRaises(TimeoutError):stream.close(timeout=.01)
            self.assertTrue(stream.worker_alive);self.assertFalse(stream.stats['closed'])
        finally:release.set();stream.close(timeout=2)
        self.assertFalse(stream.worker_alive);self.assertTrue(stream.stats['closed'])
    def test_unconsumed_error_and_size_limit_not_swallowed(self):
        failed=threading.Event();original=LookupError('producer')
        def load(index):failed.set();raise original
        stream=OrderedPrefetch(load,range(10));stream.start();self.assertTrue(failed.wait(2))
        with self.assertRaises(LookupError) as raised:stream.close()
        self.assertIs(raised.exception,original);self.assertFalse(stream.worker_alive)
        with self.assertRaises(MemoryError):
            with OrderedPrefetch(lambda index:b'0123456789',range(10),max_item_bytes=8,measure_bytes=len) as oversized:list(oversized)
        self.assertFalse(oversized.worker_alive)

if __name__=='__main__':unittest.main()
