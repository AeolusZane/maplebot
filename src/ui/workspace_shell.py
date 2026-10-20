"""Light desktop workspace. Existing controls retain their signals and persistence."""
import json
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QUrl, QSize, QPoint, QSettings
from PySide6.QtGui import QDesktopServices, QColor, QIcon, QPixmap, QPainter, QPen
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QSplitter, QGroupBox, QScrollArea, QCheckBox, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QMenu, QStackedWidget, QLineEdit,
    QHeaderView, QFrame, QSizePolicy, QTabWidget, QGridLayout, QComboBox)
from src.utils.paths import APP_ROOT

STYLE = """
QWidget { font-family: 'Microsoft YaHei UI'; font-size: 13px; color: #263650; }
QMainWindow, QWidget#workspace { background: #f5f8fd; }
QWidget#sidebar { background: #eaf2fc; border-right: 1px solid #dae5f3; }
QLabel#brand { font-size: 23px; font-weight: 700; color: #152b4d; }
QLabel#pageTitle { font-size: 26px; font-weight: 700; color: #172a46; }
QLabel#muted { color: #7a8ba4; font-size: 12px; }
QLabel#sectionTitle { font-size: 15px; font-weight: 600; color: #243b5b; }
QLabel#metric { font-size: 22px; font-weight: 600; color: #1e487d; }
QLabel#badge { background: #e7f0ff; color: #2469d5; border-radius: 5px; padding: 5px 10px; }
QFrame#card { background: white; border: 1px solid #e0e8f3; border-radius: 10px; }
QListWidget#navigation, QListWidget#categories { background: transparent; border: none; outline: none; }
QListWidget#navigation::item { height: 50px; padding-left: 16px; margin: 4px 0; border-radius: 7px; }
QListWidget#navigation::item:selected, QListWidget#categories::item:selected { background: #d9e9ff; color: #1565dc; font-weight: 600; }
QListWidget#navigation::item:hover, QListWidget#categories::item:hover { background: #e0edfc; }
QListWidget#categories::item { height: 44px; padding-left: 12px; margin-bottom: 5px; border-radius: 6px; }
QGroupBox { background: white; border: 1px solid #e0e8f3; border-radius: 9px; margin-top: 16px; padding: 20px 16px 16px; font-weight: 600; }
QGroupBox#settingsSection { margin-top: 0; padding: 0; }
QFrame#settingsDivider { color: #e0e8f3; }
QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 5px; }
QPushButton { background: #fff; border: 1px solid #d3deed; border-radius: 6px; padding: 7px 13px; min-height: 20px; }
QPushButton:hover { background: #eff5ff; border-color: #9cbdeb; }
QPushButton:pressed { background: #deebff; }
QPushButton:disabled { color: #a0aec0; background: #f7f9fc; border-color: #e3e9f2; }
QPushButton#primary { background: #246deb; color: white; border: 1px solid #246deb; font-weight: 600; padding: 9px 20px; }
QPushButton#primary:hover { background: #175ed6; }
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QKeySequenceEdit { background: white; border: 1px solid #d1ddeb; border-radius: 5px; padding: 6px 8px; min-height: 20px; selection-background-color: #dbeaff; }
QComboBox::drop-down { border: none; width: 24px; }
QListWidget, QTableWidget { background: white; border: 1px solid #e0e8f3; border-radius: 7px; selection-background-color: #e8f1ff; selection-color: #1b55a2; outline: none; alternate-background-color: #f8fafd; }
QListWidget::item { padding: 10px 12px; }
QHeaderView::section { background: #f3f7fc; color: #607592; padding: 10px 8px; border: none; border-bottom: 1px solid #e4ebf5; font-weight: 400; }
QTableWidget { gridline-color: #edf2f8; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QPlainTextEdit { background: #f8fafd; color: #52647f; border: 1px solid #e6edf5; border-radius: 6px; padding: 8px; font-family: Consolas, 'Microsoft YaHei UI'; font-size: 12px; }
QTabWidget::pane { border: none; }
QTabBar::tab { padding: 9px 15px; border: none; background: #edf3fb; }
QTabBar::tab:selected { color: #246deb; background: white; }
QSplitter::handle { background: #e3ebf6; }
QSplitter::handle:hover { background: #9bbbe9; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #c5d3e5; min-height: 30px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { background: white; color: #263650; border: 1px solid #d3deed; padding: 7px; }
"""


def label(text, name='muted'):
    result = QLabel(text); result.setObjectName(name); result.setWordWrap(True)
    return result


def card(title=None,description=None):
    widget = QFrame(); widget.setObjectName('card')
    layout = QVBoxLayout(widget); layout.setContentsMargins(16, 14, 16, 14); layout.setSpacing(12)
    if title:
        heading=label(title, 'sectionTitle')
        if description:heading.setToolTip(description)
        layout.addWidget(heading)
    return widget, layout


def page(title, subtitle):
    widget = QWidget(); layout = QVBoxLayout(widget)
    layout.setContentsMargins(24, 24, 24, 20); layout.setSpacing(16)
    header = QHBoxLayout(); titles = QVBoxLayout(); titles.setSpacing(5)
    heading=label(title, 'pageTitle')
    heading.setToolTip(subtitle)
    titles.addWidget(heading)
    header.addLayout(titles, 1); layout.addLayout(header)
    return widget, layout, header


def scroll_controls(widgets):
    content = QWidget(); layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 8, 0); layout.setSpacing(16)
    for widget in widgets: layout.addWidget(widget); widget.show()
    layout.addStretch()
    scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(content)
    return scroll


def table_style(table):
    table.setAlternatingRowColors(True); table.setShowGrid(False)
    table.verticalHeader().hide(); table.verticalHeader().setDefaultSectionSize(43)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.horizontalHeader().setStretchLastSection(True)


