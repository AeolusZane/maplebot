import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import cv2
from src.utils.manual_session import record_session, analyze_session


class Capture:
    frame_time = 0

    def get_frame(self):
        self.frame_time = time.monotonic()
        return np.zeros((100, 160, 3), dtype=np.uint8)


class Tests(unittest.TestCase):
    def test_record_without_detection_and_offline_output(self):
        cfg = dict(game_window={'size': [100,160]}, nametag={'name':'absent_test'},
                   minimap={'player_color':[136,255,255]},
                   monster_detect={'diff_thres':.05})
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'中文采集'
            with patch('src.utils.mapping_capture.locate_name', side_effect=AssertionError('live inference forbidden')), \
                 patch('src.utils.mapping_capture.minimap_rect', side_effect=AssertionError('live inference forbidden')):
                result = record_session(folder,cfg,'test',Capture(),threading.Event(),
                                        lambda *a:None,duration=.7)
            self.assertEqual(result['stop_reason'],'duration_complete')
            self.assertGreater(result['screenshots'],0)
            self.assertFalse(result['automatic_input'])
            entries=[json.loads(x) for x in (folder/'frames.jsonl').read_text().splitlines()]
            self.assertEqual(len(entries),result['video_frames'])
            video=cv2.VideoCapture(str(folder/'raw.mp4'))
            self.assertTrue(video.isOpened())
            self.assertEqual(int(video.get(cv2.CAP_PROP_FRAME_COUNT)),len(entries))
            video.release()
            with patch('src.utils.common.load_yaml',return_value={}), \
                 patch('src.utils.mapping_capture.locate_name',return_value=((10,40,20,10),.01)), \
                 patch('src.utils.mapping_capture.minimap_rect',return_value=(0,0,20,20)), \
                 patch('src.utils.common.get_player_location_on_minimap',return_value=(5,6)):
                output=analyze_session(folder,threading.Event(),lambda *a:None)
            observations=[json.loads(x) for x in (output/'observations.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(observations),result['screenshots'])
            self.assertEqual(observations[0]['minimap_player_local'],[5,6])
            self.assertEqual(observations[0]['name_box'],[10,40,20,10])

    def test_stop_without_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            stop=threading.Event();stop.set()
            result=record_session(Path(tmp)/'session',{},'test',Capture(),stop,lambda *a:None)
            self.assertEqual(result['stop_reason'],'user_stop')
            self.assertEqual(result['video_frames'],0)

    def test_low_disk(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp, patch(
                'src.utils.manual_session.shutil.disk_usage',return_value=SimpleNamespace(free=0)):
            result=record_session(Path(tmp)/'session',{},'test',Capture(),threading.Event(),lambda *a:None)
            self.assertEqual(result['stop_reason'],'low_disk_space')


if __name__ == '__main__':
    unittest.main()
