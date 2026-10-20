import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import time
import unittest
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication
from src.ui.map_debug import MapDebug
from tools.verify_map_graph import scene


class MapDebugTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_live_position_stale_status_and_layers(self):
        _,g=scene()
        bot=SimpleNamespace(_map_debug_snapshot=dict(time=time.monotonic(),map='test',graph=g,
            position=(20.,70.),valid=True,platform='P1',target=(40,62),status='测试导航',
            path=['E1'],command=['right','none','none'],latency_ms=23,
            latency_peak_ms=81,detection_source=time.monotonic(),detection_ms=12,detection_peak_ms=45))
        widget=MapDebug(lambda:bot,lambda:'test');widget.resize(1280,850);widget.show()
        self.app.processEvents();widget.refresh()
        self.assertIn('(20, 70)',widget.status.text())
        self.assertIn('实时 23 ms / 本次最高 81 ms',widget.status.text())
        self.assertIn('P1',widget.status.text());self.assertEqual(widget.table.rowCount(),len(g['platforms']))
        widget.regions.setChecked(True);widget.coords.setChecked(False);widget.render()
        bot._map_debug_snapshot=dict(bot._map_debug_snapshot,time=time.monotonic()-5,valid=False)
        widget.refresh();self.assertIn('过期',widget.status.text())
        widget.close()

if __name__=='__main__':unittest.main()
