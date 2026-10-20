"""Track screen position through short nametag occlusions using scene motion."""
import cv2
import numpy as np


class PlayerTracking:
    def __init__(self):
        self.image=None;self.map_pos=None;self.position=None;self.last_hit=-100

    def update(self, gray, map_pos, position, hit, valid, scale, now):
        # Exclude minimap/header and bottom HUD; downsample to bound CPU cost.
        h,w=gray.shape[:2]
        crop=gray[int(h*.3):int(h*.8),int(w*.15):int(w*.85)]
        current=cv2.resize(crop,None,fx=.25,fy=.25).astype(np.float32)
        result=position;reliable=bool(hit)
        if hit:
            self.position=tuple(position);self.last_hit=now
        elif (valid and scale and self.position is not None and self.map_pos is not None
              and self.image is not None and self.image.shape==current.shape and now-self.last_hit<=3):
            shift,response=cv2.phaseCorrelate(self.image,current)
            delta=np.asarray(map_pos)-self.map_pos
            camera=np.asarray(shift)*4
            if response>=.3 and np.isfinite(camera).all() and max(abs(camera))<160 and max(abs(delta))<=20:
                estimate=np.asarray(self.position)+delta*np.asarray(scale)+camera
                if 0<=estimate[0]<w and 0<=estimate[1]<h:
                    result=tuple(int(round(v)) for v in estimate);self.position=result;reliable=True
        if not reliable:self.position=None
        self.image=current;self.map_pos=np.asarray(map_pos) if valid else None
        return result,reliable


class AttackRecheck:
    def __init__(self):
        self.target=None;self.started=0;self.sent=0;self.pending=False;self.pending_since=0

    def update(self,target,now,sent,strict_hit):
        if self.pending:
            if not strict_hit:return True
            self.pending=False;self.started=now;self.sent=sent
        if target is None:
            self.target=None;return False
        if self.target is None or max(abs(target[i]-self.target[i]) for i in (0,1))>30:
            self.target=target;self.started=now;self.sent=sent
        if now-self.started>=3 and sent-self.sent>=3:
            self.pending=True;self.pending_since=now;return True
        return False
