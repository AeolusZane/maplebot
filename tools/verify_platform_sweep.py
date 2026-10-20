import unittest
from src.navigation.platform_sweep import PlatformSweep
from tools.verify_map_graph import scene,enable

class SweepTests(unittest.TestCase):
    def test_long_platform_left_region_cannot_be_starved_by_right_mobs(self):
        g=dict(platforms=[dict(id='P1',x1=0,x2=220,y=70)],edges=[],profile={})
        s=PlatformSweep()
        s.observe([dict(platform='P1',x=210,y=70)]*10,0,in_view=['P1'])
        s.next_target(g,'P1',(210,70),0)
        s.observe([dict(platform='P1',x=210,y=70)]*10,91,in_view=['P1'])
        t=s.next_target(g,'P1',(210,70),91)
        self.assertEqual(s.explore_target,'P1');self.assertLess(t['x'],10)
        s.observe([dict(platform='P1',x=215,y=70)]*20,101,in_view=['P1'])
        self.assertEqual(s.next_target(g,'P1',(150,70),101),t)
        s.next_target(g,'P1',(t['x'],70),102)
        self.assertIsNone(s.explore_target);self.assertNotIn('P1',s.done)

    def test_previously_visited_region_is_revisited_after_age_limit(self):
        _,g=scene();enable(g,'rope');s=PlatformSweep();s.visits.update(P1=5,P2=5)
        s.next_target(g,'P1',(15,70),0)
        s.observe([dict(platform='P1',x=15,y=70)]*20,95,in_view=['P1','P2'])
        s.next_target(g,'P1',(15,70),95)
        self.assertIsNotNone(s.explore_target)

    def test_two_clears_explore_unvisited_offscreen_and_ignore_local_mobs(self):
        _,g=scene();enable(g,'rope');s=PlatformSweep();s.local_clears=2;s.visits['P1']=2
        s.observe([{'platform':'P1'}]*20,10,in_view=['P1'])
        t=s.next_target(g,'P1',(15,70),10)
        self.assertEqual(s.explore_target,'P2')
        s.observe([{'platform':'P1'}]*30,11,in_view=['P1'])
        self.assertFalse(s.redirect_to_crowd(g,'P1',(20,70),11))
        t=s.next_target(g,'P2',(t['x'],62),12)
        s.next_target(g,'P2',(t['x'],62),13)
        self.assertIsNone(s.explore_target);self.assertEqual(s.local_clears,0)
        self.assertEqual(s.visits['P2'],1)

    def test_partially_visible_platform_not_used_for_exploration(self):
        _,g=scene();enable(g,'rope');s=PlatformSweep();s.local_clears=2;s.visits['P1']=2
        s.observe([],10,in_view=['P1','P2'])
        s.next_target(g,'P1',(15,70),10)
        self.assertIsNone(s.explore_target)

    def test_remote_three_monsters_override_local_respawns(self):
        _,g=scene();enable(g,'rope');s=PlatformSweep()
        s.observe([{'platform':'P1'}]*20+[{'platform':'P2'}]*3,10)
        self.assertEqual(s.next_target(g,'P1',(15,70),10)['platform'],'P2')

    def test_latest_scan_replaces_old_hotspots_and_redirects(self):
        _,g=scene();enable(g,'rope');s=PlatformSweep()
        s.observe([dict(platform='P2',x=35,y=62)]*5,10)
        t=s.next_target(g,'P1',(15,70),10)
        self.assertEqual((t['platform'],t['x']),('P2',35))
        s.observe([dict(platform='P1',x=50,y=70)],20)
        self.assertNotIn('P2',s.live_counts(20))
        self.assertTrue(s.redirect_to_crowd(g,'P1',(20,70),20))
        self.assertEqual(s.target,'P1')

    def test_empty_and_expired_scan_resume_patrol(self):
        _,g=scene();enable(g,'rope');s=PlatformSweep()
        s.observe([{'platform':'P2'}]*2,10)
        self.assertEqual(s.next_target(g,'P1',(15,70),10)['platform'],'P2')
        s.observe([],20)
        self.assertEqual(s.next_target(g,'P1',(15,70),20)['platform'],'P1')
        s.observe([{'platform':'P2'}]*5,30)
        s.next_target(g,'P1',(15,70),30)
        self.assertEqual(s.next_target(g,'P1',(15,70),43)['platform'],'P1')

    def test_unreachable_monsters_do_not_block_patrol(self):
        _,g=scene();s=PlatformSweep()
        s.observe([{'platform':'P2'}]*10,10)
        self.assertEqual(s.next_target(g,'P1',(15,70),10)['platform'],'P1')

    def test_same_scan_does_not_reset_movement_and_old_scan_ignored(self):
        _,g=scene();enable(g,'rope');s=PlatformSweep()
        s.observe([{'platform':'P2'}]*5,10)
        s.next_target(g,'P1',(15,70),10)
        self.assertFalse(s.redirect_to_crowd(g,'P1',(20,70),11))
        s.observe([{'platform':'P1'}]*20,9)
        self.assertEqual(s.counts,{'P2':5})

    def test_both_ends_then_next_platform_and_round(self):
        _,g=scene();enable(g,'rope');s=PlatformSweep()
        t=s.next_target(g,'P1',(15,70));self.assertEqual(t['platform'],'P1')
        first=t['x'];t=s.next_target(g,'P1',(first,70))
        self.assertNotEqual(t['x'],first);self.assertFalse(s.done)
        t=s.next_target(g,'P1',(t['x'],70));self.assertEqual(s.done,{'P1'})
        self.assertEqual(t['platform'],'P2')
        self.assertEqual(s.next_target(g,'P1',(30,70)),t)
        t=s.next_target(g,'P2',(t['x'],62));self.assertEqual(t['platform'],'P2')
        s.next_target(g,'P2',(t['x'],62));self.assertEqual(s.round,2)

    def test_progress_is_not_lost_after_replan(self):
        _,g=scene();enable(g,'rope');s=PlatformSweep()
        t=s.next_target(g,'P1',(15,70));t=s.next_target(g,'P1',(t['x'],70))
        t=s.next_target(g,'P1',(t['x'],70))
        for _ in range(5):self.assertEqual(s.next_target(g,'P1',(25,70)),t)

if __name__=='__main__':unittest.main()
