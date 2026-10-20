"""Read-only full-screen monster matching with per-map threshold tuning."""
import copy
import time
from pathlib import Path
from types import SimpleNamespace
import cv2
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QFontDatabase, QImage, QPixmap
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
    QDoubleSpinBox,QSizePolicy,QMessageBox)
from src.utils.paths import APP_ROOT
from src.utils.common import load_yaml,save_yaml,get_mask,get_minimap_loc_size
from src.utils.mapping_capture import client_frame
from src.utils.monster_threshold import map_threshold
from src.utils.latest_detection import LatestDetection
from src.navigation.map_graph import read_image


def scan(snapshot, threshold, source, generation):
    # Use exactly the same matcher and NMS as runtime, without constructing a bot.
    from src.engine.MapleStoryAutoLevelUp import MapleStoryAutoBot
    started=time.monotonic()
    h,w=snapshot.img_frame.shape[:2]
    mobs=MapleStoryAutoBot.get_monsters_in_range(snapshot,(0,0),(w,h))
    rect=get_minimap_loc_size(snapshot.img_frame)
    if rect:
        x,y,rw,rh=rect
        mobs=[m for m in mobs if not (x<=m['position'][0]+m['size'][0]/2<=x+rw and
                                    y<=m['position'][1]+m['size'][1]/2<=y+rh)]
    return snapshot.img_frame,mobs,threshold,source,generation,(time.monotonic()-started)*1000


