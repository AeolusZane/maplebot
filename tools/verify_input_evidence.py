import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.utils.input_evidence import EventLog,HumanState,allowed_keys,begin_auto,end_auto,backend_call,auto_event


def events(folder):
    return [json.loads(s) for s in (Path(folder)/'events.jsonl').read_text(encoding='utf-8').splitlines()]


class Tests(unittest.TestCase):
    def test_holds_repeat_focus_and_unknown_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            log=EventLog(tmp);state=HumanState(log,{'left','q'})
            state.key('left',True,True)
            state.key('left',True,True)
            state.snapshot()
            state.key('left',False,True)
            state.key('q',True,True)
            state.update_focus(False)
            state.key('q',False,False)
            state.key('a',True,False)
            state.update_focus(True)
            state.snapshot();state.cancel('session_end');log.close()
            rows=events(tmp)
            keys=[e for e in rows if e['kind']=='human_key']
            self.assertEqual([e['edge'] for e in keys],['down','repeat','up','down'])
            self.assertGreaterEqual(keys[2]['held_duration_ns'],0)
            self.assertTrue(any(e['kind']=='hold_truncated' and e['reason']=='focus_lost' for e in rows))
            self.assertEqual([e for e in rows if e['kind']=='held_snapshot'][-1]['held'],[])
            self.assertTrue(all(e['t_ns']==e['monotonic_ns']-log.origin_ns for e in rows))
            self.assertEqual([e['event_id'] for e in rows],sorted(e['event_id'] for e in rows))

    def test_actual_calls_and_errors_not_cast_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            begin_auto(tmp,{'key':{'directional_attack':'q'}})
            try:
                auto_event('decision_command',command='none none attack')
                self.assertEqual(backend_call('key_down','q',lambda:123),123)
                def fail():raise OSError('fake failure')
                with self.assertRaises(OSError):backend_call('key_up','q',fail)
            finally:end_auto()
            rows=events(tmp)
            ends=[e for e in rows if e['kind']=='key_call_end']
            self.assertEqual([e['status'] for e in ends],['returned','error'])
            self.assertTrue(all(e['skill_success']=='unknown' for e in ends))
            self.assertTrue(all(any(s['event_id']==e['call_id'] and s['kind']=='key_call_start' for s in rows) for e in ends))

    def test_adapter_routes_hold_edges(self):
        from src.input import InterceptionController as adapter
        from types import SimpleNamespace
        calls=[]
        fake=SimpleNamespace(key_down=lambda k:calls.append(('down',k)),key_up=lambda k:calls.append(('up',k)))
        with tempfile.TemporaryDirectory() as tmp,patch.object(adapter,'interception',fake):
            begin_auto(tmp,{})
            try:adapter.press_key('control',duration=0)
            finally:end_auto()
            self.assertEqual(calls,[('down','ctrl'),('up','ctrl')])
            self.assertEqual([e['api'] for e in events(tmp) if e['kind']=='key_call_start'],['key_down','key_up'])

    def test_configured_allowlist(self):
        keys=allowed_keys({'key':{'jump':'space','jump_cooldown':1},'buff_skill':{'keys':['a']},'potion':{'hp':[{'key':'home'}]}})
        self.assertTrue({'space','a','home','left'}<=keys)
        self.assertNotIn('1',keys)

    def test_review_uses_only_eligible_events(self):
        from src.ui.skill_review import review_data
        with tempfile.TemporaryDirectory() as tmp:
            begin_auto(tmp,{'key':{'directional_attack':'q'}})
            auto_event('video_frame',video_index=0)
            backend_call('key_down','q',lambda:None)
            backend_call('key_up','q',lambda:None)
            auto_event('decision_command',command='none none attack')
            end_auto()
            _,candidates,frames=review_data(tmp)
            self.assertEqual(len(candidates),1)
            self.assertEqual(len(frames),1)
            self.assertEqual(candidates[0]['skill_success'],'unknown')


if __name__=='__main__':unittest.main()
