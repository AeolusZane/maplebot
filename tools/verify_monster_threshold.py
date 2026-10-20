import unittest
from src.utils.monster_threshold import map_threshold


class ThresholdTests(unittest.TestCase):
    def test_maps_are_independent(self):
        data={'map_monster_thresholds':{'A':.15,'B':.08}}
        self.assertEqual(map_threshold(data,'A',.1),.15)
        self.assertEqual(map_threshold(data,'B',.1),.08)
        self.assertEqual(map_threshold(data,'C',.1),.1)

    def test_unset_and_invalid_fall_back(self):
        for value in (None,False,float('nan'),float('inf'),-1,2,'bad'):
            self.assertEqual(map_threshold({'map_monster_thresholds':{'A':value}},'A',.1),.1)
        self.assertEqual(map_threshold({},'A',.12),.12)

if __name__=='__main__':unittest.main()
