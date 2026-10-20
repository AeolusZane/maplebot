import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import Mock
import cv2
import numpy as np
from PySide6.QtWidgets import QApplication
from src.navigation.map_graph import platform_y,Navigator
from src.ui.walk_map_recorder import WalkMapRecorder


class PolylineTests(unittest.TestCase):
    def test_zoom_persists_across_live_redraw(self):
        app=QApplication.instance() or QApplication([])
        with TemporaryDirectory() as root:
            cv2.imwrite(str(Path(root)/'map.png'),np.zeros((100,100,3),np.uint8))
            w=WalkMapRecorder(root,{},capture=Mock());w.timer.stop();w.hotkey_timer.stop()
            w.draw();w.preview.scale(2,2);before=w.preview.transform().m11()
            w.draw();self.assertEqual(w.preview.transform().m11(),before)
            point=w.preview.mapFromScene(50,40)
            converted=w.preview.mapToScene(point)
            self.assertAlmostEqual(converted.x(),50,delta=1)
            self.assertAlmostEqual(converted.y(),40,delta=1)
            w.cleanup();w.deleteLater()

    def test_right_to_left_records_every_bend(self):
        import time
        app=QApplication.instance() or QApplication([])
        with TemporaryDirectory() as root:
            cv2.imwrite(str(Path(root)/'map.png'),np.zeros((100,100,3),np.uint8))
            w=WalkMapRecorder(root,{},capture=Mock());w.timer.stop();w.hotkey_timer.stop()
            for key,pos in [(0x75,(90,70)),(0x76,(60,50)),(0x76,(40,40)),(0x77,(10,40))]:
                w.position=pos;w.position_time=time.monotonic();w.record_hotkey(key)
            self.assertEqual(w.graph['platforms'][0]['points'],[[10,40],[40,40],[60,50],[90,70]])
            w.cleanup();w.deleteLater()

    def test_record_hotkeys_use_fresh_position_and_do_not_repeat(self):
        import time
        app=QApplication.instance() or QApplication([])
        with TemporaryDirectory() as root:
            cv2.imwrite(str(Path(root)/'map.png'),np.zeros((100,100,3),np.uint8))
            w=WalkMapRecorder(root,{},capture=Mock());w.timer.stop();w.hotkey_timer.stop()
            w.position=(10,70);w.position_time=time.monotonic()
            w.record_hotkey(0x75);self.assertEqual(w.points,[(10,70)])
            w.position=(40,40);w.record_hotkey(0x76)
            self.assertEqual(w.points,[(10,70),(40,40)])
            w.position=(90,70);w.record_hotkey(0x77)
            self.assertEqual(w.graph['platforms'][0]['points'],[[10,70],[40,40],[90,70]])
            w.items.setCurrentRow(0);w.position=(10,70);w.redo_selected()
            self.assertTrue(w.polyline)
            w.position=(45,35);w.record_hotkey(0x76)
            self.assertEqual(w.points,[(10,70),(45,35)])
            w.cancel_polyline()
            w.position=(50,70);w.record_hotkey(0x78)
            w.position=(50,40);w.record_hotkey(0x78)
            self.assertEqual(len(w.graph['ropes']),1)
            w.position_time-=1;w.record_hotkey(0x75)
            self.assertIsNone(w.active)
            w.isVisible=Mock(return_value=True);w.record_hotkey=Mock()
            w._held_keys=set();w._key_down=lambda k:k==0x75
            w.poll_hotkeys();w.poll_hotkeys()
            w.record_hotkey.assert_called_once_with(0x75)
            w.cleanup();self.assertFalse(w.hotkey_timer.isActive());w.deleteLater()

    def test_peak_with_equal_end_heights_locates(self):
        p=dict(id='P1',x1=10,x2=90,y=70,end_y=70,points=[[10,70],[50,40],[90,70]])
        self.assertEqual(platform_y(p,50),40)
        self.assertEqual(platform_y(p,30),55)
        n=Navigator(dict(platforms=[p],ropes=[],edges=[]))
        self.assertEqual(n.locate((50,40)),'P1')
        self.assertIsNone(n.locate((50,70)))
        n.last_progress=0
        self.assertEqual(n.slope_assist(p,(30,55),80,2),('right','none','none'))

    def test_click_undo_confirm_and_cancel_keep_old_data(self):
        app=QApplication.instance() or QApplication([])
        with TemporaryDirectory() as root:
            cv2.imwrite(str(Path(root)/'map.png'),np.zeros((100,100,3),np.uint8))
            w=WalkMapRecorder(root,{},capture=Mock());w.timer.stop()
            w.toggle_polyline();w.click_point(.1,.7,False);w.click_point(.5,.4,False)
            w.click_point(.4,.5,False);self.assertEqual(len(w.points),2)
            w.click_point(.9,.7,False);w.click_point(0,0,True)
            self.assertEqual(len(w.points),2)
            w.click_point(.9,.7,False);w.toggle_polyline()
            self.assertEqual(w.graph['platforms'][0]['points'],[[10,70],[50,40],[90,70]])
            w.items.setCurrentRow(0);w.toggle_polyline();w.click_point(.2,.3,False)
            w.cancel_polyline()
            self.assertEqual(w.graph['platforms'][0]['points'][0],[10,70])
            w.cleanup();w.deleteLater()

if __name__=='__main__':unittest.main()
