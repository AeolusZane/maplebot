import unittest
from src.states.damage_response import DamageResponse

class DamageTests(unittest.TestCase):
    def test_pause_is_bounded_even_with_repeated_damage(self):
        d=self.triggered()
        self.assertTrue(d.pause_for_scan(.3))
        d.observe(90,.4);d.observe(90,.5)
        self.assertTrue(d.recent(.6))
        self.assertFalse(d.pause_for_scan(2.9))
        self.assertTrue(d.pending)
        d.complete(None,True)
        self.assertFalse(d.pause_for_scan(3))

    def triggered(self):
        d=DamageResponse();d.observe(100,0);d.observe(95,.1)
        self.assertFalse(d.pending)
        d.observe(95,.2);self.assertTrue(d.pending)
        return d

    def test_all_species_and_frames_before_unmatched(self):
        d=self.triggered();templates={'A':list(range(8)),'B':list(range(6)),'C':[0,1]}
        seen={n:[] for n in templates};order=[]
        while d.pending:
            batch,token=d.batch(templates);name,indices=token
            order.append(name);seen[name]+=indices
            d.complete(token,False)
        self.assertEqual(order[:3],['A','B','C'])
        self.assertEqual(seen,templates);self.assertEqual(d.status,'unmatched')

    def test_invalid_result_retries_and_found_finishes(self):
        d=self.triggered();templates={'A':list(range(8))}
        _,token=d.batch(templates)
        d.complete(token,False,False)
        self.assertEqual(d.batch(templates)[1],token)
        d.complete(token,True)
        self.assertFalse(d.pending);self.assertEqual(d.status,'found')
        d.observe(90,.3);d.observe(90,.4)
        self.assertTrue(d.pending) # no fixed cooldown

    def test_noise_and_invalid_hp(self):
        d=DamageResponse()
        for t,h in enumerate([70,69.5,80,79.8,None,50]):d.observe(h,t*.1)
        self.assertFalse(d.pending)

if __name__=='__main__':unittest.main()
