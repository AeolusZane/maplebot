"""Asset-backed parchment skin; text and interaction remain native Qt widgets."""
from pathlib import Path
from html import escape
from functools import lru_cache
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QLabel

SOURCE_ASSETS = Path(__file__).resolve().parents[2] / 'assets' / 'ui' / 'parchment'
ASSETS = SOURCE_ASSETS / 'runtime'

@lru_cache(maxsize=32)
def asset_icon(name):
    return QIcon(str(ASSETS / f'{name}.png'))

@lru_cache(maxsize=32)
def asset_pixmap(name, width, height):
    return QPixmap(str(ASSETS / f'{name}.png')).scaled(width,height,Qt.KeepAspectRatio,Qt.SmoothTransformation)

def rich_icon(name, text, size=24):
    return f'<img src="{(ASSETS / (name+".png")).as_posix()}" width="{size}" height="{size}"> &nbsp;{text}'

class PotionResultLabel(QLabel):
    """Decorate real recognition text without changing the recognition callback."""
    def setText(self, text):
        self.raw_text=text
        if self.property('parchment'):
            text=escape(text).replace('\n','<br>')
            text=text.replace('血量',rich_icon('hp','血量',25)).replace('魔法',rich_icon('mp','魔法',25))
        super().setText(text)


def stylesheet():
    def url(name):
        return (ASSETS / f'{name}.png').as_posix()
    return """
QWidget { color:#493523; font-size:14px; }
QMainWindow, QWidget#workspace { background:#e8d6ad; background-image:url("%s"); background-origin:border; background-clip:border; }
QWidget#sidebar { background:transparent; border-right:1px solid #b7a07a; }
QWidget#sidebar QLabel { color:#60472c; }
QFrame#brandPanel { background:transparent; border:none; }
QWidget#sidebar QLabel#brand { color:#493523; font-family:'Georgia'; font-size:19px; }
QLabel#pageTitle { color:#392716; font-family:'SimSun'; font-size:32px; font-weight:700; }
QLabel#sectionTitle { color:#4e3420; font-family:'SimSun'; font-size:20px; font-weight:700; }
QLabel#muted { color:#806b4e; font-size:13px; }
QLabel#metric { color:#695333; }
QLabel#badge { background:#e4d5af; color:#5d5137; border:1px solid #b8a077; }
QFrame#card, QGroupBox, QFrame#emptyChart {
 background:#f3e7c9; border:8px solid transparent; border-radius:0;
 border-image:url("%s") 40 40 40 40 stretch stretch;
}
QGroupBox#settingsSection { padding:0; margin-top:0; }
QFrame#settingsDivider { color:#c2aa7e; }
QListWidget#navigation { color:#4e3420; background:transparent; border:none; font-family:'SimSun';font-size:20px; }
QListWidget#navigation::item { color:#4e3420; border-radius:0; border-bottom:1px solid #c1a675; height:40px; padding-left:12px; }
QListWidget#navigation::item:selected {
 color:#fff0c7; background:#4e5c36; border:4px solid transparent;
 border-image:url("%s") 24 24 24 24 stretch stretch;
}
QListWidget#navigation::item:hover { background:rgba(218,190,129,35); }
QPushButton {
 color:#493523; background:#eeddb7; border:8px solid transparent; border-radius:0;
 border-image:url("%s") 60 60 60 60 stretch stretch; padding:3px 9px;
}
QPushButton:hover { color:#2c3d20; border-color:#ad8749; }
QPushButton:pressed { color:#2b271c; border-color:#6b542c; padding:6px 10px 4px 12px; }
QPushButton:disabled { border-image:none; background:#ded3b9; color:#9c907b; border-color:#c5b895; }
QPushButton#primary { border-image:url("%s") 24 24 24 24 stretch stretch; color:#fff0c7; background:#4e5c36; }
QPushButton#settingsManagerToggle { text-align:left; font-family:'SimSun'; font-size:20px; padding:9px 18px; }
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QKeySequenceEdit {
 background:#f6edda; color:#493523; border:1px solid #b6a07c; border-radius:3px;
 selection-background-color:#d3bd87;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border:1px solid #627043; }
QLabel#potionKey { background:#f6edda; border:2px solid #a78b54; border-radius:4px; margin:6px 12px; padding:3px; color:#493523; font-family:'Georgia'; font-weight:600; }
QListWidget, QTableWidget { background:#f3e8cd; color:#493523; border:1px solid #c2ab80; alternate-background-color:#ece0c2; selection-background-color:#d5c395; selection-color:#382b1e; }
QHeaderView::section { background:#e4d3ad; color:#715737; border-bottom:1px solid #c2ab80; }
QPlainTextEdit { background:#f3e8cd; color:#59442c; border:1px solid #c2ab80; }
QTabBar::tab { background:#e4d3ad; color:#715737; }
QTabBar::tab:selected { background:#f3e8cd; color:#4f6037; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background:#b39a6b; }
QSplitter::handle { background:#c7b28a; }
QToolTip, QMenu, QDialog { background:#f3e8cd; color:#493523; border:1px solid #b6a07c; }
QMenu::item:selected { background:#d5c395; }
QCheckBox { color:#59442c; spacing:7px; }
QCheckBox::indicator { width:44px; height:26px; border:none; background:transparent; image:url("%s"); }
QCheckBox::indicator:checked { image:url("%s"); }
QWidget#workspace { border:32px solid transparent; border-image:url("%s") 160 160 160 160 stretch stretch; }
""" % (url('paper-v2'), url('panel'), url('selected'), url('button-v2'), url('selected'),
       (SOURCE_ASSETS/'toggle-off.svg').as_posix(), (SOURCE_ASSETS/'toggle-on.svg').as_posix(),url('frame-v2')) + f'''
QLineEdit[keyCap="true"], QLabel#potionKey {{
 border-image:none; border:2px solid #a78b54; border-radius:4px;
 background:#f8eed8; color:#493523; padding:2px 5px; min-height:18px;
}}
QLabel#potionKey {{ margin:3px 6px; }}
QKeySequenceEdit[keyCap="true"] {{ border:none; background:transparent; padding:0; }}
'''
