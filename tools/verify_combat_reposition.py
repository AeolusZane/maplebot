import unittest
from src.states.combat_reposition import CombatReposition
from src.navigation.horizontal_motion import HorizontalMotion

class RepositionTests(unittest.TestCase):
    def test_burst_moves_inward_then_stops_on_measured_displacement(self):
        s=CombatReposition();p=dict(x1=0,x2=30)
        self.assertIsNone(s.step(0,(25,50),p,True,0))
        self.assertIsNone(s.step(.5,(25,50),p,True,6))
        self.assertEqual(s.step(.9,(25,50),p,True,6),('left','none','none'))
        self.assertEqual(s.step(1,(23,50),p,True,7),('none','none','none'))

    def test_unknown_or_narrow_platform_does_not_reposition(self):
        s=CombatReposition()
        for t in (0,1,2):self.assertIsNone(s.step(t,(2,50),dict(x1=0,x2=4),True,int(t*10)))
        self.assertIsNone(s.step(3,(2,50),None,True,50))

    def test_fine_approach_does_not_stop_outside_trigger_region(self):
        m=HorizontalMotion();p=dict(id='P',x1=0,x2=30,y=50)
        self.assertEqual(m.step(p,(20,50),20.75,16,0,arrival_tolerance=.25),('right','none','none'))

if __name__=='__main__':unittest.main()
