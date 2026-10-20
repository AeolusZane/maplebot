"""Round-based platform coverage with latched endpoint completion."""
from .map_graph import shortest_path,platform_y
import time
from collections import Counter

class PlatformSweep:
    def __init__(self):
        self.done=set();self.target=None;self.ends=[];self.stage=0;self.round=1
        self.counts={};self.survey_time=None;self.completed_at={};self.priority_streak=0
        self.hotspots={}
        self.latest_counts={};self.urgent_target=None;self._decision_source=None
        self.in_view=set();self.visits=Counter();self.local_clears=0;self.explore_target=None
        self.coverage_since=None;self.coverage_seen={};self.coverage_target=None
        self.exploration_reason=''

    def coverage_due(self,graph,here,pos,now):
        # Long platforms have independent checkpoints, not one shared visited flag.
        import math
        if self.coverage_since is None:self.coverage_since=now
        options=[]
        for p in graph['platforms']:
            if p.get('reset_point'):continue
            margin=min(2,(p['x2']-p['x1'])/4)
            left,right=p['x1']+margin,p['x2']-margin
            count=max(1,math.ceil((right-left)/40))
            reachable=None
            for i in range(count+1):
                x=left+(right-left)*i/count;key=(p['id'],i)
                if p['id']==here and abs(pos[0]-x)<=8:self.coverage_seen[key]=now
                age=now-self.coverage_seen.get(key,self.coverage_since)
                if age<90 and not (self.local_clears>=2 and age>=30):continue
                if p['id']==here and abs(pos[0]-x)<=8:continue
                if reachable is None:reachable=shortest_path(graph,here,p['id']) is not None
                if reachable:options.append((age,abs(x-pos[0]),p,x,key))
        if self.explore_target or not options:return False
        age,_,p,x,key=max(options,key=lambda v:(v[0],v[1]))
        self.target=self.explore_target=p['id'];self.coverage_target=key
        self.urgent_target=None;self.ends=[x];self.stage=0
        self.exploration_reason=f'区域 {p["id"]} X={x:.1f} 已 {age:.0f} 秒未到访，锁定到达后再选怪'
        return True

    def observe(self,targets,source,visible_platforms=(),in_view=None):
        if self.survey_time is not None and source<=self.survey_time:return
        counts=dict(Counter(t['platform'] for t in targets));self.survey_time=source
        self.latest_counts=counts
        self.in_view=set(visible_platforms if in_view is None else in_view)|set(counts)
        self.hotspots={}
        for pid,count in counts.items():
            if source<=self.completed_at.get(pid,float('-inf')):continue
            points=[t for t in targets if t['platform']==pid and 'x' in t and 'y' in t]
            self.hotspots[pid]=dict(platform=pid,count=count,time=source,
                x=sum(t['x'] for t in points)/len(points) if points else None,
                y=sum(t['y'] for t in points)/len(points) if points else None)
        self.counts={pid:h['count'] for pid,h in self.hotspots.items()}

    def live_counts(self,now):
        if self.survey_time is None or now-self.survey_time>12:return {}
        return {pid:h['count'] for pid,h in self.hotspots.items()
                if h['time']>self.completed_at.get(pid,float('-inf'))}

    def top_hotspots(self,now):
        counts=self.live_counts(now)
        return [dict(self.hotspots[pid],age=max(0,now-self.hotspots[pid]['time']))
                for pid in sorted(counts,key=lambda pid:(-counts[pid],pid))[:3]]

    def redirect_to_crowd(self,graph,here,pos,now):
        if self.coverage_due(graph,here,pos,now):return True
        if self.explore_target:return False
        if self.local_clears>=2 and self.survey_time is not None and now-self.survey_time<=12:
            candidates=[p for p in graph['platforms'] if not p.get('reset_point') and p['id']!=here and p['id'] not in self.in_view
                        and not self.visits[p['id']] and shortest_path(graph,here,p['id']) is not None]
            if candidates:
                p=min(candidates,key=lambda p:len(shortest_path(graph,here,p['id'])))
                self.target=self.explore_target=p['id'];self.urgent_target=None
                margin=min(2,(p['x2']-p['x1'])/4);self.ends=[p['x1']+margin,p['x2']-margin]
                if abs(pos[0]-self.ends[1])<abs(pos[0]-self.ends[0]):self.ends.reverse()
                self.stage=0
                self.exploration_reason=f'完成两次目标，探索未访问平台 {p["id"]}'
                return True
        counts=self.live_counts(now)
        excluded={p['id'] for p in graph['platforms'] if p.get('reset_point')}
        options=[pid for pid,n in counts.items() if pid not in excluded and n>0 and shortest_path(graph,here,pid) is not None]
        if not options:
            if self.urgent_target:
                self.target=None;self.urgent_target=None;self.ends=[]
                return True
            return False
        if self._decision_source==self.survey_time:return False
        self._decision_source=self.survey_time
        crowded=[pid for pid in options if pid!=here and counts[pid]>=3]
        pid=max(crowded or options,key=lambda pid:(counts[pid],pid==self.target,
            -len(shortest_path(graph,here,pid))))
        p=next(p for p in graph['platforms'] if p['id']==pid)
        x=self.hotspots[pid].get('x')
        x=(p['x1']+p['x2'])/2 if x is None else max(p['x1'],min(p['x2'],x))
        changed=self.target!=pid or not self.urgent_target
        self.target=pid;self.urgent_target=pid;self.ends=[x];self.stage=0
        return changed

    def next_target(self,graph,here,pos,now=None):
        now=time.monotonic() if now is None else now
        ps={p['id']:p for p in graph['platforms'] if not p.get('reset_point')}
        self.redirect_to_crowd(graph,here,pos,now)
        if self.target and self.target not in ps:
            if self.explore_target==self.target:self.explore_target=None
            self.target=None;self.ends=[]
        if self.target and here==self.target and abs(pos[0]-self.ends[self.stage])<=2:
            self.stage+=1
            if self.stage==len(self.ends):
                coverage=self.coverage_target is not None
                if coverage:
                    self.coverage_seen[self.coverage_target]=now;self.coverage_target=None
                self.completed_at[self.target]=now
                self.visits[self.target]+=1
                if self.explore_target==self.target:
                    self.explore_target=None;self.local_clears=0
                else:self.local_clears+=1
                if self.urgent_target==self.target:self.urgent_target=None
                elif not coverage:self.done.add(self.target)
                self.hotspots.pop(self.target,None)
                self.target=None;self.ends=[]
        if self.target is None:
            reachable=[pid for pid in ps if shortest_path(graph,here,pid) is not None]
            candidates=[pid for pid in reachable if pid not in self.done]
            if not candidates:
                self.done.clear();self.round+=1;candidates=reachable
            if not candidates:return None
            self.target=candidates[0]
            p=ps[self.target]
            margin=min(2,(p['x2']-p['x1'])/4)
            ends=[p['x1']+margin,p['x2']-margin]
            if abs(pos[0]-ends[1])<abs(pos[0]-ends[0]):ends.reverse()
            self.ends=ends;self.stage=0
        p=ps[self.target];x=self.ends[self.stage]
        return dict(platform=self.target,x=x,y=platform_y(p,x))
