import unittest
from types import SimpleNamespace, MethodType
import numpy as np
from src.utils.attack_geometry import vertical_reach
from src.engine.MapleStoryAutoLevelUp import MapleStoryAutoBot

class AttackRangeTests(unittest.TestCase):
    def test_overlap_is_not_green_when_attack_is_suppressed(self):
        b=self.bot('aoe_skill');b.cmd_action='none'
        color=MapleStoryAutoBot.monster_debug_color
        self.assertEqual(color(b,True,False),(0,190,255))
        b.cmd_action='attack'
        self.assertEqual(color(b,True,False),(0,255,0))
        self.assertEqual(color(b,True,True),(128,128,128))
        self.assertEqual(color(b,False,False),(255,255,0))

    def bot(self, mode):
        skill=dict(range_x=400,range_y=170,range_up=85,range_down=185)
        b=SimpleNamespace(cfg={'bot':{'attack':mode},'aoe_skill':skill,'directional_attack':skill,
            'monster_detect':{'max_mob_area_trigger':25}},loc_player=(300,300),img_frame=np.zeros((768,1366,3)),
            monsters_info={'ghost':[(np.zeros((10,10,3)),None)]})
        b.get_attack_range=MethodType(MapleStoryAutoBot.get_attack_range,b)
        return b
    def test_legacy_and_explicit(self):
        self.assertEqual(vertical_reach({'range_y':171}),(85,86))
        self.assertEqual(vertical_reach({'range_y':170,'range_up':0,'range_down':185}),(0,185))
    def test_lower_monster_in_both_modes(self):
        for mode in ('aoe_skill','directional'):
            b=self.bot(mode)
            self.assertEqual(b.get_attack_range()[1::2],(215,485))
            b.monsters=[{'position':(280,450),'size':(10,10)}]
            self.assertIsNotNone(MapleStoryAutoBot.get_nearest_monster(b))
            b.monsters=[{'position':(280,190),'size':(10,10)}]
            self.assertIsNone(MapleStoryAutoBot.get_nearest_monster(b))
    def test_frame_clipping(self):
        b=self.bot('aoe_skill');b.loc_player=(300,740)
        self.assertEqual(b.get_attack_range()[3],768)
        b.loc_player=(300,10);self.assertEqual(b.get_attack_range()[1],0)

    def test_predicted_overlap_triggers_before_current_overlap(self):
        b=self.bot('aoe_skill')
        b.monsters=[{'position':(510,300),'size':(10,10)}]
        self.assertIsNone(MapleStoryAutoBot.get_nearest_monster(b))
        b.monsters[0]['_predicted_position']=(490,300)
        self.assertIsNotNone(MapleStoryAutoBot.get_nearest_monster(b))

    def test_one_pixel_overlap_attacks_and_turns_green(self):
        b=self.bot('aoe_skill')
        for position,expected in [((499,484),True),((500,484),False),((499,485),False)]:
            monster={'position':position,'size':(10,10)}
            b.monsters=[monster]
            self.assertEqual(MapleStoryAutoBot.get_nearest_monster(b) is not None,expected)
            self.assertEqual(MapleStoryAutoBot.monster_overlaps_attack(b,monster),expected)

    def test_cached_name_allows_fresh_detection_but_not_expired_results(self):
        from unittest.mock import patch
        b=self.bot('aoe_skill')
        b.nametag_hit=False;b.player_reference_valid=True;b.graph_position_valid=True
        b.loc_player_global=(30,30);b.img_minimap=None;b.loc_minimap=None
        monster={'position':(499,484),'size':(10,10)}
        with patch.object(MapleStoryAutoBot,'get_monsters_in_range',return_value=[monster]):
            result=MapleStoryAutoBot.scan_visible_snapshot(b,10)
        b.visible_monsters=result[0];b._visible_source_time=10;b._visible_anchor=result[3]
        self.assertTrue(result[3][2])
        self.assertEqual(MapleStoryAutoBot.current_visible_monsters(b,10.1),[monster])
        self.assertEqual(MapleStoryAutoBot.current_visible_monsters(b,11),[])
        b.player_reference_valid=False
        with patch.object(MapleStoryAutoBot,'get_monsters_in_range',return_value=[monster]):
            result=MapleStoryAutoBot.scan_visible_snapshot(b,12)
        self.assertFalse(result[3][2])

if __name__=='__main__':unittest.main()
