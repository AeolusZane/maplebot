import unittest
from src.navigation.rope_grab import RopeGrab
from src.navigation.map_graph import supplement_upward_teleports
from tools.verify_teleport_regions import TeleportRegionTests

class RopeGrabTests(unittest.TestCase):
    def test_approach_jump_then_capture(self):
        r=RopeGrab(dict(start=[85,77],end=[85,60]),dict(x1=49,x2=268),0)
        self.assertEqual(r.step((82,77),0)[0],('right','up','jump'))
        self.assertEqual(r.step((83,76),.1)[0],('right','up','jump'))
        self.assertEqual(r.step((85,74),.3)[0],('none','up','none'))
        self.assertFalse(r.grabbed)
        r.step((85,74),.7);r.step((85,73),1.1)
        self.assertTrue(r.grabbed)
        self.assertEqual(r.step((85,70),2)[0],('none','up','none'))

    def test_below_rope_backs_off_then_jumps_toward_it(self):
        r=RopeGrab(dict(start=[30,70],end=[30,40]),dict(x1=10,x2=50),0)
        self.assertEqual(r.step((30,70),0)[0],('left','none','none'))
        self.assertEqual(r.step((27,70),.3)[0],('right','up','jump'))
        r.step((30,70),1.6)
        self.assertEqual(r.step((27,70),1.9)[0],('right','up','jump'))
        self.assertEqual(r.step((30,70),4)[0][2],'none')
        self.assertEqual(r.jump_count,2)
        self.assertFalse(r.grabbed)

    def test_boundary_and_downward(self):
        r=RopeGrab(dict(start=[10,70],end=[10,40]),dict(x1=10,x2=20),0)
        self.assertEqual(r.step((10,70),0)[0],('right','none','none'))
        self.assertEqual(r.step((13,70),.3)[0],('left','up','jump'))
        down=RopeGrab(dict(start=[30,40],end=[30,70]),dict(x1=10,x2=50),0)
        self.assertEqual(down.step((30,40),0)[0],('none','down','none'))

    def test_supplement_preserves_existing_and_deduplicates(self):
        g=TeleportRegionTests().graph();g['ropes']=[]
        g['platforms'][1]['y']=59;g['profile'].update(teleport_y=11,jump_x=12,jump_y=8,drop_x=8,drop_y=24)
        g['edges']=[]
        added=supplement_upward_teleports(g)
        self.assertEqual(len(added),1);self.assertFalse(added[0]['enabled'])
        self.assertEqual(supplement_upward_teleports(g),[])

if __name__=='__main__':unittest.main()
