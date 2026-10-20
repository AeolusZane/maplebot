"""Short-horizon map-space velocity estimation; reject jumps and stale samples."""
from collections import deque

class MotionPrediction:
    def __init__(self):self.samples=deque();self.vx=0.

    def update(self,pos,now,valid=True):
        if not valid:
            self.samples.clear();self.vx=0.;return
        if self.samples:
            t,x,y=self.samples[-1];dt=now-t
            if dt<=0 or dt>.5 or abs(pos[0]-x)>8 or abs(pos[1]-y)>2:
                self.samples.clear()
        self.samples.append((now,float(pos[0]),float(pos[1])))
        while self.samples and now-self.samples[0][0]>.35:self.samples.popleft()
        self.vx=0.
        if len(self.samples)>=3:
            t,x,_=self.samples[0];dt=now-t
            if dt>=.1:self.vx=max(-30.,min(30.,(pos[0]-x)/dt))

    def advance(self,x,target,latency_ms=0):
        if self.vx*(target-x)<=0:return x
        horizon=max(.1,min(.3,float(latency_ms)/1000+.1))
        shift=max(-3.,min(3.,self.vx*horizon))
        return x+shift