class MonsterTest(QDialog):
    def __init__(self,map_name,cfg,parent=None,capture=None):
        super().__init__(parent)
        self.map_name=map_name;self.cfg=copy.deepcopy(cfg)
        self.setWindowTitle(f'怪物识别测试 · {map_name}')
        self.resize(1150,750)
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
        self.setFont(QFont('Microsoft YaHei',9))
        self.registry=Path(APP_ROOT)/'config/config_data.yaml'
        data=load_yaml(str(self.registry)) or {}
        names=(data.get('map_mobs_mapping',{}) or {}).get(map_name,[])
        self.templates={}
        for name in names:
            images=[]
            for path in (Path(APP_ROOT)/'monster'/name).glob(f'{name}*.png'):
                img=read_image(path)
                for tpl in (img,cv2.flip(img,1)):
                    images.append((tpl,get_mask(tpl,(0,255,0))))
            if images:self.templates[name]=images
        if not self.templates:
            raise ValueError('本地图没有可用怪物素材，请先在「打哪几种怪」中选择怪物。')
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel('只测试当前地图登记的怪物：'+'、'.join(self.templates)+'。不会发送游戏按键。'))
        row=QHBoxLayout();layout.addLayout(row)
        row.addWidget(QLabel('匹配误差上限（越大越宽松）：'))
        self.threshold=QDoubleSpinBox();self.threshold.setRange(.001,1);self.threshold.setDecimals(3)
        self.threshold.setSingleStep(.01)
        self.threshold.setValue(map_threshold(data,map_name,cfg['monster_detect']['diff_thres']))
        row.addWidget(self.threshold)
        self.pause=QPushButton('暂停检测');self.pause.setCheckable(True);row.addWidget(self.pause)
        save=QPushButton('保存为本地图阈值');row.addWidget(save);save.clicked.connect(self.save)
        self.status=QLabel('正在获取游戏画面…');layout.addWidget(self.status)
        self.result=QLabel('等待首次全屏识别');self.result.setAlignment(Qt.AlignCenter)
        self.result.setMinimumSize(640,360);self.result.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Expanding)
        layout.addWidget(self.result,1)
        bottom=QHBoxLayout();layout.addLayout(bottom)
        self.live=QLabel();self.live.setFixedSize(300,170);bottom.addWidget(self.live)
        self.details=QLabel('左侧：实时画面\n上方：识别结果对应帧\n框旁 M 编号对应这里的怪物名称和误差。')
        self.details.setWordWrap(True);bottom.addWidget(self.details,1)
        self.generation=0;self.source=None;self.result_count=0;self.elapsed=0
        self.last_stamp=None;self.pending=False;self.closed=False
        self.worker=LatestDetection()
        try:
            if capture is None:
                from src.input.GameWindowCapturor import GameWindowCapturor
                capture=GameWindowCapturor(cfg)
            self.capture=capture
        except Exception:
            self.worker.close();raise
        self.threshold.valueChanged.connect(self.invalidate)
        self.pause.toggled.connect(self.set_paused)
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(80)
        self.finished.connect(self.cleanup)

    def invalidate(self,*_):
        self.generation+=1;self.source=None
        self.result.clear();self.result.setText('阈值已变更，等待新结果…')
        self.details.setText('旧阈值结果已清除，下一轮检测使用新阈值。')

    def set_paused(self,paused):
        self.pause.setText('继续检测' if paused else '暂停检测')
        self.invalidate()

    @staticmethod
    def display_image(label,bgr):
        rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)
        image=QImage(rgb.data,rgb.shape[1],rgb.shape[0],rgb.strides[0],QImage.Format_RGB888).copy()
        label.setPixmap(QPixmap.fromImage(image).scaled(label.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))

    def tick(self):
        if self.closed:return
        try:
            result=self.worker.poll()
            if result is not None:
                frame,mobs,threshold,source,generation,elapsed=result
                if generation==self.generation:
                    self.source=source;self.elapsed=elapsed;self.result_count=len(mobs)
                    canvas=frame.copy();lines=[]
                    for i,m in enumerate(mobs,1):
                        x,y=map(int,m['position']);w,h=map(int,m['size'])
                        cv2.rectangle(canvas,(x,y),(x+w,y+h),(0,255,0),2)
                        cv2.putText(canvas,f'M{i} {m["score"]:.3f}',(x,max(12,y-3)),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,255,0),1)
                        lines.append(f'M{i} {m["name"]}：{m["score"]:.3f}')
                    self.display_image(self.result,canvas)
                    self.details.setText('实时画面 ←　上方为识别对应帧\n'+('；'.join(lines[:24]) or '此帧没有匹配到怪物')+f'\n本次阈值 {threshold:.3f}')
            frame=self.capture.get_frame();stamp=self.capture.frame_time
            now=time.monotonic()
            if frame is None or now-stamp>1:
                self.status.setText('抓帧暂停或过期，请勿最小化游戏；不会检测旧画面。');return
            frame=client_frame(frame,self.cfg)
            self.display_image(self.live,frame)
            if not self.pause.isChecked() and self.worker.future is None and stamp!=self.last_stamp:
                cfg=copy.deepcopy(self.cfg)
                threshold=self.threshold.value()
                cfg['monster_detect']['effective_diff_thres']=threshold
                # Exclude bottom HUD, as runtime full-screen detection does below.
                height=cfg.get('ui_coords',{}).get('ui_y_start',frame.shape[0])
                snapshot=SimpleNamespace(img_frame=frame[:height].copy(),cfg=cfg,
                    monsters_info=self.templates,loc_player=(-10000,-10000))
                self.worker.submit(scan,snapshot,threshold,stamp,self.generation)
                self.last_stamp=stamp
            age='等待结果' if self.source is None else f'结果年龄 {max(0,now-self.source):.2f} 秒'
            self.status.setText(f'{"已暂停" if self.pause.isChecked() else "全屏检测中"} | {self.result_count} 只怪 | 检测耗时 {self.elapsed:.0f} ms | {age}')
        except Exception as exc:
            self.status.setText(f'检测失败：{exc}')

    def save(self):
        try:
            data=load_yaml(str(self.registry)) or {}
            data.setdefault('map_monster_thresholds',{})[self.map_name]=self.threshold.value()
            save_yaml(data,str(self.registry))
            QMessageBox.information(self,'已保存',f'「{self.map_name}」阈值已保存为 {self.threshold.value():.3f}，下次开始挂机生效。')
        except Exception as exc:QMessageBox.warning(self,'保存失败',str(exc))

    def cleanup(self,*_):
        if self.closed:return
        self.closed=True;self.timer.stop();self.worker.close();self.capture.stop()