def nav_icon(kind,color='#5681b8'):
    pix = QPixmap(24, 24); pix.fill(Qt.transparent)
    p = QPainter(pix); p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(color), 1.7))
    if kind == 0:
        p.drawLine(3, 11, 12, 3); p.drawLine(12, 3, 21, 11); p.drawRect(6, 10, 12, 11); p.drawRect(10, 15, 4, 6)
    elif kind == 1:
        p.drawPolyline([QPoint(x,y) for x,y in [(3,5),(9,3),(15,6),(21,4),(21,20),(15,22),(9,19),(3,21),(3,5)]])
        p.drawLine(9,3,9,19); p.drawLine(15,6,15,22)
    elif kind == 2:
        for x,h in [(4,7),(10,12),(16,18)]: p.drawRoundedRect(x,22-h,4,h,1,1)
    elif kind == 3:
        p.drawRoundedRect(5,3,14,19,2,2)
        for y in (9,13,17): p.drawLine(9,y,16,y)
    elif kind == 4:
        import math
        p.drawEllipse(5,5,14,14);p.drawEllipse(9,9,6,6)
        for angle in range(0,360,45):
            a=math.radians(angle)
            p.drawLine(QPoint(round(12+8*math.cos(a)),round(12+8*math.sin(a))),QPoint(round(12+11*math.cos(a)),round(12+11*math.sin(a))))
    else:
        p.drawArc(4,3,10,12,180*16,180*16);p.drawLine(4,3,4,8);p.drawLine(14,3,14,8)
        p.drawLine(9,15,9,18);p.drawArc(9,14,10,8,180*16,180*16);p.drawLine(19,18,19,11);p.drawEllipse(17,7,4,4)
    p.end(); return QIcon(pix)


def read_json(path):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}


