import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from src.utils.nametag_recovery import recover_nearby_name
from tools.verify_two_side_mob_attack import make_stub,base_cfg,mob


class RecoveryTests(unittest.TestCase):
    def test_forced_global_recheck_is_throttled_without_false_hit(self):
        from src.engine.MapleStoryAutoLevelUp import MapleStoryAutoBot
        bot=SimpleNamespace(img_frame_gray=np.zeros((100,100),dtype=np.uint8),
            img_nametag=np.ones((8,20,3),dtype=np.uint8),
            img_nametag_gray=np.ones((8,20),dtype=np.uint8),
            cfg={'ui_coords':{'ui_y_start':100},'nametag':dict(mode='grayscale',
                diff_thres=.02,global_diff_thres=.02,offset=(0,10),split_width_fallback=10)},
            is_first_frame=False,_force_name_recheck=True,loc_nametag=(20,30),
            nametag_ever_hit=True,nametag_miss_streak=0)
        with patch('src.engine.MapleStoryAutoLevelUp.find_pattern_sqdiff',return_value=((20,30),.5,False)) as match:
            with patch('time.monotonic',return_value=10):
                MapleStoryAutoBot.get_player_location_by_nametag(bot)
            self.assertEqual(match.call_count,1)
            with patch('time.monotonic',return_value=10.1):
                self.assertEqual(MapleStoryAutoBot.get_player_location_by_nametag(bot),(30,20))
            self.assertEqual(match.call_count,1)
            self.assertFalse(bot.nametag_hit)
            with patch('time.monotonic',return_value=10.31):
                MapleStoryAutoBot.get_player_location_by_nametag(bot)
            self.assertEqual(match.call_count,2)
            self.assertEqual(match.call_args.args[1].shape[1],10)

    def test_unique_local_name_and_ambiguous_duplicates(self):
        template=np.random.default_rng(7).integers(100,255,(12,40),dtype=np.uint8)
        frame=np.zeros((350,600),dtype=np.uint8)
        frame[150:162,260:300]=(template.astype(float)*0.85).astype(np.uint8)
        mask=np.full(template.shape,255,dtype=np.uint8)
        result=recover_nearby_name(frame,template,mask,(200,150))
        self.assertIsNotNone(result);self.assertEqual(result[0],(260,150))
        frame[180:192,120:160]=frame[150:162,260:300]
        self.assertIsNone(recover_nearby_name(frame,template,mask,(200,150)))

    def test_no_early_departure_before_three_actual_presses(self):
        cfg=base_cfg();cfg['bot']['attack']='aoe_skill'
        cfg['aoe_skill']=dict(range_x=400,range_y=170,cooldown=0)
        bot=make_stub(cfg,(400,300),[mob(450,300)])
        bot.kb=SimpleNamespace(n_attack_sent=10)
        bot.update_cmd_by_mob_detection()
        bot.monsters=[]
        for count in (10,11,12):
            bot.kb.n_attack_sent=count
            bot.update_cmd_by_mob_detection()
            self.assertTrue(bot._combat_hold)
            self.assertEqual(bot.cmd_action,'attack')
            self.assertEqual(bot.cmd_move_x,'none')
        bot.kb.n_attack_sent=13
        with patch('time.monotonic',side_effect=[20,21,22,23]):
            for _ in range(4):bot.update_cmd_by_mob_detection()
        self.assertFalse(bot._combat_hold)
        self.assertEqual(bot.cmd_action,'none')


if __name__=='__main__':unittest.main()
