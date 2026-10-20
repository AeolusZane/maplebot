"""Bounded startup movement to expose an obscured character name."""
class StartupPosition:
    def __init__(self):
        self.started=None;self.stable=0;self.done=False

    def step(self,now,located):
        if self.done:return None
        if self.started is None:self.started=now
        self.stable=self.stable+1 if located else 0
        elapsed=now-self.started
        if self.stable>=3 or elapsed>=2.8:
            self.done=True;return None
        # Hold direction before each short jump request; release between attempts.
        phase=elapsed-.3
        direction='none' if phase<0 else 'left' if phase<1.25 else 'right'
        jumping=.45<=elapsed<.65 or 1.7<=elapsed<1.9
        return (direction,'none','jump' if jumping else 'none')
