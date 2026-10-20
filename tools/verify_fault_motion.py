import unittest
from tools.verify_rope_recovery import RopeRecoveryTests

class FaultMotionTests(unittest.TestCase):
    def test_no_route_enters_recovery_and_preserves_target(self):
        n=RopeRecoveryTests().nav();n.hunt_target={'platform':'P2','x':40,'y':70}
        self.assertEqual(n.recover_no_route('P2',(15,40),0),('none','none','none'))
        self.assertIsNone(n.fault)
        command=n.recover_no_route('P2',(15,40),3)
        self.assertEqual(command[0],'right');self.assertIsNotNone(n.fault)
        self.assertEqual(n.hunt_target['platform'],'P2')

    def test_recent_dismount_prevents_repeated_recovery_jumps(self):
        n=RopeRecoveryTests().nav();n.fault='到达超时';n._recovery_jump_after=10
        n.recover_fault((15,40),0)
        for t in (.2,.3,1.8,6,6.1,6.3):
            self.assertNotEqual(n.recover_fault((15,40),t)[2],'jump')

    def test_directional_jump_then_confirm_landing_preserves_target(self):
        n=RopeRecoveryTests().nav();n.fault='到达超时'
        n.hunt_target={'platform':'P2','x':40,'y':70}
        self.assertEqual(n.recover_fault((15,40),0),('right','none','none'))
        self.assertEqual(n.recover_fault((15,40),.2),('right','none','jump'))
        for t in (1,1.1,1.2,1.3):n.recover_fault((18,40),t)
        self.assertIsNone(n.fault);self.assertEqual(n.hunt_target['platform'],'P2')

    def test_rope_first_and_invalid_position_never_moves(self):
        n=RopeRecoveryTests().nav();n.fault='绳子恢复失败'
        self.assertEqual(n.recover_fault((30,55),0),('none','up','none'))
        self.assertEqual(n.recover_fault((30,55),1.2)[2],'jump')
        self.assertEqual(n.recover_fault((30,55),2,False),('none','none','none'))

    def test_stationary_failure_restarts_observation_cycle(self):
        n=RopeRecoveryTests().nav();n.fault='到达超时'
        n.recover_fault((15,40),0)
        self.assertEqual(n.recover_fault((15,40),6),('none','none','none'))
        self.assertEqual(n.recover_fault((15,40),6.1)[0],'right')

if __name__=='__main__':unittest.main()
