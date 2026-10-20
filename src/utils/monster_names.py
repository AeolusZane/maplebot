"""Local name-label confirmation for previously discovered, attacked monsters."""
from pathlib import Path
from functools import lru_cache
import cv2
import numpy as np


def text_mask(frame):
    return ((frame.min(axis=2)>=170) & (np.ptp(frame,axis=2)<55)).astype(np.uint8)*255


@lru_cache(maxsize=64)
def template(name):
    path=Path(__file__).resolve().parents[2]/'assets'/'monster_names'/f'{name}.png'
    if not path.is_file():return None
    img=cv2.imdecode(np.fromfile(str(path),dtype=np.uint8),1)
    return text_mask(img) if img is not None else None


def confirm_name(frame,previous,now,attacking):
    if not attacking or previous.get('track_age',0)>1.2:return None
    # Periodically require a fresh body match, even if a label lingers after death.
    origin=previous.get('name_track_started',now)
    if now-origin>6:return None
    pattern=template(previous['name'])
    if pattern is None:return None
    x,y=previous['position'];bw,bh=previous['size'];ph,pw=pattern.shape
    offset=previous.get('name_offset')
    ex,ey=(x+offset[0],y+offset[1]) if offset else (x+bw/2-pw/2,y+bh)
    height,width=frame.shape[:2]
    left=max(0,int(ex)-32);top=max(0,int(ey)-24)
    right=min(width,int(ex)+pw+32);bottom=min(height,int(ey)+ph+24)
    roi=frame[top:bottom,left:right]
    if roi.shape[0]<ph or roi.shape[1]<pw:return None
    scores=cv2.matchTemplate(text_mask(roi),pattern,cv2.TM_SQDIFF_NORMED)
    score,_,point,_=cv2.minMaxLoc(scores)
    if not np.isfinite(score) or score>.18:return None
    lx,ly=left+point[0],top+point[1]
    if offset is None:offset=(lx-x,ly-y)
    result=dict(previous,position=(lx-offset[0],ly-offset[1]),score=float(score),
                name_offset=offset,name_track_started=origin,name_confirmed=True,
                name_box=(lx,ly,pw,ph))
    result.pop('tracking_pending',None);result.pop('track_age',None)
    return result
