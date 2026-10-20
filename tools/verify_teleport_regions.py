import unittest
from src.navigation.map_graph import teleport_regions, Navigator


class TeleportRegionTests(unittest.TestCase):
    def graph(self, horizontal=False):
        a=dict(id='P1',x1=10,x2=60,y=70)
        b=dict(id='P2',x1=30,x2=80,y=62)
        if horizontal:b.update(x1=70,x2=80,y=70)
        e=dict(id='E1',src='P1',dst='P2',kind='teleport',enabled=True,
               start=[60,70] if horizontal else [45,70],
               end=[70,70] if horizontal else [45,62])
        return dict(platforms=[a,b],edges=[e],profile=dict(teleport_x=16,teleport_y=8))

    def test_vertical_overlap_region_and_noncentral_activation(self):
        g=self.graph();r=teleport_regions(g,g['edges'][0])[0]
        self.assertEqual((r['x1'],r['x2']),(30,60))
        n=Navigator(g)
        for t in (0,.1,.2):command=n.step((32,70),t)
        self.assertEqual(command,('none','up','none'))
        self.assertEqual(n.step((32,70),.4),('none','up','teleport'))

    def test_horizontal_landing_stays_on_target(self):
        g=self.graph(True);r=teleport_regions(g,g['edges'][0])[0]
        self.assertEqual((r['x1'],r['x2']),(54,60))
        self.assertEqual(r['landing'][::2],[70,76])
        self.assertEqual(r['direction'],('right','none'))

    def test_out_of_range_and_slope_filter(self):
        g=self.graph();g['profile']['teleport_y']=7
        self.assertEqual(teleport_regions(g,g['edges'][0]),[])
        g['profile']['teleport_y']=8;g['platforms'][1]['end_y']=52
        regions=teleport_regions(g,g['edges'][0])
        self.assertEqual(regions[0]['x1'],30)
        self.assertEqual(regions[0]['x2'],30)

    def test_outside_region_moves_toward_it_without_cast(self):
        g=self.graph();n=Navigator(g)
        for t in (0,.1,.2):command=n.step((20,70),t)
        self.assertEqual(command,('right','none','none'))
        self.assertIsNone(n.transit)

if __name__=='__main__':unittest.main()
