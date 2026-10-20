"""Persistent experience charts shared by statistics and map debug tabs."""
from datetime import datetime
import math
from PySide6.QtCore import Qt, QMargins, Signal, QSize
from PySide6.QtGui import QPainter,QFont,QFontDatabase,QColor,QPen
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QFrame,QDialog,QPushButton,QToolTip
from PySide6.QtGui import QCursor
from PySide6.QtCharts import QChart,QChartView,QBarSet,QBarSeries,QCategoryAxis,QValueAxis,QLineSeries
from src.utils.experience_history import ExperienceHistory,efficiency


class AnalyticsChartView(QChartView):
    def sizeHint(self):
        return QSize(460,300)


def sample_axis(count,offset=0):
    """At most five horizontal labels; precise timestamps are in hover details."""
    axis=QCategoryAxis();axis.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
    axis.setStartValue(-1)
    step=max(1,math.ceil(max(1,count-1)/4))
    positions=list(range(0,count,step))
    if count and (not positions or positions[-1]!=count-1):
        if len(positions)>=5:positions[-1]=count-1
        else:positions.append(count-1)
    for i in positions:axis.append(str(i+1),i+offset)
    axis.setRange(offset-.5,max(offset+.5,count-1+offset+.5))
    axis.setTitleText('采样序号');axis.setLabelsAngle(0)
    return axis


def value_axis(maximum,title):
    axis=QValueAxis();axis.setTitleText(title);axis.setLabelFormat('%.0f')
    maximum=max(1,maximum)
    magnitude=10**math.floor(math.log10(maximum))
    interval=max(1,math.ceil(maximum/4/magnitude*10)*magnitude/10)
    axis.setRange(0,interval*4);axis.setTickCount(5)
    return axis

