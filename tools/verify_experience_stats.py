import unittest
from src.utils.experience_stats import ExperienceStats,parse_experience

class ExperienceTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_experience('EXP 12,345 [12.34%]'),(12345,12.34))
        self.assertEqual(parse_experience('12345 (12.34％)'),(12345,12.34))
        self.assertEqual(parse_experience('12 [0.00%]'),(12,0.0))
        with self.assertRaises(ValueError):parse_experience('12.34%')
    def test_rates(self):
        s=ExperienceStats();s.add(0,1000,10,'');s.add(180,1600,16,'')
        self.assertEqual(s.total,600);self.assertEqual(s.per_minute,200)
        s.add(360,2500,25,'');self.assertEqual(s.per_minute,250)
    def test_level_up_does_not_invent_experience(self):
        s=ExperienceStats();s.add(0,9000,90,'');s.add(180,500,4,'')
        self.assertTrue(s.gaps);self.assertEqual(s.total,0);self.assertIsNone(s.per_minute)
        s.add(360,1000,8,'');self.assertEqual(s.total,500)
    def test_invalid_scale_rejected(self):
        s=ExperienceStats();s.add(0,1000,10,'');s.add(180,99999,12,'')
        self.assertEqual(s.total,0);self.assertTrue(s.gaps)

if __name__=='__main__':unittest.main()
