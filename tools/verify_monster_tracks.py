import unittest
from src.utils.monster_tracks import MonsterTracks


class TrackTests(unittest.TestCase):
    def test_miss_keeps_target_and_real_hit_renews_deadline(self):
        tracks=MonsterTracks(1.2);anchor=((100,100),(10,10),True)
        monster=dict(name='A',position=(120,120),size=(20,20),score=.1)
        tracks.update([monster],10,anchor)
        tracks.update([],10.5,anchor)
        self.assertEqual(len(tracks.candidates(11,anchor)),1)
        tracks.update([monster],11,anchor)
        self.assertEqual(len(tracks.candidates(12,anchor)),1)
        self.assertEqual(tracks.candidates(12.3,anchor),[])

    def test_misses_do_not_keep_dead_target_alive(self):
        tracks=MonsterTracks(1.2);anchor=((100,100),(10,10),True)
        tracks.update([dict(name='A',position=(120,120))],10,anchor)
        for time in (10.2,10.4,10.8,11.3):tracks.update([],time,anchor)
        self.assertEqual(tracks.candidates(11.3,anchor),[])

    def test_camera_shift_and_invalid_anchor(self):
        tracks=MonsterTracks(1.2);anchor=((100,100),(10,10),True)
        tracks.update([dict(name='A',position=(120,120))],10,anchor)
        self.assertEqual(tracks.candidates(10.1,((120,100),(12,10),True)),[])
        self.assertEqual(tracks.candidates(10.1,((100,100),(10,10),False)),[])
        self.assertEqual(tracks.candidates(10.1,((120,100),(12,10),True),{'scale':[10,10]})[0]['position'],(120,120))

if __name__=='__main__':unittest.main()
