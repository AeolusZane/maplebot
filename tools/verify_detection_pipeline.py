import time
import unittest
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch
from src.utils.latest_detection import LatestDetection
from src.engine.MapleStoryAutoLevelUp import MapleStoryAutoBot
from src.input.KeyBoardController import KeyBoardController
from tools.verify_two_side_mob_attack import make_stub, base_cfg, mob
from tools.verify_map_graph import scene, enable
from src.navigation.map_graph import Navigator


class PipelineTests(unittest.TestCase):
    def test_stopped_bot_never_recreates_detection(self):
        bot=SimpleNamespace(is_terminated=True)
        with patch.object(MapleStoryAutoBot,'_refresh_visible_monsters') as scan:
            MapleStoryAutoBot.refresh_visible_monsters(bot,1)
            scan.assert_not_called()
    def test_busy_survey_does_not_block_near_scan_or_replace_it(self):
        import numpy as np
        class Worker:
            def __init__(self,result=None,busy=False):
                self.result=result;self.future=object() if busy else None;self.calls=[]
            def poll(self):
                result,self.result=self.result,None
                return result
            def submit(self,*args):self.calls.append(args);self.future=object();return True
        near=Worker();survey=Worker(busy=True)
        cfg=base_cfg();cfg['bot']['attack']='aoe_skill'
        cfg['aoe_skill']=dict(range_x=360,range_up=70,range_down=150,range_y=220)
        cfg['monster_detect']['search_box_margin']=100
        bot=SimpleNamespace(cfg=cfg,img_frame=np.zeros((768,1366,3),np.uint8),
            loc_player=(600,400),loc_player_global=(60,40),monsters_info={},
            _visible_worker=near,_survey_worker=survey,graph_navigator=None)
        MapleStoryAutoBot.refresh_visible_monsters(bot,10)
        self.assertEqual(len(near.calls),1)
        self.assertEqual(near.calls[0][1].scan_region,(320,230,880,650))
        self.assertFalse(survey.calls)
        near.result=([mob(620,420)],10,50,((600,400),(60,40),True),bot.img_frame.shape,(320,230,880,650))
        survey.result=([],8,2000,((600,400),(60,40),True),bot.img_frame.shape,None)
        MapleStoryAutoBot.refresh_visible_monsters(bot,10.1)
        self.assertEqual(len(bot.visible_monsters),1)
        self.assertEqual(bot._visible_source_time,10)

    def test_held_teleport_request_reuses_token(self):
        kb=SimpleNamespace(cfg={'bot':{'navigation':'map_graph'}},cmd_action='none')
        KeyBoardController.set_command(kb,'none up teleport');token=kb._graph_teleport_token
        KeyBoardController.set_command(kb,'none up teleport')
        self.assertIs(kb._graph_teleport_token,token)
        KeyBoardController.set_command(kb,'none none none')
        KeyBoardController.set_command(kb,'none up teleport')
        self.assertIsNot(kb._graph_teleport_token,token)

    def test_remote_targets_suppress_survey_until_arrival(self):
        from src.navigation.mob_memory import PlatformMobMemory
        memory=PlatformMobMemory()
        self.assertTrue(memory.needs_survey(0))
        memory.last_survey=0
        memory.remember([dict(platform='P2',x=30,y=60)],'P1')
        self.assertFalse(memory.needs_survey(100))
        memory.arrive('P1');self.assertIn('P2',memory.targets)
        memory.arrive('P2');self.assertEqual(memory.targets,{})
        self.assertTrue(memory.needs_survey(100))
        memory.last_survey=100
        self.assertFalse(memory.needs_survey(101))
        self.assertTrue(memory.needs_survey(103))

    def test_slow_detection_never_blocks_or_queues_frames(self):
        worker=LatestDetection();release=Event();entered=Event()
        def slow():
            entered.set();release.wait(2);return 'new result'
        try:
            self.assertTrue(worker.submit(slow));self.assertTrue(entered.wait(1))
            self.assertIsNone(worker.poll())
            self.assertFalse(worker.submit(lambda:'queued stale frame'))
            release.set();worker.future.result(timeout=2)
            self.assertEqual(worker.poll(),'new result')
            self.assertIsNone(worker.poll())
        finally:release.set();worker.close()

    def test_full_frame_target_triggers_combat_without_second_detector(self):
        cfg=base_cfg();cfg['bot']['attack']='aoe_skill'
        cfg['aoe_skill']=dict(range_x=400,range_y=270,range_up=85,range_down=185,cooldown=1)
        bot=make_stub(cfg,(400,300),[])
        bot.graph_navigator=SimpleNamespace(graph={})
        bot.loc_player_global=(40,30);bot.graph_position_valid=True
        bot.visible_monsters=[mob(450,440)]
        bot._visible_source_time=bot._visible_scan_time=time.monotonic()
        bot._visible_anchor=((400,300),(40,30),True)
        bot.get_monsters_in_range=Mock(side_effect=AssertionError('duplicate detector'))
        with patch.object(MapleStoryAutoBot,'refresh_visible_monsters'):
            for _ in range(2):bot.update_cmd_by_mob_detection()
        self.assertTrue(bot._combat_hold);self.assertEqual(bot.cmd_action,'attack')
        self.assertEqual(len(bot.monsters),1)
        # The engine must hold attack through the keyboard-owned cooldown.
        bot.t_last_attack=time.time()
        with patch.object(MapleStoryAutoBot,'refresh_visible_monsters'):
            bot.update_cmd_by_mob_detection()
            self.assertEqual(bot.cmd_action,'attack')
            bot._player_reference_reliable=True;bot.visible_monsters=[]
            bot.update_cmd_by_mob_detection()
            self.assertEqual(bot.cmd_action,'attack')
            bot._last_attackable_time=time.monotonic()-.3
            bot.update_cmd_by_mob_detection()
            self.assertEqual(bot.cmd_action,'attack')
            bot._last_attackable_time=time.monotonic()-.7
            bot.update_cmd_by_mob_detection()
            self.assertEqual(bot.cmd_action,'none')
        bot.get_monsters_in_range.assert_not_called()
        self.assertEqual(MapleStoryAutoBot.current_visible_monsters(bot,time.monotonic()+2),[])

    def test_camera_compensation_uses_both_player_positions(self):
        bot=SimpleNamespace(loc_player=(500,300),loc_player_global=(50,30),graph_position_valid=True,
            graph_navigator=SimpleNamespace(graph={'hunt_calibration':{'scale':[10,10]}}),
            _visible_source_time=10,_visible_anchor=((400,300),(40,30),True),
            visible_monsters=[mob(600,300)])
        # Player moved 100px in a stationary camera: boxes must not shift.
        self.assertEqual(MapleStoryAutoBot.current_visible_monsters(bot,10.1)[0]['position'],(580,280))
        bot.loc_player=(400,300) # Camera followed the player by 100px.
        self.assertEqual(MapleStoryAutoBot.current_visible_monsters(bot,10.1)[0]['position'],(480,280))

    def test_stop_releases_keys_even_if_cached_state_says_none(self):
        bot=SimpleNamespace(cmd_left_right_last='none',cmd_up_down_last='none',_kd=Mock())
        with patch('src.input.KeyBoardController.key_up') as up:
            KeyBoardController.apply_directions(bot,'none','none')
        self.assertEqual([c.args[0] for c in up.call_args_list],['left','right','up','down'])
        bot._kd.assert_not_called()

    def test_patrol_prefers_unvisited_platform(self):
        _,g=scene();enable(g,'rope');nav=Navigator(g);nav.random_patrol=True
        nav.patrol_visits['P1']=3
        for t in (0,.1,.2):nav.step((15,70),t)
        self.assertEqual(nav.goal,'P2')


if __name__=='__main__':unittest.main()
