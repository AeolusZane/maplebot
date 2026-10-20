"""Bounded background OCR learns missing labels, never changes combat thresholds."""
import re
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import cv2
import numpy as np
from src.utils.monster_names import template,text_mask
from src.utils.logger import logger


class NameLearner:
    def __init__(self,root=None):
        self.root=Path(root) if root else Path(__file__).resolve().parents[2]/'assets'/'monster_names'
        self.pool=None;self.future=None;self.engine=None;self.next_at=0;self.votes={};self.attempts={}

    def offer(self,frame,monsters,now):
        if self.future is not None:
            if not self.future.done():return
            try:
                result=self.future.result()
                if result:self.accept(*result)
            except Exception as error:logger.warning(f'[名字采集] 本次跳过：{error}')
            self.future=None
        if now<self.next_at:return
        for m in sorted(monsters,key=lambda item:self.attempts.get(item['name'],-1)):
            name=m['name']
            if template(name) is not None or m.get('name_confirmed') or m.get('tracking_pending'):continue
            if Path(name).name!=name or any(c in name for c in '/\\:'):continue
            x,y=m['position'];w,h=m['size'];height,width=frame.shape[:2]
            left=max(0,int(x+w/2)-100);right=min(width,int(x+w/2)+100)
            top=max(0,int(y+h)-20);bottom=min(height,int(y+h)+45)
            crop=frame[top:bottom,left:right].copy()
            if crop.size==0:continue
            if self.pool is None:self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='monster-name')
            self.future=self.pool.submit(self.read,crop,name,now)
            self.attempts[name]=now
            self.next_at=now+3
            return

    def read(self,crop,name,now):
        if self.engine is None:
            from rapidocr_onnxruntime import RapidOCR
            self.engine=RapidOCR(intra_op_num_threads=1,inter_op_num_threads=1)
        rows,_=self.engine(cv2.resize(crop,None,fx=3,fy=3),use_cls=False)
        rows=list(rows or [])
        # OCR may split the level prefix and species into two adjacent boxes.
        joined=[]
        for box,text,confidence in rows:
            if not re.fullmatch(r'等级\d{1,3}',re.sub(r'\s+','',text)):continue
            a=np.asarray(box)
            for other,word,prob in rows:
                if re.sub(r'\s+','',word)!=name:continue
                b=np.asarray(other)
                if (0<=b[:,0].min()-a[:,0].max()<=45 and
                        abs(a[:,1].mean()-b[:,1].mean())<=12):
                    points=np.concatenate([a,b]);lo=points.min(axis=0);hi=points.max(axis=0)
                    joined.append(([[lo[0],lo[1]],[hi[0],lo[1]],[hi[0],hi[1]],[lo[0],hi[1]]],
                                   re.sub(r'\s+','',text)+name,min(confidence,prob)))
        rows+=joined
        matches=[]
        for box,text,confidence in rows or []:
            text=re.sub(r'\s+','',text)
            # Whole line must identify the expected species AND level; no fuzzy learning.
            if confidence<.92 or not re.fullmatch(r'等级\d{1,3}'+re.escape(name),text):continue
            points=np.asarray(box)/3
            x0,y0=np.floor(points.min(axis=0)-1).astype(int)
            x1,y1=np.ceil(points.max(axis=0)+1).astype(int)
            image=crop[max(0,y0):min(crop.shape[0],y1),max(0,x0):min(crop.shape[1],x1)].copy()
            if image.size:matches.append((name,image,text,float(confidence),now))
        return matches[0] if len(matches)==1 else None

    def accept(self,name,image,text,confidence,now):
        if not re.fullmatch(r'等级\d{1,3}'+re.escape(name),text) or confidence<.92:return False
        if Path(name).name!=name or any(c in name for c in '/\\:'):return False
        path=self.root/f'{name}.png'
        if path.exists():return False
        mask=text_mask(image)
        if mask.size==0 or np.count_nonzero(mask)<30:return False
        old=self.votes.get(name)
        count=1
        if old and old['text']==text and 2<=now-old['time']<=60:
            prior=old['mask']
            if abs(prior.shape[0]-mask.shape[0])<=2 and abs(prior.shape[1]-mask.shape[1])<=2:
                aligned=cv2.resize(mask,(prior.shape[1],prior.shape[0]),interpolation=cv2.INTER_NEAREST)
                intersection=np.count_nonzero((prior>0)&(aligned>0))
                union=np.count_nonzero((prior>0)|(aligned>0))
                if intersection/max(1,union)>=.7:count=old['count']+1
        self.votes[name]=dict(mask=mask,text=text,time=now,count=count)
        logger.info(f'[名字采集] {name} 已校验 {count}/3，OCR {confidence:.2f}')
        if count<3:return False
        self.root.mkdir(parents=True,exist_ok=True)
        data=cv2.imencode('.png',image)[1].tobytes()
        with path.open('xb') as stream:stream.write(data)
        path.with_suffix('.json').write_text(json.dumps(dict(name=name,text=text,confidence=confidence,
            confirmations=count,source='attack-body-match-and-ocr'),ensure_ascii=False),encoding='utf-8')
        template.cache_clear()
        logger.info(f'[名字采集] {name} 样本已保存并启用：{path}')
        return True


learner=NameLearner()
