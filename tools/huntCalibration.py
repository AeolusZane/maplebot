"""Two landmark pairs align a stopped game frame with the reviewed map."""
from PySide6.QtCore import Qt,QPointF
from PySide6.QtGui import QImage,QPixmap,QPainter,QPen,QColor
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QPushButton,QWidget,QScrollArea,QMessageBox
from src.navigation.mob_hunt import calibrate

class PointCanvas(QWidget):
    def __init__(self,image,callback,platforms=()):
        super().__init__();self.callback=callback;self.points=[];self.platforms=platforms
        rgb=image[:,:,::-1].copy();h,w=rgb.shape[:2]
        self.pixmap=QPixmap.fromImage(QImage(rgb.data,w,h,3*w,QImage.Format_RGB888).copy())
        self.factor=min(3.,1000/w);self.setFixedSize(round(w*self.factor),round(h*self.factor))
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:self.callback((event.position().x()/self.factor,event.position().y()/self.factor))
    def paintEvent(self,event):
        p=QPainter(self);p.scale(self.factor,self.factor);p.drawPixmap(0,0,self.pixmap)
        p.setPen(QPen(QColor('#36e1a0'),1/self.factor))
        for a in self.platforms:p.drawLine(QPointF(a['x1'],a['y']),QPointF(a['x2'],a.get('end_y',a['y'])))
        p.setPen(QPen(QColor('#ff5555'),2/self.factor))
        for i,point in enumerate(self.points):
            p.drawEllipse(QPointF(*point),4/self.factor,4/self.factor);p.drawText(QPointF(*point),str(i+1))

class HuntCalibration(QDialog):
    def __init__(self,frame,map_image,graph,player_screen,player_map,parent=None):
        super().__init__(parent);self.setWindowTitle('全屏找怪：画面与地图两点校准');self.resize(1050,850)
        self.result_data=None;self.frame=frame;self.player_screen=player_screen;self.player_map=player_map;self.step=0
        root=QVBoxLayout(self);self.hint=QLabel();self.hint.setWordWrap(True);root.addWidget(self.hint)
        body=QWidget();layout=QVBoxLayout(body);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(body);root.addWidget(scroll)
        layout.addWidget(QLabel('上图：停止挂机时的最后一帧（不是实时画面）'))
        self.game=PointCanvas(frame,lambda p:self.pick('game',p));layout.addWidget(self.game)
        layout.addWidget(QLabel('下图：点相应的平台绿线位置；第二组点需与第一组横向、纵向都拉开距离'))
        self.mini=PointCanvas(map_image,lambda p:self.pick('mini',p),graph['platforms']);layout.addWidget(self.mini)
        b=QPushButton('重新选点');b.clicked.connect(self.reset);root.addWidget(b)
        self.apply=QPushButton('应用校准');self.apply.setEnabled(False);self.apply.clicked.connect(self.finish);root.addWidget(self.apply)
        self.update_hint()
    def update_hint(self):
        self.hint.setText(['1/4：在上图点一个清晰的平台端点（实际站立表面）。','2/4：在下图平台绿线上点同一个端点。','3/4：在上图点另一高度、另一横向位置的平台端点。','4/4：在下图平台绿线上点第二个对应端点。','检查两组对应点，然后应用。'][self.step])
    def pick(self,which,point):
        if self.step>=4 or which!=('game' if self.step%2==0 else 'mini'):return
        canvas=self.game if which=='game' else self.mini;canvas.points.append(point);canvas.update()
        self.step+=1;self.apply.setEnabled(self.step==4);self.update_hint()
    def reset(self):
        self.step=0
        for c in (self.game,self.mini):c.points=[];c.update()
        self.apply.setEnabled(False);self.update_hint()
    def finish(self):
        a,b=self.mini.points;sa,sb=self.game.points
        if abs(a[0]-b[0])<4 or abs(a[1]-b[1])<4 or abs(sa[0]-sb[0])<30 or abs(sa[1]-sb[1])<30:
            QMessageBox.warning(self,'两点太近','请选横向、纵向都明显分开的两处平台端点。');return
        try:self.result_data=calibrate(self.game.points,self.mini.points,self.player_screen,self.player_map,self.frame.shape)
        except ValueError as exc:QMessageBox.warning(self,'校准失败',str(exc));return
        self.accept()
