import unittest
from unittest.mock import patch
from src.navigation.horizontal_motion import HorizontalMotion,duration


class MotionTests(unittest.TestCase):
    platform=dict(id='P1',x1=0,x2=100,y=50)

    def test_prepare_one_teleport_then_wait_for_landing(self):
        move=HorizontalMotion()
        self.assertEqual(move.step(self.platform,(20,50),90,16,0),('right','none','none'))
        self.assertEqual(move.step(self.platform,(21,50),90,16,.16),('right','none','teleport'))
        self.assertEqual(move.step(self.platform,(21,50),90,16,.18),('right','none','teleport'))
        self.assertEqual(move.step(self.platform,(37,50),90,16,.2),('right','none','none'))

    def test_near_target_and_slope_walk_without_forced_pause(self):
        for p,target in ((self.platform,30),(dict(self.platform,end_y=60),90)):
            move=HorizontalMotion()
            with patch('random.gauss',side_effect=lambda mean,sigma:mean):
                self.assertEqual(move.step(p,(20,50),target,16,0)[2],'none')
                self.assertEqual(move.step(p,(21,50),target,16,.31),('right','none','none'))
                self.assertEqual(move.step(p,(21,50),target,16,.46),('right','none','none'))

    def test_failed_teleport_falls_back_to_walking(self):
        move=HorizontalMotion()
        move.step(self.platform,(20,50),90,16,0)
        move.step(self.platform,(21,50),90,16,.16)
        self.assertEqual(move.step(self.platform,(21,50),90,16,1),('right','none','none'))
        self.assertEqual(move.phase,'walk')
        self.assertGreater(move.next_teleport,5)

    def test_duration_is_bounded(self):
        with patch('random.gauss',return_value=-100):self.assertEqual(duration(.3,.1,.1,.5),.1)
        with patch('random.gauss',return_value=100):self.assertEqual(duration(.3,.1,.1,.5),.5)


if __name__=='__main__':unittest.main()
