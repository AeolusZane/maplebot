"""Manual capture UI: inference is available only after recording stops."""
import copy
import json
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
    QMessageBox,QLineEdit,QSizePolicy,QFileDialog)
from src.utils.paths import APP_ROOT
from src.utils.manual_session import record_session, analyze_session, write_json
from src.ui.monster_test import MonsterTest


class ManualCapture(QDialog):
    progress = Signal(object,str)
    completed = Signal(str)

    def __init__(self,map_name,cfg,parent=None):
        super().__init__(parent)
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
        self.setFont(QFont('Microsoft YaHei', 9))
        self.cfg=copy.deepcopy(cfg);self.map_name=map_name
        self.folder=None;self.busy=False;self.stop_event=threading.Event()
        self.setWindowTitle(f'人工采集 · {map_name} · 10分钟')
        self.resize(1000,700)
        layout=QVBoxLayout(self)
        helptext=QLabel('采集期间仅抓屏：不识别怪物/人物，不发送自动按键。\n'
            '保存10 FPS原始录像＋每秒2张截图。录完点击“录后识别”，再生成人物框、小地图位置与怪物框。\n'
            '主界面F1/F2/F3暂挂。仅监听游戏配置键的按下/释放/持有和窗口焦点，不发送按键。\n'
            '经验请手填；跨级请填累计获得经验。技能成功与否需录后根据画面校验。')
        helptext.setWordWrap(True);layout.addWidget(helptext)
        row=QHBoxLayout();layout.addLayout(row)
        self.start=QPushButton('开始10分钟采集');row.addWidget(self.start)
        self.stop=QPushButton('停止');self.stop.setEnabled(False);row.addWidget(self.stop)
        self.analyze=QPushButton('录后识别');self.analyze.setEnabled(False);row.addWidget(self.analyze)
        self.open=QPushButton('打开记录文件夹');self.open.setEnabled(False);row.addWidget(self.open)
        self.load=QPushButton('选择已有采集');row.addWidget(self.load)
        self.review=QPushButton('技能画面核验');row.addWidget(self.review)
        self.status=QLabel('准备就绪。开始前请确保游戏窗口已打开，小地图展开。');layout.addWidget(self.status)
        self.preview=QLabel('原始画面预览');self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(640,360);self.preview.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Expanding)
        layout.addWidget(self.preview,1)
        row=QHBoxLayout();layout.addLayout(row)
        self.exp_start=QLineEdit();self.exp_start.setPlaceholderText('开始经验数字')
        self.exp_end=QLineEdit();self.exp_end.setPlaceholderText('结束经验数字（未升级时）')
        self.exp_gain=QLineEdit();self.exp_gain.setPlaceholderText('或填实际获得经验（跨级用）')
        for widget in (self.exp_start,self.exp_end,self.exp_gain):row.addWidget(widget)
        self.save_exp=QPushButton('保存经验收益');row.addWidget(self.save_exp)
        self.result=QLabel('收益按本次实际采集时长计算；请保持手动打怪与采集同步。');layout.addWidget(self.result)
        self.start.clicked.connect(self.begin)
        self.stop.clicked.connect(self.stop_event.set)
        self.analyze.clicked.connect(self.begin_analysis)
        self.open.clicked.connect(lambda:os.startfile(str(self.folder)))
        self.save_exp.clicked.connect(self.experience)
        self.load.clicked.connect(self.load_session)
        self.review.clicked.connect(self.review_skills)
        self.progress.connect(self.show_progress);self.completed.connect(self.finish)

    def set_busy(self,value):
        self.busy=value;self.start.setEnabled(not value)
        self.load.setEnabled(not value)
        self.review.setEnabled(not value)
        self.stop.setEnabled(value);self.analyze.setEnabled(not value and self.folder is not None)

    def review_skills(self):
        if not self.folder:return
        try:
            from src.ui.skill_review import SkillReview
            SkillReview(self.folder,self).exec()
        except Exception as exc:QMessageBox.warning(self,'画面核验',str(exc))

    def load_session(self):
        path=QFileDialog.getExistingDirectory(self,'选择人工采集会话',str(Path(APP_ROOT)/'sessions/manual'))
        if not path:return
        try:
            folder=Path(path)
            manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
            if manifest.get('mode')!='manual_capture' or not (folder/'frames.jsonl').exists():
                raise ValueError('请选择包含 manifest.json 和 frames.jsonl 的人工采集目录')
            self.folder=folder;self.open.setEnabled(True);self.analyze.setEnabled(True)
            self.exp_start.clear();self.exp_end.clear();self.exp_gain.clear()
            self.status.setText(f'已载入 {manifest["map_name"]}：{folder.name}')
            self.result.setText('可进行录后识别，或补录本次经验收益')
        except Exception as exc:QMessageBox.warning(self,'读取失败',str(exc))

    def begin(self):
        base=Path(APP_ROOT)/'sessions'/'manual'
        base.mkdir(parents=True,exist_ok=True)
        if shutil.disk_usage(base).free<3*1024**3:
            QMessageBox.warning(self,'空间不足','至少需要3GB空闲空间；低于1GB会自动停止。');return
        self.folder=base/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        self.stop_event.clear();self.set_busy(True);self.open.setEnabled(False)
        self.status.setText('正在启动只读抓屏…')
        self.result.setText('本次经验收益尚未保存')
        self.exp_end.clear();self.exp_gain.clear()
        def work():
            capture=None
            try:
                from src.input.GameWindowCapturor import GameWindowCapturor
                cfg=copy.deepcopy(self.cfg)
                cfg.setdefault('system',{})['fps_limit_window_capturor']=10
                capture=GameWindowCapturor(cfg)
                manifest=record_session(self.folder,cfg,self.map_name,capture,self.stop_event,self.progress.emit)
                message=f'采集结束：{manifest["duration_actual"]:.1f}秒，{manifest["screenshots"]}张截图。原因：{manifest["stop_reason"]}'
                if manifest.get('error'):message+='；'+manifest['error']
            except Exception as exc:message=f'采集失败：{exc}'
            finally:
                if capture is not None:
                    try:capture.stop()
                    except Exception as exc:message+=f'；抓屏停止异常：{exc}'
            self.completed.emit(message)
        self.worker=threading.Thread(target=work,daemon=True);self.worker.start()

    def begin_analysis(self):
        if not self.folder or not (self.folder/'frames.jsonl').exists():return
        self.stop_event.clear();self.set_busy(True)
        self.status.setText('正在加载素材进行录后识别…')
        def work():
            try:
                output=analyze_session(self.folder,self.stop_event,self.progress.emit)
                message=f'录后识别结束：{output}'
            except Exception as exc:message=f'录后识别失败（原始记录保留）：{exc}'
            self.completed.emit(message)
        self.worker=threading.Thread(target=work,daemon=True);self.worker.start()

    def show_progress(self,frame,message):
        self.status.setText(message)
        if frame is not None:MonsterTest.display_image(self.preview,frame)

    def finish(self,message):
        self.set_busy(False);self.status.setText(message)
        self.open.setEnabled(self.folder is not None and self.folder.exists())
        self.analyze.setEnabled(self.folder is not None and (self.folder/'frames.jsonl').exists())

    def experience(self):
        try:
            if self.busy or not self.folder:raise ValueError('请先完成采集')
            manifest=json.loads((self.folder/'manifest.json').read_text(encoding='utf-8'))
            def number(text):return int(text.replace(',','').replace('，','').strip())
            gain=number(self.exp_gain.text()) if self.exp_gain.text().strip() else number(self.exp_end.text())-number(self.exp_start.text())
            if gain<0:raise ValueError('跨级时请填写实际获得经验，不能直接相减')
            seconds=manifest['duration_actual']
            if seconds<=0:raise ValueError('采集时长无效')
            result=dict(map_name=manifest['map_name'],source='manual_entry',gain=gain,
                duration_seconds=seconds,exp_per_minute=gain*60/seconds,
                exp_per_10min=gain*600/seconds,start_text=self.exp_start.text(),end_text=self.exp_end.text())
            write_json(self.folder/'experience.json',result)
            self.result.setText(f'已保存：获得 {gain:,} 经验；每分钟 {result["exp_per_minute"]:,.0f}；折合10分钟 {result["exp_per_10min"]:,.0f}')
        except Exception as exc:QMessageBox.warning(self,'经验收益',str(exc))

    def reject(self):
        if self.busy:
            self.stop_event.set();self.status.setText('正在停止并保存，请完成后关闭窗口。');return
        super().reject()

    def closeEvent(self,event):
        if self.busy:
            self.stop_event.set();self.status.setText('正在停止并保存，请完成后关闭窗口。');event.ignore()
        else:event.accept()
