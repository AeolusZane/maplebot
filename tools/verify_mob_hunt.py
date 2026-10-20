import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from tools.verify_map_graph import scene,enable
from src.navigation.mob_hunt import calibrate,project_monsters,choose_target,route_to
from src.navigation.map_graph import Navigator

class HuntTests(unittest.TestCase):
    def test_preview_scan_during_combat_without_localization_and_reuse(self):
        from src.engine.MapleStoryAutoLevelUp import MapleStoryAutoBot
        from unittest.mock import Mock
        bot=SimpleNamespace(img_frame=np.zeros((300,400,3),dtype=np.uint8),
            img_minimap=np.zeros((20,20,3),dtype=np.uint8),loc_minimap=(0,0),
            _combat_hold=True,nametag_hit=False,graph_position_valid=False,
            cfg={},monsters_info={},loc_player=(100,100))
        with patch.object(MapleStoryAutoBot,'get_monsters_in_range',return_value=[
                dict(position=(5,5),size=(10,10)),dict(position=(350,150),size=(20,30))]) as detect:
            try:
                MapleStoryAutoBot.refresh_visible_monsters(bot,10)
                bot._visible_worker.future.result(timeout=2)
                MapleStoryAutoBot.refresh_visible_monsters(bot,10.1)
                self.assertEqual(len(bot.visible_monsters),1)
                self.assertEqual(bot.visible_monsters[0]['position'],(350,150))
                self.assertEqual(detect.call_count,1)
                detect.return_value=[]
                MapleStoryAutoBot.refresh_visible_monsters(bot,11)
                bot._visible_worker.future.result(timeout=2)
                MapleStoryAutoBot.refresh_visible_monsters(bot,11.1)
                self.assertEqual(bot.visible_monsters,[])
            finally:bot._visible_worker.close()

    def test_confirmed_teleport_is_preferred(self):
        _,g=scene()
        for e in g['edges']:e['enabled']=e['kind'] in ('rope','teleport')
        route=route_to(g,'P1',(40,70),dict(platform='P2',x=40,y=62))
        selected=next(e for e in g['edges'] if e['id']==route[1][0])
        self.assertEqual(selected['kind'],'teleport')

    def test_detection_returns_width_then_height(self):
        from src.engine.MapleStoryAutoLevelUp import MapleStoryAutoBot
        image=np.zeros((100,150,3),dtype=np.uint8)
        pattern=np.random.default_rng(8).integers(30,240,(11,23,3),dtype=np.uint8)
        image[30:41,70:93]=pattern
        bot=SimpleNamespace(img_frame=image,loc_player=(0,0),monsters_info={'test':[(pattern,None)]},
            cfg={'character':{'width':1,'height':1},'monster_detect':{'mode':'grayscale','contour_blur':3,'diff_thres':0.001,'with_enemy_hp_bar':False}})
        result=MapleStoryAutoBot.get_monsters_in_range(bot,(0,0),(150,100))
        self.assertEqual(len(result),1);self.assertEqual(result[0]['size'],(23,11))

    def test_calibration_projection_and_resolution_guard(self):
        _,g=scene()
        g['hunt_calibration']=calibrate([(100,200),(500,100)],[(20,70),(70,57.5)],(260,168),(40,66),(768,1366,3))
        mobs=[dict(position=(250,184),size=(20,16))]
        targets=project_monsters(mobs,(260,168),(40,66),g,(768,1366,3))
        self.assertEqual(len(targets),1);self.assertEqual(targets[0]['platform'],'P1');self.assertAlmostEqual(targets[0]['x'],40)
        self.assertEqual(project_monsters(mobs,(260,168),(40,66),g,(600,800,3)),[])
    def test_choose_reachable_and_walk_distance(self):
        _,g=scene();enable(g,'rope')
        targets=[dict(platform='P2',x=40,y=62),dict(platform='P1',x=75,y=70)]
        picked=choose_target(g,'P1',(40,70),targets)
        self.assertEqual(picked[1]['platform'],'P2')
        for e in g['edges']:e['enabled']=False
        self.assertEqual(choose_target(g,'P1',(40,70),targets)[1]['platform'],'P1')
    def test_same_platform_goal_and_arrival(self):
        _,g=scene();n=Navigator(g);n.hunt_target=dict(platform='P1',x=65,y=70)
        for t in (0,.1,.2):cmd=n.step((30,70),t)
        self.assertEqual(cmd,('right','none','none'))
        self.assertEqual(n.step((65,70),.3),('none','none','none'))
    def test_random_patrol_only_reachable(self):
        _,g=scene();enable(g,'rope');n=Navigator(g);n.random_patrol=True
        with patch('random.choice',side_effect=lambda xs:xs[0]) as choice:
            for t in (0,.1,.2):n.step((15,70),t)
            choice.assert_called_once_with(['P2'])
        self.assertEqual(n.goal,'P2')
    def test_scan_target_then_three_empty_scans(self):
        from src.engine.MapleStoryAutoLevelUp import MapleStoryAutoBot
        _,g=scene();enable(g,'rope');g['hunt_calibration']=dict(scale=[8,8],offset=[0,0],frame_size=[400,300])
        n=Navigator(g)
        bot=SimpleNamespace(graph_navigator=n,graph_position_valid=True,nametag_hit=True,_combat_hold=False,
            img_frame=np.zeros((300,400,3),dtype=np.uint8),img_minimap=np.zeros((20,20,3),dtype=np.uint8),loc_minimap=(0,0),
            loc_player=(100,100),loc_player_global=(40,70))
        bot.visible_monsters=[dict(position=(170,90),size=(20,10))]
        with patch.object(MapleStoryAutoBot,'refresh_visible_monsters'):
            bot._visible_scan_time=bot._visible_source_time=0
            MapleStoryAutoBot.update_visible_hunt(bot,0)
            self.assertEqual(n.hunt_target['platform'],'P1')
            bot.visible_monsters=[]
            # Empty scans before arrival cannot release the locked destination.
            for t in (.1,.2,.3,.4):
                bot._visible_scan_time=bot._visible_source_time=t
                MapleStoryAutoBot.update_visible_hunt(bot,t)
                self.assertEqual(n.hunt_target['x'],50)
            bot.loc_player_global=(50,70)
            for t in (1,2):
                bot._visible_scan_time=bot._visible_source_time=t
                MapleStoryAutoBot.update_visible_hunt(bot,t);self.assertIsNotNone(n.hunt_target)
            bot._visible_scan_time=bot._visible_source_time=3
            MapleStoryAutoBot.update_visible_hunt(bot,3);self.assertIsNone(n.hunt_target)
        self.assertTrue(n.random_patrol)

if __name__=='__main__':unittest.main()
