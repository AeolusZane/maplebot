"""Simple manual walk-to-map recorder with read-only game capture."""
import json
import time
from pathlib import Path
import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap, QFont, QFontDatabase
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QListWidget, QMessageBox, QMenu, QSizePolicy, QApplication, QGraphicsView, QGraphicsScene, QTableWidget, QTableWidgetItem, QDialogButtonBox)
from src.navigation.map_graph import read_image, new_graph, save_graph, platform_y, shortest_path, validate
from src.navigation.walk_mapping import endpoint_segment, build_connections
from src.utils.common import get_minimap_loc_size, get_player_location_on_minimap, find_pattern_sqdiff
from src.utils.mapping_capture import client_frame, minimap_rect, locate_name
from src.utils.paths import APP_ROOT


class ClickMap(QGraphicsView):
    clicked=Signal(float,float,bool)
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self));self.picture=None
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(Qt.black)
        self.press=None

    def set_map(self,pix):
        first=self.picture is None
        if first:self.picture=self.scene().addPixmap(pix)
        else:self.picture.setPixmap(pix)
        self.setSceneRect(self.picture.boundingRect())
        if first:self.fitInView(self.sceneRect(),Qt.KeepAspectRatio)

    def wheelEvent(self,event):
        factor=1.2 if event.angleDelta().y()>0 else 1/1.2
        scale=self.transform().m11()*factor
        if .2<=scale<=30:self.scale(factor,factor)
        event.accept()

    def mousePressEvent(self,event):
        self.press=event.position()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self,event):
        if self.picture is not None and self.press is not None and (event.position()-self.press).manhattanLength()<4:
            point=self.mapToScene(event.position().toPoint());rect=self.sceneRect()
            if rect.contains(point):self.clicked.emit(point.x()/rect.width(),point.y()/rect.height(),event.button()==Qt.RightButton)
        self.press=None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self,event):
        self.fitInView(self.sceneRect(),Qt.KeepAspectRatio);event.accept()


