"""Low-frequency background OCR statistics; no game input."""
import json
import time
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import Qt,QTimer,QRect,QSettings,Signal
from PySide6.QtGui import QImage,QPixmap
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QDialog,QRubberBand,QScrollArea,QSplitter
from src.utils.experience_stats import ExperienceStats,ExperienceOCR

# Fixed bottom HUD at the supported 1366 x 768 game resolution.
DEFAULT_EXPERIENCE_ROI=[800/1366,728/768,190/1366,24/768]


class RegionPicker(QLabel):
    def __init__(self,pixmap,callback):
        super().__init__();self.setPixmap(pixmap);self.setFixedSize(pixmap.size())
        self.callback=callback;self.band=QRubberBand(QRubberBand.Rectangle,self);self.origin=None
    def mousePressEvent(self,event):
        self.origin=event.position().toPoint();self.band.setGeometry(QRect(self.origin,self.origin));self.band.show()
    def mouseMoveEvent(self,event):
        if self.origin is not None:self.band.setGeometry(QRect(self.origin,event.position().toPoint()).normalized())
    def mouseReleaseEvent(self,event):
        if self.origin is None:return
        rect=QRect(self.origin,event.position().toPoint()).normalized().intersected(self.rect());self.origin=None
        if rect.width()>15 and rect.height()>5:self.callback(rect)


