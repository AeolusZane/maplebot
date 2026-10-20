import tempfile,unittest
from pathlib import Path
from src.utils.experience_history import ExperienceHistory,efficiency

class HistoryTests(unittest.TestCase):
    def test_restart_and_weighted_rates_and_level_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'history.sqlite3';h=ExperienceHistory(path)
            for level,gain,duration in [(50,600,180),(50,600,60),(51,None,0)]:
                h.append('run',1,'map',level,180,1000,10,gain,duration,'sample')
            rows=ExperienceHistory(path).rows()
            self.assertEqual(len(rows),3)
            self.assertEqual(efficiency([r for r in rows if r['level']==50]),(1200,240,300))
            self.assertIsNone(efficiency([r for r in rows if r['level']==51])[2])

if __name__=='__main__':unittest.main()