def install(window):
    overview, main, heading = page('运行总览', '实时画面与运行状态，一处掌握当前进展。')
    heading.addWidget(window.button_start_pause); window.button_start_pause.setObjectName('primary')
    recording = label('●  录制随挂机启动', 'badge')
    upper = QSplitter(Qt.Horizontal); upper.setChildrenCollapsible(False); upper.setHandleWidth(8)
    preview, pl = card('实时游戏画面')
    window.debug_canvas.setMinimumSize(320, 180); window.debug_canvas.setAlignment(Qt.AlignCenter)
    window.debug_canvas.setStyleSheet('background:#edf3fb; color:#8195b2; border:1px dashed #ccdbee; border-radius:7px;')
    window.debug_canvas.setText('等待游戏画面\n\n开始运行后显示实时画面与识别结果')
    pl.addWidget(window.debug_canvas, 1); upper.addWidget(preview)
    status_card, sl = card('运行状态'); status_card.setMinimumWidth(245); status_card.setMaximumWidth(310)
    state = label('●  待机', 'badge'); sl.addWidget(state)
    sl.addWidget(recording)
    sl.addWidget(label('当前地图')); map_value = label('未选择地图', 'metric'); sl.addWidget(map_value)
    sl.addWidget(label('本次经验统计')); status = label('等待启动'); sl.addWidget(status)
    sl.addStretch()
    goto = QPushButton('查看采集与记录  →'); goto.clicked.connect(lambda:window.tabs.setCurrentIndex(3)); sl.addWidget(goto)
    goto.setToolTip('画面、决策、按键及配置版本随运行归档，停止后自动收尾。')
    upper.addWidget(status_card); upper.setSizes([730, 275])
    lower = QSplitter(Qt.Horizontal); lower.setHandleWidth(8); lower.setChildrenCollapsible(False)
    trend, tl = card('经验趋势')
    from src.ui.experience_charts import ExperienceCharts
    overview_charts = ExperienceCharts(lambda:window.selected_map or '', compact=True, history=window.tab_statistics.history)
    overview_charts.setProperty('overview', True)
    overview_charts.bars.hide()
    # Overview shows one authentic trend; detailed filters remain in Data.
    overview_charts.layout().itemAt(0).layout().itemAt(0).widget().hide()
    overview_charts.maps.hide(); overview_charts.layout().itemAt(0).layout().itemAt(2).widget().hide(); overview_charts.levels.hide()
    overview_charts.comparison.hide(); tl.addWidget(overview_charts)
    window.tab_statistics.history_changed.connect(overview_charts.reload)
    lower.addWidget(trend)
    events, el = card('最近事件'); window.log_output.setMaximumHeight(16777215)
    window.log_output.setStyleSheet(''); window.log_output.setProperty('lightTheme', True)
    el.addWidget(window.log_output); lower.addWidget(events); lower.setSizes([500,500])
    vertical = QSplitter(Qt.Vertical); vertical.setChildrenCollapsible(False); vertical.setHandleWidth(9)
    vertical.addWidget(upper); vertical.addWidget(lower); vertical.setSizes([460,260]); main.addWidget(vertical,1)

    maps, ml, _ = page('地图与怪物', '选择地图，检查平台与连接，维护当前地图的怪物识别。')
    old = window.map_selection_gbox; record_buttons = []
    for button in old.findChildren(QPushButton):
        if button.text() in ('人工采集（10分钟）…', '技能画面核验…'):
            button.setParent(None); record_buttons.append(button)
    window.map_selection_gbox, mcl = card('地图列表')
    window.map_selection_gbox.setMinimumWidth(180); window.map_selection_gbox.setMaximumWidth(230)
    search = QLineEdit(); search.setPlaceholderText('搜索地图'); mcl.addWidget(search)
    window.list_widget_maps.setStyleSheet('QListWidget {border:none;} QListWidget::item {padding:14px 8px;}')
    mcl.addWidget(window.list_widget_maps,1)
    search.textChanged.connect(lambda text:[window.list_widget_maps.item(i).setHidden(text.casefold() not in window.list_widget_maps.item(i).text().casefold()) for i in range(window.list_widget_maps.count())])
    window.btn_new_map.setText('＋ 新增地图'); mcl.addWidget(window.btn_new_map)
    more = QPushButton('地图工具  ···'); menu = QMenu(more); more.setMenu(menu)
    secondary = [window.btn_mob_lib, window.btn_delete_map]
    for button in old.findChildren(QPushButton):
        if button.text() == '怪物识别测试…':
            button.setText('识别测试');button.setToolTip('测试当前地图配置的怪物识别效果')
            mcl.insertWidget(mcl.count()-1,button);button.show()
    menu_links=[]
    for button in secondary:
        button.setParent(window.map_selection_gbox); button.hide()
        action=menu.addAction(button.text()); action.triggered.connect(button.click); menu_links.append((action,button))
    menu.aboutToShow.connect(lambda:[a.setEnabled(b.isEnabled()) for a,b in menu_links]); mcl.addWidget(more)
    debug=window.tab_map_debug; debug.layout().setContentsMargins(0,0,0,0)
    legend=debug.layout().itemAt(debug.layout().count()-1).widget()
    if isinstance(legend,QLabel):
        debug.view.setToolTip(legend.text());legend.hide()
    # Numerical telemetry belongs to diagnostics, not the everyday map workflow.
    for tabs in debug.findChildren(QTabWidget):
        tabs.hide()
    debug.coords.setChecked(False)
    debug.coords.hide()
    table_style(debug.table)
    debug.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    # Keep the existing telemetry canvas, toolbar and property panel together.
    debug.status.setObjectName('muted'); debug.status.setMaximumHeight(100)
    window.label_map_info.setWordWrap(True)
    # Properties sit alongside the canvas, below its existing live preview.
    map_split=debug.findChildren(QSplitter)[0]
    map_split.widget(1).setMinimumWidth(215); map_split.widget(1).setMaximumWidth(300)
    props=map_split.widget(1).layout()
    window.label_map_info.setParent(map_split.widget(1));window.label_map_info.hide()
    info, info_layout=card()
    info_layout.addWidget(label('当前地图'))
    map_title=label('选择一张地图','mapName');info_layout.addWidget(map_title)
    map_subtitle=label('从左侧列表选择需要运行的地图');info_layout.addWidget(map_subtitle)
    info_layout.addSpacing(4);info_layout.addWidget(label('识别怪物','sectionTitle'))
    monsters=label('尚未选择地图');info_layout.addWidget(monsters)
    tolerance_row=QHBoxLayout();tolerance_row.addWidget(label('识别容差'))
    tolerance=label('—','badge');tolerance_row.addStretch();tolerance_row.addWidget(tolerance);info_layout.addLayout(tolerance_row)
    scope=label('');info_layout.addWidget(scope)
    tolerance.setToolTip('识别匹配允许的差异，数值越大越宽松。可在下方怪物设置中调整。')
    props.insertWidget(0,info)
    debug.preview.setMaximumHeight(180)
    info_cache=[None]
    def refresh_map_card():
        from src.utils.monster_threshold import map_threshold
        name=window.selected_map or window.cfg.get('bot',{}).get('map','')
        mobs=(window.data.get('map_mobs_mapping',{}) or {}).get(name,[])
        threshold=map_threshold(window.data,name,window.cfg.get('monster_detect',{}).get('diff_thres',.1))
        own=name in (window.data.get('map_monster_thresholds',{}) or {})
        signature=(name,tuple(mobs),threshold,own)
        if info_cache[0]==signature:return
        info_cache[0]=signature
        map_title.setText(name or '选择一张地图')
        map_subtitle.setText(f'{len(mobs)} 种怪物已配置' if name else '从左侧列表选择需要运行的地图')
        monsters.setText('  ·  '.join(mobs) if mobs else '尚未添加怪物，点击下方按钮设置')
        tolerance.setText(f'{threshold:.2f}' if name else '—')
        scope.setText('此地图专用设置' if own else '使用默认识别设置')
    window.refresh_map_card=refresh_map_card
    window.list_widget_maps.itemSelectionChanged.connect(refresh_map_card)
    refresh_map_card()
    window.btn_map_graph.setText('编辑平台与连接…'); window.btn_map_mobs.setText('怪物与识别阈值…')
    props.addStretch()
    props.addWidget(window.btn_map_graph); props.addWidget(window.btn_map_mobs)
    # Retain the configuration-bound control without exposing an implementation
    # mode switch. Saving/editing a map already selects map-graph navigation.
    window.graph_navigation_checkbox.setParent(map_split.widget(1))
    window.graph_navigation_checkbox.hide()
    map_body=QSplitter(); map_body.setChildrenCollapsible(False); map_body.setHandleWidth(10)
    map_body.addWidget(window.map_selection_gbox); map_body.addWidget(debug); map_body.setSizes([190,850]); ml.addWidget(map_body,1)
    debug.show(); debug.setMinimumHeight(280)
    debug.preview.setStyleSheet('background:#edf3fb;color:#8195b2;border-radius:6px;')
    from PySide6.QtGui import QBrush
    debug.view.setBackgroundBrush(QBrush(QColor('#edf3fb')))

    records, rl, rh = page('采集与记录', '自动运行与人工示范统一归档，保留画面、按键和配置版本。')
    for button in record_buttons:
        if '人工采集' in button.text(): button.setText('人工采集 · 10分钟'); button.setObjectName('primary'); rh.addWidget(button)
    tools, tool_layout=card(); filter_row=QHBoxLayout()
    kind=__import__('PySide6.QtWidgets',fromlist=['QComboBox']).QComboBox(); kind.addItems(['全部记录','自动运行','人工采集']); filter_row.addWidget(kind)
    record_search=QLineEdit(); record_search.setPlaceholderText('搜索会话 / 地图 / 版本'); filter_row.addWidget(record_search,1)
    refresh=QPushButton('刷新'); filter_row.addWidget(refresh)
    for button in record_buttons:
        if '技能' in button.text(): filter_row.addWidget(button)
    tool_layout.addLayout(filter_row); rl.addWidget(tools)
    table=QTableWidget(0,5); table.setHorizontalHeaderLabels(['会话','类型','地图','版本','状态']); table_style(table)
    table.setColumnWidth(0,220); table.setColumnWidth(1,85); table.setColumnWidth(2,110); table.setColumnWidth(3,110)
    details, dl=card('会话详情'); details.setMinimumWidth(265); details.setMaximumWidth(350)
    detail_title=label('选择一条记录', 'sectionTitle'); dl.addWidget(detail_title)
    detail_text=label('在左侧选择会话，查看归档内容与代码版本。'); detail_text.setTextInteractionFlags(Qt.TextSelectableByMouse); dl.addWidget(detail_text); dl.addStretch()
    open_record=QPushButton('打开会话目录'); open_record.setEnabled(False); dl.addWidget(open_record)
    rs=QSplitter(); rs.setChildrenCollapsible(False); rs.setHandleWidth(12); rs.addWidget(table); rs.addWidget(details); rs.setSizes([700,300]); rl.addWidget(rs,1)
    empty=label('暂无匹配记录 · 自动运行结束或人工采集后，记录会显示在这里。'); rl.addWidget(empty)
    selected={'path':None}; all_rows=[]; visible=[]
    def show_record():
        i=table.currentRow()
        if not 0<=i<len(visible):return
        path,mode,meta,prov=visible[i]; selected['path']=path
        detail_title.setText('人工示范' if mode=='人工采集' else '自动运行')
        folder=path if path.is_dir() else Path(str(path)+'.session')
        version=prov.get('automation_version') or '未记录'
        duration=meta.get('duration_actual',meta.get('duration_seconds',meta.get('duration')))
        text=f"会话  {path.name}\n\n地图  {meta.get('map_name','未记录')}\n开始  {meta.get('started_at','未记录')}\n时长  {str(round(duration,1))+' 秒' if isinstance(duration,(int,float)) else '未记录'}\n\n版本  {version}\n\n"
        for title,exists in [('配置快照',(folder/'config_snapshot.json').exists()),('代码快照',(folder/'source_snapshot.zip').exists()),('按键与事件',any(folder.glob('*.jsonl'))),('原始录像',path.suffix=='.mp4' or any(folder.glob('*.mp4'))),('截图目录',(folder/'frames').exists())]: text+=f"{title}  {'已保存' if exists else '未发现'}\n"
        detail_text.setText(text);open_record.setEnabled(True)
    def filter_records():
        nonlocal visible
        query=record_search.text().casefold();visible=[r for r in all_rows if (kind.currentIndex()==0 or r[1]==kind.currentText()) and query in (r[0].name+str(r[2].get('map_name',''))+str(r[3].get('automation_version',''))).casefold()]
        table.setRowCount(len(visible))
        for i,(path,mode,meta,prov) in enumerate(visible):
            values=[path.stem,mode,meta.get('map_name','—'),prov.get('automation_version','—')[:12],{'finished':'已结束','recording':'采集中','error':'异常'}.get(meta.get('status'),'已归档' if path.suffix=='.mp4' else '未记录')]
            for j,value in enumerate(values):
                item=QTableWidgetItem(str(value));item.setToolTip(str(value));table.setItem(i,j,item)
        empty.setVisible(not visible); selected['path']=None;open_record.setEnabled(False)
        if visible:table.selectRow(0);show_record()
        else:detail_title.setText('暂无记录');detail_text.setText('完成一次自动运行或人工采集后，可在此查看归档详情。')
    def reload_records():
        all_rows.clear(); root=Path(APP_ROOT)
        for manifest in (root/'sessions').rglob('manifest.json'):
            meta=read_json(manifest);folder=manifest.parent;all_rows.append((folder,'人工采集',meta,meta.get('provenance') or read_json(folder/'provenance.json')))
        for video in (root/'video').glob('*.mp4'):
            folder=Path(str(video)+'.session');meta=read_json(folder/'manifest.json');prov=read_json(folder/'provenance.json')
            # Automatic evidence begins with a real session event, not a manifest.
            try:
                with (folder/'events.jsonl').open(encoding='utf-8') as stream:
                    event=json.loads(stream.readline())
                cfg=event.get('cfg') or {}
                meta.setdefault('map_name',cfg.get('bot',{}).get('map','—'))
            except (OSError,ValueError): pass
            all_rows.append((video,'自动运行',meta,prov))
        all_rows.sort(key=lambda r:r[0].stat().st_mtime,reverse=True);filter_records()
    kind.currentIndexChanged.connect(filter_records);record_search.textChanged.connect(filter_records);refresh.clicked.connect(reload_records)
    table.itemSelectionChanged.connect(show_record)
    open_record.clicked.connect(lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(selected['path'] if selected['path'].is_dir() else selected['path'].parent))) if selected['path'] else None)
    table.cellDoubleClicked.connect(lambda *_:open_record.click());window.reload_record_list=reload_records;reload_records()
    folders=QHBoxLayout()
    for title,relative in [('自动录像目录','video'),('人工采集目录','sessions')]:
        button=QPushButton(title);button.clicked.connect(lambda checked=False,relative=relative:QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(APP_ROOT)/relative))));folders.addWidget(button)
    folders.addStretch();rl.addLayout(folders)

    settings, stl, sh=page('角色与设置','角色、技能与常用按键集中设置；修改后自动保存。')
    sh.addWidget(label('●  自动保存', 'badge'))
    calibration,cl=card()
    cl.setContentsMargins(20,18,20,18)
    identity_row=QHBoxLayout();identity_row.setSpacing(16)
    avatar=label('●','metric');avatar.setFixedSize(76,76);identity_row.addWidget(avatar)
    identity=QVBoxLayout();identity.setSpacing(4);identity.addWidget(label('当前角色'))
    role_name=label('尚未标定','mapName')
    name_row=QHBoxLayout();name_row.setSpacing(16);name_row.addWidget(role_name)
    role_badge=label('待标定','badge');role_badge.setMaximumHeight(38);name_row.addWidget(role_badge,alignment=Qt.AlignVCenter);name_row.addStretch()
    identity.addLayout(name_row);identity_row.addLayout(identity,1)
    window.button_nametag.setText('重新标定');identity_row.addWidget(window.button_nametag)
    window.button_template.setText('截取怪物模板…');cl.addLayout(identity_row)
    role_name.setToolTip('通过角色名字定位当前人物，更换角色或识别不稳定时重新标定。')
    maintenance=QGroupBox('诊断工具');maint=QVBoxLayout(maintenance)
    maintenance.setToolTip('出现识别或运行异常时，导出本机诊断包用于排查。')
    include=QCheckBox('包含游戏画面');include.setChecked(True);maint.addWidget(include)
    export=QPushButton('导出诊断包…');export.clicked.connect(lambda:window._launch_diagnose() if include.isChecked() else window._launch_diagnose_nopic());maint.addWidget(export)
    advanced=QPushButton('展开素材维护');advanced.setCheckable(True);maint.addWidget(advanced)
    qa=QPushButton('检查重复模板…');qa.clicked.connect(window._launch_mob_template_qa);qa.hide();maint.addWidget(qa);advanced.toggled.connect(qa.setVisible)
    for group,title in [(window.attack_gbox,'攻击方式与范围'),(window.key_binding_gbox,'常用按键'),(window.pickup_gbox,'自动拾取'),(window.buff_skill_gbox,'增益技能'),(window.potion_gbox,'自动补给')]: group.setTitle(title)
    for field in [window.attack_range_x,window.attack_range_up,window.attack_range_down,window.attack_cooldown]:field.setFixedWidth(110)
    window.attack_mode.setFixedWidth(170)
    potion_tip=window.potion_gbox.layout().itemAt(0).widget()
    potion_tip.setToolTip(potion_tip.text())
    potion_tip.setText('自动监控血蓝并按配置补给，使用 1366 × 768 窗口化游戏画面。')
    window.potion_gbox.setToolTip(potion_tip.text());potion_tip.hide()
    # Keep the small set of everyday fields on one page. Reuse the actual
    # inputs, including their validators and config signals, in compact rows.
    def compact_fields(group, fields):
        previous=group.layout()
        holder=QWidget(group);holder.setLayout(previous);holder.hide()
        grid=QGridLayout(group);grid.setContentsMargins(16,24,16,16)
        grid.setHorizontalSpacing(10);grid.setVerticalSpacing(10)
        grid.setAlignment(Qt.AlignTop)
        grid.setColumnStretch(1,1);grid.setColumnStretch(3,1)
        for i,(caption,field) in enumerate(fields):
            row,col=divmod(i,2)
            grid.addWidget(QLabel(caption),row,col*2)
            field.setMinimumWidth(90);field.setMaximumWidth(120)
            grid.addWidget(field,row,col*2+1,alignment=Qt.AlignLeft);field.show()
        # Attack's original error label remains visible for validation feedback.
        if group is window.attack_gbox:
            error=previous.itemAt(0).widget()
            grid.addWidget(error,(len(fields)+1)//2,0,1,4);error.show()
    compact_fields(window.attack_gbox,[('攻击间隔（秒）',window.attack_cooldown),('水平范围',window.attack_range_x),('向上范围',window.attack_range_up),('向下范围',window.attack_range_down)])
    old_keys=window.key_binding_gbox.layout();key_holder=QWidget(window.key_binding_gbox);key_holder.setLayout(old_keys);key_holder.hide()
    window.key_binding_gbox.setTitle('');window.key_binding_gbox.setObjectName('settingsSection')
    battle=QVBoxLayout(window.key_binding_gbox);battle.setContentsMargins(20,18,20,20);battle.setSpacing(20)
    battle_title=label('战斗与按键','sectionTitle');battle.addWidget(battle_title)
    attack_row=QHBoxLayout();attack_row.setSpacing(16);attack_row.addWidget(QLabel('攻击方式'));attack_row.addWidget(window.attack_mode);attack_row.addStretch();battle.addLayout(attack_row)
    divider=QFrame();divider.setFrameShape(QFrame.HLine);divider.setObjectName('settingsDivider');battle.addWidget(divider)
    key_grid=QGridLayout();key_grid.setHorizontalSpacing(10);key_grid.setVerticalSpacing(18)
    for i,(caption,field) in enumerate([('基础攻击',window.basic_attack_key),('群体技能',window.aoe_skill_key),('瞬移',window.teleport_key),('跳跃',window.jump_key)]):
        row,col=divmod(i,2);key_grid.addWidget(QLabel(caption),row,col*2)
        field.setProperty('keyCap',True)
        for key_input in field.findChildren(QLineEdit):key_input.setProperty('keyCap',True)
        field.setMinimumWidth(64);field.setMaximumWidth(112);key_grid.addWidget(field,row,col*2+1);field.show()
    battle.addLayout(key_grid)
    window.button_template.setParent(maintenance);window.button_template.hide()
    auxiliary, auxiliary_layout=card()
    auxiliary_layout.setContentsMargins(20,18,20,20);auxiliary_layout.setSpacing(18)
    supply_title=label('自动补给','sectionTitle')
    supply_header=QHBoxLayout();supply_header.addWidget(supply_title);supply_header.addStretch()
    window.cb_potion_enabled.setText('启用');supply_header.addWidget(window.cb_potion_enabled);auxiliary_layout.addLayout(supply_header)
    potion_table=QTableWidget(0,3);potion_table.setHorizontalHeaderLabels(['类型','触发条件','按键']);table_style(potion_table)
    potion_table.setObjectName('potionRules')
    potion_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    potion_table.horizontalHeader().setMinimumSectionSize(55)
    potion_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    potion_table.setFocusPolicy(Qt.NoFocus);potion_table.setSelectionMode(QAbstractItemView.NoSelection)
    potion_table.setMinimumHeight(170);auxiliary_layout.addWidget(potion_table)
    potion_keys=label('');potion_keys.hide();window.potion_keys_label=potion_keys
    window.btn_potion_test.setText('测试血蓝识别');auxiliary_layout.addWidget(window.btn_potion_test,alignment=Qt.AlignLeft)
    from src.ui.parchment import PotionResultLabel
    window.potion_test_result=PotionResultLabel();window.potion_test_result.setText('血量 —  ·  魔法 —');window.potion_test_result.setWordWrap(True)
    window.potion_test_result.setObjectName('badge');window.potion_test_result.setMinimumHeight(58);auxiliary_layout.addWidget(window.potion_test_result)
    def style_potion_rows(parchment):
        from src.ui.parchment import ASSETS
        for i in range(potion_table.rowCount()):
            item=potion_table.item(i,0)
            item.setIcon(QIcon(str(ASSETS/('hp.png' if item.text()=='补血' else 'mp.png'))) if parchment else QIcon())
            if parchment:
                key=QLabel(potion_table.item(i,2).text());key.setObjectName('potionKey');key.setAlignment(Qt.AlignCenter)
                potion_table.item(i,2).setForeground(QColor(Qt.transparent))
                potion_table.setCellWidget(i,2,key)
            else:
                previous=potion_table.cellWidget(i,2)
                if previous:previous.hide()
                potion_table.removeCellWidget(i,2)
                potion_table.item(i,2).setForeground(potion_table.palette().text())
    auxiliary_layout.addStretch()
    old_buff=window.buff_skill_gbox.layout();buff_holder=QWidget(window.buff_skill_gbox);buff_holder.setLayout(old_buff);buff_holder.hide()
    window.buff_skill_gbox.setTitle('');window.buff_skill_gbox.setObjectName('settingsSection')
    buff_layout=QVBoxLayout(window.buff_skill_gbox);buff_layout.setContentsMargins(20,18,20,20);buff_layout.setSpacing(18)
    buff_title=label('增益技能','sectionTitle')
    buff_header=QHBoxLayout();buff_header.addWidget(buff_title);buff_header.addStretch()
    window.checkbox_enable_buff.setText('启用');buff_header.addWidget(window.checkbox_enable_buff);buff_layout.addLayout(buff_header)
    buff_scroll=QScrollArea();buff_scroll.setObjectName('buffScroll');buff_scroll.setWidgetResizable(True)
    buff_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    buff_scroll.setWidget(window.buff_section_container);buff_layout.addWidget(buff_scroll,1)
    window.buff_skill_gbox.setFixedHeight(300)
    window.checkbox_enable_buff.toggled.connect(buff_scroll.setVisible)
    buff_scroll.setVisible(window.checkbox_enable_buff.isChecked())
    buff_empty=label('未启用');buff_empty.setAlignment(Qt.AlignCenter);buff_empty.setMinimumHeight(48);buff_layout.addWidget(buff_empty)
    window.button_add_buff.setText('＋ 添加增益');window.button_add_buff.setFixedWidth(180)
    buff_layout.addWidget(window.button_add_buff,alignment=Qt.AlignHCenter)
    window.button_add_buff.clicked.connect(lambda:window.checkbox_enable_buff.setChecked(True))
    window.checkbox_enable_buff.toggled.connect(lambda checked:buff_empty.setVisible(not checked))
    columns=QWidget();columns_layout=QHBoxLayout(columns);columns_layout.setContentsMargins(0,0,0,0);columns_layout.setSpacing(18)
    left=QVBoxLayout();left.setSpacing(18);left.addWidget(window.key_binding_gbox);left.addWidget(window.buff_skill_gbox);left.addStretch()
    columns_layout.addLayout(left,1);columns_layout.addWidget(auxiliary,1)
    potion_signature=[None]
    rare_keys=QGroupBox('拾取按键')
    rare_layout=QHBoxLayout(rare_keys);rare_layout.setContentsMargins(18,24,18,16);rare_layout.setSpacing(16)
    rare_layout.addWidget(QLabel('拾取'));rare_layout.addWidget(window.pickup_key);rare_layout.addStretch()
    window.return_home_key.hide()
    window.control_gbox, profiles=card('管理多套设置','日常修改会自动记住，无需创建设置。需要不同按键或技能组合时，再复制一套。')
    profile_row=QHBoxLayout();profile_row.addWidget(QLabel('当前设置'))
    window.config_combo.setMinimumWidth(160);window.config_combo.lineEdit().setReadOnly(True)
    profile_row.addWidget(window.config_combo,1)
    window.button_new_config.clicked.disconnect()
    window.button_new_config.setText('复制当前设置');window.button_new_config.setFixedWidth(120)
    window.button_new_config.clicked.connect(window._copy_current_settings)
    rename=QPushButton('重命名');rename.clicked.connect(window._rename_settings_dialog)
    window.button_delete_config.setText('删除');window.button_delete_config.setFixedWidth(62)
    profile_row.addWidget(window.button_new_config);profile_row.addWidget(rename);profile_row.addWidget(window.button_delete_config)
    profiles.addLayout(profile_row)
    advanced_body=QWidget();advanced_layout=QVBoxLayout(advanced_body);advanced_layout.setContentsMargins(0,0,0,0);advanced_layout.setSpacing(14)
    for widget in (window.attack_gbox,rare_keys,window.pickup_gbox,window.control_gbox):advanced_layout.addWidget(widget);widget.show()
    from src.ui.parchment import SOURCE_ASSETS
    advanced_toggle=QPushButton('高级设置');advanced_toggle.setCheckable(True);advanced_toggle.setObjectName('settingsManagerToggle')
    advanced_toggle.setIcon(QIcon(str(SOURCE_ASSETS/'chevron-right.svg')))
    def toggle_advanced(expanded):
        advanced_body.setVisible(expanded)
        advanced_toggle.setIcon(QIcon(str(SOURCE_ASSETS/('chevron-down.svg' if expanded else 'chevron-right.svg'))))
    advanced_toggle.toggled.connect(toggle_advanced)
    settings_scroll=scroll_controls([calibration,columns,advanced_toggle,advanced_body])
    advanced_body.hide();stl.addWidget(settings_scroll,1);window.settings_scroll=settings_scroll
    window.settings_advanced=advanced_body
    conflict_hint=label('');conflict_hint.setObjectName('keyConflictHint');conflict_hint.hide()
    stl.insertWidget(1,conflict_hint)
    def refresh_key_conflicts():
        from src.ui.key_conflicts import conflicts,normalize_key
        fields=[('基础攻击',window.basic_attack_key),('群体技能',window.aoe_skill_key),
                ('瞬移',window.teleport_key),('跳跃',window.jump_key),('拾取',window.pickup_key)]
        if window.checkbox_enable_buff.isChecked():
            fields.extend((f'增益技能 {i+1}',key) for i,(key,_) in enumerate(window.buff_inputs))
        bindings=[(name,field.get_key()) for name,field in fields]
        if window.cb_potion_enabled.isChecked():
            for kind,name in [('hp','补血'),('mp','补蓝')]:
                bindings.extend((name,tier.get('key')) for tier in window.cfg.get('potion',{}).get(kind,[]) if isinstance(tier,dict))
        clashes=conflicts(bindings)
        def mark(widget,key):
            actions=clashes.get(normalize_key(key))
            flagged=bool(actions)
            if widget.property('keyConflict')!=flagged:
                widget.setProperty('keyConflict',flagged);widget.style().unpolish(widget);widget.style().polish(widget);widget.update()
            widget.setToolTip(('按键冲突：'+'、'.join(actions)) if flagged else '')
        for name,field in fields:
            mark(field,field.get_key())
            for child in field.findChildren(QLineEdit):mark(child,field.get_key())
        if not window.checkbox_enable_buff.isChecked():
            for field,_ in window.buff_inputs:
                mark(field,'')
                for child in field.findChildren(QLineEdit):mark(child,'')
        for i in range(potion_table.rowCount()):
            item=potion_table.item(i,2);widget=potion_table.cellWidget(i,2)
            actions=clashes.get(normalize_key(item.text())) if window.cb_potion_enabled.isChecked() else None
            if widget:mark(widget,item.text() if window.cb_potion_enabled.isChecked() else '')
            else:item.setForeground(QColor('#d34d42') if actions else potion_table.palette().text())
            item.setToolTip('按键冲突：'+'、'.join(actions) if actions else '')
        conflict_hint.setText('按键冲突：'+'；'.join(key.upper()+' → '+'、'.join(actions) for key,actions in clashes.items()))
        conflict_hint.setVisible(bool(clashes))
    window.refresh_key_conflicts=refresh_key_conflicts
    for field in (window.basic_attack_key,window.aoe_skill_key,window.teleport_key,window.jump_key,window.pickup_key):
        field.keySequenceChanged.connect(refresh_key_conflicts)
    window.checkbox_enable_buff.toggled.connect(refresh_key_conflicts)
    window.cb_potion_enabled.toggled.connect(refresh_key_conflicts)

    diagnostics, diagnostic_layout, _=page('诊断与维护','遇到运行或识别问题时，再使用这里的检查与维护工具。')
    window.potion_gbox.setTitle('血蓝识别检查')
    materials, materials_layout=card('识别素材','更换怪物或识别不稳定时，截取模板或检查素材。')
    materials_row=QHBoxLayout();materials_row.addWidget(window.button_template);window.button_template.show()
    materials_row.addWidget(qa);qa.show();materials_row.addStretch();materials_layout.addLayout(materials_row)
    advanced.hide()
    experience_check, experience_layout=card('经验识别检查')
    experience_layout.addWidget(window.tab_statistics.status)
    experience_layout.addWidget(window.tab_statistics.preview)
    experience_buttons=QHBoxLayout()
    experience_buttons.addWidget(window.tab_statistics.pick_region_button)
    experience_buttons.addWidget(window.tab_statistics.reset_region_button)
    experience_buttons.addStretch();experience_layout.addLayout(experience_buttons)
    diagnostic_layout.addWidget(scroll_controls([maintenance,window.potion_gbox,experience_check,materials]),1)
    window.tab_diagnostics=diagnostics

    data, datal, data_heading=page('经验与效率','分析历史经验收益与采样明细，拖动分隔条调整图表和表格高度。\n'+str(window.tab_statistics.property('samplingHelp') or ''))
    data_heading.addWidget(window.tab_statistics.sample_now_button)
    exp_test=QPushButton('测试经验识别');data_heading.addWidget(exp_test)
    exp_result=label('');exp_result.hide();datal.addWidget(exp_result)
    exp_test.clicked.connect(lambda:window.tab_statistics.test_reading(window.cfg,exp_result,exp_test))
    datal.addWidget(window.tab_statistics,1);window.tab_statistics.show()
    window.tab_statistics.layout().setContentsMargins(0,0,0,0)
    window.tab_statistics.summary.setObjectName('badge');window.tab_statistics.summary.setMinimumHeight(48)
    window.tab_statistics.status.setObjectName('muted');table_style(window.tab_statistics.table)
    window.tab_statistics.table.setMinimumHeight(190);window.tab_statistics.data_splitter.setSizes([480,200])
    window.tabs.clear()
    for widget,title in [(overview,'总览'),(maps,'地图'),(data,'数据'),(records,'记录'),(settings,'设置'),(diagnostics,'诊断')]:window.tabs.addTab(widget,title)
    window.tabs.tabBar().hide();window.tab_main=overview;window.tab_maps=maps;window.tab_records=records;window.tab_settings=settings
    shell=QWidget();shell.setObjectName('workspace');outer=QHBoxLayout(shell);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0)
    sidebar=QWidget();sidebar.setObjectName('sidebar');sidebar.setFixedWidth(218)
    side=QVBoxLayout(sidebar);side.setContentsMargins(16,28,16,20);side.setSpacing(8)
    brand_panel=QFrame();brand_panel.setObjectName('brandPanel');brand_row=QHBoxLayout(brand_panel);brand_row.setContentsMargins(0,8,0,8);brand_row.setSpacing(10)
    brand_icon=QLabel();brand_icon.setObjectName('brandIcon');brand_icon.setFixedSize(36,44);brand_row.addWidget(brand_icon)
    brand_text=QVBoxLayout();brand_title=label('MapleBot','brand');brand_title.setWordWrap(False);brand_text.addWidget(brand_title);brand_text.addWidget(label('冒险岛助手'));brand_row.addLayout(brand_text)
    side.addWidget(brand_panel);side.addSpacing(12)
    navigation=QListWidget();navigation.setObjectName('navigation');navigation.setIconSize(QSize(22,22))
    from PySide6.QtWidgets import QListWidgetItem
    for i,title in enumerate(['总览','地图','数据','记录','设置','诊断']):navigation.addItem(QListWidgetItem(nav_icon(i),'  '+title))
    side.addWidget(navigation,1)
    theme_row=QHBoxLayout();theme_row.addWidget(label('界面风格'))
    theme_combo=QComboBox();theme_combo.addItems(['亮色','暗色','羊皮卷']);theme_combo.setObjectName('themeSelector');theme_row.addWidget(theme_combo,1);side.addLayout(theme_row)
    from src.ui.parchment import SOURCE_ASSETS
    theme_combo.setStyleSheet(f'QComboBox::down-arrow {{image:url("{(SOURCE_ASSETS/"chevron-down.svg").as_posix()}");width:12px;height:8px;}}')
    navigation.currentRowChanged.connect(window.tabs.setCurrentIndex);window.tabs.currentChanged.connect(navigation.setCurrentRow);navigation.setCurrentRow(0)
    outer.addWidget(sidebar);outer.addWidget(window.tabs,1);window.navigation=navigation
    window.setCentralWidget(shell);window.setStyleSheet(STYLE);window.setMinimumSize(1080,760);window.resize(1360,900)
    theme_settings=QSettings('MapleBot','Appearance')
    def apply_theme(mode,persist=True):
        from src.ui.theme import stylesheet,set_palette,colors,style_chart
        from PySide6.QtCharts import QChartView
        dark=mode=='dark'
        from src.ui.parchment import stylesheet as parchment_style
        parchment=mode=='parchment'
        set_palette(dark,parchment);window.setStyleSheet(stylesheet(STYLE,dark)+(parchment_style() if parchment else '')+'''
QTableWidget#potionRules::item {border-right:1px solid '''+colors(window)['border']+''';}
QTableWidget#potionRules QHeaderView::section {border-right:1px solid '''+colors(window)['border']+''';}
QWidget[keyConflict="true"], QLabel#potionKey[keyConflict="true"] {border:2px solid #d34d42; color:#d34d42;}
QLabel#keyConflictHint {color:#d34d42;}
''')
        outer.setContentsMargins(12,12,12,12) if parchment else outer.setContentsMargins(0,0,0,0)
        from src.ui.parchment import ASSETS, rich_icon, asset_icon, asset_pixmap
        def picture(widget,name,width,height):
            widget.setPixmap(asset_pixmap(name,width,height))
        brand_icon.setVisible(parchment)
        theme_combo.setVisible(True)
        if parchment:
            picture(brand_icon,'maple',36,44);picture(avatar,'avatar',76,76)
        else:
            avatar.setPixmap(QIcon(str(SOURCE_ASSETS/('avatar-dark.svg' if dark else 'avatar-light.svg'))).pixmap(76,76))
        for title,text,icon in [(battle_title,'战斗与按键','swords'),(supply_title,'自动补给','hp'),(buff_title,'增益技能','maple')]:
            title.setText(rich_icon(icon,text,30) if parchment else text)
        buff_empty.setText(rich_icon('maple-muted','<br>未启用',36) if parchment else '未启用')
        for button in (window.button_nametag,window.btn_potion_test,exp_test):
            button.setIcon(asset_icon('target') if parchment else QIcon());button.setIconSize(QSize(24,24))
        for checkbox in (window.checkbox_enable_buff,window.cb_potion_enabled):
            checkbox.setText('' if parchment else '启用')
            checkbox.setToolTip('启用自动补给' if checkbox is window.cb_potion_enabled else '启用增益技能')
        style_potion_rows(parchment)
        window.potion_test_result.setProperty('parchment',parchment)
        window.potion_test_result.setText(window.potion_test_result.raw_text)
        window.setProperty('theme',mode)
        badge_text='名字已配置' if window.cfg.get('nametag',{}).get('name','') else '待标定'
        role_badge.setText(rich_icon('maple' if badge_text=='名字已配置' else 'maple-muted',badge_text,18) if parchment else badge_text)
        c=colors(window)
        for i in range(navigation.count()):navigation.item(i).setIcon(nav_icon(i,'#79582e' if parchment else c['accent'] if dark else '#5681b8'))
        window.tab_statistics.data_splitter.setStyleSheet(f"QSplitter::handle:vertical {{background:{c['border']};margin:2px 0;}} QSplitter::handle:vertical:hover {{background:{c['accent']};}}")
        window.debug_canvas.setStyleSheet(f"background:{c['raised']};color:{c['muted']};border:1px dashed {c['border']};border-radius:7px;")
        debug.preview.setStyleSheet(f"background:{c['raised']};color:{c['muted']};border-radius:7px;")
        window.pickup_hint.setStyleSheet(f"color:{c['muted']};")
        debug.view.setBackgroundBrush(QBrush(QColor(c['raised'])))
        for charts in window.findChildren(ExperienceCharts):
            charts.update_empty_theme()
        for view in window.findChildren(QChartView):style_chart(view)
        window.log_output.setProperty('lightTheme',not dark)
        window.log_output.setStyleSheet(f"color:{c['text']};")
        # Existing log entries carry explicit foreground formats.
        from PySide6.QtGui import QTextCursor,QTextCharFormat
        cursor=window.log_output.textCursor();cursor.select(QTextCursor.Document)
        fmt=QTextCharFormat();fmt.setForeground(QColor(c['text']));cursor.mergeCharFormat(fmt)
        theme_combo.blockSignals(True);theme_combo.setCurrentIndex(2 if parchment else 1 if dark else 0);theme_combo.blockSignals(False)
        if persist:theme_settings.setValue('theme',mode)
        refresh_key_conflicts()
    window.apply_theme=apply_theme
    theme_combo.currentIndexChanged.connect(lambda i:apply_theme(('light','dark','parchment')[i]))
    apply_theme(theme_settings.value('theme','light'),persist=False)
    def refresh_status():
        bot=window.controller.auto_bot;thread=getattr(bot,'thread_auto_bot',None)
        running=bool(thread and thread.is_alive() and not getattr(bot,'is_terminated',False))
        state.setText('●  运行中' if running else '●  待机');map_value.setText(window.selected_map or '未选择地图')
        recording.setText('●  自动录制中' if getattr(bot,'video_writer',None) is not None else '●  录制随挂机启动')
        status.setText(window.tab_statistics.summary.text())
        refresh_map_card()
        role=window.cfg.get('nametag',{}).get('name','')
        role_name.setText(role or '尚未标定')
        badge_text='名字已配置' if role else '待标定'
        if window.property('theme')=='parchment':
            from src.ui.parchment import rich_icon
            badge_text=rich_icon('maple' if role else 'maple-muted',badge_text,18)
        if role_badge.text()!=badge_text:role_badge.setText(badge_text)
        rules=window.cfg.get('potion',{})
        signature=repr(rules)
        if potion_signature[0]!=signature:
            potion_signature[0]=signature
            rows=[]
            for kind,title in [('hp','补血'),('mp','补蓝')]:
                for tier in rules.get(kind,[]):
                    if isinstance(tier,dict):rows.append((title,f"低于 {tier.get('threshold','—')}%",str(tier.get('key') or '不使用').upper()))
            potion_table.setRowCount(len(rows))
            for i,row in enumerate(rows):
                for j,value in enumerate(row):potion_table.setItem(i,j,QTableWidgetItem(value))
                if window.property('theme')=='parchment':
                    from src.ui.parchment import ASSETS
                    potion_table.item(i,0).setIcon(QIcon(str(ASSETS/('hp.png' if row[0]=='补血' else 'mp.png'))))
            potion_table.setIconSize(QSize(26,30))
            style_potion_rows(window.property('theme')=='parchment')
            potion_table.setFixedHeight(46+max(1,len(rows))*43)
        hp=[];mp=[]
        for name,output in [('hp',hp),('mp',mp)]:
            for tier in window.cfg.get('potion',{}).get(name,[]):
                if isinstance(tier,dict) and tier.get('key'):
                    output.append(f"{str(tier['key']).upper()}（低于 {tier.get('threshold','—')}%）")
        potion_keys.setText('补血：'+(' / '.join(hp) or '未设置按键')+'\n补蓝：'+(' / '.join(mp) or '未设置按键'))
        refresh_key_conflicts()
    window.workspace_timer=QTimer(window);window.workspace_timer.timeout.connect(refresh_status);window.workspace_timer.start(1000);refresh_status()
