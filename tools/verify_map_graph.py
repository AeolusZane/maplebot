"""Offline navigation tests: no game, window enumeration or real input required."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from src.navigation.map_graph import (new_graph, detect_geometry, propose_edges,
    validate, save_graph, load_graph, Navigator, shortest_path, fingerprint, platform_y)


def scene():
    image=np.zeros((100,150,3),np.uint8)
    g=new_graph(image)
    g['platforms']=[dict(id='P1',x1=10,x2=80,y=70),dict(id='P2',x1=20,x2=70,y=62)]
    g['ropes']=[dict(id='R1',x=40,y1=62,y2=70)]
    propose_edges(g)
    return image,g


def enable(g,kind):
    for e in g['edges']:e['enabled']=e['kind']==kind


class MapGraphTests(unittest.TestCase):
    def test_vertical_drop_can_start_inside_overlap_away_from_saved_point(self):
        _,g=scene();g['edges']=[dict(id='D',kind='drop',src='P2',dst='P1',start=[40,62],end=[40,70],enabled=True)]
        n=Navigator(g)
        for t in (0,.1,.2):command=n.step((60,62),t)
        self.assertEqual(command,('none','down','none'))
        self.assertEqual(n.transit['start'],[60,62])
        self.assertEqual(g['edges'][0]['start'],[40,62])

    def test_down_jump_preferred_over_rope_and_teleport(self):
        from src.navigation.mob_hunt import route_to
        _,g=scene()
        g['edges']=[dict(id=kind,kind=kind,src='P2',dst='P1',start=[40,62],end=[40,70],enabled=True)
                    for kind in ('rope','teleport','drop')]
        target=dict(platform='P1',x=40,y=70)
        self.assertEqual(shortest_path(g,'P2','P1'),['drop'])
        self.assertEqual(route_to(g,'P2',(40,62),target)[1],['drop'])
        g['edges'][2]['enabled']=False
        self.assertEqual(shortest_path(g,'P2','P1'),['teleport'])
        g['edges'][1]['enabled']=False
        self.assertEqual(shortest_path(g,'P2','P1'),['rope'])

    def test_failed_edges_use_longer_cooldown_after_repeated_failures(self):
        _,g=scene();enable(g,'rope');n=Navigator(g)
        edge=next(e for e in n.edges.values() if e['enabled'])
        manual=next(e for e in n.edges.values() if not e['enabled'])
        n.block_edge(edge,0)
        self.assertEqual(n.retry_failed_edges(9),[])
        self.assertEqual(n.retry_failed_edges(10),[edge['id']])
        self.assertFalse(manual['enabled'])
        n.block_edge(edge,11);self.assertEqual(n.retry_failed_edges(21),[edge['id']])
        n.block_edge(edge,22);self.assertEqual(n.retry_failed_edges(51),[])
        self.assertEqual(n.retry_failed_edges(52),[edge['id']])

    def test_vertical_drop_holds_down_before_jump(self):
        _,g=scene();n=Navigator(g)
        n.transit=dict(id='drop',kind='drop',src='P2',dst='P1',start=[40,62],end=[40,70],enabled=True)
        n.started=0;n.deadline=3;n.path=['drop'];n.aim=('edge','drop')
        self.assertEqual(n.step((40,62),.1),('none','down','none'))
        for t in (.2,.3,.4):self.assertEqual(n.step((40,62),t),('none','down','jump'))
        self.assertEqual(n.step((40,62),.6),('none','none','none'))

    def test_upward_teleport_overrides_nearer_rope_and_falls_back(self):
        from src.navigation.mob_hunt import route_to
        _,g=scene()
        g['edges']=[dict(id='rope',src='P1',dst='P2',kind='rope',start=[40,70],end=[40,62],enabled=True),
            dict(id='tele',src='P1',dst='P2',kind='teleport',start=[65,70],end=[65,62],enabled=True)]
        target=dict(platform='P2',x=40,y=62)
        g['edges'].append(dict(id='jump',src='P1',dst='P2',kind='jump',start=[40,70],end=[40,62],enabled=True))
        self.assertEqual(shortest_path(g,'P1','P2'),['tele'])
        self.assertEqual(route_to(g,'P1',(40,70),target)[1],['tele'])
        g['edges'][1]['_runtime_failures']=2
        self.assertNotEqual(shortest_path(g,'P1','P2'),['tele'])
        self.assertNotEqual(route_to(g,'P1',(40,70),target)[1],['tele'])
        g['edges'][1].pop('_runtime_failures')
        g['edges'].pop()
        g['edges'][1]['enabled']=False
        self.assertEqual(route_to(g,'P1',(40,70),target)[1],['rope'])
        g['edges'][1]['enabled']=True;g['profile']['teleport_y']=4
        self.assertEqual(route_to(g,'P1',(40,70),target)[1],['rope'])

    def test_candidates_need_confirmation(self):
        im,g=scene()
        self.assertTrue(all(not e['enabled'] for e in g['edges']))
        self.assertTrue(validate(g,im,reviewed=True))

    def test_review_hash_and_image(self):
        im,g=scene();enable(g,'rope')
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'地图.json';save_graph(path,g,im,True)
            self.assertEqual(load_graph(path,im)['platforms'],g['platforms'])
            changed=im.copy();changed[0,0]=255
            with self.assertRaises(ValueError):load_graph(path,changed)
            g['platforms'][0]['x1']=11
            self.assertTrue(validate(g,im,reviewed=True))

    def test_directions_and_reachability(self):
        im,g=scene();enable(g,'rope')
        self.assertEqual(len(shortest_path(g,'P1','P2')),1)
        self.assertEqual(len(shortest_path(g,'P2','P1')),1)
        g['edges']=[e for e in g['edges'] if e['src']=='P1']
        g['confirmed']=True;g['review_digest']=fingerprint(g)
        self.assertTrue(any('无法到达' in x for x in validate(g,im,True)))

    def test_teleport_range_validation(self):
        im,g=scene();enable(g,'teleport');g['profile']['teleport_y']=4
        self.assertTrue(any('瞬移距离' in x for x in validate(g)))

    def test_rope_endpoints_validation(self):
        im,g=scene();enable(g,'rope');g['ropes'][0]['y1']=69
        self.assertTrue(any('绳子' in x for x in validate(g)))

    def test_unknown_and_invalid_stop(self):
        im,g=scene();n=Navigator(g)
        for valid in [True,False]:
            self.assertEqual(n.step((120,90),1,valid),('none','none','none'))

    def test_climb_and_arrival(self):
        im,g=scene();enable(g,'rope');n=Navigator(g)
        n.step((40,70),0);n.step((40,70),.1)
        self.assertEqual(n.step((40,70),.2),('right','none','none'))
        self.assertEqual(n.step((43,70),.3),('left','up','jump'))
        self.assertEqual(n.step((40,66),.5),('none','up','none'))
        for t in [.6,.7,.8]:self.assertEqual(n.step((40,62),t),('none','up','none'))
        for t in [1,1.1,1.2]:self.assertEqual(n.step((40,62),t),('none','none','none'))
        self.assertIsNone(n.transit)
        self.assertEqual(n.current,'P2')

    def test_teleport_single_proposal_and_timeout(self):
        im,g=scene();enable(g,'teleport');n=Navigator(g)
        x=next(e['start'][0] for e in g['edges'] if e['src']=='P1' and e['enabled'])
        n.step((x,70),0);n.step((x,70),.1)
        self.assertEqual(n.step((x,70),.2),('none','up','none'))
        self.assertEqual(n.step((x,70),.3),('none','up','teleport'))
        self.assertEqual(n.step((x,70),.4),('none','up','teleport'))
        self.assertEqual(n.step((x,70),.5),('none','up','teleport'))
        self.assertEqual(n.step((x,70),.6),('none','none','none'))
        self.assertEqual(n.step((x,70),1.1),('none','none','none'))
        self.assertIsNone(n.fault)
        self.assertIn('禁用',n.status)
        self.assertIsNone(n.transit)
        self.assertTrue(any(not e['enabled'] for e in n.edges.values()))

    def test_fault_recovers_on_stable_platform_only_once(self):
        im,g=scene();n=Navigator(g);n.fault='导航无进展'
        for t in (0,.1,.2):n.step((20,70),t)
        self.assertIsNone(n.fault);self.assertIn('重新规划',n.status)
        n.fault='导航无进展'
        for t in (1,2,3,4):n.step((20,70),t)
        self.assertIsNotNone(n.fault)
        for t in (5,6,7):n.step((25,70),t,valid=False)
        self.assertIsNotNone(n.fault)

    def test_stuck_walk_stops(self):
        im,g=scene();enable(g,'rope');n=Navigator(g)
        for t in [0,.1,.2]:n.step((20,70),t)
        self.assertEqual(n.step((20,70),6),('right','none','jump'))
        self.assertEqual(n.step((20,70),12),('left','none','jump'))
        self.assertEqual(n.step((20,70),18),('none','none','none'))
        self.assertIn('无进展',n.fault)

    def test_wrong_landing_replans_without_old_action(self):
        im,g=scene();enable(g,'teleport')
        g['platforms'].append(dict(id='P3',x1=10,x2=80,y=85))
        n=Navigator(g);x=45
        for t in [0,.1,.2]:n.step((x,70),t)
        self.assertIsNotNone(n.transit)
        self.assertEqual(n.step((x,85),.3),('none','none','none'))
        self.assertIsNone(n.transit)
        self.assertIsNone(n.current)
        for t in [.4,.5]:self.assertEqual(n.step((x,85),t),('none','none','none'))

    def test_closed_loop_rope_patrol(self):
        im,g=scene();enable(g,'rope');n=Navigator(g)
        x,y=20.,70.;visited=set();trace=[]
        for frame in range(500):
            command=n.step((x,y),frame*.05);trace.append(command)
            if command[0]!='none':x+=.5 if command[0]=='right' else -.5
            if command[1]!='none':y=max(62,min(70,y+(-.5 if command[1]=='up' else .5)))
            here=n.locate((x,y))
            if here:visited.add(here)
            self.assertTrue(10<=x<=80 and 62<=y<=70)
            self.assertIsNone(n.fault)
        self.assertEqual(visited,{'P1','P2'})
        self.assertTrue(any(c[1]=='down' for c in trace))

    def test_synthetic_geometry_candidates(self):
        im=np.full((100,160,3),20,np.uint8)
        cv2.line(im,(20,40),(120,40),(0,150,220),2)
        cv2.line(im,(20,70),(120,70),(0,150,220),2)
        cv2.line(im,(50,40),(50,70),(130,130,130),1)
        g=detect_geometry(im)
        self.assertEqual(len(g['platforms']),2)
        self.assertGreaterEqual(len(g['ropes']),1)
        # Background padding is excluded; proposals never enable themselves.
        self.assertTrue(all(not e['enabled'] for e in g['edges']))
        self.assertTrue(all(p['x2']>p['x1'] for p in g['platforms']))

    def test_slope_height_and_localization(self):
        im,g=scene();g['platforms']=[dict(id='P1',x1=20,x2=60,y=70,end_y=60)]
        propose_edges(g)
        n=Navigator(g)
        self.assertEqual(platform_y(g['platforms'][0],40),65)
        self.assertEqual(n.locate((40,65)),'P1')
        self.assertIsNone(n.locate((40,70)))
        self.assertEqual(validate(g,im),[])

    def test_step_jump_and_reverse_drop(self):
        im,g=scene();g['platforms']=[dict(id='P1',x1=10,x2=40,y=70),dict(id='P2',x1=44,x2=80,y=64)]
        propose_edges(g)
        jumps=[e for e in g['edges'] if e['kind']=='jump']
        drops=[e for e in g['edges'] if e['kind']=='drop']
        self.assertEqual([(e['src'],e['dst']) for e in jumps],[('P1','P2')])
        self.assertEqual([(e['src'],e['dst']) for e in drops],[('P2','P1')])
        for e in g['edges']:e['enabled']=e['kind'] in ('jump','drop')
        self.assertEqual(validate(g),[])
        n=Navigator(g)
        for t in [0,.1]:n.step((40,70),t)
        self.assertEqual(n.step((40,70),.2),('left','none','none'))
        self.assertEqual(n.step((37,70),.3),('right','none','none'))
        self.assertEqual(n.step((40,70),.4),('right','none','jump'))
        self.assertEqual(n.step((42,63),.6),('right','none','none'))
        # Cross target on ascent: no early arrival or repeated jump.
        n.step((44,64),.65);self.assertIsNotNone(n.transit)
        for t in [.8,.9,1,1.1]:n.step((45,64),t)
        self.assertIsNone(n.transit)
        self.assertEqual(n.current,'P2')

    def test_jump_timeout_on_source_disables_connection_without_retry(self):
        im,g=scene();enable(g,'jump');n=Navigator(g)
        e=next(e for e in g['edges'] if e['enabled']);x=e['start'][0]
        for t in [0,.1,.2]:command=n.step((x,70),t)
        command=n.step((x,70),1.3)
        self.assertEqual(command[2],'jump')
        self.assertEqual(n.step((x,70),4.5),('none','none','none'))
        self.assertIsNone(n.fault)
        self.assertIn('超时',n.status)
        self.assertFalse(e['enabled'])
        self.assertIsNone(n.transit)

    def test_touching_slope_has_walk_connection(self):
        im,g=scene();g['platforms']=[dict(id='P1',x1=10,x2=40,y=70),dict(id='P2',x1=40,x2=60,y=70,end_y=65)]
        propose_edges(g)
        walks=[e for e in g['edges'] if e['kind']=='walk']
        self.assertEqual(len(walks),2)
        for e in walks:e['enabled']=True
        self.assertEqual(validate(g),[])


if __name__=='__main__':unittest.main(verbosity=2)
