"""Short-lived tracks refreshed only by actual matches, never by predictions."""
import math


class MonsterTracks:
    def __init__(self, ttl=2.5):
        self.ttl=ttl;self.tracks=[]

    def candidates(self, now, anchor, calibration=None):
        self.tracks=[t for t in self.tracks if now-t['seen']<=self.ttl]
        if not anchor[2]:return []
        result=[]
        for track in self.tracks:
            old=track['anchor']
            delta=[anchor[0][i]-old[0][i] for i in (0,1)]
            if calibration:
                delta=[delta[i]-(anchor[1][i]-old[1][i])*calibration['scale'][i] for i in (0,1)]
            elif max(map(abs,delta))>8:continue
            m=track['monster']
            result.append(dict(m,position=tuple(round(m['position'][i]+delta[i]) for i in (0,1)),
                               track_age=now-track['seen']))
        return result

    def update(self, detections, source, anchor, calibration=None):
        self.candidates(source,anchor,calibration)
        if not anchor[2]:return
        for monster in detections:
            # Remove only a nearby track of the same species. Other living
            # monsters survive a missed frame until their own timeout expires.
            matches=[]
            for track in self.tracks:
                projected=MonsterTracks(self.ttl);projected.tracks=[track]
                boxes=projected.candidates(source,anchor,calibration)
                if boxes and boxes[0]['name']==monster['name'] and math.dist(boxes[0]['position'],monster['position'])<=48:
                    matches.append((math.dist(boxes[0]['position'],monster['position']),track))
            if matches:self.tracks.remove(min(matches,key=lambda item:item[0])[1])
            self.tracks.append(dict(monster=dict(monster),seen=source,anchor=anchor))
        self.tracks=self.tracks[-12:]