class WalkMapRecorder(QDialog):
    def __init__(self, folder, cfg, parent=None, capture=None):
        super().__init__(parent)
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
        self.setFont(QFont('Microsoft YaHei', 9))
        self.setWindowTitle('录制地图 · 实走平台和绳索')
        self.resize(1180, 780)
        self.folder = Path(folder)
        self.image = read_image(self.folder/'map.png')
        self.graph = new_graph(self.image)
        path = self.folder/'navigation.json'
        if path.exists():
            self.graph = json.loads(path.read_text(encoding='utf-8'))
        self.cfg = cfg
        self.confirmed_graph = None
        self.active = None
        self.polyline=False
        self.points = []
        self.position = None
        self.position_time = 0
        self.live_canvas = self.image.copy()
        self.live_minimap = None
        self.game_frame = None
        self.name_status = '名字：等待识别'
        name_path=Path(APP_ROOT)/'nametag'/f"{cfg.get('nametag',{}).get('name','')}.png"
        self.name_template=read_image(name_path) if name_path.is_file() else None
        self.last_frame = None
        self.dirty = False
        layout = QHBoxLayout(self)
        views = QVBoxLayout()
        layout.addLayout(views, 1)
        self.game_title = QLabel('游戏画面 · 等待抓帧（无需启动挂机）')
        views.addWidget(self.game_title)
        self.game_preview = QLabel('等待游戏画面')
        self.game_preview.setMinimumSize(480,270)
        self.game_preview.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Expanding)
        self.game_preview.setAlignment(Qt.AlignCenter)
        self.game_preview.setStyleSheet('background:#111;color:white')
        views.addWidget(self.game_preview,3)
        self.live_title = QLabel('游戏小地图 · 等待实时画面')
        views.addWidget(self.live_title)
        self.live_preview = ClickMap()
        self.live_preview.setAlignment(Qt.AlignCenter)
        self.live_preview.setMinimumSize(240, 70)
        self.live_preview.setMaximumHeight(110)
        self.live_preview.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Expanding)
        views.addWidget(self.live_preview)
        views.addWidget(QLabel('坐标与路径：红点=当前位置　黄线=正在录制　绿线=平台　蓝线=绳索　白线=选中项'))
        self.preview = ClickMap()
        self.preview.clicked.connect(self.click_point)
        self.preview.setMinimumSize(420, 160)
        self.preview.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Expanding)
        self.preview.setAlignment(Qt.AlignCenter)
        views.addWidget(self.preview, 1)
        side = QVBoxLayout()
        layout.addLayout(side)
        tip = QLabel('站在一端按 F6，转折处按 F7，另一端按 F8。\n黄色线实时连接起点和当前位置。\n绳索同样只需定位两端。\n起伏地面可以录成同一条折线平台。')
        side.addWidget(tip)
        self.items = QListWidget()
        self.items.setContextMenuPolicy(Qt.CustomContextMenu)
        self.items.customContextMenuRequested.connect(self.menu)
        self.items.currentItemChanged.connect(self.selection_changed)
        side.addWidget(self.items, 1)
        self.platform_button = QPushButton('新增平台')
        self.rope_button = QPushButton('新增绳索')
        self.platform_button.clicked.connect(lambda: self.record_hotkey(0x75))
        self.rope_button.clicked.connect(lambda: self.record_hotkey(0x78))
        side.addWidget(self.platform_button)
        side.addWidget(self.rope_button)
        self.poly_button=QPushButton('点选折线平台（新增／修改选中平台）')
        self.poly_button.clicked.connect(lambda: self.record_hotkey(0x77))
        self.point_button=QPushButton("F7 折线点")
        self.point_button.clicked.connect(lambda: self.record_hotkey(0x76))
        side.addWidget(self.point_button)
        side.addWidget(self.poly_button)
        self.poly_cancel=QPushButton('取消折线修改');self.poly_cancel.setEnabled(False)
        self.poly_cancel.clicked.connect(self.cancel_polyline);side.addWidget(self.poly_cancel)
        side.addWidget(QLabel('折线模式：在下方坐标图依次左键点转折点，\n右键撤销最后一点；再点按钮确认。\n高度对照红色人物标记，不是画面里的脚底。'))
        self.redo_button = QPushButton('重新录制选中项')
        self.redo_button.setEnabled(False)
        self.redo_button.clicked.connect(self.redo_selected)
        side.addWidget(self.redo_button)
        self.delete_button=QPushButton('删除选中平台／绳索')
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_selected)
        side.addWidget(self.delete_button)
        reset=QPushButton('选中平台：设为／取消复位点');reset.clicked.connect(self.toggle_reset_point);side.addWidget(reset)
        geometry=QPushButton('调整选中平台／绳索坐标');geometry.clicked.connect(self.adjust_geometry);side.addWidget(geometry)
        connections=QPushButton('检查平台连接');connections.clicked.connect(self.check_connections);side.addWidget(connections)
        side.addWidget(QLabel('坐标图：滚轮缩放，拖动平移，双击适应窗口。'))
        self.key_feedback=QLabel('按键记录：等待 F6 起点')
        self.key_feedback.setWordWrap(True);self.key_feedback.setMaximumWidth(310)
        side.addWidget(self.key_feedback)
        self.status = QLabel('选择新增；录完后再次点击同一按钮结束并确认。\n选择已有平台或绳索可重新录制。')
        self.status.setWordWrap(True)
        self.status.setMaximumWidth(310)
        side.addWidget(self.status)
        side.addWidget(QLabel('瞬移连接按当前技能范围自动生成。'))
        self.draft = QPushButton('保存草稿')
        self.finish = QPushButton('完成建图并启用导航')
        self.draft.clicked.connect(lambda: self.save(False))
        self.finish.clicked.connect(lambda: self.save(True))
        side.addWidget(self.draft)
        side.addWidget(self.finish)
        side.addWidget(QLabel('游戏内快捷键：F6 起点 → F7 折线点（可多次）→ F8 终点\nF9 绳索：按一次起点，再按一次终点\n右键坐标图撤销最后一点；选中平台后 F6 可重录。'))
        self.sync_record_buttons()
        self.refresh_list()
        if capture is None:
            from src.input.GameWindowCapturor import GameWindowCapturor
            capture = GameWindowCapturor(cfg)
        self.capture = capture
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(100)
        self.finished.connect(self.cleanup)
        self.hotkey_timer=QTimer(self)
        self.hotkey_timer.timeout.connect(self.poll_hotkeys)
        self._held_keys=set()
        import ctypes
        self._key_down=lambda key:bool(ctypes.windll.user32.GetAsyncKeyState(key)&0x8000)
        self._held_keys={key for key in range(0x75,0x79) if self._key_down(key)}
        self.hotkey_timer.start(20)

    def poll_hotkeys(self):
        down={key for key in range(0x75,0x79) if self._key_down(key)}
        pressed=down-self._held_keys;self._held_keys=down
        if not self.isVisible() or QApplication.activeModalWidget() not in (None,self):return
        # Process one transition per tick; an unrelated held key never repeats.
        if pressed:self.record_hotkey(min(pressed))

    def sync_record_buttons(self):
        self.platform_button.setText('F6 起点')
        self.point_button.setText('F7 折线点')
        self.poly_button.setText('F8 终点')
        self.rope_button.setText('F9 绳索终点' if self.active and not self.polyline else 'F9 绳索起点')
        self.platform_button.setEnabled(not self.active)
        self.point_button.setEnabled(self.polyline)
        self.poly_button.setEnabled(self.polyline)
        self.rope_button.setEnabled(not self.active or not self.polyline)

    def record_hotkey(self,key):
        if self.position is None or time.monotonic()-self.position_time>.25:
            self.key_feedback.setText('未记录：人物定位未更新，请等待红点恢复后重按。');return
        if key==0x75 and not self.active:
            self.toggle_polyline()
            self.points=[tuple(self.position)]
            self.status.setText(f'起点已记录 {self.position}；转折处按 F7，终点按 F8。')
        elif key in (0x76,0x77) and self.polyline:
            point=tuple(self.position)
            if self.points and point!=self.points[-1]:
                if not self.append_point(point):return
            self.status.setText(f'已记录 {len(self.points)} 个点，最新坐标 {point}；终点按 F8。')
            if key==0x77:self.toggle_polyline()
        elif key==0x78 and not self.polyline:
            self.toggle('ropes')
        else:
            self.status.setText('请先按 F6 记录平台起点，或 F9 记录绳索。')
        self.key_feedback.setText(self.status.text())
        self.sync_record_buttons();self.draw()

    def append_point(self,point):
        if self.points:
            delta=point[0]-self.points[-1][0]
            direction=self.points[-1][0]-self.points[0][0]
            if delta==0 or (direction and delta*direction<0):
                self.key_feedback.setText('未记录：请沿同一方向继续走；同一横坐标不能记录两个高度。右键可撤销。')
                return False
        self.points.append(point)
        self.key_feedback.setText(f'已记录第 {len(self.points)} 点：{point}')
        return True

    def cleanup(self, *_):
        if hasattr(self,'hotkey_timer'):self.hotkey_timer.stop()
        self.timer.stop()
        if self.capture is not None:
            self.capture.stop()
            self.capture = None

    def refresh_list(self):
        self.items.clear()
        for kind, label in [('platforms', '平台'), ('ropes', '绳索')]:
            for obj in self.graph[kind]:
                coords = (f"({obj['x1']}, {obj['y']}) → ({obj['x2']}, {obj.get('end_y',obj['y'])})"
                          if kind == 'platforms' else f"x={obj['x']}，y={obj['y1']} → {obj['y2']}")
                self.items.addItem(f"{label}{obj['id'][1:]}　"+("[复位点]" if obj.get("reset_point") else "✓")+f"\n{coords}")
                self.items.item(self.items.count()-1).setData(Qt.UserRole, (kind, obj['id']))

    def selection_changed(self, *_):
        item = self.items.currentItem()
        self.redo_button.setEnabled(item is not None and not self.active)
        self.delete_button.setEnabled(item is not None and not self.active)
        self.draw()

    def delete_selected(self):
        item=self.items.currentItem()
        if item is None or self.active:return
        kind,identity=item.data(Qt.UserRole)
        self.graph[kind]=[obj for obj in self.graph[kind] if obj['id']!=identity]
        build_connections(self.graph)
        self.dirty=True
        self.refresh_list();self.draw()
        self.status.setText(f'已删除 {identity}，连接已更新；点击保存草稿或完成建图保存修改。')

    def toggle_reset_point(self):
        item=self.items.currentItem()
        if not item or self.active:return
        kind,identity=item.data(Qt.UserRole)
        if kind!='platforms':return
        p=next(p for p in self.graph[kind] if p['id']==identity)
        p['reset_point']=not p.get('reset_point',False)
        self.dirty=True;self.refresh_list();self.draw()
        self.status.setText(f'{identity} 已更新：红色复位点不参与巡逻；传入后优先离开。出口缺失只提示，允许保存。')

    def check_connections(self):
        if self.active:
            self.status.setText('请先完成当前录制，再检查连接。');return
        build_connections(self.graph)
        dialog=QDialog(self);dialog.setWindowTitle('平台连接检查与修复');dialog.resize(650,450)
        layout=QVBoxLayout(dialog)
        layout.addWidget(QLabel('选择问题后点「调整坐标」。缺少实际地面时请返回补录平台；不要凭空拉长绳索。'))
        listing=QListWidget();layout.addWidget(listing)
        def row(text,kind=None,identity=None):
            listing.addItem(text);listing.item(listing.count()-1).setData(Qt.UserRole,(kind,identity))
        def refresh():
            listing.clear()
            for r in self.graph['ropes']:
                for label,key in [('上端','y1'),('下端','y2')]:
                    if not any(p['x1']<=r['x']<=p['x2'] and abs(platform_y(p,r['x'])-r[key])<=4 for p in self.graph['platforms']):
                        row(f"{r['id']} {label} ({r['x']}, {r[key]}) 无衔接平台：检查绳索坐标或补录地面",'ropes',r['id'])
            for a in self.graph['platforms']:
                missing=[b['id'] for b in self.graph['platforms'] if shortest_path(self.graph,a['id'],b['id']) is None]
                if missing:row(f"{a['id']} 无法到达：{', '.join(missing)}；检查平台端点及中间地面",'platforms',a['id'])
            for e in self.graph['edges']:
                if e['enabled']:row(f"已连接：{e['src']} → {e['dst']}（{e['kind']}）")
            if not listing.count():row('暂无连接，请先录制平台。')
        def edit():
            item=listing.currentItem()
            if not item:return
            kind,identity=item.data(Qt.UserRole)
            if not kind:return
            self.adjust_geometry(kind,identity);refresh();self.draw()
        button=QPushButton('调整所选问题的坐标');button.clicked.connect(edit);layout.addWidget(button)
        refresh();dialog.exec()

    def adjust_geometry(self,kind=None,identity=None):
        if self.active:return
        if not isinstance(kind,str):
            item=self.items.currentItem()
            if not item:
                self.status.setText('请先选中一个平台或绳索。');return
            kind,identity=item.data(Qt.UserRole)
        obj=next(p for p in self.graph[kind] if p['id']==identity)
        points=(obj.get('points',[[obj['x1'],obj['y']],[obj['x2'],obj.get('end_y',obj['y'])]])
                if kind=='platforms' else [[obj['x'],obj['y1']],[obj['x'],obj['y2']]])
        dialog=QDialog(self);dialog.setWindowTitle(f'调整 {identity} 坐标');layout=QVBoxLayout(dialog)
        layout.addWidget(QLabel('按小地图人物标记坐标填写；平台每行一个转折点，绳索两行的 X 必须一致。'))
        table=QTableWidget(len(points),2);table.setHorizontalHeaderLabels(['X','Y']);layout.addWidget(table)
        for i,p in enumerate(points):
            for j,v in enumerate(p):table.setItem(i,j,QTableWidgetItem(str(v)))
        if kind=='platforms':
            add=QPushButton('添加转折点');add.clicked.connect(lambda:table.insertRow(table.rowCount()));layout.addWidget(add)
            remove=QPushButton('删除选中转折点');remove.clicked.connect(lambda:table.removeRow(table.currentRow()) if table.currentRow()>=0 else None);layout.addWidget(remove)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);layout.addWidget(buttons)
        def apply():
            import copy
            try:
                pts=[[float(table.item(i,j).text()) for j in range(2)] for i in range(table.rowCount())]
                if len(pts)<2 or not np.isfinite(pts).all():raise ValueError('至少需要两个有效坐标点')
                edited=dict(obj)
                if kind=='platforms':
                    pts.sort();edited.update(x1=pts[0][0],y=pts[0][1],x2=pts[-1][0],end_y=pts[-1][1],points=pts)
                    if any(a[0]>=b[0] for a,b in zip(pts,pts[1:])):raise ValueError('平台转折点 X 不能重复')
                else:
                    if pts[0][0]!=pts[1][0]:raise ValueError('绳索两个端点 X 必须相同')
                    edited.update(x=pts[0][0],y1=min(p[1] for p in pts),y2=max(p[1] for p in pts))
                candidate=copy.deepcopy(self.graph)
                candidate[kind]=[edited if p['id']==identity else p for p in candidate[kind]]
                build_connections(candidate);errors=validate(candidate,self.image,reviewed=False)
                if errors:raise ValueError('\n'.join(errors))
                self.graph=candidate;self.dirty=True;self.refresh_list();self.draw();dialog.accept()
            except (ValueError,AttributeError) as error:QMessageBox.warning(dialog,'坐标无效',str(error))
        buttons.accepted.connect(apply);buttons.rejected.connect(dialog.reject);dialog.exec()

    def click_point(self,x,y,undo):
        if not self.polyline:return
        if undo:
            if self.points:self.points.pop()
        else:
            point=(min(self.image.shape[1]-1,round(x*self.image.shape[1])),
                   min(self.image.shape[0]-1,round(y*self.image.shape[0])))
            if not self.append_point(point):return
        self.status.setText(f'已点选 {len(self.points)} 个转折点；右键撤销，按 F8 记录终点并保存本项。')
        self.draw()

    def cancel_polyline(self):
        self.polyline=False;self.active=None;self.points=[]
        self.poly_button.setText('点选折线平台（新增／修改选中平台）')
        self.poly_cancel.setEnabled(False)
        for button in (self.platform_button,self.rope_button,self.draft,self.finish):button.setEnabled(True)
        self.items.setEnabled(True)
        self.selection_changed();self.sync_record_buttons()

    def toggle_polyline(self):
        if self.polyline:
            if len(self.points)<2:
                self.status.setText('至少点选两个点，按沿同一方向的顺序。');return
            ordered=sorted(self.points,key=lambda p:p[0])
            a,b=ordered[0],ordered[-1];identity=self.active[1]
            obj=dict(id=identity,x1=a[0],x2=b[0],y=a[1],end_y=b[1],
                     points=[list(p) for p in ordered],source='manual_polyline')
            obj['reset_point']=next((p.get('reset_point',False) for p in self.graph['platforms'] if p['id']==identity),False)
            self.graph['platforms']=[p for p in self.graph['platforms'] if p['id']!=identity]+[obj]
            self.dirty=True;build_connections(self.graph)
            self.cancel_polyline();self.refresh_list();self.draw();return
        if self.active:
            self.status.setText('请先完成或取消当前端点录制。');return
        item=self.items.currentItem();selected=item.data(Qt.UserRole) if item else None
        identity=selected[1] if selected and selected[0]=='platforms' else 'P'+str(max([int(p['id'][1:]) for p in self.graph['platforms']]+[0])+1)
        self.active=('platforms',identity);self.polyline=True;self.points=[]
        self.poly_button.setText('确认折线平台');self.poly_cancel.setEnabled(True)
        for button in (self.platform_button,self.rope_button,self.draft,self.finish,self.redo_button):button.setEnabled(False)
        self.items.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.status.setText(f'正在重画 {identity}：在下方坐标图沿同一方向点击起点、坡顶、坡脚和终点。确认前保留旧平台。')
        self.draw()

    def redo_selected(self):
        item = self.items.currentItem()
        if item is not None and not self.active:
            kind,identity=item.data(Qt.UserRole)
            if kind=='platforms':self.record_hotkey(0x75)
            else:self.toggle(kind,identity)
            self.sync_record_buttons()

    def toggle(self, kind, identity=None):
        if self.polyline:return
        if self.position is None or time.monotonic()-self.position_time > .5:
            QMessageBox.information(self,'等待有效定位','当前小地图定位无效或已过期，请等待红点和坐标出现后再点击。')
            return
        if self.active:
            active_kind, identity = self.active
            try:
                obj = endpoint_segment(self.points[0], self.position, active_kind, identity)
            except ValueError as exc:
                QMessageBox.information(self, '暂不能确认', str(exc))
                return
            self.graph[active_kind] = [p for p in self.graph[active_kind] if p['id'] != identity] + [obj]
            self.active = None
            self.points = []
            self.dirty = True
            build_connections(self.graph)
            self.refresh_list()
        else:
            if identity is None:
                number = max([int(p['id'][1:]) for p in self.graph[kind]]+[0])+1
                identity = ('P' if kind == 'platforms' else 'R')+str(number)
            self.active = (kind, identity)
            self.points = [tuple(self.position)]
        self.platform_button.setEnabled(not self.active or kind == 'platforms')
        self.rope_button.setEnabled(not self.active or kind == 'ropes')
        self.platform_button.setText('确认平台终点' if self.active and kind == 'platforms' else '新增平台')
        self.rope_button.setText('确认绳索终点' if self.active and kind == 'ropes' else '新增绳索')
        self.draft.setEnabled(not self.active)
        self.finish.setEnabled(not self.active)
        self.redo_button.setEnabled(not self.active and self.items.currentItem() is not None)
        self.delete_button.setEnabled(not self.active and self.items.currentItem() is not None)
        self.draw()

    def menu(self, pos):
        if self.polyline:return
        item = self.items.itemAt(pos)
        menu = QMenu(self)
        if self.active:
            cancel = menu.addAction('取消本次录制')
            if menu.exec(self.items.mapToGlobal(pos)) == cancel:
                self.active = None
                self.points = []
                self.platform_button.setEnabled(True); self.rope_button.setEnabled(True)
                self.platform_button.setText('新增平台'); self.rope_button.setText('新增绳索')
                self.draft.setEnabled(True); self.finish.setEnabled(True)
                self.items.setEnabled(True)
                self.redo_button.setEnabled(self.items.currentItem() is not None)
            return
        if not item:
            return
        redo = menu.addAction('重录'); delete = menu.addAction('删除')
        choice = menu.exec(self.items.mapToGlobal(pos))
        kind, identity = item.data(Qt.UserRole)
        if choice == redo:
            self.items.setCurrentItem(item)
            self.redo_selected()
        elif choice == delete:
            self.graph[kind] = [p for p in self.graph[kind] if p['id'] != identity]
            build_connections(self.graph)
            self.dirty = True
            self.refresh_list()

    def tick(self):
        self.position = None
        try:
            frame = self.capture.get_frame()
            stamp = self.capture.frame_time
            if frame is None or stamp == self.last_frame or time.monotonic()-stamp > 1:
                self.status.setText('等待新的游戏画面；当前未采样。')
                self.live_title.setText('游戏小地图 · 画面未更新，未采样')
                self.game_title.setText('游戏画面 · 等待新帧，请勿最小化游戏')
                self.draw()
                return
            self.last_frame = stamp
            frame = client_frame(frame,self.cfg)
            self.game_frame = frame.copy()
            name_rect, name_score = locate_name(frame,self.name_template,self.cfg)
            self.name_status = '名字：未匹配' if self.name_template is not None else '名字：未配置模板'
            if name_rect:
                nx,ny,nw,nh=name_rect
                cv2.rectangle(self.game_frame,(nx,ny),(nx+nw,ny+nh),(0,255,0),2)
                center=(nx+nw//2,ny-self.cfg.get('nametag',{}).get('offset',[0,30])[1])
                cv2.drawMarker(self.game_frame,center,(0,255,0),cv2.MARKER_CROSS,20,2)
                self.name_status=f'名字：已识别，人物中心 {center}'
            self.game_title.setText(f'游戏画面 · 实时 {time.strftime("%H:%M:%S")} · {self.name_status}')
            # Display video even when minimap matching fails below.
            self.show_image(self.game_preview,self.game_frame)
            rect = minimap_rect(frame)
            x, y, w, h = rect
            mini = frame[y+1:y+h-1, x+1:x+w-1]
            cv2.rectangle(self.game_frame,(x,y),(x+w,y+h),(255,200,0),2)
            self.live_minimap = mini.copy()
            self.live_title.setText(f'游戏小地图 · 实时更新 {time.strftime("%H:%M:%S")}')
            if (not self.graph['platforms'] and not self.graph['ropes'] and
                (self.image.shape[1]/self.image.shape[0]>12 or self.image.shape[0]<mini.shape[0])):
                self.repair_empty_map(mini)
            if mini.shape[0] > self.image.shape[0] or mini.shape[1] > self.image.shape[1]:
                raise ValueError('小地图尺寸已改变，请恢复原来的小地图大小。')
            origin, score, _ = find_pattern_sqdiff(self.image, mini)
            if score < .1:
                ox, oy = origin
                self.live_origin=(ox,oy)
                mh, mw = mini.shape[:2]
                self.live_canvas = self.image.copy()
                self.live_canvas[oy:oy+mh, ox:ox+mw] = mini
            marker = get_player_location_on_minimap(mini, self.cfg['minimap']['player_color'])
            if marker is not None:
                cv2.circle(self.game_frame,(x+1+marker[0],y+1+marker[1]),5,(0,0,255),2)
                cv2.circle(self.live_minimap,marker,3,(0,0,255),1)
            if marker is None or not score < .1:
                raise ValueError('人物点或地图匹配不可靠，暂停采样。')
            offset = self.cfg['minimap']['offset']
            self.position = (origin[0]+marker[0]+offset[0], origin[1]+marker[1]+offset[1])
            if not (0 <= self.position[0] < self.image.shape[1] and 0 <= self.position[1] < self.image.shape[0]):
                self.position = None
                raise ValueError('人物坐标越界，暂停采样。')
            self.position_time = time.monotonic()
            message = f'小地图坐标：{self.position}\n匹配误差：{score:.4f}（小于 0.1 有效）\n{self.name_status}'
            if self.polyline:
                message+=f'\n{self.active[1]} 已记录 {len(self.points)} 个点（F7 加点，F8 结束）'
                message+='\n'+' → '.join(f'{i+1}:{p}' for i,p in enumerate(self.points))
            elif self.active and self.points:
                message += f'\n{self.active[1]} 起点：{self.points[0]}\n终点预览：{self.position}，到位后点击确认终点'
            self.status.setText(message)
        except Exception as exc:
            self.status.setText(str(exc))
            self.live_title.setText('游戏小地图 · ' + str(exc))
        self.draw()

    def repair_empty_map(self, mini):
        import shutil
        pad=int(self.cfg.get('route_recoder',{}).get('map_padding',20))
        canvas=np.zeros((mini.shape[0]+2*pad,mini.shape[1]+2*pad,3),np.uint8)
        canvas[pad:pad+mini.shape[0],pad:pad+mini.shape[1]]=mini
        path=self.folder/'map.png'
        shutil.copy2(path,self.folder/f'map_before_recapture_{time.time_ns()}.png')
        from src.utils.common import imwrite_unicode
        if not imwrite_unicode(str(path),canvas):
            raise ValueError('重新获取底图失败')
        self.image=canvas
        self.live_canvas=canvas.copy()
        self.graph=new_graph(canvas)
        self.points=[]
        self.dirty=True

    def draw(self):
        canvas = self.live_canvas.copy()
        selected = self.items.currentItem()
        selected = selected.data(Qt.UserRole) if selected else None
        for p in self.graph['platforms']:
            a=tuple(map(lambda v: int(round(v)),(p['x1'],p['y'])))
            b=tuple(map(lambda v: int(round(v)),(p['x2'],p.get('end_y',p['y']))))
            vertices=np.array(p.get('points',[a,b]),dtype=np.int32)
            cv2.polylines(canvas,[vertices],False,(0,0,255) if p.get('reset_point') else (255,255,255) if selected == ('platforms',p['id']) else (120,255,100),1)
            cv2.putText(canvas,p['id'],a,cv2.FONT_HERSHEY_SIMPLEX,.3,(120,255,100),1)
        for r in self.graph['ropes']:
            x,y1,y2=(int(round(r[k])) for k in ('x','y1','y2'))
            cv2.line(canvas,(x,y1),(x,y2),(255,255,255) if selected == ('ropes',r['id']) else (255,200,0),1)
            cv2.putText(canvas,r['id'],(x,y1),cv2.FONT_HERSHEY_SIMPLEX,.3,(255,200,0),1)
        if self.polyline and self.points:
            if len(self.points)>1:cv2.polylines(canvas,[np.array(self.points,dtype=np.int32)],False,(0,255,255),2)
            if self.position is not None:
                cv2.line(canvas,tuple(map(int,self.points[-1])),tuple(map(int,self.position)),(0,160,255),1)
        elif self.active and self.points and self.position is not None:
            cv2.line(canvas,tuple(map(int,self.points[0])),tuple(map(int,self.position)),(0,255,255),1)
        for index,point in enumerate(self.points):
            pt=tuple(map(int,point))
            cv2.circle(canvas,pt,2,(0,255,255),-1)
            cv2.putText(canvas,str(index+1),(pt[0]+3,pt[1]-4),cv2.FONT_HERSHEY_SIMPLEX,.35,(0,255,255),1)
        if self.position:
            cv2.circle(canvas,tuple(map(int,self.position)),2,(0,0,255),-1)
            cv2.putText(canvas,f'{self.position[0]},{self.position[1]}',
                        (int(self.position[0])+3,int(self.position[1])-3),cv2.FONT_HERSHEY_SIMPLEX,.3,(0,255,255),1)
        self.show_image(self.preview,canvas)
        if self.live_minimap is not None:
            if hasattr(self,"live_origin"):
                ox,oy=self.live_origin;mh,mw=self.live_minimap.shape[:2]
                self.show_image(self.live_preview,canvas[oy:oy+mh,ox:ox+mw])
            else:self.show_image(self.live_preview,self.live_minimap)
        if self.game_frame is not None:
            self.show_image(self.game_preview,self.game_frame)

    @staticmethod
    def show_image(label, canvas):
        rgb = cv2.cvtColor(canvas,cv2.COLOR_BGR2RGB)
        qimage = QImage(rgb.data,rgb.shape[1],rgb.shape[0],rgb.strides[0],QImage.Format_RGB888).copy()
        pix=QPixmap.fromImage(qimage)
        if isinstance(label,ClickMap):label.set_map(pix)
        else:label.setPixmap(pix.scaled(label.size(),Qt.KeepAspectRatio,Qt.FastTransformation))

    def save(self, confirm):
        if self.active:
            return
        try:
            if confirm and not self.graph['platforms']:
                raise ValueError('请至少录制一个平台。')
            build_connections(self.graph)
            save_graph(self.folder/'navigation.json',self.graph,self.image,confirm)
            self.dirty = False
            if confirm:
                self.confirmed_graph = self.graph
                self.accept()
            else:
                self.status.setText('草稿已保存，可以稍后继续录制。')
        except ValueError as exc:
            missing=[]
            for rope in self.graph['ropes']:
                for label,key in [('上端','y1'),('下端','y2')]:
                    if not any(p['x1']<=rope['x']<=p['x2'] and
                               abs(platform_y(p,rope['x'])-rope[key])<=4 for p in self.graph['platforms']):
                        missing.append(f"{rope['id']} {label} ({rope['x']}, {rope[key]}) 附近未录到衔接平台")
            detail=('\n\n连接检查：\n'+'\n'.join(missing)) if missing else ''
            QMessageBox.warning(self,'请补录连接位置',str(exc)+detail+'\n\n可先保存草稿；补录实际可站立的平台后再启用导航，不需要删除想巡逻的平台。')

    def reject(self):
        if self.active or self.dirty:
            if QMessageBox.question(self,'退出录制','有未保存内容，确定放弃这些更改并退出？') != QMessageBox.Yes:
                return
        super().reject()
