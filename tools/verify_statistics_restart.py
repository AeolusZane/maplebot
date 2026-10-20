import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
from PySide6.QtWidgets import QApplication
from src.ui.statistics_tab import StatisticsTab
from src.engine.MapleStoryAutoLevelUp import MapleStoryAutoBot
app=QApplication([])
b=SimpleNamespace(cfg={},is_disable_control=False,args=SimpleNamespace(test_image='',init_state=''),fsm=MagicMock(),loop=lambda:None,is_terminated=True)
b.start_record=MagicMock()
with patch('src.engine.MapleStoryAutoLevelUp.KeyBoardController'),patch('src.engine.MapleStoryAutoLevelUp.GameWindowCapturor'),patch('src.engine.MapleStoryAutoLevelUp.threading.Thread') as thread:
 thread.return_value.is_alive.return_value=True
 MapleStoryAutoBot.start(b)
 assert b.is_terminated is False
 w=StatisticsTab(lambda:b);w.tick()
 assert w.session is b.thread_auto_bot
 b.is_terminated=True;thread.return_value.is_alive.return_value=False;w.tick()
 with patch('src.engine.MapleStoryAutoLevelUp.threading.Thread') as restarted:
  restarted.return_value.is_alive.return_value=True
  MapleStoryAutoBot.start(b);w.tick()
  assert b.is_terminated is False
  assert w.session is restarted.return_value
  assert b.start_record.call_count == 2
 w.close();w.pool.shutdown(wait=False)
print('Start-stop-start statistics test passed')
