import unittest
from src.navigation.map_graph import Navigator

class SlopeTests(unittest.TestCase):
    def test_p11_slope_starts_left_jump_at_entrance_and_targets_top(self):
        edge=dict(id='E7',src='P11',dst='P28',kind='walk',start=[229,58],end=[227,57],enabled=True)
        n=Navigator(dict(platforms=[dict(id='P11',x1=229,x2=251,y=58),
            dict(id='P28',x1=223,x2=229,y=55,end_y=58)],edges=[edge],ropes=[]))
        for t in (0,.1,.2):command=n.step((230,58),t)
        self.assertEqual(command,('left','none','none'))
        self.assertEqual(n.transit['end'],[223,55])
        self.assertEqual(n.step((229,58),.4),('left','none','jump'))
        self.assertEqual(edge['end'],[227,57])

    def test_generic_second_recovery_cannot_reverse_uphill(self):
        n,_=self.nav();n.aim=('edge','E1');n._unstuck_origin=(41,70);n._unstuck_attempts=1
        n.deadline=20
        self.assertEqual(n.step((41,70),6),('right','none','none'))
        self.assertEqual(n.step((41,70),6.2),('right','none','jump'))

    def nav(self):
        e=dict(id='E1',src='P1',dst='P2',kind='walk',start=[40,70],end=[42,68],enabled=True)
        n=Navigator(dict(platforms=[dict(id='P1',x1=10,x2=40,y=70),
            dict(id='P2',x1=40,x2=46,y=70,end_y=64)],edges=[e],ropes=[]))
        n.transit=e;n.path=['E1'];n.deadline=2;n.last_pos=(41,70);n.last_progress=0
        return n,e

    def test_uphill_stall_jumps_instead_of_false_arrival(self):
        n,e=self.nav()
        self.assertEqual(n.step((41,70),.9),('right','none','none'))
        self.assertIsNotNone(n.transit)
        self.assertEqual(n.step((42,65),1),('right','none','none'))
        self.assertEqual(n.step((42,65),1.1),('right','none','jump'))
        self.assertEqual(n.step((42,65),1.2),('right','none','jump'))
        self.assertEqual(n.step((42,65),1.4),('right','none','none'))
        self.assertIsNotNone(n.transit)
        for t in (1.8,1.9,2,2.1):n.step((42,68),t)
        self.assertIsNone(n.transit);self.assertEqual(n.current,'P2')

    def test_repeated_stall_disables_edge(self):
        n,e=self.nav()
        self.assertEqual(n.step((41,70),.9)[0],'right')
        self.assertEqual(n.step((41,70),1.1)[2],'jump')
        self.assertEqual(n.step((41,70),1.8)[0],'right')
        self.assertEqual(n.step((41,70),2)[2],'jump')
        self.assertEqual(n.step((41,70),2.7),('none','none','none'))
        self.assertFalse(e['enabled']);self.assertIsNone(n.transit)

    def test_left_uphill_keeps_left_direction_during_jump(self):
        n,_=self.nav()
        slope=dict(id='left',x1=20,x2=30,y=60,end_y=70)
        self.assertEqual(n.slope_assist(slope,(29,70),21,1),('left','none','none'))
        self.assertEqual(n.step((29,70),1.2),('left','none','jump'))
        self.assertEqual(n.step((28,65),1.5),('left','none','none'))

    def test_downhill_and_flat_do_not_trigger_jump(self):
        n,e=self.nav()
        self.assertIsNone(n.slope_assist(n.platforms['P2'],(44,66),41,2))
        self.assertIsNone(n.slope_assist(n.platforms['P1'],(20,70),30,2))

if __name__=='__main__':unittest.main()
