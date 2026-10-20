import unittest
from src.navigation.map_graph import Navigator

class UnknownRecoveryTests(unittest.TestCase):
    def nav(self):
        return Navigator(dict(platforms=[dict(id='P1',x1=10,x2=30,y=50)],edges=[],ropes=[]))

    def test_wait_walk_then_stable_platform_resets_fault(self):
        n=self.nav();n.fault='到达超时'
        self.assertIsNone(n.recover_unknown((35,50),0))
        self.assertIsNone(n.recover_unknown((35,50),1))
        self.assertEqual(n.recover_unknown((35,50),2),('left','none','jump'))
        self.assertEqual(n.recover_unknown((35,50),2.1),('left','none','jump'))
        self.assertEqual(n.recover_unknown((35,50),2.4),('left','none','none'))
        for t in (3,3.1,3.2):self.assertEqual(n.recover_unknown((29,50),t),('none','none','none'))
        self.assertIsNone(n.fault);self.assertEqual(n.current,'P1')

    def test_two_attempts_then_observe_and_retry(self):
        n=self.nav();n.recover_unknown((35,50),0)
        n.recover_unknown((35,50),2)
        self.assertEqual(n.recover_unknown((35,50),5),('right','none','jump'))
        self.assertEqual(n.recover_unknown((35,50),8),('none','none','none'))
        self.assertEqual(n.recover_unknown((35,50),10),('none','none','none'))
        self.assertEqual(n.recover_unknown((35,50),12),('left','none','jump'))

    def test_invalid_transit_and_rope_do_not_sideways_search(self):
        n=self.nav()
        for t in (0,3):self.assertIsNone(n.recover_unknown((35,50),t,False))
        n.transit={'kind':'jump'}
        for t in (0,3):self.assertIsNone(n.recover_unknown((35,50),t))
        n.transit=None;n.graph['ropes']=[dict(id='R1',x=35,y1=40,y2=60)]
        for t in (0,3):self.assertIsNone(n.recover_unknown((35,50),t))

if __name__=='__main__':unittest.main()
