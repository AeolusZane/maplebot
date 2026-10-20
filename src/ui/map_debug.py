"""Read-only map telemetry viewer; never issues game input or edits geometry."""
import json
import time
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QRectF
from PySide6.QtGui import QColor,QPen,QBrush,QPixmap,QFont,QFontDatabase,QImage
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QCheckBox,
    QPushButton,QGraphicsView,QGraphicsScene,QTableWidget,QTableWidgetItem,QSplitter,QTabWidget)
from src.utils.paths import resource_path
from src.navigation.map_graph import platform_y,teleport_regions


class MapView(QGraphicsView):
    def __init__(self):
        super().__init__();self.setScene(QGraphicsScene(self))
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QColor('#15191f'));self.scale(3,3)

    def wheelEvent(self,event):
        factor=1.2 if event.angleDelta().y()>0 else 1/1.2
        if .5<=self.transform().m11()*factor<=15:self.scale(factor,factor)
        event.accept()


class MapDebug(QWidget):
    def __init__(self,bot_getter,map_getter,edit_callback=None):
        super().__init__();self.bot_getter=bot_getter;self.map_getter=map_getter
        font_path=Path('C:/Windows/Fonts/msyh.ttc')
        if font_path.exists():QFontDatabase.addApplicationFont(str(font_path))
        self.setFont(QFont('Microsoft YaHei',9))
        self.map_name=None;self.graph=None;self.pixmap=None;self.stamp=None;self.history=[]
        layout=QVBoxLayout(self);self.status=QLabel('等待地图数据');self.status.setWordWrap(True)
        layout.setSpacing(12)
        layout.addWidget(self.status);row=QHBoxLayout();row.setSpacing(18);row.setContentsMargins(0,0,0,2);layout.addLayout(row)
        if edit_callback:
            edit=QPushButton('编辑地图');edit.setToolTip('暂停运行并编辑当前地图');edit.setMinimumHeight(28);edit.clicked.connect(edit_callback);row.addWidget(edit)
        self.coords=QCheckBox('平台坐标');self.coords.setChecked(True)
        self.regions=QCheckBox('瞬移区域');self.trace=QCheckBox('最近轨迹');self.trace.setChecked(True)
        for check in (self.coords,self.regions,self.trace):
            row.addWidget(check);check.toggled.connect(lambda _:self.render())
        row.addSpacing(6)
        button=QPushButton('适应整图');button.setMinimumHeight(28);row.addWidget(button);row.addStretch()
        self.view=MapView();button.clicked.connect(lambda:self.view.fitInView(self.view.sceneRect(),Qt.KeepAspectRatio))
        self.table=QTableWidget(0,3);self.table.setHorizontalHeaderLabels(['平台','左端 (X,Y)','右端 (X,Y)'])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        side=QWidget();side_layout=QVBoxLayout(side);side_layout.setContentsMargins(0,0,0,0);side_layout.setSpacing(12)
        self.preview_status=QLabel('游戏画面 · 等待开始')
        self.preview=QLabel('等待游戏画面');self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(240,135);self.preview.setMaximumHeight(260)
        self.preview.setStyleSheet('background:#101010;color:#cccccc;')
        from PySide6.QtWidgets import QSizePolicy
        self.preview.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Expanding)
        side_layout.addWidget(self.preview_status);side_layout.addWidget(self.preview,1)
        from src.ui.experience_charts import ExperienceCharts
        self.experience_charts=ExperienceCharts(map_getter,compact=True)
        detail_tabs=QTabWidget();detail_tabs.addTab(self.table,'平台坐标');detail_tabs.addTab(self.experience_charts,'经验效率')
        side_layout.addWidget(detail_tabs,2)
        split=QSplitter();split.addWidget(self.view);split.addWidget(side)
        split.setStretchFactor(0,3);split.setStretchFactor(1,1);split.setSizes([850,360])
        layout.addWidget(split,1)
        layout.addWidget(QLabel('坐标与地图标注一致，X 向右、Y 向下。黄点：人物；橙线：当前平台；红叉：定位失效或数据过期；紫点：目标。滚轮缩放，拖动平移。'))
        self.snapshot=None;self.timer=QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(200)

    def refresh(self):
        if not self.isVisible():return
        bot=self.bot_getter();snapshot=getattr(bot,'_map_debug_snapshot',None)
        self.refresh_preview(bot)
        name=self.map_getter()
        changed=self.map_name!=name
        if changed:
            self.experience_charts.reload()
            self.map_name=name;self.history=[];self.snapshot=None;self.stamp=None
            folder=Path(resource_path(f'minimaps/{name}'))
            self.pixmap=QPixmap(str(folder/'map.png'))
            try:self.graph=json.loads((folder/'navigation.json').read_text(encoding='utf-8'))
            except (OSError,ValueError):self.graph=None
        if snapshot and snapshot['map']==name and snapshot['time']>getattr(self,'ignore_before',0):
            self.snapshot=snapshot;self.graph=snapshot['graph']
            if self.stamp!=snapshot['time']:
                self.stamp=snapshot['time']
                if snapshot['valid']:self.history=(self.history+[snapshot['position']])[-150:]
        self.render()
        if changed:self.view.fitInView(self.view.sceneRect(),Qt.KeepAspectRatio)

    def refresh_preview(self,bot):
        # Reuse the engine's latest frame; no additional capture or detection job.
        frame,stamp=getattr(self,'annotated_frame',(None,None))
        if frame is None or not getattr(frame,'size',0):
            self.preview.clear();self.preview.setText('等待游戏画面')
            self.preview_status.setText('游戏画面 · 等待开始');return
        if frame.ndim!=3 or frame.shape[2]!=3:return
        import numpy as np
        pixels=np.ascontiguousarray(frame)
        height,width=pixels.shape[:2]
        image=QImage(pixels.data,width,height,pixels.strides[0],QImage.Format_BGR888).copy()
        self.preview.setPixmap(QPixmap.fromImage(image).scaled(
            self.preview.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
        stale=stamp is None or time.monotonic()-stamp>1
        self.preview_status.setText('游戏画面 · '+('已暂停/画面过期' if stale else '实时')+'（含识别框）')

    def label(self,text,x,y,color='#ffffff'):
        item=self.view.scene().addText(text);item.setDefaultTextColor(QColor(color))
        font=QFont('Microsoft YaHei');font.setPixelSize(4);item.setFont(font);item.setPos(x,y)

    def render(self):
        scene=self.view.scene();scene.clear()
        if self.pixmap and not self.pixmap.isNull():
            scene.addPixmap(self.pixmap);scene.setSceneRect(QRectF(self.pixmap.rect()))
        g=self.graph;s=self.snapshot
        self.status.setVisible(not g or bool(s))
        if not g:
            self.status.setText('当前地图没有平台标注，请先在「检查并修正地图」中识别并保存。');self.table.setRowCount(0);return
        stale=not s or time.monotonic()-s['time']>1
        valid=s and s['valid'] and not stale
        self.table.setRowCount(len(g['platforms']))
        for row,p in enumerate(g['platforms']):
            y2=p.get('end_y',p['y']);current=s and s['platform']==p['id']
            color='#ff4444' if p.get('reset_point') else '#ffb347' if current else '#36e1a0'
            vertices=p.get('points',[(p['x1'],p['y']),(p['x2'],y2)])
            for a,b in zip(vertices,vertices[1:]):
                scene.addLine(*a,*b,QPen(QColor(color),1.2 if current else .6))
            text=p['id']
            if self.coords.isChecked():text+=f" ({p['x1']:g},{p['y']:g})→({p['x2']:g},{y2:g})"
            self.label(text,p['x1'],p['y']-6,color)
            for col,value in enumerate((p['id'],f"{p['x1']:g}, {p['y']:g}",f"{p['x2']:g}, {y2:g}")):
                item=QTableWidgetItem(value)
                if current:item.setBackground(QColor('#ffcf84'))
                self.table.setItem(row,col,item)
        for r in g['ropes']:scene.addLine(r['x'],r['y1'],r['x'],r['y2'],QPen(QColor('#4bbaff'),.7))
        if self.regions.isChecked():
            for edge in g['edges']:
                if not edge['enabled']:continue
                for region in teleport_regions(g,edge):
                    x0,y0,x1,y1=region['source'];scene.addRect(x0,y0,max(.3,x1-x0),y1-y0,QPen(QColor('#ee77ef'),.4))
        if self.trace.isChecked():
            for a,b in zip(self.history,self.history[1:]):scene.addLine(*a,*b,QPen(QColor('#e4d77a'),.35))
        if not s:self.status.clear();return
        for rank,hotspot in enumerate(s.get('hotspots',[]),1):
            p=next((p for p in g['platforms'] if p['id']==hotspot['platform']),None)
            if not p:continue
            hx=hotspot.get('x');hy=hotspot.get('y')
            if hx is None:hx=(p['x1']+p['x2'])/2
            if hy is None:hy=platform_y(p,hx)
            color=QColor(('#ff5555','#ff9c35','#ffe066')[rank-1])
            scene.addEllipse(hx-3,hy-3,6,6,QPen(color,1))
            self.label(f"#{rank} {hotspot['platform']} {hotspot['count']}只",hx+3,hy-10,color.name())
        x,y=s['position'];color=QColor('#ffe45c' if valid else '#ff5555')
        scene.addEllipse(x-1.8,y-1.8,3.6,3.6,QPen(color,.5),QBrush(color))
        scene.addLine(x-4,y,x+4,y,QPen(color,.5));scene.addLine(x,y-4,x,y+4,QPen(color,.5))
        self.label(f'人物 ({x:g},{y:g})',x+3,y-5,color.name())
        if not valid:scene.addLine(x-3,y-3,x+3,y+3,QPen(color,1))
        target=s.get('target')
        if target:
            tx,ty=target;scene.addEllipse(tx-2,ty-2,4,4,QPen(QColor('#ee77ef'),1))
            scene.addLine(x,y,tx,ty,QPen(QColor('#ee77ef'),.4,Qt.DashLine))
        age=max(0,time.monotonic()-s['time'])
        metric=lambda value: '—' if value is None else f'{value:.0f} ms'
        latency=('已暂停/数据过期' if stale else metric(s.get('latency_ms')))
        source=s.get('detection_source')
        detection_age='—' if source is None else f'{max(0,time.monotonic()-source)*1000:.0f} ms'
        self.status.setText(f"截图→决策延迟：实时 {latency} / 本次最高 {metric(s.get('latency_peak_ms'))} | "
            f"怪物检测耗时 {metric(s.get('detection_ms'))} / 最高 {metric(s.get('detection_peak_ms'))} | 怪物结果年龄 {detection_age}\n"
            f"全视野扫描：{s.get('survey_status','等待扫描')} | 距上次有效扫描 "
            f"{('—' if s.get('survey_time') is None else str(round(max(0,time.monotonic()-s['survey_time']),1))+' 秒')} | "
            f"下次扫描{'已暂停' if stale else '约 '+str(round(s.get('survey_due',0),1))+' 秒后'}\n"
            '最近全屏扫描前三：'+('；'.join(f"#{i} {h['platform']} {h['count']}只（{h['age']:.0f}秒前观测）" for i,h in enumerate(s.get('hotspots',[]),1)) or '暂无')+'\n'+
            '探索：'+s.get('exploration','')+' | 本轮未扫：'+('、'.join(p['id'] for p in g['platforms'] if p['id'] not in s.get('sweep_done',[])) or '已完成')+'\n'+
            f"锁定平台：{s.get('priority_target') or '无'} | 本次扫描怪物数量："+
            ('，'.join(f'{pid}: {count}' for pid,count in sorted(s.get('platform_mobs',{}).items(),key=lambda item:-item[1])) or '暂无有效结果')+'\n'+
            f"地图：{self.map_name} | 人物：({x:g}, {y:g}) | 当前平台：{s['platform'] or '未匹配'} | "
            f"{'已暂停/数据过期' if stale else '小地图定位有效' if valid else '小地图定位失效'} | 数据年龄 {age:.1f} 秒\n"
            f"当前原因：{s['status']}（持续 {s.get('reason_seconds',0):.1f} 秒） | 路径：{' → '.join(s['path']) or '无'} | 按键：{' '.join(s['command'])}\n"
            f"锁定故障：{s.get('fault') or '无'} | 执行连接：{s.get('transit') or '无'}")