class StatisticsTab(QWidget):
    history_changed=Signal()
    def __init__(self,bot_getter):
        super().__init__();self.bot_getter=bot_getter;self.stats=ExperienceStats()
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='experience-ocr');self.ocr=ExperienceOCR()
        self.future=None;self.session=None;self.started=None;self.elapsed=0;self.due=0;self.generation=0
        self.run_id=uuid.uuid4().hex;self.last_level=None;self.last_map=None
        from src.utils.experience_history import ExperienceHistory
        self.history=ExperienceHistory()
        self.settings=QSettings('MapleBot','ExperienceStats')
        try:self.roi=json.loads(self.settings.value('roi','null'))
        except (ValueError,TypeError):self.roi=None
        if not self.roi:self.roi=list(DEFAULT_EXPERIENCE_ROI)
        layout=QVBoxLayout(self);self.summary=QLabel('等待启动');layout.addWidget(self.summary)
        self.status=QLabel('开始后自动读取底部经验栏，无需框选。');self.status.setWordWrap(True);layout.addWidget(self.status)
        row=QHBoxLayout();layout.addLayout(row)
        pick=QPushButton('调整识别区域（可选）');pick.clicked.connect(self.pick);row.addWidget(pick)
        reset=QPushButton('恢复默认位置');reset.clicked.connect(self.reset_region);row.addWidget(reset)
        sample=QPushButton('立即采样');sample.clicked.connect(lambda:setattr(self,'due',0));row.addWidget(sample);row.addStretch()
        self.pick_region_button=pick;self.reset_region_button=reset;self.sample_now_button=sample
        self.preview=QLabel();layout.addWidget(self.preview)
        from src.ui.experience_charts import ExperienceCharts
        self.charts=ExperienceCharts(lambda:(getattr(self.bot_getter(),'cfg',None) or {}).get('bot',{}).get('map',''),history=self.history)
        self.data_splitter=QSplitter(Qt.Vertical)
        self.data_splitter.setChildrenCollapsible(False)
        self.data_splitter.setHandleWidth(9)
        self.data_splitter.setStyleSheet('QSplitter::handle:vertical { background: #d5dbe2; margin: 2px 0; } QSplitter::handle:vertical:hover { background: #8faecb; }')
        self.data_splitter.addWidget(self.charts)
        self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(['运行时间','当前经验','百分比','本次增加','状态','识别文字'])
        self.data_splitter.addWidget(self.table)
        layout.addWidget(self.data_splitter,1)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setMinimumHeight(100)
        self.data_splitter.setStretchFactor(0,2)
        self.data_splitter.setStretchFactor(1,1)
        self.data_splitter.setSizes([440,220])
        saved=self.settings.value('data_splitter_state')
        if saved is not None:self.data_splitter.restoreState(saved)
        self.data_splitter.handle(1).setToolTip('上下拖动，调整图表和数据表高度；位置自动保存')
        self.data_splitter.splitterMoved.connect(
            lambda *_:self.settings.setValue('data_splitter_state',self.data_splitter.saveState()))
        self.history_changed.connect(self.charts.reload)
        hint=QLabel('启动时取基准，之后每 3 分钟采样。每 1 / 10 分钟为有效采样区间的平均速率换算。\n升级、经验下降或识别异常的区间不推算，累计会标记为部分统计；停止后保留本次结果，再次开始重新统计。')
        hint.setWordWrap(True);layout.addWidget(hint)
        self.setProperty('samplingHelp',hint.text());hint.hide()
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(500)

    def test_reading(self,cfg,result_label,button):
        """One-shot passive recognition, independent of running statistics."""
        import copy
        if getattr(self,'test_future',None) is not None:return
        result_label.setText('正在读取游戏经验…');result_label.show();button.setEnabled(False)
        config=copy.deepcopy(cfg);roi=list(self.roi)
        def read():
            from src.input.GameWindowCapturor import GameWindowCapturor
            from src.utils.common import crop_frame_to_client,resolve_title_bar_height
            cap=None
            try:
                cap=GameWindowCapturor(config);raw=None
                for _ in range(30):
                    raw=cap.get_frame()
                    if raw is not None:break
                    time.sleep(.1)
                if raw is None:raise RuntimeError('未取得游戏画面，请确认游戏已打开且未最小化')
                h,w=config['game_window']['size']
                frame,msg=crop_frame_to_client(raw,(int(h),int(w)),resolve_title_bar_height(config,tag='经验试读'),tag='经验试读')
                if frame is None:raise RuntimeError(msg)
                h,w=frame.shape[:2];x,y,rw,rh=roi
                crop=frame[max(0,int(y*h)):min(h,int((y+rh)*h)),max(0,int(x*w)):min(w,int((x+rw)*w)),:3].copy()
                level=frame[int(728*h/768):h,:int(105*w/1366),:3].copy()
                return self.ocr.read_sample(crop,level)
            finally:
                if cap is not None:cap.stop()
        self.test_future=self.pool.submit(read)
        timer=QTimer(self);timer.setInterval(100)
        def finish():
            if not self.test_future.done():return
            try:
                value,percent,text,level=self.test_future.result()
                result_label.setText(f'经验：{value:,}  ·  {percent:g}%  ·  '+(f'Lv.{level}' if level else '等级未识别')+'\n识别文字：'+text)
            except Exception as exc:result_label.setText('经验识别失败：'+str(exc))
            finally:
                self.test_future=None;button.setEnabled(True);timer.stop();timer.deleteLater()
        timer.timeout.connect(finish);timer.start()

    def reset_region(self):
        self.roi=list(DEFAULT_EXPERIENCE_ROI)
        self.settings.remove('roi');self.generation+=1;self.due=0
        self.stats=ExperienceStats();self.table.setRowCount(0)
        self.status.setText('已恢复底部固定经验栏，将自动采样')

    def pick(self):
        bot=self.bot_getter();frame=getattr(bot,'img_frame',None)
        if frame is None:self.status.setText('请先启动，让程序取得游戏画面。');return
        h,w=frame.shape[:2];rgb=frame[:,:,:3][:,:,::-1].copy()
        pix=QPixmap.fromImage(QImage(rgb.data,w,h,rgb.strides[0],QImage.Format_RGB888).copy())
        dialog=QDialog(self);dialog.setWindowTitle('拖框选中经验数字及百分比，松开确认');layout=QVBoxLayout(dialog)
        def chosen(rect):
            self.roi=[rect.x()/w,rect.y()/h,rect.width()/w,rect.height()/h]
            self.settings.setValue('roi',json.dumps(self.roi));self.generation+=1
            self.stats=ExperienceStats();self.table.setRowCount(0);self.due=0
            self.status.setText('经验区域已保存，将重新建立统计基准');dialog.accept()
        scroll=QScrollArea();scroll.setWidget(RegionPicker(pix,chosen));layout.addWidget(scroll)
        dialog.resize(1100,750);dialog.exec()

    def tick(self):
        bot=self.bot_getter();thread=getattr(bot,'thread_auto_bot',None)
        running=thread is not None and thread.is_alive() and not getattr(bot,'is_terminated',False)
        now=time.monotonic()
        if running and thread is not self.session:
            self.run_id=uuid.uuid4().hex;self.last_level=None;self.last_map=None
            self.session=thread;self.started=now;self.elapsed=0;self.due=0;self.generation+=1
            self.stats=ExperienceStats();self.table.setRowCount(0)
            self.status.setText('等待起始经验采样' if self.roi else '请框选经验数字及百分比')
        if running:self.elapsed=now-self.started
        if self.future and self.future.done():
            future,generation,sampled=self.future,self.job_generation,self.job_elapsed;self.future=None
            try:
                value,percent,text,level=future.result()
                if generation==self.generation:
                    previous=self.stats.previous
                    same_group=self.last_level==level and self.last_map==self.job_map
                    if previous and not same_group:
                        self.stats.previous=None;self.stats.gaps=True
                    self.stats.add(sampled,value,percent,text);self.render_rows()
                    elapsed,experience,pct,gain,note,_=self.stats.rows[-1]
                    duration=sampled-previous[0] if previous and same_group and gain is not None else 0
                    self.last_level=level;self.last_map=self.job_map
                    self.history.append(self.run_id,self.job_wall_time,self.job_map,level,elapsed,experience,pct,gain,duration,note)
                    self.history_changed.emit()
                    self.status.setText(f'采样完成 · {self.job_map} · '+(f'Lv.{level}' if level else '等级未识别')+'：'+text)
                    from src.utils.logger import logger
                    logger.info(f'[经验采样] 成功：{text}；运行 {sampled:.1f} 秒')
            except Exception as exc:
                if generation==self.generation:
                    self.status.setText('本次未计入，10 秒后重试：'+str(exc))
                    self.due=now+10
                    from src.utils.logger import logger
                    logger.warning(f'[经验采样] 失败：{exc}；10 秒后补采')
                    try:
                        import cv2
                        folder=Path('debug');folder.mkdir(exist_ok=True)
                        cv2.imwrite(str(folder/'experience_last_failed.png'),self.job_crop)
                    except Exception as save_error:logger.warning(f'[经验采样] 诊断图保存失败：{save_error}')
        if running and self.roi and self.future is None and now>=self.due:
            frame=getattr(bot,'img_frame',None)
            if frame is not None:
                h,w=frame.shape[:2];x,y,rw,rh=self.roi
                crop=frame[max(0,int(y*h)):min(h,int((y+rh)*h)),max(0,int(x*w)):min(w,int((x+rw)*w)),:3].copy()
                if crop.size:
                    rgb=crop[:,:,::-1].copy();ch,cw=rgb.shape[:2]
                    self.preview.setPixmap(QPixmap.fromImage(QImage(rgb.data,cw,ch,rgb.strides[0],QImage.Format_RGB888).copy()).scaledToHeight(60))
                    self.job_generation=self.generation;self.job_elapsed=self.elapsed
                    self.job_map=bot.cfg.get('bot',{}).get('map','未命名地图');self.job_wall_time=time.time()
                    self.job_crop=crop
                    level_crop=frame[int(728*h/768):h,:int(105*w/1366),:3].copy()
                    self.future=self.pool.submit(self.ocr.read_sample,crop,level_crop);self.due=now+180
                    self.status.setText('后台识别经验中…')
        rate=self.stats.per_minute
        rates='等待两次有效采样' if rate is None else f'平均每 1 分钟 {rate:,.0f}  |  每 10 分钟 {rate*10:,.0f}'
        seconds=int(self.elapsed);duration=f'{seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}'
        suffix='（部分统计，有未计入区间）' if self.stats.gaps else ''
        total=f'{self.stats.total:,}' if self.stats.covered else '等待采样'
        self.summary.setText(f'本次运行 {duration}  |  累计经验 {total}{suffix}\n{rates}  |  '+(f'下次采样 {max(0,int(self.due-now))} 秒' if running and self.roi else '未运行或尚未框选'))

    def render_rows(self):
        self.table.setRowCount(len(self.stats.rows))
        for i,(elapsed,value,percent,gain,note,text) in enumerate(self.stats.rows):
            for j,item in enumerate((f'{int(elapsed)//60}:{int(elapsed)%60:02}',f'{value:,}',f'{percent:g}%', '—' if gain is None else f'{gain:,}',note,text)):
                self.table.setItem(i,j,QTableWidgetItem(item))
        self.table.resizeColumnsToContents()
