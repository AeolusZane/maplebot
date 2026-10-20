"""Map geometry in saved map.png coordinates. Candidates require human review.

No window capture, driver, or input initialization is permitted in this module.
"""
from __future__ import annotations

import hashlib
import heapq
import json
import math
from pathlib import Path

import cv2
import numpy as np


def image_hash(image):
    return hashlib.sha256(str(image.shape).encode() + image.tobytes()).hexdigest()


def read_image(path):
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("无法读取地图图片")
    return image


def fingerprint(graph):
    fields = {k: v for k, v in graph.items() if k not in ("review_digest", "confirmed")}
    return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def new_graph(image):
    h, w = image.shape[:2]
    return dict(version=1, image_hash=image_hash(image), width=w, height=h,
                platforms=[], ropes=[], edges=[], confirmed=False,
                profile=dict(teleport_x=16, teleport_y=8, jump_x=12, jump_y=8,
                             drop_x=8, drop_y=24, marker_offset=4))


def platform_y(platform, x):
    """Player marker height on a flat or sloping platform; legacy y stays valid."""
    points=platform.get('points')
    if points:
        if x<=points[0][0]:return points[0][1]
        for a,b in zip(points,points[1:]):
            if x<=b[0]:return a[1]+(x-a[0])/(b[0]-a[0])*(b[1]-a[1])
        return points[-1][1]
    width=platform['x2']-platform['x1']
    t=max(0.,min(1.,(x-platform['x1'])/width)) if width else 0.
    return platform['y']+t*(platform.get('end_y',platform['y'])-platform['y'])


def teleport_regions(graph, edge):
    """Derived source/landing bands; no migration of reviewed map data required.

    Bands visualize marker tolerance. Runtime still requires the source surface.
    Horizontal travel uses configured distance, not an arbitrary point in range.
    """
    if edge['kind']!='teleport':return []
    ps={p['id']:p for p in graph['platforms']}
    a,b=ps.get(edge['src']),ps.get(edge['dst'])
    if not a or not b:return []
    dy=edge['end'][1]-edge['start'][1]
    vertical=abs(dy)>2
    sign=1 if (dy if vertical else edge['end'][0]-edge['start'][0])>0 else -1
    reach=float(graph['profile']['teleport_y' if vertical else 'teleport_x'])
    if reach<=0:return []
    shift=0 if vertical else sign*reach
    lo=max(a['x1'],b['x1']-shift);hi=min(a['x2'],b['x2']-shift)
    if hi<lo:return []
    def allowed(x):
        height=platform_y(b,x+shift)-platform_y(a,x)
        return 2<sign*height<=reach if vertical else abs(height)<=2
    # Split slopes wherever the height difference exceeds the skill range.
    xs=[lo+i*.5 for i in range(int((hi-lo)/.5)+1)]
    if xs[-1]<hi:xs.append(hi)
    runs=[];run=[]
    for x in xs:
        if allowed(x):run.append(x)
        elif run:runs.append(run);run=[]
    if run:runs.append(run)
    result=[]
    for run in runs:
        left,right=run[0],run[-1]
        sy=[platform_y(a,x) for x in (left,right)]
        ey=[platform_y(b,x+shift) for x in (left,right)]
        result.append(dict(x1=left,x2=right,shift=shift,
            source=[left,min(sy)-2,right,max(sy)+2],
            landing=[left+shift,min(ey)-2,right+shift,max(ey)+2],
            direction=('none','up' if sign<0 else 'down') if vertical else
                      ('left' if sign<0 else 'right','none')))
    return result


def supplement_upward_teleports(graph):
    """Append unapproved upward candidates without changing existing edges."""
    import copy
    candidate=copy.deepcopy(graph);propose_edges(candidate)
    existing={(e['src'],e['dst'],e['kind']) for e in graph['edges']}
    number=max([int(e['id'][1:]) for e in graph['edges']]+[0]);added=[]
    for edge in candidate['edges']:
        key=(edge['src'],edge['dst'],edge['kind'])
        if edge['kind']!='teleport' or edge['end'][1]>=edge['start'][1]-2 or key in existing:continue
        number+=1;edge['id']=f'E{number}';edge['enabled']=False
        graph['edges'].append(edge);existing.add(key);added.append(edge)
    if added:graph['confirmed']=False;graph['review_digest']=''
    return added


