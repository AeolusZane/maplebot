"""Experience sampling and rates, independent of game input."""
import re


def parse_experience(text):
    text=text.replace(',', '').replace('，','').replace('％','%')
    match=re.search(r'(?<![\d.])(\d+)(?:\s*[\[（(]\s*|\s+)(\d+(?:\.\d+)?)\s*%',text)
    if not match:
        raise ValueError('未识别到「经验数字 + 百分比」，请确认底部经验栏未被遮挡')
    value,percent=int(match[1]),float(match[2])
    if not 0<=percent<=100:
        raise ValueError('经验数字与百分比不一致')
    return value,percent


class ExperienceStats:
    def __init__(self):
        self.rows=[];self.total=0;self.covered=0.;self.previous=None;self.gaps=False

    def add(self,elapsed,value,percent,text):
        gain=None;note='起始基准';dt=0
        if self.previous:
            t,old,old_percent=self.previous;dt=elapsed-t
            if dt<=0:return
            # A level-up/death or OCR inconsistency cannot be resolved from two snapshots.
            old_scale=old/old_percent if old_percent else None
            scale=value/percent if percent else None
            if value<old or percent<old_percent or (old_scale and scale and abs(scale/old_scale-1)>.02):
                note='升级/经验下降/识别异常：本区间未计入';self.gaps=True
            else:
                gain=value-old;self.total+=gain;self.covered+=dt;note='有效采样'
        self.previous=(elapsed,value,percent)
        self.rows.append((elapsed,value,percent,gain,note,text))

    @property
    def per_minute(self):
        return self.total*60/self.covered if self.covered else None


class ExperienceOCR:
    def __init__(self):self.engine=None
    def read_sample(self,image,level_image):
        import cv2
        value,percent,text=self.read(image)
        level=None
        result,_=self.engine(cv2.resize(level_image,None,fx=4,fy=4),use_cls=False)
        words=[r[1] for r in result or [] if r[2]>=.85]
        match=re.search(r'LV\s*[.：:]?\s*(\d{1,3})(?!\d)',' '.join(words),re.I)
        if match and 1<=int(match[1])<=300:level=int(match[1])
        return value,percent,text,level

    def read(self,image):
        import cv2
        if self.engine is None:
            from rapidocr_onnxruntime import RapidOCR
            self.engine=RapidOCR(intra_op_num_threads=1,inter_op_num_threads=1)
        image=cv2.resize(image,None,fx=3,fy=3,interpolation=cv2.INTER_CUBIC)
        result,_=self.engine(image,use_cls=False)
        lines=[r[1] for r in (result or []) if r[2]>=.85]
        candidates=[]
        for line in lines:
            try:
                value,percent=parse_experience(line)
                candidates.append((value,percent,line))
            except ValueError:pass
        if len(candidates)==1:return candidates[0]
        if len(candidates)>1:raise ValueError('检测到多个经验候选，本次不计入')
        text=' '.join(lines)
        try:value,percent=parse_experience(text)
        except ValueError as exc:
            raw=' | '.join(f'{r[1]} ({r[2]:.2f})' for r in (result or []))
            raise ValueError(f'{exc}；识别文字：{raw or "无文字"}') from exc
        return value,percent,text
