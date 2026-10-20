"""Health drops request a detection sweep, never blind attacks."""
import math


class DamageResponse:
    def __init__(self):
        self.baseline=None;self.previous_time=None;self.low=None
        self.pending=False;self.remaining=None;self.status="idle"
        self.last_damage=None;self.pause_started=None

    def observe(self,hp,now):
        if hp is None or not math.isfinite(hp) or not 0<hp<=100:
            self.baseline=None;self.low=None;return
        if self.baseline is None or self.previous_time is None or now-self.previous_time>1:
            self.baseline=hp;self.low=None;self.previous_time=now;return
        self.previous_time=now
        if hp>=self.baseline-1:
            self.baseline=hp;self.low=None;return
        if self.baseline-hp>=2:
            if self.low is None:self.low=hp;return
            if hp<=self.baseline-2:
                self.last_damage=now
                if not self.pending:
                    self.pending=True;self.remaining=None;self.status="pending"
                    self.pause_started=None
                self.baseline=hp;self.low=None

    def recent(self,now):
        return self.last_damage is not None and now-self.last_damage<=1.5

    def pause_for_scan(self,now):
        # One bounded pause per sweep; repeated damage cannot extend it forever.
        if not self.pending:return False
        if self.pause_started is None:self.pause_started=now
        return now-self.pause_started<2.5

    def batch(self,templates):
        if not self.pending:return None
        if self.remaining is None:
            self.remaining={name:list(range(len(frames))) for name,frames in templates.items() if frames}
        if not self.remaining:
            self.pending=False;self.status='no_templates';return None
        name=next(iter(self.remaining));indices=self.remaining[name][:4]
        self.status='checking:'+name
        return {name:[templates[name][i] for i in indices]},(name,indices)

    def complete(self,token,found,valid=True):
        if not self.pending or not valid:return None
        if found:
            self.pending=False;self.remaining=None;self.status='found';return 'found'
        if token is None:return None
        name,indices=token
        if self.remaining and name in self.remaining:
            rest=[i for i in self.remaining.pop(name) if i not in indices]
            if rest:self.remaining[name]=rest
        if not self.remaining:
            self.pending=False;self.status='unmatched';return 'unmatched'
        return None
