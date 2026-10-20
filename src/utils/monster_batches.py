"""Fair animation-frame rotation, with a bounded density bonus."""
from collections import Counter


class MonsterBatches:
    def __init__(self):
        self.cursor={};self.density={};self.density_time=-100

    def observe(self, detections, now):
        self.density=Counter(m['name'] for m in detections)
        self.density_time=now

    def select(self, templates, now):
        selected={}
        def take(name, count):
            images=templates[name]
            if not images:return
            cursor=self.cursor.get(name,0)
            selected.setdefault(name,[]).extend(images[(cursor+i)%len(images)] for i in range(min(count,len(images))))
            self.cursor[name]=(cursor+min(count,len(images)))%len(images)
        # One original/mirrored pair of every species on every near scan.
        for name in templates:take(name,2)
        if now-self.density_time<=20:
            eligible=[n for n in selected if self.density.get(n,0)>0 and len(templates[n])>2]
            if eligible:take(max(eligible,key=lambda n:self.density[n]),2)
        return selected
