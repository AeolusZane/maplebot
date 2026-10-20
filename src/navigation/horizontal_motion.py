"""Continuous walking with confirmed, same-platform horizontal teleports."""
import random


def duration(mean, sigma, low, high):
    return max(low, min(high, random.gauss(mean, sigma)))


class HorizontalMotion:
    def __init__(self):
        self.phase = None
        self.until = 0.0
        self.key = None
        self.next_teleport = 0.0
        self.origin = 0.0

    def cancel(self):
        self.phase = None
        self.key = None

    def step(self, platform, position, target, reach, now, arrival_tolerance=1):
        stop = ('none', 'none', 'none')
        x = position[0]
        direction = 'left' if target < x else 'right'
        key = (platform['id'], direction)
        if key != self.key:
            self.cancel(); self.key = key
        distance = abs(target-x)
        if distance <= arrival_tolerance:
            self.cancel()
            return stop
        if self.phase == 'landing':
            moved=abs(x-self.origin)>=max(2,reach*0.4)
            if now < self.until and not moved:
                if now<getattr(self,'request_until',0):return (direction,'none','teleport')
                return stop
            if not moved:
                self.next_teleport = now+5.0
            self.phase = None
        landing = x + (-reach if direction == 'left' else reach)
        flat = abs(platform.get('end_y', platform['y'])-platform['y']) <= 1
        safe = (flat and reach > 0 and distance >= reach+2 and
                platform['x1']+2 <= landing <= platform['x2']-2 and
                platform['x1']+2 <= landing+getattr(self,'predicted_shift',0) <= platform['x2']-2 and
                abs(target-(x+getattr(self,'predicted_shift',0)))>=reach+2)
        if self.phase == 'prepare':
            if not safe:
                self.phase = None
            elif now < self.until:
                return (direction, 'none', 'none')
            else:
                self.origin = x
                self.phase = 'landing'
                self.until = now+.35
                self.request_until=now+.2
                self.next_teleport = now+0.8
                return (direction, 'none', 'teleport')
        if safe and now >= self.next_teleport:
            self.phase = 'prepare'
            self.until = now+0.08
            return (direction, 'none', 'none')
        self.phase = 'walk'
        return (direction, 'none', 'none')
