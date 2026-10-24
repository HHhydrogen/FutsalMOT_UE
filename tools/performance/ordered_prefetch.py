"""有界、单生产线程的确定性CPU预取候选；不管理训练更新或GPU。

契约：tasks必须是已冻结的有限tuple/list/range；loader只按任务确定性加载，不读写
全局随机流、不使用GPU、不提交优化器更新。消费者只使用返回值，不再直接访问同一
CachedDataset/LRU。绑定方法自动以__self__作独占resource；lambda包装缓存时显式传resource。
with块或finally中必须close。close等当前一次loader返回后join，绝不假装能强杀Python
线程；阻塞loader应自行响应cancel_event。显式timeout未结束会报TimeoutError，调用者仍
负责再次close。正常消费严格按原序抛出原异常并停止生产；主动关闭时未消费的生产异常
也会从close抛出，不能将其静默当作成功取消。

模块不seed、不触碰任何随机状态，不自动重试loader，不重放样本/未提交更新。
"""
from dataclasses import dataclass
import queue
import sys
import threading
import weakref

_LEASE_LOCK=threading.Lock()
_LEASES={}
_END=object()

@dataclass
class _Value:
    index:int
    value:object
    size:int

@dataclass
class _Failure:
    index:int
    error:BaseException
    traceback:object

class OrderedPrefetch:
    """队列默认2，允许2..4；仅一个loader线程，最多capacity+1个预取结果。

    max_item_bytes/measure_bytes可限制每个已生成结果。其严格含义是保留结果的计量
    字节不超过(capacity+1)*max_item_bytes；不含消费者已取走的对象、源任务表、
    Dataset自身缓存或loader内部解码瞬态/库分配。并非整个进程RSS上限。
    """
    def __init__(self,loader,tasks,*,capacity=2,resource=None,deterministic_loader=True,
                 max_item_bytes=None,measure_bytes=None):
        if type(capacity) is not int or not 2<=capacity<=4:raise ValueError('capacity只允许2..4')
        if type(tasks) not in (tuple,list,range):raise TypeError('先冻结有限任务表tuple/list/range，不接收动态随机generator')
        if not callable(loader) or deterministic_loader is not True:raise ValueError('仅接收显式确定性CPU loader')
        if max_item_bytes is not None and (type(max_item_bytes) is not int or max_item_bytes<=0 or not callable(measure_bytes)):
            raise ValueError('字节上限需正整数及measure_bytes')
        self.loader=loader;self.tasks=tuple(tasks) if type(tasks) is list else tasks
        self.capacity=capacity;self.resource=resource if resource is not None else getattr(loader,'__self__',loader)
        self.max_item_bytes=max_item_bytes;self.measure_bytes=measure_bytes
        self._queue=queue.Queue(maxsize=capacity);self.cancel_event=threading.Event();self._finished=threading.Event()
        self._thread=None;self._closed=False;self._close_complete=False;self._failure=None;self._failure_delivered=False
        self._leased=False;self._consumer_ident=None;self._lock=threading.Lock()
        self._stats=dict(loaded=0,yielded=0,queue_peak=0,max_item_bytes_seen=0,failure_index=None)
    def start(self):
        if self._closed:raise RuntimeError('已关闭的预取器不可重启/重放')
        if self._thread is not None:return self
        key=id(self.resource)
        with _LEASE_LOCK:
            old=_LEASES.get(key);owner=old() if old else None
            if owner is not None and owner is not self:raise RuntimeError('同一loader/CachedDataset resource已有生产者')
            _LEASES[key]=weakref.ref(self);self._leased=True
        self._thread=threading.Thread(target=self._produce,name='OrderedCPU-Prefetch-'+str(id(self)),daemon=False)
        try:self._thread.start()
        except BaseException:
            self._release();self._closed=True;raise
        return self
    def _release(self):
        if self._leased:
            with _LEASE_LOCK:
                old=_LEASES.get(id(self.resource))
                if old is not None and old() is self:del _LEASES[id(self.resource)]
            self._leased=False
    def _put(self,entry):
        while not self.cancel_event.is_set():
            try:
                self._queue.put(entry,timeout=.05)
                with self._lock:self._stats['queue_peak']=max(self._stats['queue_peak'],self._queue.qsize())
                return True
            except queue.Full:pass
        return False
    def _produce(self):
        index=0
        try:
            for index in range(len(self.tasks)):
                if self.cancel_event.is_set():return
                value=self.loader(self.tasks[index])
                size=self.measure_bytes(value) if self.measure_bytes is not None else 0
                if type(size) is not int or size<0:raise ValueError('measure_bytes必须返回非负整数')
                with self._lock:
                    self._stats['loaded']+=1;self._stats['max_item_bytes_seen']=max(self._stats['max_item_bytes_seen'],size)
                if self.max_item_bytes is not None and size>self.max_item_bytes:raise MemoryError('结果超过显式字节上限')
                if not self._put(_Value(index,value,size)):return
                del value
            self._put(_END)
        except BaseException as error:
            failure=_Failure(index,error,sys.exc_info()[2])
            with self._lock:self._failure=failure;self._stats['failure_index']=index
            self._put(failure)
        finally:self._finished.set()
    def __iter__(self):return self
    def __next__(self):
        identity=threading.get_ident()
        if self._consumer_ident is None:self._consumer_ident=identity
        if self._consumer_ident!=identity:raise RuntimeError('仅支持一个按序消费者')
        if self._closed:raise StopIteration
        self.start()
        while True:
            try:entry=self._queue.get(timeout=.05);break
            except queue.Empty:
                if self.cancel_event.is_set():self.close();raise StopIteration
                if self._finished.is_set():self.close();raise StopIteration
        if entry is _END:self.close();raise StopIteration
        if isinstance(entry,_Failure):
            self._failure_delivered=True;self.close();raise entry.error.with_traceback(entry.traceback)
        with self._lock:self._stats['yielded']+=1
        return entry.value
    def cancel(self):
        """请求停止，不代表线程已退出；随后必须close等待确认。"""
        self.cancel_event.set()
    def close(self,timeout=None):
        """等待当前loader结束且join；超时明确失败，绝不遗留线程却报告成功。"""
        self._closed=True;self.cancel_event.set()
        while True:
            try:entry=self._queue.get_nowait();del entry
            except queue.Empty:break
        if self._thread is not None:
            if self._thread.ident==threading.get_ident():raise RuntimeError('loader不能在生产线程中close/join自身')
            self._thread.join(timeout)
            if self._thread.is_alive():raise TimeoutError('生产者仍在loader内；保持resource租约，调用者须再次close')
        self._release();self._close_complete=True
        failure=self._failure
        if failure is not None and not self._failure_delivered:
            self._failure_delivered=True;self._failure=None
            raise failure.error.with_traceback(failure.traceback)
        self._failure=None
    @property
    def worker_alive(self):return self._thread is not None and self._thread.is_alive()
    @property
    def stats(self):
        with self._lock:value=dict(self._stats)
        value.update(capacity=self.capacity,producer_threads=1,closed=self._close_complete,worker_alive=self.worker_alive,
            retained_result_bytes_bound=(self.capacity+1)*self.max_item_bytes if self.max_item_bytes is not None else None)
        return value
    def __enter__(self):return self.start()
    def __exit__(self,exc_type,exc,tb):self.close();return False
