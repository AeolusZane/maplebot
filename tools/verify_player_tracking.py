import unittest
import numpy as np
from src.utils.player_tracking import PlayerTracking,AttackRecheck


class TrackingTests(unittest.TestCase):
    def test_stationary_camera_map_motion_corrects_cached_position(self):
        gray=np.random.default_rng(3).integers(0,255,(400,600),dtype=np.uint8)
        t=PlayerTracking();t.update(gray,(20,20),(200,200),True,True,(10,10),0)
        pos,valid=t.update(gray,(22,20),(200,200),False,True,(10,10),.1)
        self.assertTrue(valid);self.assertAlmostEqual(pos[0],220,delta=1)
        pos,valid=t.update(gray,(22,20),(200,200),False,True,(10,10),4)
        self.assertFalse(valid)
        pos,valid=t.update(gray,(22,20),(225,201),True,True,(10,10),5)
        self.assertEqual(pos,(225,201));self.assertTrue(valid)

    def test_scroll_compensates_map_movement(self):
        gray=np.random.default_rng(9).integers(0,255,(400,600),dtype=np.uint8)
        t=PlayerTracking();t.update(gray,(20,20),(200,200),True,True,(10,10),0)
        pos,valid=t.update(np.roll(gray,-20,axis=1),(22,20),(200,200),False,True,(10,10),.1)
        self.assertTrue(valid);self.assertAlmostEqual(pos[0],200,delta=3)

    def test_recheck_needs_actual_attacks_and_strict_reacquisition(self):
        r=AttackRecheck()
        self.assertFalse(r.update((100,100),0,0,False))
        self.assertFalse(r.update((100,100),4,2,False))
        self.assertTrue(r.update((100,100),5,3,False))
        self.assertTrue(r.update(None,6,3,False))
        self.assertFalse(r.update((100,100),7,3,True))

    def test_unknown_platform_does_not_skip_nearby_attack(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from src.states.hunting import HuntingState
        nav=SimpleNamespace(transit=None,fault=None,locate=lambda p:None,
            step=Mock(),status='',last_progress=0)
        bot=SimpleNamespace(graph_navigator=nav,graph_position_valid=True,
            nametag_hit=True,loc_player_global=(136,70),_graph_status_last='',kb=Mock())
        def detect():bot._combat_hold=True;bot.cmd_action='attack'
        bot.update_cmd_by_mob_detection=detect
        HuntingState(None,bot).on_frame()
        bot.kb.set_command.assert_called_with('none none attack');nav.step.assert_not_called()

if __name__=='__main__':unittest.main()
