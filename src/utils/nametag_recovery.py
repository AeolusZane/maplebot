"""Conservative full-name recovery near a previously verified character."""
import cv2
import numpy as np


def recover_nearby_name(image, template, mask, previous, threshold=0.06):
    h,w=template.shape[:2];x,y=previous
    x0=max(0,int(x)-160);y0=max(0,int(y)-90)
    x1=min(image.shape[1],int(x)+w+160);y1=min(image.shape[0],int(y)+h+90)
    roi=image[y0:y1,x0:x1]
    if roi.shape[0]<h or roi.shape[1]<w:return None
    scores=cv2.matchTemplate(roi,template,cv2.TM_SQDIFF_NORMED,mask=mask)
    scores=np.nan_to_num(scores,nan=1,posinf=1,neginf=1)
    score,_,point,_=cv2.minMaxLoc(scores)
    if score>=threshold:return None
    px,py=point
    competitors=scores.copy()
    competitors[max(0,py-h):py+h+1,max(0,px-w):px+w+1]=1
    second=float(competitors.min())
    if second<score*1.5+0.01:return None
    return (x0+px,y0+py),score
