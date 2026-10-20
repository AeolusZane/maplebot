"""Bounded closed-loop rope acquisition, in minimap coordinates."""
class RopeGrab:
    def __init__(self,edge,platform,now):
        self.edge=edge;self.platform=platform;self.started=now
        self.grabbed=False;self.pulse_until=0;self.rest_until=0;self.direction='none'
        self.jump_until=0.;self.next_jump=now;self.jump_count=0;self.capture_since=None
        self.takeoff_x=None;self.jump_started=None

    def step(self,pos,now):
        direction='up' if self.edge['end'][1]<self.edge['start'][1] else 'down'
        rise=(self.edge['start'][1]-pos[1])*(1 if direction=='up' else -1)
        aligned=abs(pos[0]-self.edge['start'][0])<=1.5
        # A jump alone changes Y: only confirm capture after the jump window,
        # while aligned with the rope and remaining above the takeoff platform.
        if rise>=2 and aligned and now>=self.jump_until:
            if self.capture_since is None:self.capture_since=now
            if direction=='down' or now-self.capture_since>=.3:self.grabbed=True
        else:self.capture_since=None
        if self.grabbed:
            return ('none',direction,'none'),'已抓住绳子，持续攀爬'
        if direction=='up':
            rope_x=self.edge['start'][0]
            dx=rope_x-pos[0]
            if now<self.jump_until:
                lateral='none' if abs(dx)<=.5 else 'left' if dx<0 else 'right'
                # Hold the request long enough for the keyboard worker to consume
                # its one-shot token; it still presses jump only once per attempt.
                action='jump' if now-self.jump_started<.18 else 'none'
                return (lateral,'up',action),'方向＋上＋跳抓绳：空中对准绳索'
            if rise>=2 and aligned:
                return ('none','up','none'),'确认已抓绳，持续向上'
            if self.jump_count>=2:
                return ('none','none','none'),'两次助跑抓绳未成功，等待导航恢复或改走其他路线'
            if now<self.next_jump:
                return ('none','up','none'),'等待本次跳跃落地，准备重新助跑'
            if self.takeoff_x is None:
                lead=min(5,3+getattr(self,'approach_lead',0))
                # Start on the approach side; directly below the rope, back off
                # toward the side with more ground before jumping back toward it.
                sign=(-1 if dx>0 else 1) if abs(dx)>.5 else (
                    -1 if rope_x-self.platform['x1']>=self.platform['x2']-rope_x else 1)
                self.takeoff_x=max(self.platform['x1'],min(self.platform['x2'],rope_x+sign*lead))
            near=abs(pos[0]-self.takeoff_x)<=1
            if not near:
                return ('left' if self.takeoff_x<pos[0] else 'right','none','none'),'提前靠近起跳点，留出助跑距离'
            self.jump_count+=1;self.jump_started=now
            self.jump_until=now+.65;self.next_jump=now+1.2;self.takeoff_x=None
            lateral='left' if dx<0 else 'right' if dx>0 else 'none'
            return (lateral,'up','jump'),f'第 {self.jump_count} 次方向＋上＋跳抓绳'
        offsets=(0,-1,1,-2,2)
        index=min(len(offsets)-1,int(max(0,now-self.started)/1.2))
        target=max(self.platform['x1'],min(self.platform['x2'],self.edge['start'][0]+offsets[index]))
        dx=target-pos[0]
        label=f'抓绳试探 {index+1}/5：目标 X={target:g}，当前 X={pos[0]:g}，等待高度变化'
        if abs(dx)<=.35:return ('none',direction,'none'),label
        if now<self.pulse_until:return (self.direction,direction,'none'),label
        if now<self.rest_until:return ('none',direction,'none'),label
        self.direction='left' if dx<0 else 'right'
        self.pulse_until=now+.06;self.rest_until=now+.24
        return (self.direction,direction,'none'),label
