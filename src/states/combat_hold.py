"""Require repeated fresh empty observations before resuming patrol."""
class CombatHold:
    def __init__(self):
        self.active=False;self.empty_since=None;self.empty_count=0

    def update(self,has_target,fresh,now):
        if has_target:
            self.active=True;self.empty_since=None;self.empty_count=0
        elif self.active and fresh:
            if self.empty_since is None:self.empty_since=now
            self.empty_count+=1
            if self.empty_count>=3 and now-self.empty_since>=1.5:self.active=False
        return self.active


class LocalizationGate:
    """Stop immediately on lost localization; resume only after stable observations."""
    def __init__(self):
        self.paused_at=None;self.good_since=None;self.good_count=0
    def update(self,valid,now):
        if not valid:
            if self.paused_at is None:self.paused_at=now
            self.good_since=None;self.good_count=0
            return False,0.
        if self.paused_at is None:return True,0.
        if self.good_since is None:self.good_since=now
        self.good_count+=1
        if self.good_count<3 or now-self.good_since<0.2:return False,0.
        duration=now-self.paused_at;self.paused_at=None
        return True,duration
