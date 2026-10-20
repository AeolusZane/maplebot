import unittest
from src.navigation.reset_escape import ResetEscape

class ResetTests(unittest.TestCase):
    def recovery(self):
        return ResetEscape(dict(id='P6',x1=180,x2=192,y=40),[dict(id='R5',x=188,y1=42,y2=56)],0)

    def test_rope_down_then_drop_and_jump_rotation(self):
        r=self.recovery()
        self.assertEqual(r.step((184,40),0,True,False)[0],('right','down','none'))
        self.assertEqual(r.step((188,44),1,True,False)[0],('none','down','none'))
        r.step((188,56),2,True,False)
        self.assertEqual(r.step((188,56),2.1,True,False)[0],('none','down','jump'))
        r.step((188,56),3.3,True,False)
        self.assertEqual(r.step((188,56),3.5,True,False)[0],('left','none','jump'))

    def test_reset_platform_never_counts_as_success_and_invalid_stops(self):
        r=self.recovery()
        for t in (0,.1,.2,.3):r.step((185,40),t,True,False)
        self.assertFalse(r.done)
        self.assertEqual(r.step((185,40),.4,False,False)[0],('none','none','none'))
        for t in (1,1.1,1.2,1.3):r.step((188,74),t,True,True)
        self.assertTrue(r.done)

if __name__=='__main__':unittest.main()
