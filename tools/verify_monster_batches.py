import unittest
from src.utils.monster_batches import MonsterBatches


class BatchTests(unittest.TestCase):
    def test_all_species_and_poses_get_turns(self):
        scheduler=MonsterBatches();templates={'A':list(range(12)),'B':list(range(16)),'C':list(range(8))}
        seen={name:set() for name in templates}
        for tick in range(8):
            batch=scheduler.select(templates,tick)
            self.assertEqual(sum(map(len,batch.values())),6)
            for name,frames in batch.items():seen[name].update(frames)
        self.assertEqual(seen,{name:set(frames) for name,frames in templates.items()})

    def test_density_bonus_cannot_starve_other_species(self):
        scheduler=MonsterBatches();templates={name:list(range(8)) for name in ('A','B','C')}
        scheduler.observe([{'name':'B'}]*5,10)
        batch=scheduler.select(templates,11)
        self.assertEqual({name:len(frames) for name,frames in batch.items()},{'A':2,'B':4,'C':2})
        self.assertEqual(sum(map(len,scheduler.select(templates,31).values())),6)

    def test_empty_and_single_template(self):
        scheduler=MonsterBatches()
        self.assertEqual(scheduler.select({'A':[],'B':[1]},0),{'B':[1]})

if __name__=='__main__':unittest.main()