class ExperienceCharts(QWidget):
    def __init__(self,map_getter=None,compact=False,history=None):
        super().__init__();self.history=history or ExperienceHistory();self.map_getter=map_getter;self.compact=compact
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
        self.setFont(QFont('Microsoft YaHei',9))
        self.rows=[];self.current_map=None
        layout=QVBoxLayout(self);layout.setContentsMargins(2,2,2,2)
        filters=QHBoxLayout();layout.addLayout(filters)
        self.maps=QComboBox();self.levels=QComboBox()
        filters.addWidget(QLabel('地图'));filters.addWidget(self.maps);filters.addWidget(QLabel('等级'));filters.addWidget(self.levels)
        self.maps.setMinimumWidth(170);self.maps.setMaximumWidth(240)
        self.levels.setMinimumWidth(100);self.levels.setMaximumWidth(140);filters.addStretch()
        self.summary=QLabel();self.summary.setWordWrap(True);layout.addWidget(self.summary)
        self.metrics=[]
        if not compact:
            metrics=QHBoxLayout();metrics.setSpacing(12);layout.addLayout(metrics)
            for title in ('平均经验 / 分钟','有效采样时长','历史经验增长'):
                tile=QFrame();tile.setObjectName('card');body=QVBoxLayout(tile);body.setContentsMargins(16,12,16,12)
                caption=QLabel(title);caption.setObjectName('muted');body.addWidget(caption)
                value=QLabel('—');value.setObjectName('metric');body.addWidget(value);self.metrics.append(value);metrics.addWidget(tile,1)
            self.summary.hide()
        chart_layout=QVBoxLayout() if compact else QHBoxLayout();layout.addLayout(chart_layout,1)
        self.chart_layout=chart_layout
        self.bars=AnalyticsChartView();self.line=AnalyticsChartView()
        self.empty=QWidget()
        empty_layout=QHBoxLayout(self.empty);empty_layout.setContentsMargins(0,0,0,0);empty_layout.setSpacing(16)
        self.empty_cards=[]
        titles=('区间经验效率',) if compact else ('采样经验增量','区间经验效率')
        for title in titles:
            tile=QFrame();tile.setObjectName('emptyChart');tile.setMinimumHeight(135 if compact else 180)
            body=QVBoxLayout(tile);body.setContentsMargins(18,16,18,18)
            heading=QLabel(title);heading.setObjectName('sectionTitle');body.addWidget(heading)
            message=QLabel('暂无有效采样\n运行后根据真实采样显示趋势');message.setObjectName('muted')
            message.setAlignment(Qt.AlignCenter);body.addWidget(message,1)
            empty_layout.addWidget(tile,1);self.empty_cards.append(tile)
        self.update_empty_theme()
        layout.addWidget(self.empty,1)
        for view in (self.bars,self.line):
            view.setRenderHint(QPainter.Antialiasing);view.setMinimumHeight(135 if compact else 180)
            view.setToolTip('悬停在柱形或折线节点上查看完整时间与数值。')
            view.setCursor(Qt.ArrowCursor)
            chart_layout.addWidget(view)
        self.comparison=QLabel();self.comparison.setWordWrap(True);layout.addWidget(self.comparison)
        self.maps.currentTextChanged.connect(self.refresh_levels);self.levels.currentIndexChanged.connect(self.render)
        self.reload()

    def update_empty_theme(self):
        from src.ui.theme import colors
        c=colors(self)
        if c['background']=='#e8d6ad':
            self.empty.setStyleSheet('')
            return
        self.empty.setStyleSheet(f"QFrame#emptyChart {{background:{c['surface']};border:1px solid {c['border']};border-radius:9px;}}")

    def show_sample(self,active,row):
        if not active:QToolTip.hideText();return
        gain=row['gain'];duration=row['duration']
        QToolTip.showText(QCursor.pos(),datetime.fromtimestamp(row['time']).strftime('%Y-%m-%d %H:%M:%S')+
            f"\n经验增量：{gain:,}\n采样区间：{duration/60:.1f} 分钟\n区间效率：{gain*60/duration:,.0f} EXP/分钟",self)

    def reload(self):
        self.rows=self.history.rows()
        current=self.maps.currentText();requested=self.map_getter() if self.map_getter else None
        if requested and requested!=self.current_map:current=requested;self.current_map=requested
        names=sorted({r['map'] for r in self.rows}|({requested} if requested else set()))
        self.maps.blockSignals(True);self.maps.clear();self.maps.addItems(names or ['暂无记录'])
        if current in names:self.maps.setCurrentText(current)
        self.maps.blockSignals(False);self.refresh_levels()

    def refresh_levels(self):
        old=self.levels.currentData();levels=sorted({r['level'] for r in self.rows if r['map']==self.maps.currentText() and r['level'] is not None})
        unknown=any(r['level'] is None for r in self.rows if r['map']==self.maps.currentText())
        self.levels.blockSignals(True);self.levels.clear()
        for level in levels:self.levels.addItem(f'Lv.{level}',level)
        if unknown:self.levels.addItem('等级未识别',None)
        i=self.levels.findData(old)
        if i>=0:self.levels.setCurrentIndex(i)
        elif levels:self.levels.setCurrentIndex(len(levels)-1)
        self.levels.blockSignals(False);self.render()

    def render(self,*args):
        level=self.levels.currentData();name=self.maps.currentText()
        rows=[r for r in self.rows if r['map']==name and r['level']==level]
        total,duration,rate=efficiency(rows)
        if self.metrics:
            for widget,value in zip(self.metrics,('—' if rate is None else f'{rate:,.0f}',f'{duration/60:.1f} 分钟' if duration else '—',f'{total:,}' if duration else '—')):widget.setText(value)
        self.summary.setText('等待有效经验采样' if rate is None else f'历史有效收益 {total:,} EXP / {duration/60:.1f} 分钟\n平均 {rate:,.0f} EXP/分钟 · {rate*10:,.0f} EXP/10分钟')
        samples=rows[-(16 if self.compact else 40):]
        expanded=self.property('expanded')
        bars=QChart();bars.setTitle('采样经验增量');bars.legend().hide()
        barset=QBarSet('EXP');barset.setColor(QColor('#70a3f5'));barset.setBorderColor(QColor('#70a3f5'))
        valid=[r for r in samples if r['gain'] is not None and r['duration']>0]
        self.layout().setStretchFactor(self.chart_layout,1 if valid else 0)
        self.empty.setVisible(not valid)
        for i,tile in enumerate(self.empty_cards):
            tile.setVisible(not expanded or (i==0 if expanded=='bars' else i==len(self.empty_cards)-1))
        self.bars.setVisible(bool(valid) and not self.property('overview') and expanded!='line')
        self.line.setVisible(bool(valid) and expanded!='bars')
        for i,r in enumerate(valid):
            barset.append(r['gain'])
        barset.hovered.connect(lambda active,index:self.show_sample(active,valid[index]))
        series=QBarSeries();series.append(barset);bars.addSeries(series)
        axis=sample_axis(len(valid))
        y=value_axis(max([r['gain'] for r in valid]+[1]),'EXP')
        bars.addAxis(axis,Qt.AlignBottom);bars.addAxis(y,Qt.AlignLeft);series.attachAxis(axis);series.attachAxis(y)
        line=QChart();line.setTitle('区间效率 · EXP/分钟');line.legend().hide()
        segment=None;previous=None;maxrate=1
        for i,r in enumerate(samples):
            if r['gain'] is None or r['duration']<=0:segment=None;previous=None;continue
            if segment is None or previous!=r['run']:
                segment=QLineSeries();segment.setPointsVisible(True);line.addSeries(segment)
                segment.hovered.connect(lambda point,active:self.show_sample(active,samples[int(round(point.x()))-1]))
            value=r['gain']*60/r['duration'];segment.append(i+1,value);maxrate=max(maxrate,value);previous=r['run']
        xaxis=sample_axis(len(samples),1)
        yaxis=value_axis(maxrate,'EXP/分钟')
        line.addAxis(xaxis,Qt.AlignBottom);line.addAxis(yaxis,Qt.AlignLeft)
        for segment in line.series():
            segment.attachAxis(xaxis);segment.attachAxis(yaxis);segment.setPen(QPen(QColor('#246deb'),2))
        for view,chart in ((self.bars,bars),(self.line,line)):
            chart.setFont(self.font());chart.setTitleFont(self.font())
            chart.setBackgroundRoundness(8);chart.setBackgroundBrush(QColor('white'));chart.setMargins(QMargins(8,8,8,8))
            view.setStyleSheet('background:transparent;border:none;')
            for a in chart.axes():
                a.setLabelsFont(self.font());a.setTitleFont(self.font())
                a.setLabelsColor(QColor('#7386a1'));a.setGridLineColor(QColor('#e8eef7'))
            old=view.chart();view.setChart(chart);old.deleteLater()
            from src.ui.theme import style_chart
            style_chart(view)
        summaries=[]
        if level is not None:
            for other in sorted({r['map'] for r in self.rows if r['level']==level}):
                _,seconds,avg=efficiency([r for r in self.rows if r['map']==other and r['level']==level])
                if avg is not None:summaries.append((avg,other,seconds))
        self.comparison.setText('同等级地图对比：'+('；'.join(f'{m} {v:,.0f}/分钟（{s/60:.1f}分钟样本）' for v,m,s in sorted(summaries,reverse=True)) or '暂无可比数据'))