def detect_geometry(image):
    """Conservative visual proposals, never a claim about actual collision geometry."""
    graph = new_graph(image)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # Minimap platform surfaces commonly use amber. Thin horizontal runs only.
    mask = cv2.inRange(hsv, (8, 75, 65), (42, 255, 255))
    # Ignore the minimap's decorative outer frame and the black padding.
    yy,xx=np.where(np.any(image>0,axis=2))
    if len(yy):
        mask[:int(yy.min())+10]=0
        mask[:, :int(xx.min())+4]=0
        mask[:, int(xx.max())-3:]=0
    horizontal = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((1, 5), np.uint8))
    horizontal = cv2.morphologyEx(horizontal, cv2.MORPH_OPEN, np.ones((1, 7), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(horizontal)
    for x, y, w, h, area in stats[1:count]:
        if w >= 9 and h <= 6:
            graph["platforms"].append(dict(id=f"P{len(graph['platforms']) + 1}",
                x1=int(x), x2=int(x+w-1), y=max(0, int(y)-4), source="candidate"))
    # Ladder/rope proposals: narrow persistent gray vertical strokes near platforms.
    # A wide gray floor is common in subway maps, unlike the amber platforms.
    floor=cv2.inRange(hsv,(0,0,85),(179,55,230))
    floor=cv2.morphologyEx(floor,cv2.MORPH_CLOSE,np.ones((1,5),np.uint8))
    floor=cv2.morphologyEx(floor,cv2.MORPH_OPEN,np.ones((1,35),np.uint8))
    count,_,stats,_=cv2.connectedComponentsWithStats(floor)
    for x,y,w,h,area in stats[1:count]:
        if w>=35 and h<=8 and len(yy) and y>yy.min()+15:
            graph['platforms'].append(dict(id=f"P{len(graph['platforms'])+1}",x1=int(x),x2=int(x+w-1),
                y=max(0,int(y)-4),source='candidate'))
    vertical = cv2.inRange(hsv, (0, 0, 35), (179, 100, 180))
    vertical = cv2.morphologyEx(vertical, cv2.MORPH_OPEN, np.ones((7, 1), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(vertical)
    for x, y, w, h, area in stats[1:count]:
        if h >= 7 and w <= 5 and y > 3 and x > 3:
            cx = int(x+w//2)
            near = [p for p in graph["platforms"] if p["x1"]-3 <= cx <= p["x2"]+3
                    and y-8 <= p["y"] <= y+h+3]
            if len(near) >= 2:
                graph["ropes"].append(dict(id=f"R{len(graph['ropes'])+1}",
                    x=cx, y1=max(0,int(y)-4), y2=int(y+h-1), source="candidate"))
    propose_edges(graph)
    return graph


def propose_edges(graph):
    """Replace connections with unapproved, directed rope/teleport proposals."""
    graph["confirmed"] = False
    graph["edges"] = []
    ps = graph["platforms"]
    profile = graph["profile"]
    for a in ps:
        for b in ps:
            if a["id"] == b["id"]:
                continue
            lo, hi = max(a["x1"],b["x1"]), min(a["x2"],b["x2"])
            if lo<=hi:ax=bx=(lo+hi)//2
            else:ax,bx=(a['x2'],b['x1']) if a['x2']<b['x1'] else (a['x1'],b['x2'])
            ay,by=platform_y(a,ax),platform_y(b,bx)
            dy=by-ay
            for r in graph["ropes"]:
                ry1,ry2=platform_y(a,r['x']),platform_y(b,r['x'])
                if (lo <= r["x"] <= hi and abs(dy) > 2 and
                    r["y1"] <= min(ry1,ry2)+4 and r["y2"] >= max(ry1,ry2)-4):
                    _edge(graph,a,b,"rope",[r['x'],ry1],[r['x'],ry2],r['id'])
            if lo <= hi and 2 < abs(dy) <= profile["teleport_y"]:
                x = (lo+hi)//2
                _edge(graph,a,b,"teleport",[x,ay],[x,by])
            elif abs(dy) <= 2 and lo > hi:
                ax,bx = (a["x2"],b["x1"]) if a["x2"] < b["x1"] else (a["x1"],b["x2"])
                if abs(ax-bx) <= profile["teleport_x"]:
                    _edge(graph,a,b,"teleport",[ax,ay],[bx,by])
            if abs(bx-ax)<=profile.get('jump_x',12) and -profile.get('jump_y',8)<=dy<=2 and (dy < -2 or lo>hi):
                _edge(graph,a,b,'jump',[ax,ay],[bx,by])
            if 2<dy<=profile.get('drop_y',24) and abs(bx-ax)<=profile.get('drop_x',8):
                _edge(graph,a,b,'drop',[ax,ay],[bx,by])
            if ((lo>hi and abs(bx-ax)<=2) or 0<=hi-lo<=2) and abs(dy)<=2:
                to_right=(b['x1']+b['x2'])>(a['x1']+a['x2'])
                wx=min(b['x2'],b['x1']+2) if to_right else max(b['x1'],b['x2']-2)
                _edge(graph,a,b,'walk',[ax,ay],[wx,platform_y(b,wx)])
    return graph


def _edge(graph,a,b,kind,start,end,rope=None):
    graph["edges"].append(dict(id=f"E{len(graph['edges'])+1}",src=a["id"],dst=b["id"],
        kind=kind,start=start,end=end,rope=rope,enabled=False))


def sync_structural_edges(graph):
    """Explicit UI action: turn annotated ladders/touching surfaces into routes."""
    import copy
    candidate=copy.deepcopy(graph);propose_edges(candidate)
    count=0
    for edge in candidate['edges']:
        if edge['kind'] not in ('rope','walk'):continue
        existing=next((e for e in graph['edges'] if (e['src'],e['dst'],e['kind'],e.get('rope')) ==
                       (edge['src'],edge['dst'],edge['kind'],edge.get('rope'))),None)
        if existing:
            if existing['enabled']:continue
            existing.update(start=edge['start'],end=edge['end'],enabled=True)
        else:
            edge['id']=f"E{max([int(e['id'][1:]) for e in graph['edges']]+[0])+1}"
            edge['enabled']=True;graph['edges'].append(edge)
        count+=1
    if count:graph['confirmed']=False
    return count


def preferred_edges(graph):
    """Prefer upward teleport and vertical down+jump for equivalent transfers."""
    edges=[e for e in graph['edges'] if e['enabled']]
    alternatives={(e['src'],e['dst']) for e in edges if e['kind']!='teleport' and e.get('_runtime_failures',0)<2}
    edges=[e for e in edges if not (e['kind']=='teleport' and e.get('_runtime_failures',0)>=2
                                    and (e['src'],e['dst']) in alternatives)]
    upward={(e['src'],e['dst']) for e in edges if e['kind']=='teleport'
            and e['end'][1]<=e['start'][1]+2 and teleport_regions(graph,e)}
    downward={(e['src'],e['dst']) for e in edges if e['kind']=='drop'
              and abs(e['end'][0]-e['start'][0])<=1
              and 2<e['end'][1]-e['start'][1]<=graph['profile'].get('drop_y',24)}
    return [e for e in edges
            if not (e['kind']!='teleport' and (e['src'],e['dst']) in upward)
            and not (e['kind']!='drop' and (e['src'],e['dst']) in downward)]


def shortest_path(graph, source, target):
    edges=preferred_edges(graph)
    queue = [(0,source,[])]
    seen = set()
    while queue:
        cost,node,path = heapq.heappop(queue)
        if node in seen:
            continue
        if node == target:
            return path
        seen.add(node)
        for e in edges:
            if e["enabled"] and e["src"] == node:
                heapq.heappush(queue,(cost+(0.6 if e['kind']=='teleport' else 1.2 if e['kind']=='rope' else 1),e["dst"],path+[e["id"]]))
    return None


def validate(graph, image=None, reviewed=False):
    errors=[]
    if graph.get("version") != 1:
        errors.append("地图格式版本不支持")
    if image is not None and (graph.get("image_hash") != image_hash(image)):
        errors.append("底图已变化，需要重新识别并确认")
    if not graph.get("platforms"):
        errors.append("至少需要一个平台")
    calibration=graph.get('hunt_calibration')
    if calibration is not None:
        try:
            valid=(len(calibration['scale'])==2 and len(calibration['offset'])==2 and len(calibration['frame_size'])==2
                   and all(math.isfinite(v) and 1<=v<=100 for v in calibration['scale'])
                   and all(math.isfinite(v) for v in calibration['offset'])
                   and all(isinstance(v,int) and v>0 for v in calibration['frame_size']))
        except (KeyError,TypeError,ValueError):valid=False
        if not valid:errors.append('全屏找怪校准数据无效，请重新校准')
    ps={p["id"]:p for p in graph["platforms"]}
    if len(ps)!=len(graph["platforms"]):
        errors.append("平台编号重复")
    w,h=graph["width"],graph["height"]
    for p in ps.values():
        if p.get('points'):
            pts=p['points']
            if (len(pts)<2 or any(not(0<=x<w and 0<=y<h) for x,y in pts) or
                any(a[0]>=b[0] for a,b in zip(pts,pts[1:])) or
                list(pts[0])!=[p['x1'],p['y']] or list(pts[-1])!=[p['x2'],p.get('end_y',p['y'])]):
                errors.append(f"{p['id']} 折线点无效：需从左到右且不越界")
        if not (0<=p["x1"]<p["x2"]<w and 0<=p["y"]<h and 0<=p.get('end_y',p['y'])<h):
            errors.append(f"{p['id']} 平台端点无效或越界")
    if len({e['id'] for e in graph['edges']}) != len(graph['edges']):
        errors.append('连接编号重复')
    if len({r['id'] for r in graph['ropes']}) != len(graph['ropes']):
        errors.append('楼梯/绳子编号重复')
    for r in graph['ropes']:
        if not(0<=r['x']<w and 0<=r['y1']<r['y2']<h):
            errors.append(f"{r['id']} 楼梯/绳子端点无效或越界")
    for e in graph["edges"]:
        if e["src"] not in ps or e["dst"] not in ps or e["kind"] not in ("rope","teleport","jump","drop","walk"):
            errors.append(f"{e['id']} 连接无效")
            continue
        a,b=ps[e["src"]],ps[e["dst"]]
        sx,sy=e["start"];ex,ey=e["end"]
        if not(a["x1"]<=sx<=a["x2"] and abs(sy-platform_y(a,sx))<0.01 and b["x1"]<=ex<=b["x2"] and abs(ey-platform_y(b,ex))<0.01):
            errors.append(f"{e['id']} 连接点不在所属平台上")
        if e['enabled'] and e['kind'] in ('jump','drop','walk'):
            dx,dy=abs(ex-sx),ey-sy
            if e['kind']=='jump':valid=dx<=graph['profile'].get('jump_x',12) and -graph['profile'].get('jump_y',8)<=dy<=2
            elif e['kind']=='drop':valid=dx<=graph['profile'].get('drop_x',8) and 2<dy<=graph['profile'].get('drop_y',24)
            else:valid=dx<=4 and abs(dy)<=3
            if not valid:errors.append(f"{e['id']} 跳跃/下落/步行方向或距离不符合设置")
        if e["enabled"] and e["kind"]=="teleport":
            if abs(ey-sy)>2:
                valid=abs(ex-sx)<=1 and abs(ey-sy)<=graph["profile"]["teleport_y"]
            else:
                valid=abs(ex-sx)<=graph["profile"]["teleport_x"]
            if not valid:
                errors.append(f"{e['id']} 超出配置的瞬移距离或方向不是上下左右")
        if e["enabled"] and e["kind"]=="rope":
            ropes={r["id"]:r for r in graph["ropes"]}
            r=ropes.get(e.get("rope"))
            if not r or abs(sx-ex)>1 or abs(sx-r["x"])>1 or r["y1"]>min(sy,ey)+4 or r["y2"]<max(sy,ey)-4:
                errors.append(f"{e['id']} 绳子没有连接这两个平台")
    if not errors and reviewed:
        for a in ps:
            if ps[a].get('reset_point'):continue
            for b in ps:
                if ps[b].get('reset_point'):continue
                if shortest_path(graph,a,b) is None:
                    errors.append(f"{a} 无法到达 {b}：请补连接或删除不参与巡逻的平台")
                    break
        if not graph.get("confirmed") or graph.get("review_digest")!=fingerprint(graph):
            errors.append("地图尚未确认或确认后被修改")
    return list(dict.fromkeys(errors))


def save_graph(path,graph,image,confirm=False):
    graph["confirmed"]=bool(confirm)
    graph["review_digest"]=fingerprint(graph) if confirm else ""
    errors=validate(graph,image,reviewed=confirm)
    if errors:
        graph["confirmed"]=False
        raise ValueError("\n".join(errors))
    p=Path(path);tmp=p.with_suffix('.tmp')
    tmp.write_text(json.dumps(graph,ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(p)


def load_graph(path,image):
    graph=json.loads(Path(path).read_text(encoding='utf-8'))
    errors=validate(graph,image,reviewed=True)
    if errors:
        raise ValueError("\n".join(errors))
    return graph


class Navigator:
    """Closed-loop commands only. Caller owns capture and input execution.

    Unknown platform => stop, never steer toward an unreachable nearest pixel.
    Failed transfer => stop; unexpected landing => discard path and replan.
    """
    def __init__(self,graph):
        self.graph=graph;self.platforms={p['id']:p for p in graph['platforms']}
        self.edges={e['id']:e for e in graph['edges']}
        self.current=None;self.goal=None;self.path=[];self.transit=None
        self.started=0.;self.deadline=0.;self.status="等待定位";self.fault=None
        self.last_pos=None;self.last_progress=0.;self.aim=None;self.settle=0
        self.walk_target=None;self.walk_side=False
        self.observed=None;self.observed_frames=0
        self.hunt_target=None;self.random_patrol=False
        self.patrol_visits={pid:0 for pid in self.platforms}
        self._visited_platform=None
        self.horizontal_motion=None

    def locate(self,pos):
        x,y=pos
        matches=[p for p in self.platforms.values() if p['x1']-1<=x<=p['x2']+1 and abs(y-platform_y(p,x))<=2]
        if not matches:return None
        return min(matches,key=lambda p:abs(y-platform_y(p,x)))['id']

    def block_edge(self,edge,now):
        edge['enabled']=False
        if edge['id'] in self.edges:self.edges[edge['id']]['enabled']=False
        if not hasattr(self,'_edge_failures'):self._edge_failures={}
        previous=self._edge_failures.get(edge['id'],(0,0))
        count=previous[0]+1
        edge['_runtime_failures']=count
        if edge['id'] in self.edges:self.edges[edge['id']]['_runtime_failures']=count
        self._edge_failures[edge['id']]=(count,now+(10 if count<3 else 30))

    def retry_failed_edges(self,now):
        restored=[]
        for eid,(count,until) in getattr(self,'_edge_failures',{}).items():
            edge=self.edges.get(eid)
            if edge and not edge['enabled'] and now>=until:
                edge['enabled']=True;restored.append(eid)
        return restored

    def recover_no_route(self,goal,pos,now):
        """A locked unreachable goal must not bypass the normal recovery path forever."""
        previous=getattr(self,'_no_route_wait',None)
        if previous is None or previous[0]!=goal:
            self._no_route_wait=(goal,now)
        elif now-previous[1]>=3:
            self._no_route_wait=None
            self.fault=f'目标 {goal} 连续无可达路线，自动换位恢复后重新规划'
            self.status=self.fault
            return self.recover_fault(pos,now)
        return ('none','none','none')

    def recover_fault(self,pos,now,valid=True):
        """Closed-loop recovery after a failed transfer; never discard hunt target."""
        if not self.fault:
            self._fault_motion=None;return None
        if not valid:
            self._fault_motion=None
            self.status='恢复中：等待小地图重新定位'
            return ('none','none','none')
        active=getattr(self,'_fault_motion',None)
        if active is None:
            ropes=[r for r in self.graph.get('ropes',[]) if abs(pos[0]-r['x'])<=2 and r['y1']<=pos[1]<=r['y2']]
            p=self.platforms.get(self.locate(pos))
            if p is None and self.platforms:
                p=min(self.platforms.values(),key=lambda p:abs(platform_y(p,pos[0])-pos[1])+abs((p['x1']+p['x2'])/2-pos[0]))
            target=(p['x1']+p['x2'])/2 if p else pos[0]+3
            direction='left' if target<pos[0] else 'right'
            active=dict(start=now,origin=tuple(pos),direction=direction,rope=bool(ropes),stable=0,last=tuple(pos))
            self._fault_motion=active
        here=self.locate(pos)
        near_rope=any(abs(pos[0]-r['x'])<=2 and r['y1']<=pos[1]<=r['y2'] for r in self.graph.get('ropes',[]))
        stable=here is not None and not near_rope and math.dist(pos,active['last'])<=.5 and math.dist(pos,active['origin'])>=2
        active['last']=tuple(pos);active['stable']=active['stable']+1 if stable else 0
        if active['stable']>=3:
            self.fault=None;self.rope_recovery=None;self._rope_failed=None;self._unknown_failed=None
            self.transit=None;self.path=[];self.goal=None;self.aim=None;self._fault_motion=None
            self.current=here;self.observed=here;self.observed_frames=3;self.last_pos=pos;self.last_progress=now
            self.status=f'自动脱困成功：已回到 {here}，重新规划原目标'
            return ('none','none','none')
        elapsed=now-active['start']
        if elapsed>=6:
            self._fault_motion=None
            self.status='脱困动作结束，重新评估位置后继续尝试'
            return ('none','none','none')
        if active['rope'] and elapsed<1:
            self.status='超时自动恢复：先向上尝试脱绳'
            return ('none','up','none')
        phase=elapsed-(1 if active['rope'] else 0)
        direction=active['direction'] if phase<1.6 else ('right' if active['direction']=='left' else 'left')
        # Share a cooldown with rope dismounts; do not chain recovery jumps.
        action='none'
        if .15<=phase<.4 and now>=getattr(self,'_recovery_jump_after',0):
            action='jump';self._recovery_jump_after=now+10
        moving=phase<.8 or 1.6<=phase<2.4
        self.status=f'超时自动恢复：{direction} 方向跳跃/落地确认，保留原目标'
        return (direction if moving else 'none','none',action)

    def recover_rope(self,pos,now,valid=True):
        """Recover only a confirmed marked rope interior, never a nearby platform."""
        active=getattr(self,'rope_recovery',None)
        if not valid:
            self.rope_recovery=None;self._rope_seen=None;self._rope_frames=0
            return None
        if active:
            rope,top=active['rope'],active['top']
            if 'exit_started' in active:
                elapsed=now-active['exit_started']
                landing=self.locate(pos)
                previous=active.get('exit_position');active['exit_position']=tuple(pos)
                stable=previous is not None and math.dist(pos,previous)<=.5
                landed=(abs(pos[0]-rope['x'])>=2.5 and landing is not None and stable)
                active['exit_settle']=active.get('exit_settle',0)+1 if landed and elapsed>=.4 else 0
                if active['exit_settle']>=3:
                    self.rope_recovery=None;self.fault=None;self.transit=None
                    self.current=landing;self.path=[];self.goal=None;self.aim=None
                    self.last_progress=now;self._rope_completed_pos=tuple(pos)
                    self.status='已横向离开绳子并确认落地，恢复攻击'
                    return ('none','none','none')
                if elapsed>=2:
                    if abs(pos[0]-rope['x'])>=2.5 and landing is None:
                        self.rope_recovery=None;self._rope_failed=None
                        self.status='已离开绳子，交给未知平台恢复重新定位'
                        return None
                    self.fault='绳子恢复失败：跳离后未确认落地，请检查平台定位'
                    self.status=self.fault
                    return ('none','none','none')
                self.status='绳顶脱离确认：向平台内跳离，落地前禁止攻击'
                return (active['exit_direction'] if elapsed<.7 else 'none','none','none')
            if abs(pos[0]-rope['x'])>2:
                self.rope_recovery=None;return None
            if active.get('top_probe') and now-active['started']<.6:
                self.status='绳顶边界恢复：短暂向上脱绳，暂不攻击'
                return ('none','up','none')
            if self.locate(pos)==top['id'] and pos[1]<=platform_y(top,pos[0])+.5:
                active['settle']+=1
                if active['settle']>=3:
                    if active.get('top_probe'):
                        active['exit_started']=now
                        active['exit_direction']='left' if rope['x']-top['x1']>=top['x2']-rope['x'] else 'right'
                        self.status='绳顶边界位置重叠，先向平台内跳离再确认'
                        action='none'
                        if now>=getattr(self,'_recovery_jump_after',0):
                            action='jump';self._recovery_jump_after=now+10
                        return (active['exit_direction'],'none',action)
                    self.rope_recovery=None;self.fault=None;self.transit=None
                    self.current=top['id'];self.path=[];self.goal=None;self.aim=None
                    self.last_progress=now;self._rope_seen=None;self._rope_frames=0
                    self._rope_completed_pos=tuple(pos)
                self.status='绳子恢复：已到顶部，确认平台位置'
                return ('none','none','none')
            active['settle']=0
            if abs(pos[1]-active['y'])>=.5:active['y']=pos[1];active['progress']=now
            if now-active['progress']>6 or now-active['started']>20:
                self.rope_recovery=None;self._rope_failed=(rope['id'],tuple(pos))
                self.fault='绳子恢复失败：持续向上仍无进展，请检查绳子位置或按键'
                self.status=self.fault;return ('none','none','none')
            self.status=f"绳子恢复：沿 {rope['id']} 向上爬到 {top['id']}，暂不攻击"
            return ('none','up','none')
        # Normal transfers retain their planned direction while progressing.
        if self.transit and not self.fault and now-self.last_progress<=5 and now<=self.deadline:return None
        located=self.locate(pos)
        completed=getattr(self,'_rope_completed_pos',None)
        if completed is not None:
            if math.dist(pos,completed)<2:return None
            self._rope_completed_pos=None
        top_probe=located is not None and pos[1]<=platform_y(self.platforms[located],pos[0])+.5
        if top_probe and now<getattr(self,'_recovery_jump_after',0):
            self._rope_seen=None;self._rope_frames=0
            return None
        if top_probe and not any(abs(pos[0]-r['x'])<=1.5 and r['y1']+.5<pos[1]<=r['y1']+2
                                for r in self.graph.get('ropes',[])):return None
        candidates=[r for r in self.graph.get('ropes',[]) if abs(pos[0]-r['x'])<=1.5
                    and r['y1']+.5<pos[1]<r['y2']-2]
        if not candidates:
            self._rope_seen=None;self._rope_frames=0;return None
        rope=min(candidates,key=lambda r:abs(r['x']-pos[0]))
        failed=getattr(self,'_rope_failed',None)
        if failed and failed[0]==rope['id'] and math.dist(pos,failed[1])<2:
            self.status=self.fault or '绳子恢复失败，等待位置变化或修正绳子标注'
            return ('none','none','none')
        tops=[p for p in self.platforms.values() if p['x1']<=rope['x']<=p['x2']
              and abs(platform_y(p,rope['x'])-rope['y1'])<=2]
        if not tops:return None
        self._rope_frames=getattr(self,'_rope_frames',0)+1 if getattr(self,'_rope_seen',None)==rope['id'] else 1
        self._rope_seen=rope['id']
        if self._rope_frames<3:
            self.status='疑似位于绳子中段，等待连续定位确认';return ('none','none','none')
        top=min(tops,key=lambda p:abs(platform_y(p,rope['x'])-rope['y1']))
        self.rope_recovery=dict(rope=rope,top=top,started=now,progress=now,y=pos[1],settle=0,top_probe=top_probe)
        self.fault=None;self.transit=None;self.path=[];self.aim=None
        self.status=f"绳子恢复：沿 {rope['id']} 向上爬到 {top['id']}，暂不攻击"
        return ('none','up','none')

    def recover_unknown(self,pos,now,valid=True):
        """Bounded directional search after a stationary unknown map position."""
        stop=('none','none','none')
        active=getattr(self,'_unknown_search',None)
        if not valid:
            self._unknown_search=None;self._unknown_wait=None;return None
        here=self.locate(pos)
        if here:
            self._unknown_wait=None
            if not active:return None
            active['settle']=active.get('settle',0)+1
            self.status=f'恢复到 {here}，等待连续定位确认'
            if active['settle']>=3:
                self._unknown_search=None;self._unknown_failed=None
                self.fault=None;self.transit=None;self.path=[];self.goal=None;self.aim=None
                self.current=here;self.observed=here;self.observed_frames=3;self.last_progress=now;self.last_pos=pos
                self.status=f'已恢复到 {here}，重新规划'
            return stop
        if self.transit and not self.fault:return None
        if getattr(self,'rope_recovery',None):return None
        # Do not walk sideways off a marked rope, even when its top is unmapped.
        if any(abs(pos[0]-r['x'])<=2 and r['y1']<=pos[1]<=r['y2'] for r in self.graph.get('ropes',[])):
            self._unknown_search=None;self._unknown_wait=None;return None
        failed=getattr(self,'_unknown_failed',None)
        if failed and math.dist(pos,failed)<3:
            if now<getattr(self,'_unknown_retry_at',0):
                self.status='未知位置恢复：短暂观察落点，随后重新方向跳跃';return stop
            self._unknown_failed=None;self._unknown_wait=(tuple(pos),now-2)
        if not active:
            wait=getattr(self,'_unknown_wait',None)
            if not wait or math.dist(pos,wait[0])>1:
                self._unknown_wait=(tuple(pos),now);return None
            if now-wait[1]<2:return None
            if not self.platforms:return None
            target=min(self.platforms.values(),key=lambda p:abs(pos[1]-platform_y(p,pos[0]))*3+
                       abs(pos[0]-max(p['x1'],min(p['x2'],pos[0]))))
            tx=max(target['x1'],min(target['x2'],pos[0]))
            direction='left' if tx<pos[0] else 'right'
            active=dict(direction=direction,started=now,origin=tuple(pos),attempt=1,settle=0)
            self._unknown_search=active;self.transit=None;self.path=[];self.aim=None
        active['settle']=0
        if now-active['started']>=3 or abs(pos[0]-active['origin'][0])>=16:
            if active['attempt']==2:
                self._unknown_failed=tuple(pos);self._unknown_search=None;self._unknown_retry_at=now+4
                self.status='未知位置恢复：左右尝试后观察 4 秒，再继续恢复';return stop
            active.update(direction='right' if active['direction']=='left' else 'left',
                          started=now,origin=tuple(pos),attempt=2,jump_sent=False)
        direction=active['direction']
        # Keep one request asserted across keyboard ticks; its token prevents repeats.
        jump=now-active['started']<.35
        self.status=f"未知平台恢复：向{'左' if direction=='left' else '右'}跳跃试走（{active['attempt']}/2），找到平台即停止"
        return (direction,'none','jump' if jump else 'none')

    def slope_assist(self,platform,pos,target,now,edge=None):
        probe=(pos[0]+max(-4,min(4,target-pos[0]))) if platform.get('points') else target
        if platform_y(platform,probe)>=pos[1]-.5:return None
        if now-self.last_progress<.8:return None
        uphill='right' if target>pos[0] else 'left'
        key=(platform['id'],round(pos[0]),uphill)
        attempts=getattr(self,'_slope_attempts',{})
        if attempts.get(key,0)>=2:
            if edge:
                self.block_edge(edge,now);self.transit=None;self.path=[];self.goal=None;self.aim=None
                self.status='上坡跳跃仍无进展，本次禁用连接并重新规划'
            else:
                self.fault='斜坡内部移动受阻，两次跳跃未恢复，请检查斜坡标注';self.status=self.fault
            return ('none','none','none')
        attempts[key]=attempts.get(key,0)+1;self._slope_attempts=attempts
        self._slope_jump_start=now+.15
        self._slope_air_until=now+.85;self._slope_direction=key[2]
        if self.horizontal_motion:self.horizontal_motion.cancel()
        self.last_progress=now
        if edge:self.deadline=max(self.deadline,now+2)
        self.status=f"上坡受阻：第 {attempts[key]}/2 次，先按住方向再跳跃"
        return (key[2],'none','none')

    def release_failed_rope(self,pos,now,valid=True):
        edge=self.transit;grab=getattr(self,'_rope_grab',None)
        eligible=(valid and edge and edge['kind']=='rope' and grab and
                  getattr(self,'_rope_grab_edge',None)==id(edge) and
                  grab.jump_count>=2 and not grab.grabbed and now>=grab.next_jump and
                  self.locate(pos)==edge['src'] and
                  abs(pos[1]-platform_y(self.platforms[edge['src']],pos[0]))<=.5)
        previous=getattr(self,'_rope_ground_sample',None)
        if not eligible:
            self._rope_ground_sample=None;return False
        if previous is None or math.dist(pos,previous[0])>.5:
            self._rope_ground_sample=(pos,now);return False
        if now-previous[1]<.3:return False
        self.block_edge(edge,now)
        self.transit=None;self.path=[];self.aim=None;self.goal=None
        self.current=edge['src'];self._rope_grab_edge=None;self._rope_ground_sample=None
        self.status='抓绳失败但已稳定落回平台，退出攀爬并恢复近身攻击'
        return True

    def step(self,pos,now,valid=True):
        self.retry_failed_edges(now)
        from .motion_prediction import MotionPrediction
        if not hasattr(self,'motion_prediction'):self.motion_prediction=MotionPrediction()
        self.motion_prediction.update(pos,now,valid and not self.transit and now>=getattr(self,'_slope_air_until',0))
        stop=('none','none','none')
        if self.fault:
            # Recover only after a stable, known landing. One retry per location
            # prevents an unmovable character from entering an endless retry loop.
            here=self.locate(pos) if valid else None
            key=(here,round(pos[0]),round(pos[1]))
            previous=getattr(self,'_fault_observation',None)
            count=previous[1]+1 if previous and previous[0]==key and here else 1
            self._fault_observation=(key,count)
            tried=getattr(self,'_fault_retried',set())
            on_rope=any(abs(pos[0]-r['x'])<=2 and r['y1']<=pos[1]<=r['y2'] for r in self.graph.get('ropes',[]))
            if here and count>=3 and key not in tried and not (self.fault.startswith('绳子恢复失败') and on_rope):
                tried.add(key);self._fault_retried=tried
                if self.transit:self.transit['enabled']=False
                self.fault=None;self.transit=None;self.path=[];self.goal=None;self.aim=None
                self.current=here;self.observed=here;self.observed_frames=3
                self.last_progress=now;self.last_pos=pos;self._fault_observation=None
                if self.horizontal_motion:self.horizontal_motion.cancel()
                self.status=f'位置已稳定在 {here}，清除旧超时并重新规划'
                return stop
            self.status=self.fault;return stop
        if not valid:
            self.status="小地图定位无效，停止移动";self.transit=None;self.path=[]
            self.current=None;self.observed_frames=0;self.aim=None;return stop
        if now<getattr(self,'_slope_air_until',0):
            jump_start=getattr(self,'_slope_jump_start',None)
            jumping=jump_start is not None and jump_start<=now<jump_start+.25
            self.status='方向＋跳跃上坡，持续按住方向' if jumping else '跳跃恢复：保持方向，等待落点确认'
            return (self._slope_direction,'none','jump' if jumping else 'none')
        if self.last_pos is None or math.dist(pos,self.last_pos)>=1:
            self.last_progress=now;self.last_pos=pos
        if self.aim and now-self.last_progress>5 and not (self.transit and self.transit['kind']=='rope'):
            slope=self.platforms.get(self.transit['dst']) if self.transit and self.transit['kind']=='walk' else self.platforms.get(self.locate(pos))
            if slope and (slope.get('points') or abs(slope.get('end_y',slope['y'])-slope['y'])>=.5):
                target=self.aim[2] if self.aim[0]=='walk' else (slope['x2'] if slope.get('end_y',slope['y'])<slope['y'] else slope['x1'])
                assist=self.slope_assist(slope,pos,target,now,self.transit)
                if assist is not None:return assist
            origin=getattr(self,'_unstuck_origin',None)
            if origin is None or math.dist(pos,origin)>3:
                self._unstuck_origin=tuple(pos);self._unstuck_attempts=0
            count=getattr(self,'_unstuck_attempts',0)
            if count<2:
                self._unstuck_attempts=count+1
                target=self.aim[2] if self.aim[0]=='walk' else pos[0]+1
                first='left' if target<pos[0] else 'right'
                direction=first if count==0 else ('right' if first=='left' else 'left')
                self.last_progress=now;self._slope_air_until=now+.6;self._slope_direction=direction
                self._slope_jump_start=None
                if self.transit:self.deadline=max(self.deadline,now+2)
                self.status=f'原地受阻：第 {count+1}/2 次向{direction}跳跃恢复'
                return (direction,'none','jump')
            self.fault="导航无进展，已停止；请检查平台和连接标注";self.status=self.fault;return stop
        here=self.locate(pos)
        if here==self.observed:self.observed_frames+=1
        else:self.observed=here;self.observed_frames=1
        if self.transit:
            e=self.transit
            # Jumping can cross the target height on ascent. Require time to
            # leave the source, then a stable landing before advancing the path.
            arrival_ready=e['kind'] not in ('jump','drop') or now-self.started>=0.3
            if e['kind']=='rope':
                # Proximity to a platform is not proof the character has left
                # the rope. Keep holding up until reaching its actual surface.
                surface=platform_y(self.platforms[e['dst']],pos[0])
                upward=e['end'][1]<e['start'][1]
                arrival_ready=pos[1]<=surface+.5 if upward else pos[1]>=surface-.5
                if getattr(self,'_rope_arrival_edge',None)!=id(e):
                    self._rope_arrival_edge=id(e);self._rope_arrival_since=None
                if here==e['dst'] and arrival_ready:
                    if self._rope_arrival_since is None:self._rope_arrival_since=now
                    if now-self._rope_arrival_since<.35:
                        self.status='绳索到端余量：继续向'+('上' if upward else '下')+'移动，等待平台确认'
                        self.settle=0
                        return ('none','up' if upward else 'down','none')
                else:self._rope_arrival_since=None
            previous=getattr(self,'landing_position',None)
            stable=previous is not None and math.dist(pos,previous)<=0.5
            self.landing_position=pos
            slope_transfer=e['kind']=='walk' and abs(self.platforms[e['dst']].get('end_y',self.platforms[e['dst']]['y'])-self.platforms[e['dst']]['y'])>.5
            if slope_transfer:
                arrival_ready=(abs(pos[1]-platform_y(self.platforms[e['dst']],pos[0]))<=.5
                               and abs(pos[0]-e['end'][0])<=1)
            if here==e['dst'] and arrival_ready and (e['kind'] not in ('jump','drop') and not slope_transfer or stable):
                self.settle+=1
                if self.settle>=(2 if e['kind']=='teleport' else 3):
                    self.current=here;self.transit=None;self.path=self.path[1:];self.aim=None
                    if here==self.goal:self.goal=None;self.path=[]
                self.status="等待到达位置稳定";return stop
            self.settle=0
            if here and here not in (e['src'],e['dst']):
                self.block_edge(e,now)
                self.transit=None;self.path=[];self.current=None;self.aim=None;self.observed_frames=0
                self.goal=None
                self.status="落到其他平台，失败连接冷却后自动重试";return stop
            if slope_transfer:
                assist=self.slope_assist(self.platforms[e['dst']],pos,e['end'][0],now,e)
                if assist is not None:return assist
            if now>self.deadline:
                if here==e['src']:
                    self.block_edge(e,now)
                    self.transit=None;self.path=[];self.aim=None;self.goal=None
                    seconds=self._edge_failures[e['id']][1]-now
                    self.status=f"{e['id']} 到达超时，临时禁用并冷却 {seconds:.0f} 秒，重新规划"
                    return stop
                self.fault=f"{e['id']} 到达超时，位置未确认，已停止；请检查连接"
                self.block_edge(e,now)
                self.transit=None;self.status=self.fault;return stop
            self.status=f"{e['src']} → {e['dst']}：等待到达"
            if e['kind']=='drop' and abs(e['end'][0]-e['start'][0])<=1:
                elapsed=now-self.started
                if elapsed<.15:return ('none','down','none')
                if elapsed<.5:return ('none','down','jump')
            if e['kind']=='teleport':
                dy=e['end'][1]-e['start'][1];dx=e['end'][0]-e['start'][0]
                direction=('none','up' if dy<0 else 'down') if abs(dy)>2 else ('left' if dx<0 else 'right','none')
                if not getattr(self,'teleport_fired',True):
                    if now-self.started<.08:return (*direction,'none')
                    self.teleport_fired=True;self._teleport_request_until=now+.25
                    self.deadline=now+max(.7,min(1.2,.6+getattr(self,'input_latency_ms',0)/1000*2))
                    return (*direction,'teleport')
                if now<getattr(self,'_teleport_request_until',0):return (*direction,'teleport')
            if e['kind']=='rope':
                if e['end'][1]>e['start'][1] and 0<e['end'][1]-pos[1]<=self.graph.get('profile',{}).get('drop_y',24):
                    dst=self.platforms[e['dst']]
                    right=dst['x2']-pos[0];left=pos[0]-dst['x1']
                    if max(left,right)>=4 and dst['x1']<=pos[0]<=dst['x2']:
                        if getattr(self,'_rope_drop_edge',None)!=id(e):
                            self._rope_drop_edge=id(e);self._rope_drop_started=now
                            self._rope_drop_direction='right' if right>=left else 'left'
                        elapsed=now-self._rope_drop_started
                        if elapsed<.65:
                            self.status='下绳快捷离开：朝平台内侧方向＋跳跃，等待落地'
                            return (self._rope_drop_direction,'none','jump' if .1<=elapsed<.3 else 'none')
                from src.navigation.rope_grab import RopeGrab
                if getattr(self,'_rope_grab_edge',None)!=id(e):
                    self._rope_grab=RopeGrab(e,self.platforms[e['src']],now)
                    self._rope_grab_edge=id(e)
                command,detail=self._rope_grab.step(pos,now)
                self.status=f"{e['id']} {detail}"
                return command
            if e['kind'] in ('jump','drop','walk'):
                if e['kind']=='jump' and now-self.started<.18:
                    return (self._jump_direction,'none','jump')
                dx=e['end'][0]-pos[0]
                if abs(dx)>1:
                    return ('left' if dx<0 else 'right','none','none')
            return stop
        if here is None:
            self.status="不在已标注平台，停止；请补充平台或手动回到平台";self.path=[];self.aim=None;self.current=None;return stop
        if here!=self.current and self.observed_frames<3:
            self.status="等待平台定位稳定";return stop
        if here!=self.current:
            self.current=here;self.path=[];self.aim=None;self.walk_target=None
        if here!=self._visited_platform:
            self.patrol_visits[here]+=1;self._visited_platform=here
        p=self.platforms[here]
        if p.get('reset_point'):
            exits=[q for q in self.platforms if not self.platforms[q].get('reset_point') and shortest_path(self.graph,here,q)]
            if not exits:
                normal=[q for q in self.platforms if not self.platforms[q].get('reset_point')]
                self.status='复位点暂无已知出口，尝试有界脱困恢复'
                return self.recover_no_route(normal[0] if normal else here,pos,now)
            goal=min(exits,key=lambda q:len(shortest_path(self.graph,here,q)))
            self.hunt_target=dict(platform=goal,x=(self.platforms[goal]['x1']+self.platforms[goal]['x2'])/2)
        sweep=getattr(self,'platform_sweep',None)
        if sweep and not p.get('reset_point'):
            selected=sweep.next_target(self.graph,here,pos,now)
            if selected!=self.hunt_target:
                from src.utils.logger import logger
                logger.info(f'[平台目标] {self.hunt_target} → {selected}；已完成 {sorted(sweep.done)}')
                self.hunt_target=selected;self.path=[];self.goal=None;self.aim=None
            if selected is None:
                self.status='本轮没有可达平台';return stop
        if self.hunt_target and here==self.hunt_target['platform']:
            target=self.hunt_target['x']
            if abs(pos[0]-target)<=1:
                self.aim=None
                key=(here,round(target))
                if getattr(self,'_hunt_arrival_key',None)!=key:
                    self._hunt_arrival_key=key;self._hunt_arrival_time=now
                self.status='已到锁定目标，等待有效扫描确认清怪完成'
                return stop
        elif len(self.platforms)==1:
            margin=min(2,(p['x2']-p['x1'])/4)
            if self.walk_target is None:self.walk_target=p['x2']-margin
            if abs(pos[0]-self.walk_target)<=1:
                self.walk_side=not self.walk_side
                self.walk_target=p['x1']+margin if self.walk_side else p['x2']-margin
            target=self.walk_target
        else:
            if not self.path:
                if self.hunt_target:
                    from .mob_hunt import route_to
                    self.goal=self.hunt_target['platform']
                    route=route_to(self.graph,here,pos,self.hunt_target)
                    self.path=route[1] if route else []
                    if route is None:
                        restored=self.retry_failed_edges(now)
                        if restored:
                            self.status=f"保留目标 {self.goal}，冷却完成，重试连接 {', '.join(restored)}"
                            return stop
                        pending=[until-now for count,until in getattr(self,'_edge_failures',{}).values() if until>now]
                        detail=f'等待连接冷却 {min(pending):.1f} 秒后重试' if pending else '地图暂未连通，将自动换位重试'
                        self.status=f"锁定目标 {self.goal} 暂无可达路线，{detail}"
                        return self.recover_no_route(self.goal,pos,now)
                    self._no_route_wait=None
                elif self.random_patrol:
                    import random
                    reachable=[pid for pid in self.platforms if pid!=here and shortest_path(self.graph,here,pid) is not None]
                    least=min((self.patrol_visits[pid] for pid in reachable),default=0)
                    candidates=[pid for pid in reachable if self.patrol_visits[pid]==least]
                    self.goal=random.choice(candidates) if candidates else here
                    self.path=shortest_path(self.graph,here,self.goal)
                else:
                    ids=list(self.platforms);idx=ids.index(here)
                    self.goal=ids[(idx+1)%len(ids)]
                    self.path=shortest_path(self.graph,here,self.goal)
                if not self.path:
                    self.status="无可达目标，停止";return stop
            e=self.edges[self.path[0]];target=e['start'][0]
            region=None
            if e['kind']=='drop' and abs(e['end'][0]-e['start'][0])<=1:
                src,dst=self.platforms[e['src']],self.platforms[e['dst']]
                lo=max(src['x1'],dst['x1'])+1;hi=min(src['x2'],dst['x2'])-1
                if lo<=hi:
                    x=max(lo,min(hi,pos[0]))
                    sy,dy=platform_y(src,x),platform_y(dst,x)
                    if 2<dy-sy<=self.graph.get('profile',{}).get('drop_y',24):
                        e=dict(e,start=[x,sy],end=[x,dy]);target=x
            if e['kind']=='teleport':
                regions=teleport_regions(self.graph,e)
                if not regions:
                    e['enabled']=False;self.path=[];self.goal=None
                    self.status='瞬移无有效落地区域，重新规划';return stop
                region=min(regions,key=lambda r:abs(pos[0]-max(r['x1'],min(r['x2'],pos[0]))))
                margin=min(.5,(region['x2']-region['x1'])/2)
                target=max(region['x1']+margin,min(region['x2']-margin,pos[0]))
            ready=(region['x1']<=pos[0]<=region['x2']) if region else abs(pos[0]-target)<=1
            if e['kind']=='walk':ready=abs(pos[0]-target)<=2
            predicted=self.motion_prediction.advance(pos[0],target,getattr(self,'input_latency_ms',0))
            lead=abs(predicted-pos[0])
            if e['kind']=='jump':
                src=self.platforms[e['src']];dest=self.platforms[e['dst']]
                sign=1 if dest['x1']+dest['x2']>src['x1']+src['x2'] else -1
                direction='right' if sign>0 else 'left'
                run=getattr(self,'_jump_runup',None)
                if run and run['edge']!=e['id']:self._jump_runup=None;run=None
                if not run and abs(pos[0]-target)<=2 and sign*self.motion_prediction.vx<1:
                    back=max(src['x1'],min(src['x2'],target-sign*3))
                    self._jump_runup=run=dict(edge=e['id'],back=back,forward=False,started=now)
                if run:
                    if not run['forward'] and abs(pos[0]-run['back'])>.5 and now-run['started']<1:
                        self.status='边缘跳跃：回撤留出助跑距离'
                        return ('left' if run['back']<pos[0] else 'right','none','none')
                    run['forward']=True
                ready=abs(pos[0]-target)<=1+min(2,lead)
                if ready:
                    landing=max(dest['x1'],min(dest['x2'],e['end'][0]+sign*2))
                    e=dict(e,end=[landing,platform_y(dest,landing)])
                    self._jump_direction=direction;self._jump_runup=None
                elif run:
                    self.status='边缘跳跃：向目标助跑，预测起跳位置'
                    return (direction,'none','none')
            dst=self.platforms[e['dst']]
            approaching_slope=(e['kind']=='walk' and abs(dst.get('end_y',dst['y'])-dst['y'])>.5
                               and platform_y(dst,e['end'][0])<pos[1]-.5)
            if approaching_slope and lead>0:
                ready=ready or abs(pos[0]-target)<=1+lead
            if e['kind']=='rope' and e['end'][1]<e['start'][1]:
                ready=abs(pos[0]-target)<=min(5,3+lead)
            if ready:
                # An uphill walk edge must reach the upper end of the slope,
                # rather than stopping at an automatically generated midpoint.
                dst=self.platforms[e['dst']]
                uphill_walk=(e['kind']=='walk' and abs(dst.get('end_y',dst['y'])-dst['y'])>.5
                             and platform_y(dst,e['end'][0])<pos[1]-.5)
                if uphill_walk:
                    e=dict(e)
                    top_x=dst['x2'] if dst.get('end_y',dst['y'])<dst['y'] else dst['x1']
                    e['end']=[top_x,platform_y(dst,top_x)]
                self.transit=e;self.started=now;self.deadline=now+(8 if e['kind']=='rope' else 3 if e['kind'] in ('jump','drop') else 2)
                self.landing_position=None
                self._rope_grab_edge=None
                self.aim=('edge',e['id']);self.last_progress=now;self.settle=0
                if uphill_walk:
                    self.last_progress=now-.81
                    command=self.slope_assist(dst,pos,e['end'][0],now,e)
                    if lead>0:
                        self._slope_jump_start=now
                        self.status=f'预测坡脚起跳：速度 {self.motion_prediction.vx:.1f}，提前 {lead:.1f} 地图像素'
                        return (self._slope_direction,'none','jump')
                    return command
                dy=e['end'][1]-e['start'][1];dx=e['end'][0]-e['start'][0]
                if e['kind']=='rope':
                    from src.navigation.rope_grab import RopeGrab
                    self._rope_grab=RopeGrab(e,self.platforms[e['src']],now);self._rope_grab_edge=id(e)
                    self._rope_grab.approach_lead=min(2,lead)
                    command,self.status=self._rope_grab.step(pos,now)
                    return command
                direction='none' if abs(dx)<=1 else 'left' if dx<0 else 'right'
                if e['kind']=='jump':return (self._jump_direction,'none','jump')
                if e['kind']=='drop':return (direction,'down' if direction=='none' else 'none','none')
                if e['kind']=='walk':return (direction,'none','none')
                self.teleport_fired=False
                if abs(dy)>2:return ('none','up' if dy<0 else 'down','none')
                return ('left' if dx<0 else 'right','none','none')
        self.status=f"{here}：走向连接点 / 巡逻点"
        target=max(p['x1'],min(p['x2'],target))
        if abs(target-pos[0])<=0.5 and not (self.path and self.edges[self.path[0]]['kind']=='teleport'):
            self.status=f'{here}：已到平台边界，停止并重新规划'
            self.path=[];self.goal=None;self.aim=None
            return stop
        aim=('walk',here,target)
        if self.aim!=aim:self.last_progress=now;self.aim=aim
        assist=self.slope_assist(p,pos,target,now)
        if assist is not None:return assist
        if self.horizontal_motion is not None:
            predicted=self.motion_prediction.advance(pos[0],target,getattr(self,'input_latency_ms',0))
            self.horizontal_motion.predicted_shift=predicted-pos[0]
            command=self.horizontal_motion.step(p,pos,target,float(self.graph['profile']['teleport_x']),now,arrival_tolerance=.25)
            phase=self.horizontal_motion.phase
            labels={'prepare':'准备瞬移','landing':'确认瞬移落点','walk':'连续走位'}
            self.status=f"{here}：{labels.get(phase,'调整位置')}"
            return command
        return ('left' if target<pos[0] else 'right','none','none')
