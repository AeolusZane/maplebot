import json
import tempfile
import unittest
import numpy as np
from src.utils.detection_trace import DetectionTrace


class TraceTests(unittest.TestCase):
    def test_frame_metadata_and_throttle(self):
        with tempfile.TemporaryDirectory() as root:
            trace=DetectionTrace(root,10)
            frame=np.full((20,30,3),100,np.uint8)
            trace.record('near',frame,{'detections':[{'score':np.float32(.12)}],'source_monotonic':1})
            trace.record('near',frame,{'ignored':True})
            trace.record('decision',frame,{'detection_source':1,'reason':'expired'})
            trace.close();trace.thread.join(3)
            self.assertFalse(trace.thread.is_alive());self.assertIsNone(trace.error)
            events=[json.loads(x) for x in (trace.folder/'events.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(events),2)
            self.assertTrue(all((trace.folder/e['image']).exists() for e in events))
            self.assertEqual(events[1]['detection_source'],events[0]['source_monotonic'])

    def test_expired_session_does_not_record(self):
        with tempfile.TemporaryDirectory() as root:
            trace=DetectionTrace(root,-1)
            trace.record('near',np.zeros((2,2,3),np.uint8),{})
            trace.close();trace.thread.join(2)
            self.assertEqual(trace.count,0)

if __name__=='__main__':unittest.main()
