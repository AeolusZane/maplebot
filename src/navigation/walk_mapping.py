"""Geometry acquisition from observed minimap markers; never sends input."""
import numpy as np
from .map_graph import propose_edges, teleport_regions


def endpoint_segment(start, end, kind, identity):
    a, b = [tuple(int(round(v)) for v in point) for point in (start,end)]
    if kind == 'ropes':
        if abs(a[0]-b[0]) > 3 or abs(a[1]-b[1]) < 3:
            raise ValueError('绳索两端需在同一竖线上，且高度差至少 3 个小地图像素。')
        return dict(id=identity,x=round((a[0]+b[0])/2),y1=min(a[1],b[1]),
                    y2=max(a[1],b[1]),source='recorded_endpoints')
    a,b=sorted((a,b))
    if b[0]-a[0]<2:
        raise ValueError('平台两端水平距离至少需要 2 个小地图像素。')
    return dict(id=identity,x1=a[0],x2=b[0],y=a[1],end_y=b[1],source='recorded_endpoints')


def fit_segment(points, kind, identity):
    pts = np.asarray(points, dtype=float)
    if len(pts) < 8:
        raise ValueError('有效采样不足，请继续移动后再确认。')
    x, y = pts[:, 0], pts[:, 1]
    if kind == 'ropes':
        cx = float(np.median(x))
        if np.max(np.abs(x-cx)) > 3 or np.ptp(y) < 5:
            raise ValueError('请仅录制爬绳过程：保持在同一条绳索上，爬过至少 5 个小地图像素。')
        return dict(id=identity, x=round(cx), y1=round(float(y.min())),
                    y2=round(float(y.max())), source='recorded')
    if np.ptp(x) < 5:
        raise ValueError('平台录制太短，请从平台一端走到另一端。')
    # Median per column suppresses marker jitter without weighting stationary time.
    xs = np.unique(x)
    ys = np.array([np.median(y[x == xx]) for xx in xs])
    slope, intercept = np.polyfit(xs, ys, 1)
    if np.max(np.abs(ys-(slope*xs+intercept))) > 2:
        raise ValueError('轨迹不是同一段平面或斜坡。请分段录制，录平台时不要跳跃或瞬移。')
    if abs(slope) > 1:
        raise ValueError('轨迹过陡，请检查是否在爬绳或发生跌落。')
    a, b = float(xs.min()), float(xs.max())
    return dict(id=identity, x1=round(a), x2=round(b),
                y=round(float(slope*a+intercept)),
                end_y=round(float(slope*b+intercept)), source='recorded')


def build_connections(graph):
    propose_edges(graph)
    for edge in graph['edges']:
        # A horizontal teleport must actually land on the destination surface.
        edge['enabled'] = edge['kind'] != 'teleport' or bool(teleport_regions(graph, edge))
    return graph
