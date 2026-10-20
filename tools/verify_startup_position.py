import unittest
from src.navigation.startup_position import StartupPosition

class StartupTests(unittest.TestCase):
    def test_left_then_right_with_bounded_directional_jumps(self):
        s=StartupPosition();self.assertEqual(s.step(0,False),('none','none','none'))
        for t in (.4,1,1.5):self.assertEqual(s.step(t,False),('left','none','none'))
        for t in (1.6,2,2.7):self.assertEqual(s.step(t,False),('right','none','none'))
        self.assertIsNone(s.step(2.8,False));self.assertIsNone(s.step(10,False))

    def test_jump_windows_release_between_directions(self):
        s=StartupPosition();s.step(0,False)
        self.assertEqual(s.step(.5,False),('left','none','jump'))
        self.assertEqual(s.step(.7,False),('left','none','none'))
        self.assertEqual(s.step(1.8,False),('right','none','jump'))
        self.assertEqual(s.step(2,False),('right','none','none'))

    def test_stable_detection_finishes_early_and_never_restarts(self):
        s=StartupPosition();s.step(0,True);s.step(.1,True)
        self.assertIsNone(s.step(.2,True));self.assertIsNone(s.step(2,False))

if __name__=='__main__':unittest.main()
