"""Read-only recorder vision, independent of the automation state machine."""
import cv2
from .common import get_minimap_loc_size, get_mask


def client_frame(frame, cfg):
    h, w = cfg.get('game_window', {}).get('size', frame.shape[:2])
    fh, fw = frame.shape[:2]
    if (fh, fw) == (h, w):
        return frame.copy()
    if 0 <= fw-w <= 4 and 0 < fh-h <= 80:
        x = (fw-w)//2
        y = fh-h-1
        return frame[y:y+h,x:x+w].copy()
    raise ValueError('游戏窗口尺寸与配置不一致，请恢复配置的游戏分辨率。')


def minimap_rect(frame):
    rect = get_minimap_loc_size(frame)
    if rect is None:
        raise ValueError('未识别到小地图，请展开游戏小地图。')
    x,y,w,h = map(int,rect)
    if w > frame.shape[1]*.8 or h < 30 or w/h > 12:
        raise ValueError('检测到的区域不是有效小地图，等待下一帧。')
    return x,y,w,h


def locate_name(frame, template, cfg):
    if template is None:
        return None, None
    opts=cfg.get('nametag',{})
    gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
    roi=gray[:cfg.get('ui_coords',{}).get('ui_y_start',int(gray.shape[0]*.92))]
    target=cv2.cvtColor(template,cv2.COLOR_BGR2GRAY)
    mode=opts.get('mode','grayscale')
    if mode=='white_mask':
        roi=cv2.inRange(cv2.GaussianBlur(roi,(3,3),0),150,255)
        target=cv2.inRange(cv2.GaussianBlur(target,(3,3),0),150,255)
    elif mode=='histogram_eq':
        _,roi=cv2.threshold(cv2.equalizeHist(roi),150,255,cv2.THRESH_BINARY)
        _,target=cv2.threshold(cv2.equalizeHist(target),150,255,cv2.THRESH_BINARY)
    if roi.shape[0]<target.shape[0] or roi.shape[1]<target.shape[1]:
        return None,None
    result=cv2.matchTemplate(roi,target,cv2.TM_SQDIFF_NORMED,mask=get_mask(template,(0,255,0)))
    score,_,position,_=cv2.minMaxLoc(result)
    if score > opts.get('global_diff_thres',opts.get('diff_thres',.02)):
        return None,score
    return (*position,target.shape[1],target.shape[0]),score
