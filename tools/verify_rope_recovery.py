import unittest
from types import SimpleNamespace
from src.navigation.map_graph import Navigator


class RopeRecoveryTests(unittest.TestCase):
    def test_rope_drop_uses_direction_then_single_jump_window(self):
        n=self.nav()
        n.transit=dict(id='E1',kind='rope',src='P1',dst='P2',start=[30,40],end=[30,70],enabled=True)
        n.path=['E1'];n.deadline=8;n.started=0
        self.assertEqual(n.step((30,55),.1),('right','none','none'))
        self.assertEqual(n.step((30,55),.25),('right','none','jump'))
        self.assertEqual(n.step((31,56),.5),('right','none','none'))

    def test_downward_arrival_requires_surface_and_margin(self):
        n=self.nav()
        n.transit=dict(id='E1',kind='rope',src='P1',dst='P2',start=[30,40],end=[30,70],enabled=True)
        n.path=['E1'];n.deadline=8;n.started=0
        self.assertEqual(n.step((30,68),.1),('right','none','none'))
        for t in (.2,.3,.4):self.assertEqual(n.step((30,70),t),('none','down','none'))
        self.assertIsNotNone(n.transit)
        for t in (.6,.7,.8):n.step((30,70),t)
        self.assertIsNone(n.transit)

    def failed_grab(self):
        n=self.nav()
        n.transit=dict(id='E1',kind='rope',src='P2',dst='P1',start=[30,70],end=[30,40])
        n._rope_grab_edge=id(n.transit)
        n._rope_grab=SimpleNamespace(jump_count=2,grabbed=False,next_jump=1)
        return n

    def test_failed_grab_releases_only_after_stable_landing(self):
        n=self.failed_grab()
        self.assertFalse(n.release_failed_rope((30,70),2))
        self.assertTrue(n.release_failed_rope((30,70),2.4))
        self.assertIsNone(n.transit)
        self.assertEqual(n.current,'P2')
        self.assertIsNone(n.recover_rope((30,70),2.4))

    def test_failed_grab_does_not_release_airborne_invalid_or_grabbed(self):
        for pos,valid,grabbed in [((30,68),True,False),((30,70),False,False),((30,70),True,True)]:
            n=self.failed_grab();n._rope_grab.grabbed=grabbed
            self.assertFalse(n.release_failed_rope(pos,2,valid))
            self.assertFalse(n.release_failed_rope(pos,3,valid))
            self.assertIsNotNone(n.transit)

    def test_rope_top_one_pixel_above_platform_gets_bounded_probe(self):
        n=self.nav();n.graph['ropes'][0]['y1']=39
        for t in (0,.1,.2):command=n.recover_rope((30,40),t)
        self.assertEqual(command,('none','up','none'))
        self.assertEqual(n.recover_rope((30,40),.5),('none','up','none'))
        commands=[n.recover_rope((30,40),t) for t in (1,1.1,1.2)]
        self.assertEqual(sum(c[2]=='jump' for c in commands),1)
        self.assertIsNotNone(n.rope_recovery)
        self.assertEqual(n.recover_rope((30,40),1.3),('left','none','none'))
        for t in (1.7,1.8,1.9,2):n.recover_rope((27,40),t)
        self.assertIsNone(n.rope_recovery)
        self.assertIsNone(n.recover_rope((27,40),2))
        for t in (2.1,2.2,2.3):self.assertIsNone(n.recover_rope((30,40),t))

    def test_exit_failure_recovers_on_other_platform_with_two_pixel_offset(self):
        n=self.nav();n.graph['ropes'][0]['y1']=39
        for t in (0,.1,.2,1,1.1,1.2,4):n.recover_rope((30,40),t)
        self.assertIsNotNone(n.fault)
        for t in (5,5.1,5.2,5.3):n.recover_rope((25,68),t)
        self.assertIsNone(n.fault);self.assertIsNone(n.rope_recovery)
        self.assertEqual(n.current,'P2')

    def test_still_on_rope_never_releases_to_combat(self):
        n=self.nav();n.graph['ropes'][0]['y1']=39
        for t in (0,.1,.2,1,1.1,1.2):n.recover_rope((30,40),t)
        self.assertEqual(n.recover_rope((30,40),4),('none','none','none'))
        self.assertIsNotNone(n.rope_recovery)
        self.assertIn('未确认落地',n.fault)

    def nav(self):
        return Navigator(dict(platforms=[dict(id='P1',x1=10,x2=50,y=40),
            dict(id='P2',x1=10,x2=50,y=70)],ropes=[dict(id='R1',x=30,y1=40,y2=70)],edges=[]))

    def test_fault_midrope_climbs_and_clears_after_top_confirmed(self):
        n=self.nav();n.fault='导航无进展'
        self.assertEqual(n.recover_rope((30,55),0),('none','none','none'))
        n.recover_rope((30,55),.1)
        self.assertEqual(n.recover_rope((30,55),.2),('none','up','none'))
        self.assertIsNone(n.fault)
        self.assertEqual(n.recover_rope((30,48),1),('none','up','none'))
        for t in (2,2.1,2.2):self.assertEqual(n.recover_rope((30,40),t),('none','none','none'))
        self.assertIsNone(n.rope_recovery);self.assertEqual(n.current,'P1')

    def test_no_motion_timeout_does_not_retry_forever(self):
        n=self.nav()
        for t in (0,.1,.2):n.recover_rope((30,55),t)
        self.assertEqual(n.recover_rope((30,55),7),('none','none','none'))
        self.assertIn('恢复失败',n.fault)
        self.assertEqual(n.recover_rope((30,55),8),('none','none','none'))

    def test_ground_invalid_and_unmarked_positions_do_not_climb(self):
        n=self.nav()
        for pos,valid in [((30,70),True),((34,55),True),((30,55),False)]:
            self.assertIsNone(n.recover_rope(pos,1,valid))

    def test_healthy_downward_transit_keeps_original_direction(self):
        n=self.nav();n.transit=dict(kind='rope');n.last_progress=0;n.deadline=8
        self.assertIsNone(n.recover_rope((30,55),1))

    def test_two_pixels_below_top_does_not_finish_climb(self):
        n=self.nav()
        edge=dict(id='E1',kind='rope',src='P2',dst='P1',start=[30,70],end=[30,40],enabled=True)
        n.transit=edge;n.path=['E1'];n.deadline=8;n.started=0
        for t in (.1,.2,.3,.4):
            self.assertEqual(n.step((30,42),t),('none','up','none'))
            self.assertIsNotNone(n.transit)
        for t in (.5,.6,.7,.9,1,1.1):n.step((30,40),t)
        self.assertIsNone(n.transit);self.assertEqual(n.current,'P1')

    def test_already_stopped_below_top_recovers_despite_platform_tolerance(self):
        n=self.nav()
        self.assertEqual(n.locate((30,42)),'P1')
        for t in (0,.1,.2):command=n.recover_rope((30,42),t)
        self.assertEqual(command,('none','up','none'))
        self.assertEqual(n.recover_rope((30,42),.3),('none','up','none'))

if __name__=='__main__':unittest.main()
