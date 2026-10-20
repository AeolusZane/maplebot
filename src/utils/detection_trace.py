"""Bounded asynchronous diagnostic history; never blocks the vision loop."""
import json
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
import cv2


class DetectionTrace:
    def __init__(self, root, seconds=180):
        self.folder=Path(root)/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        self.until=time.monotonic()+seconds
        self.queue=queue.Queue(maxsize=4)
        self.lock=threading.Lock();self.last={};self.count=0;self.dropped=0
        self.closed=False;self.error=None
        self.thread=threading.Thread(target=self.run,daemon=True,name='detection-trace')
        self.thread.start()

    def record(self,kind,frame,metadata):
        now=time.monotonic()
        with self.lock:
            if self.closed or now>self.until or self.count>=600 or now-self.last.get(kind,-100)<1:return
            if self.queue.full():self.dropped+=1;return
            self.last[kind]=now;self.count+=1
            entry=dict(metadata,kind=kind,sequence=self.count,recorded_monotonic=now,
                       recorded_at=datetime.now().isoformat(),dropped_records=self.dropped)
            self.queue.put_nowait((None if frame is None else frame.copy(),entry))

    def close(self):
        self.closed=True

    def run(self):
        try:
            self.folder.mkdir(parents=True,exist_ok=True)
            while not (self.closed and self.queue.empty()):
                try:frame,entry=self.queue.get(timeout=.2)
                except queue.Empty:
                    if time.monotonic()>self.until and self.queue.empty():break
                    continue
                if frame is not None:
                    name=f'{entry["sequence"]:04d}_{entry["kind"]}.jpg'
                    ok,encoded=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,95])
                    if not ok:raise ValueError('截图编码失败')
                    encoded.tofile(str(self.folder/name));entry['image']=name
                with (self.folder/'events.jsonl').open('a',encoding='utf-8') as f:
                    f.write(json.dumps(entry,ensure_ascii=False,default=lambda x:x.item() if hasattr(x,'item') else str(x))+'\n')
        except Exception as exc:self.error=str(exc)
