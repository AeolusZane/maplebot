"""Shared light/dark tokens for widgets and native Qt charts."""
from PySide6.QtGui import QColor, QPalette, QBrush
from PySide6.QtWidgets import QApplication

LIGHT = dict(background='#f5f8fd',surface='#ffffff',raised='#edf3fb',border='#d3deed',text='#263650',muted='#7386a1',grid='#e8eef7',accent='#246deb')
DARK = dict(background='#141b27',surface='#1e2838',raised='#263449',border='#35465e',text='#e0e8f5',muted='#9bacc3',grid='#334258',accent='#7aabff')
PARCHMENT = dict(background='#e8d6ad',surface='#f3e8cd',raised='#e4d3ad',border='#b6a07c',text='#493523',muted='#806b4e',grid='#ded0ad',accent='#687b45')


def colors(widget):
    if QApplication.instance().property('appearance') == 'parchment':
        return PARCHMENT
    return DARK if widget.palette().color(QPalette.Window).lightness()<128 else LIGHT


def stylesheet(base,dark):
    if not dark:return base+'\nQDialog, QMenu {background:#f5f8fd;} QLabel#mapName {font-size:20px;font-weight:600;} '
    replacements={
        '#f5f8fd':'#141b27','#eaf2fc':'#192436','#dae5f3':'#2e3e55',
        '#263650':'#e0e8f5','#152b4d':'#ecf2ff','#172a46':'#ecf2ff',
        '#7a8ba4':'#9bacc3','#243b5b':'#c7d9f3','#1e487d':'#a7c8ff',
        '#e7f0ff':'#253d60','#2469d5':'#a1c4ff','#e0e8f3':'#334258',
        '#d9e9ff':'#2b4870','#1565dc':'#b7d3ff','#e0edfc':'#263951',
        '#d3deed':'#35465e','#eff5ff':'#2a3b53','#9cbdeb':'#7097c9',
        '#deebff':'#314e75','#a0aec0':'#73859e','#f7f9fc':'#1a2433',
        '#e3e9f2':'#2f3b50','#d1ddeb':'#42536d','#dbeaff':'#36577e',
        '#e8f1ff':'#29486b','#1b55a2':'#d7e7ff','#f8fafd':'#1a2535',
        '#f3f7fc':'#253247','#607592':'#acbdd3','#e4ebf5':'#334258',
        '#edf2f8':'#334258','#52647f':'#b8c9e0','#e6edf5':'#334258',
        '#edf3fb':'#263449','#e3ebf6':'#334258','#9bbbe9':'#7097c9','#c5d3e5':'#4c607c'}
    import re
    base=re.sub(r'#[0-9a-fA-F]{6}\b',lambda m:replacements.get(m.group().lower(),m.group()),base)
    base=base.replace('background: white','background: #1e2838').replace('background: #fff;','background: #1e2838;')
    return base+'\nQDialog, QMenu {background:#141b27;} QMenu::item:selected {background:#2b4870;} QLabel#mapName {font-size:20px;font-weight:600;} '


def set_palette(dark, parchment=False):
    QApplication.instance().setProperty('appearance', 'parchment' if parchment else ('dark' if dark else 'light'))
    c=PARCHMENT if parchment else DARK if dark else LIGHT
    palette=QPalette()
    for role,key in [(QPalette.Window,'background'),(QPalette.WindowText,'text'),(QPalette.Base,'surface'),(QPalette.AlternateBase,'raised'),(QPalette.Text,'text'),(QPalette.Button,'surface'),(QPalette.ButtonText,'text'),(QPalette.ToolTipBase,'surface'),(QPalette.ToolTipText,'text'),(QPalette.Highlight,'raised'),(QPalette.HighlightedText,'text'),(QPalette.PlaceholderText,'muted')]:
        palette.setColor(role,QColor(c[key]))
    QApplication.instance().setPalette(palette)


def style_chart(view):
    from PySide6.QtCharts import QBarSeries,QLineSeries
    from PySide6.QtGui import QPen
    c=colors(view);chart=view.chart()
    parchment=c is PARCHMENT
    for series in chart.series():
        if isinstance(series,QBarSeries):
            for bars in series.barSets():
                bars.setColor(QColor('#718052' if parchment else '#70a3f5'))
                bars.setBorderColor(QColor('#59663e' if parchment else '#70a3f5'))
        elif isinstance(series,QLineSeries):
            series.setPen(QPen(QColor('#a87938' if parchment else '#246deb'),2))
    chart.setBackgroundBrush(QBrush(QColor(c['surface'])))
    chart.setTitleBrush(QBrush(QColor(c['text'])))
    for axis in chart.axes():
        axis.setLabelsColor(QColor(c['muted']));axis.setGridLineColor(QColor(c['grid']))
        axis.setLinePenColor(QColor(c['border']));axis.setTitleBrush(QBrush(QColor(c['muted'])))
