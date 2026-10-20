import unittest
from unittest.mock import patch
import cv2
import numpy as np
from src.utils.monster_names import confirm_name,template


class NameTests(unittest.TestCase):
    def scene(self):
        pattern=template('石膏犬')
        self.assertIsNotNone(pattern)
        frame=np.zeros((180,250,3),np.uint8)
        h,w=pattern.shape
        frame[100:100+h,80:80+w]=pattern[:,:,None]
        monster=dict(name='石膏犬',position=(90,50),size=(60,50),score=.1)
        return frame,monster

    def test_only_after_attack_and_real_name_hit(self):
        frame,m=self.scene()
        self.assertIsNone(confirm_name(frame,m,1,False))
        found=confirm_name(frame,m,1,True)
        self.assertTrue(found['name_confirmed'])
        self.assertEqual(found['position'],m['position'])
        self.assertIsNone(confirm_name(np.zeros_like(frame),found,1.1,True))

    def test_moves_body_with_label_and_requires_periodic_body_recheck(self):
        frame,m=self.scene();found=confirm_name(frame,m,1,True)
        moved=np.roll(frame,10,axis=1)
        updated=confirm_name(moved,found,2,True)
        self.assertEqual(updated['position'],(100,50))
        self.assertIsNone(confirm_name(moved,updated,7.1,True))

    def test_missing_species_and_stale_tracks_do_not_confirm(self):
        frame,m=self.scene();m['name']='不存在'
        self.assertIsNone(confirm_name(frame,m,1,True))
        m['name']='石膏犬';m['track_age']=1.3
        self.assertIsNone(confirm_name(frame,m,1,True))


if __name__=='__main__':unittest.main()
