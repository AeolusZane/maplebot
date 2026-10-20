import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from pathlib import Path
import numpy as np
from src.navigation.walk_mapping import fit_segment, build_connections
from src.navigation.map_graph import new_graph, save_graph, load_graph


class MappingTests(unittest.TestCase):
    def test_two_endpoints_reverse_and_rope(self):
        from src.navigation.walk_mapping import endpoint_segment
        p=endpoint_segment((40,20),(10,30),'platforms','P1')
        self.assertEqual((p['x1'],p['y'],p['x2'],p['end_y']),(10,30,40,20))
        r=endpoint_segment((20,40),(21,10),'ropes','R1')
        self.assertEqual((r['y1'],r['y2']),(10,40))
        with self.assertRaises(ValueError):endpoint_segment((10,20),(20,40),'ropes','R2')
    def test_client_crop(self):
        from src.utils.mapping_capture import client_frame
        image=np.zeros((800,1368,3),np.uint8)
        image[31,1]=77
        cropped=client_frame(image,{'game_window':{'size':[768,1366]}})
        self.assertEqual(cropped.shape,(768,1366,3))
        self.assertEqual(int(cropped[0,0,0]),77)

    def test_reject_title_bar_as_map(self):
        from unittest.mock import patch
        from src.utils.mapping_capture import minimap_rect
        with patch('src.utils.mapping_capture.get_minimap_loc_size',return_value=(0,0,1366,32)):
            with self.assertRaises(ValueError):
                minimap_rect(np.zeros((768,1366,3),np.uint8))

    def test_platform_reverse(self):
        p=fit_segment([(x,30) for x in range(40,9,-1)],'platforms','P1')
        self.assertEqual((p['x1'],p['x2'],p['y'],p['end_y']),(10,40,30,30))

    def test_slope(self):
        p=fit_segment([(x,40-x//2) for x in range(10,31)],'platforms','P1')
        self.assertLess(p['end_y'],p['y'])

    def test_jump_rejected(self):
        with self.assertRaises(ValueError):
            fit_segment([(x,30 if x<15 or x>25 else 20) for x in range(40)],'platforms','P1')

    def test_rope(self):
        r=fit_segment([(20,y) for y in range(10,40)],'ropes','R1')
        self.assertEqual((r['x'],r['y1'],r['y2']),(20,10,39))

    def test_automatic_routes_roundtrip(self):
        image=np.zeros((100,100,3),np.uint8)
        graph=new_graph(image)
        graph['platforms']=[fit_segment([(x,y) for x in range(10,41)],'platforms',identity)
                            for identity,y in [('P1',40),('P2',33)]]
        build_connections(graph)
        self.assertTrue(any(e['enabled'] and e['kind']=='teleport' for e in graph['edges']))
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'navigation.json'
            save_graph(path,graph,image,True)
            self.assertTrue(load_graph(path,image)['confirmed'])

    def test_capture_cleanup(self):
        from PySide6.QtWidgets import QApplication
        from src.ui.walk_map_recorder import WalkMapRecorder
        from src.utils.common import imwrite_unicode
        app=QApplication.instance() or QApplication([])
        class Capture:
            stopped=False
            def stop(self):self.stopped=True
        capture=Capture()
        with tempfile.TemporaryDirectory() as d:
            imwrite_unicode(str(Path(d)/'map.png'),np.zeros((100,100,3),np.uint8))
            dialog=WalkMapRecorder(d,{},capture=capture)
            dialog.reject()
            self.assertTrue(capture.stopped)
            self.assertFalse(dialog.timer.isActive())

    def test_live_frame_coordinates_and_rerecord(self):
        import time
        from unittest.mock import patch
        from PySide6.QtWidgets import QApplication
        from src.ui.walk_map_recorder import WalkMapRecorder
        from src.utils.common import imwrite_unicode
        app=QApplication.instance() or QApplication([])
        class Capture:
            frame_time=time.monotonic()
            def get_frame(self):return np.full((22,32,3),80,np.uint8)
            def stop(self):pass
        with tempfile.TemporaryDirectory() as d:
            imwrite_unicode(str(Path(d)/'map.png'),np.zeros((100,100,3),np.uint8))
            dialog=WalkMapRecorder(d,{'minimap':{'offset':[1,2],'player_color':[136,255,255]}},capture=Capture())
            dialog.timer.stop()
            dialog.graph['platforms']=[dict(id='P4',x1=10,x2=40,y=30)]
            dialog.refresh_list()
            dialog.items.setCurrentRow(0)
            self.assertTrue(dialog.redo_button.isEnabled())
            dialog.position=(10,30)
            dialog.position_time=time.monotonic()
            dialog.redo_selected()
            self.assertEqual(dialog.active,('platforms','P4'))
            dialog.ready_at=0
            with patch('src.ui.walk_map_recorder.minimap_rect',return_value=(0,0,32,22)), \
                 patch('src.ui.walk_map_recorder.find_pattern_sqdiff',return_value=((10,20),.01,True)), \
                 patch('src.ui.walk_map_recorder.get_player_location_on_minimap',return_value=(5,6)):
                dialog.tick()
            self.assertEqual(dialog.points,[(10,30)])
            self.assertEqual(dialog.position,(16,28))
            self.assertEqual(int(dialog.live_canvas[20,10,0]),80)
            self.assertEqual(dialog.live_minimap.shape,(20,30,3))
            self.assertEqual(dialog.graph['platforms'][0]['x1'],10) # old geometry retained until confirmed
            dialog.capture.frame_time=time.monotonic()
            with patch('src.ui.walk_map_recorder.minimap_rect',side_effect=ValueError('小地图未找到')):
                dialog.tick()
            self.assertIsNotNone(dialog.game_frame)
            self.assertFalse(dialog.game_preview.pixmap().isNull())
            self.assertIsNone(dialog.position)
            self.assertEqual(len(dialog.points),1) # video continues, invalid positions do not record
            with patch('src.ui.walk_map_recorder.QMessageBox.information'):
                dialog.toggle('platforms')
            self.assertIsNotNone(dialog.active) # invalid endpoint cannot replace old platform
            dialog.position=(35,25)
            dialog.position_time=time.monotonic()
            dialog.toggle('platforms')
            self.assertIsNone(dialog.active)
            self.assertEqual(dialog.graph['platforms'][0]['x2'],35)
            self.assertEqual(dialog.graph['platforms'][0]['end_y'],25)
            dialog.dirty=False
            dialog.reject()

if __name__=='__main__':unittest.main()
