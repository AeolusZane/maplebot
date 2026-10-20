"""Short, platform-bounded movement after a sustained burst of actual key presses."""
class CombatReposition:
    def __init__(self):
        self.start=None;self.base=0;self.active=None;self.next_allowed=0

    def step(self,now,pos,platform,attacking,sent):
        if platform is None:
            self.start=None;self.active=None;return None
        if self.active:
            direction,x,deadline=self.active
            if now>=deadline or abs(pos[0]-x)>=2 or not platform['x1']+1<pos[0]<platform['x2']-1:
                self.active=None;self.start=None;self.next_allowed=now+2
                return ('none','none','none')
            return (direction,'none','none')
        if not attacking:
            self.start=None;return None
        if self.start is None:self.start=now;self.base=sent
        if now<self.next_allowed or sent-self.base<6 or now-self.start<.8:return None
        left=pos[0]-platform['x1'];right=platform['x2']-pos[0]
        if max(left,right)<4:return None
        direction='left' if left>right else 'right'
        self.active=(direction,pos[0],now+.3)
        return (direction,'none','none')
