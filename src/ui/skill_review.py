"""Human visual verification of skill input candidates, not inferred cast success."""
import json
from pathlib import Path
import cv2
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QPushButton,QLineEdit,QMessageBox
from PySide6.QtGui import QFont,QFontDatabase
from src.utils.input_evidence import normalize
from src.utils.manual_session import write_json
from src.ui.monster_test import MonsterTest


def review_data(folder):
    folder=Path(folder)
    events=[json.loads(s) for s in (folder/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    if (folder/'manifest.json').exists():
        manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        cfg=manifest['cfg'];video=folder/'raw.mp4'
    else:
        cfg=next(e['cfg'] for e in events if e['kind']=='session')
        video=Path(str(folder).removesuffix('.session'))
    keys={normalize(cfg.get('key',{}).get(k,'')) for k in ('aoe_skill','directional_attack','jump','teleport')}
    keys.discard('')
    calls={e['event_id']:e for e in events if e['kind']=='key_call_start'}
    candidates=[]
    for e in events:
        human=e['kind']=='human_key' and e.get('edge')=='down'
        auto=e['kind']=='key_call_end' and e.get('api')=='key_down' and e.get('status')=='returned'
        if (human or auto) and normalize(e.get('key','')) in keys:
            candidate=dict(e)
            if auto:candidate['t_ns']=calls.get(e.get('call_id'),e)['t_ns']
            candidates.append(candidate)
    frames=sorted((e for e in events if e['kind']=='video_frame'),key=lambda e:e['t_ns'])
    return video,candidates,frames


class SkillReview(QDialog):
    def __init__(self,folder,parent=None):
        super().__init__(parent)
        self.folder=Path(folder);self.video,self.candidates,self.frames=review_data(folder)
        if not self.frames:raise ValueError('没有可关联的录像帧记录')
        if not self.candidates:raise ValueError('没有记录到配置中的攻击/跳跃/瞬移按键事件')
        self.cap=cv2.VideoCapture(str(self.video))
        if not self.cap.isOpened():raise ValueError('无法打开录像，请先结束录制')
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc');self.setFont(QFont('Microsoft YaHei',9))
        self.setWindowTitle('技能画面核验（人工标注）');self.resize(1200,500)
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel('按键仅是候选事件。查看前后画面后标注；动画被遮挡、持续按键或采样不足时选“无法判断”。'))
        self.select=QComboBox();layout.addWidget(self.select)
        for e in self.candidates:self.select.addItem(f'{e["t_ns"]/1e9:.3f}秒 · {e["key"]} · 事件 {e["event_id"]}')
        row=QHBoxLayout();layout.addLayout(row)
        self.images=[]
        for title in ('前0.5秒','按键时刻','后0.5秒'):
            column=QVBoxLayout();row.addLayout(column);column.addWidget(QLabel(title))
            image=QLabel();image.setFixedSize(370,230);column.addWidget(image);self.images.append(image)
        row=QHBoxLayout();layout.addLayout(row)
        self.offset=QComboBox();self.offset.addItems(['0.5','1.0','2.0']);row.addWidget(QLabel('前后间隔（秒）'));row.addWidget(self.offset)
        self.verdict=QComboBox();self.verdict.addItems(['无法判断','成功','失败']);row.addWidget(self.verdict)
        self.note=QLineEdit();self.note.setPlaceholderText('依据：技能动画/伤害/位移；可填写限制');row.addWidget(self.note)
        save=QPushButton('保存当前核验');save.clicked.connect(self.save);row.addWidget(save)
        self.info=QLabel();layout.addWidget(self.info)
        self.select.currentIndexChanged.connect(self.render);self.offset.currentIndexChanged.connect(self.render)
        self.finished.connect(lambda *_:self.cap.release())
        self.render()

    def render(self,*_):
        e=self.candidates[self.select.currentIndex()];step=float(self.offset.currentText())*1e9
        self.evidence=[]
        for label,delta in zip(self.images,(-step,0,step)):
            target=e['t_ns']+delta
            frame=min(self.frames,key=lambda f:abs(f['t_ns']-target))
            self.cap.set(cv2.CAP_PROP_POS_FRAMES,frame['video_index']);ok,img=self.cap.read()
            if ok:MonsterTest.display_image(label,img)
            else:label.clear();label.setText('帧读取失败')
            self.evidence.append(dict(video_index=frame['video_index'],t_ns=frame['t_ns'],readable=ok,
                requested_t_ns=int(target),timing_error_ns=int(frame['t_ns']-target)))
        self.verdict.setCurrentIndex(0);self.note.clear()
        self.info.setText('实际帧时刻：'+' / '.join(f'{f["t_ns"]/1e9:.3f}s' for f in self.evidence)+'；标签默认未知，不由按键调用自动确认。')

    def save(self):
        path=self.folder/'skill_reviews.json'
        try:
            labels=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
            e=self.candidates[self.select.currentIndex()]
            labels[str(e['event_id'])]=dict(event_id=e['event_id'],key=e['key'],
                verdict=self.verdict.currentText(),source='human_visual_review',
                evidence_frames=self.evidence,note=self.note.text(),video=str(self.video.name))
            write_json(path,labels);self.info.setText('已保存人工画面核验；原始事件未修改。')
        except Exception as exc:QMessageBox.warning(self,'保存失败',str(exc))
