"""Short relative-motion prediction using distinct, recent detection frames."""
import math

class AttackPrediction:
    def __init__(self):self.stamp=None;self.previous=[];self.velocities=[]

    def update(self,monsters,player,stamp,now,reliable):
        monsters=[{k:v for k,v in m.items() if k!='_predicted_position'} for m in monsters]
        if not reliable or now-stamp>.25:
            self.stamp=None;self.previous=[];self.velocities=[];return monsters
        # A repeated frame may have a different ROI/order; never reuse velocities by index.
        if stamp==self.stamp:
            return monsters
        points=[(m['position'][0]-player[0],m['position'][1]-player[1]) for m in monsters]
        if stamp!=self.stamp:
            dt=stamp-self.stamp if self.stamp is not None else 0
            velocities=[];used=set()
            for point in points:
                candidates=sorted((math.dist(point,p),i) for i,p in enumerate(self.previous) if i not in used)
                velocity=None
                if .025<=dt<=.25 and candidates and candidates[0][0]<=min(60,320*dt):
                    if len(candidates)==1 or candidates[1][0]-candidates[0][0]>8:
                        distance,index=candidates[0];used.add(index)
                        old=self.previous[index];velocity=((point[0]-old[0])/dt,(point[1]-old[1])/dt)
                velocities.append(velocity)
            self.previous=points;self.velocities=velocities;self.stamp=stamp
        result=[]
        for i,m in enumerate(monsters):
            m=dict(m);v=self.velocities[i] if i<len(self.velocities) else None
            if v:
                x,y=m['position']
                m['_predicted_position']=(x+max(-24,min(24,v[0]*.18)),y+max(-16,min(16,v[1]*.18)))
            result.append(m)
        return result
