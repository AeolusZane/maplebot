import unittest
from src.utils.attack_prediction import AttackPrediction

class PredictionTests(unittest.TestCase):
    def mob(self,x):return dict(position=(x,100),size=(20,20))

    def test_relative_player_motion_predicts_approach(self):
        p=AttackPrediction()
        self.assertNotIn('_predicted_position',p.update([self.mob(200)],(100,100),1,1,True)[0])
        m=p.update([self.mob(200)],(110,100),1.1,1.1,True)[0]
        self.assertLess(m['_predicted_position'][0],200)
        self.assertGreaterEqual(m['_predicted_position'][0],176)

    def test_stale_unreliable_and_ambiguous_do_not_predict(self):
        p=AttackPrediction();p.update([self.mob(200),self.mob(202)],(100,100),1,1,True)
        self.assertNotIn('_predicted_position',p.update([self.mob(195)],(100,100),1.1,1.1,True)[0])
        self.assertNotIn('_predicted_position',p.update([self.mob(190)],(100,100),1.2,2,True)[0])
        self.assertNotIn('_predicted_position',p.update([self.mob(185)],(100,100),2,2,False)[0])

    def test_repeated_frame_does_not_reuse_velocity_for_another_monster(self):
        p=AttackPrediction()
        p.update([self.mob(200)],(100,100),1,1,True)
        predicted=p.update([self.mob(190)],(100,100),1.1,1.1,True)
        self.assertIn('_predicted_position',predicted[0])
        self.assertNotIn('_predicted_position',p.update(predicted,(100,100),1.1,1.15,True)[0])

if __name__=='__main__':unittest.main()
