import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from src.states.combat_hold import CombatHold
from src.states.hunting import HuntingState

class CombatTests(unittest.TestCase):
    def test_damage_scan_stops_patrol_until_bounded_wait_finishes(self):
        from src.states.damage_response import DamageResponse
        d=DamageResponse();d.pending=True
        nav=SimpleNamespace(transit=None,fault=None,locate=lambda p:'P1',
            step=Mock(return_value=('right','none','none')),status='',last_progress=0)
        bot=SimpleNamespace(graph_navigator=nav,graph_position_valid=True,nametag_hit=True,
            loc_player_global=(10,10),_graph_status_last='',kb=Mock(),
            update_cmd_by_mob_detection=Mock(),_damage_response=d)
        state=HuntingState(None,bot);state.on_frame()
        nav.step.assert_not_called();bot.kb.set_command.assert_called_with('none none none')
        d.pause_started-=3
        state.on_frame();nav.step.assert_called_once()

    def test_recent_damage_prevents_crowd_trip_cancelling_attack(self):
        import time
        from src.states.damage_response import DamageResponse
        d=DamageResponse();d.last_damage=time.monotonic()
        sweep=SimpleNamespace(urgent_target='P2',redirect_to_crowd=Mock(return_value=False),live_counts=lambda now:{'P2':3})
        nav=SimpleNamespace(transit=None,fault=None,locate=lambda p:'P1',platform_sweep=sweep,
            step=Mock(),status='',last_progress=0,graph={},_combat_paused_at=time.monotonic()-2)
        bot=SimpleNamespace(graph_navigator=nav,graph_position_valid=True,nametag_hit=True,
            loc_player_global=(10,10),_graph_status_last='',kb=Mock(),_damage_response=d)
        def attack():bot._combat_hold=True;bot.cmd_action='attack'
        bot.update_cmd_by_mob_detection=attack
        HuntingState(None,bot).on_frame()
        nav.step.assert_not_called();bot.kb.set_command.assert_called_with('none none attack')

    def test_unknown_observation_can_attack_but_not_on_rope(self):
        nav=SimpleNamespace(fault=None,graph={'ropes':[]},status='观察',
            _unknown_failed=(10,10),_unknown_retry_at=float('inf'),
            recover_unknown=Mock(return_value=('none','none','none')))
        bot=SimpleNamespace(graph_navigator=nav,graph_position_valid=True,nametag_hit=True,
            loc_player_global=(10,10),_graph_status_last='',kb=Mock())
        def attack():bot.cmd_action='attack'
        bot.update_cmd_by_mob_detection=Mock(side_effect=attack)
        HuntingState(None,bot).on_frame()
        bot.kb.set_command.assert_called_with('none none attack')
        bot.update_cmd_by_mob_detection.reset_mock()
        nav.graph['ropes']=[dict(x=10,y1=0,y2=20)]
        HuntingState(None,bot).on_frame()
        bot.update_cmd_by_mob_detection.assert_not_called()
        bot.kb.set_command.assert_called_with('none none none')

    def test_visible_target_travel_still_checks_nearby_attack(self):
        sweep=SimpleNamespace(urgent_target='P2',redirect_to_crowd=Mock(return_value=False),live_counts=lambda now:{'P2':3})
        nav=SimpleNamespace(transit=None,fault=None,path=[],locate=lambda p:'P1',platform_sweep=sweep,
            graph={},step=Mock(return_value=('right','none','none')),status='',last_progress=0)
        bot=SimpleNamespace(graph_navigator=nav,graph_position_valid=True,nametag_hit=True,
            loc_player_global=(10,10),_graph_status_last='',kb=Mock(),update_cmd_by_mob_detection=Mock())
        HuntingState(None,bot).on_frame()
        bot.update_cmd_by_mob_detection.assert_called_once()

    def test_fault_recovery_has_priority_over_monsters(self):
        nav=SimpleNamespace(transit=None,fault='超时',step=Mock(return_value=('none','none','none')),
            status='超时恢复',last_progress=0)
        bot=SimpleNamespace(graph_navigator=nav,graph_position_valid=True,nametag_hit=True,
            loc_player_global=(10,10),_graph_status_last='',kb=Mock(),update_cmd_by_mob_detection=Mock())
        HuntingState(None,bot).on_frame()
        nav.step.assert_called_once();bot.update_cmd_by_mob_detection.assert_not_called()

    def test_localization_loss_keeps_path_and_stops_input(self):
        nav=SimpleNamespace(transit=None,fault=None,path=['E1'],step=Mock(),status='',last_progress=0)
        bot=SimpleNamespace(graph_navigator=nav,graph_position_valid=True,nametag_hit=False,loc_player_global=(10,10),_graph_status_last='',kb=Mock(),update_cmd_by_mob_detection=Mock())
        HuntingState(None,bot).on_frame()
        bot.kb.set_command.assert_called_with('none none none')
        nav.step.assert_not_called();bot.update_cmd_by_mob_detection.assert_not_called()
        self.assertEqual(nav.path,['E1'])

    def test_localization_requires_stable_recovery(self):
        from src.states.combat_hold import LocalizationGate
        gate=LocalizationGate();self.assertEqual(gate.update(False,0),(False,0))
        self.assertFalse(gate.update(True,1)[0]);self.assertFalse(gate.update(True,1.1)[0])
        ready,paused=gate.update(True,1.3);self.assertTrue(ready);self.assertEqual(paused,1.3)

    def test_obscured_name_keeps_moving_with_live_minimap(self):
        nav=SimpleNamespace(transit=None,fault=None,path=['E1'],locate=lambda p:'P1',
            step=Mock(return_value=('right','none','none')),status='',last_progress=0)
        bot=SimpleNamespace(graph_navigator=nav,graph_position_valid=True,
            nametag_hit=True,nametag_ever_hit=True,loc_player_global=(10,10),
            _graph_status_last='',kb=Mock(),update_cmd_by_mob_detection=Mock())
        state=HuntingState(None,bot)
        state.on_frame()
        bot.nametag_hit=False
        for x in (11,12,13):
            bot.loc_player_global=(x,10)
            state.on_frame()
            bot.kb.set_command.assert_called_with('right none none')
            self.assertEqual(nav.step.call_args.args[0],(x,10))
        self.assertEqual(nav.step.call_count,4)
        self.assertEqual(nav.path,['E1'])
        bot.nametag_hit=True
        state.on_frame()
        self.assertEqual(nav.step.call_count,5)

    def test_cached_name_does_not_override_lost_minimap(self):
        nav=SimpleNamespace(transit=None,path=['E1'],step=Mock(),status='',last_progress=0)
        bot=SimpleNamespace(graph_navigator=nav,graph_position_valid=False,
            nametag_hit=False,nametag_ever_hit=True,loc_player_global=(10,10),
            _graph_status_last='',kb=Mock(),update_cmd_by_mob_detection=Mock())
        HuntingState(None,bot).on_frame()
        bot.kb.set_command.assert_called_with('none none none')
        nav.step.assert_not_called()

    def test_flicker_and_fresh_empty_confirmation(self):
        c=CombatHold();self.assertFalse(c.update(False,True,0))
        self.assertTrue(c.update(True,True,1))
        self.assertTrue(c.update(False,True,2))
        for t in (3,4,5):self.assertTrue(c.update(False,False,t))
        self.assertTrue(c.update(False,True,6))
        self.assertFalse(c.update(False,True,7))
        self.assertTrue(c.update(True,True,8))
        self.assertTrue(c.update(False,True,9))
        self.assertTrue(c.update(True,True,10))
        self.assertTrue(c.update(False,True,11))

    def test_empty_grace_and_reappearance_reset(self):
        c=CombatHold();c.update(True,True,0)
        for t in (.1,.4,.8,1.4):self.assertTrue(c.update(False,True,t))
        self.assertTrue(c.update(True,True,1.5))
        for t in (1.6,2,2.8):self.assertTrue(c.update(False,True,t))
        self.assertTrue(c.update(False,False,3.2))
        self.assertFalse(c.update(False,True,3.3))
    def test_graph_combat_pauses_planner_and_resumes(self):
        nav=SimpleNamespace(transit=None,fault=None,locate=lambda p:'P1',step=Mock(return_value=('right','none','none')),status='',last_progress=0)
        bot=SimpleNamespace(graph_navigator=nav,graph_position_valid=True,loc_player_global=(10,10),_graph_status_last='',kb=Mock())
        def detect():
            bot._combat_hold=True;bot.cmd_action='attack';bot._combat_status='交战中'
        bot.update_cmd_by_mob_detection=detect
        state=HuntingState(None,bot);state.on_frame()
        nav.step.assert_not_called();bot.kb.set_command.assert_called_with('none none attack')
        self.assertGreater(nav.last_progress,0)
        bot.update_cmd_by_mob_detection=lambda:None
        state.on_frame();nav.step.assert_called_once();bot.kb.set_command.assert_called_with('right none none')
    def test_transit_keeps_navigation_priority(self):
        nav=SimpleNamespace(transit={'kind':'rope'},fault=None,step=Mock(return_value=('none','up','none')),status='',last_progress=0)
        bot=SimpleNamespace(graph_navigator=nav,graph_position_valid=True,loc_player_global=(10,10),_graph_status_last='',kb=Mock(),update_cmd_by_mob_detection=Mock())
        HuntingState(None,bot).on_frame();bot.update_cmd_by_mob_detection.assert_not_called()
        bot.kb.set_command.assert_called_with('none up none')

if __name__=='__main__':unittest.main()
