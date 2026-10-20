"""Visible-target projection and distance-weighted directed routing."""
import heapq
import math

def route_to(graph,here,pos,target):
    from .map_graph import preferred_edges
    edges=preferred_edges(graph)
    # State includes arrival coordinate: two arrivals on one platform can have different costs.
    queue=[(0.,here,float(pos[0]),float(pos[1]),())];best={};answer=None
    platforms={p['id']:p for p in graph['platforms']}
    def walk(pid,a,b):
        p=platforms[pid];slope=(p.get('end_y',p['y'])-p['y'])/(p['x2']-p['x1'])
        return abs(a-b)*math.hypot(1,slope)
    while queue:
        cost,pid,x,y,path=heapq.heappop(queue)
        key=(pid,x,y)
        if cost>=best.get(key,float('inf')):continue
        best[key]=cost
        if answer and cost>=answer[0]:continue
        if pid==target['platform']:
            total=cost+walk(pid,x,target['x'])
            if answer is None or total<answer[0]:answer=(total,list(path))
        for e in edges:
            if not e['enabled'] or e['src']!=pid:continue
            sx,sy=e['start'];ex,ey=e['end']
            transfer=(1.0 if e['kind']=='teleport' else math.dist(e['start'],e['end'])+{'rope':4,'jump':2,'drop':2,'walk':0}[e['kind']])
            heapq.heappush(queue,(cost+walk(pid,x,sx)+transfer,e['dst'],float(ex),float(ey),path+(e['id'],)))
    return answer

def calibrate(screen,map_points,player_screen,player_map,shape):
    sx=(screen[1][0]-screen[0][0])/(map_points[1][0]-map_points[0][0])
    sy=(screen[1][1]-screen[0][1])/(map_points[1][1]-map_points[0][1])
    if not (1<=sx<=100 and 1<=sy<=100):raise ValueError('两组点方向不一致或比例异常，请重新选择。')
    offset=[map_points[0][i]+(player_screen[i]-screen[0][i])/[sx,sy][i]-player_map[i] for i in (0,1)]
    return dict(scale=[sx,sy],offset=offset,frame_size=[shape[1],shape[0]])

def project_monsters(monsters,player_screen,player_map,graph,frame_shape):
    from .map_graph import platform_y
    c=graph.get('hunt_calibration')
    if not c or c['frame_size']!=[frame_shape[1],frame_shape[0]]:return []
    result=[]
    for m in monsters:
        x,y=m['position'];w,h=m['size'];foot=[x+w/2,y+h]
        point=[player_map[i]+(foot[i]-player_screen[i])/c['scale'][i]+c['offset'][i] for i in (0,1)]
        choices=sorted((abs(point[1]-platform_y(p,point[0])),p['id'],p) for p in graph['platforms'] if p['x1']<=point[0]<=p['x2'])
        if not choices or choices[0][0]>2.5:continue
        if len(choices)>1 and choices[1][0]-choices[0][0]<0.75:continue
        _,pid,p=choices[0];result.append(dict(platform=pid,x=point[0],y=platform_y(p,point[0])))
    return result

def choose_target(graph,here,pos,targets,previous=None):
    options=[]
    for t in targets:
        route=route_to(graph,here,pos,t)
        if route:options.append((route[0],t,route[1]))
    if not options:return None
    best=min(options,key=lambda v:v[0])
    if previous:
        same=[v for v in options if v[1]['platform']==previous['platform'] and abs(v[1]['x']-previous['x'])<=8]
        if same:
            old=min(same,key=lambda v:abs(v[1]['x']-previous['x']))
            if old[0]<=best[0]*1.25+3:return old
    return best
