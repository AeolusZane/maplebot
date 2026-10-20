"""Bounded recovery from spawn/reset platforms, independent of upward rope rescue."""
class ResetEscape:
    def __init__(self,platform,ropes,now):
        self.source=platform['id'];self.platform=platform
        self.ropes=sorted([r for r in ropes if platform['x1']<=r['x']<=platform['x2'] and
                           r['y2']>platform['y']+2],key=lambda r:abs(r['x']-(platform['x1']+platform['x2'])/2))
        self.index=0;self.started=now;self.stable=0;self.last=None;self.done=False

    def step(self,pos,now,valid,normal):
        stop=('none','none','none')
        if not valid:
            self.started=now;return stop,'复位点恢复：等待可靠定位'
        stable=self.last is not None and abs(pos[0]-self.last[0])<=.5 and abs(pos[1]-self.last[1])<=.5
        self.last=pos;self.stable=self.stable+1 if normal and stable else 0
        if self.stable>=3:
            self.done=True;return stop,'复位点恢复成功：已稳定到达普通平台'
        if normal:return stop,'复位点恢复：确认普通平台落地'
        elapsed=now-self.started
        if self.index<len(self.ropes):
            r=self.ropes[self.index]
            if elapsed>=5 or pos[1]>=r['y2']:
                self.index+=1;self.started=now;return stop,'绳索下行结束，切换下一种恢复动作'
            dx=r['x']-pos[0]
            lateral='none' if abs(dx)<=.7 else 'right' if dx>0 else 'left'
            return (lateral,'down','none'),f"复位点恢复：靠近 {r['id']} 并向下，禁止向上返回复位点"
        phase=self.index-len(self.ropes)
        durations=[1.2,1.4,1.4,2.]
        if elapsed>=durations[phase]:
            self.index+=1;self.started=now
            if self.index>=len(self.ropes)+len(durations):self.index=0
            return stop,'复位点恢复：轮换动作，重新检查落点'
        if phase==0:return ('none','down','jump' if elapsed<.25 else 'none'),'复位点恢复：下＋跳，等待下落'
        if phase in (1,2):
            direction='left' if phase==1 else 'right'
            return (direction,'none','jump' if .15<=elapsed<.4 else 'none'),'复位点恢复：'+direction+'助跑跳离'
        return stop,'复位点恢复：本轮未离开，短暂观察后重新尝试'
