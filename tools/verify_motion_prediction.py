import unittest
from src.navigation.motion_prediction import MotionPrediction
from src.navigation.map_graph import Navigator

class PredictionTests(unittest.TestCase):
    def test_direction_latency_and_jump_rejection(self):
        m=MotionPrediction()
        for t,x in [(0,30),(.1,29),(.2,28)]:m.update((x,58),t)
        self.assertAlmostEqual(m.advance(28,20,100),26)
        self.assertEqual(m.advance(28,35,100),28)
        m.update((12,58),.3)
        self.assertEqual(m.advance(12,0,100),12)
        m.update((11,58),1)
        self.assertEqual(m.vx,0)

    def test_moving_left_jumps_before_slope_entrance(self):
        edge=dict(id='E',src='P11',dst='P28',kind='walk',start=[229,58],end=[227,57],enabled=True)
        n=Navigator(dict(platforms=[dict(id='P11',x1=229,x2=251,y=58),
            dict(id='P28',x1=223,x2=229,y=55,end_y=58)],edges=[edge],ropes=[]))
        n.input_latency_ms=100
        n.step((234,58),0);n.step((233,58),.1)
        self.assertEqual(n.step((232,58),.2),('left','none','jump'))
        self.assertEqual(n.transit['end'],[223,55])

if __name__=='__main__':unittest.main()
