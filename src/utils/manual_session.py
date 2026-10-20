"""Passive, bounded manual session recording. No automation/input dependencies."""
import json
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
import cv2


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
        default=lambda v: v.item() if hasattr(v, 'item') else str(v)), encoding='utf-8')


def record_session(folder, cfg, map_name, capture, stop, progress, duration=600):
    """10fps indexed video + 2fps original JPEGs; inference is deliberately absent."""
    from src.utils.mapping_capture import client_frame
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    (folder/'frames').mkdir()
    from src.utils.session_provenance import save_provenance
    provenance = save_provenance(folder, cfg)
    origin_ns = time.monotonic_ns()
    started = origin_ns / 1e9
    manifest = dict(schema_version=1, mode='manual_capture', map_name=map_name,
        started_at=datetime.now().isoformat(), duration_target=duration,
        cfg=cfg, detection_during_capture=False, automatic_input=False,
        input_recording=False, video_fps=10, screenshot_fps=2,
        coordinates='offline analysis: game_screen_px and minimap_local_px',
        status='recording')
    manifest['origin_monotonic_ns'] = origin_ns
    manifest['provenance'] = provenance
    from src.utils.paths import APP_ROOT
    from src.utils.common import load_yaml
    registry = load_yaml(str(Path(APP_ROOT)/'config/config_data.yaml')) or {}
    manifest['detection_registry'] = {
        'map_mobs_mapping': {map_name: (registry.get('map_mobs_mapping', {}) or {}).get(map_name, [])},
        'map_monster_thresholds': registry.get('map_monster_thresholds', {}) or {}}
    write_json(folder/'manifest.json', manifest)
    writer = None
    video_tmp = None
    count = shots = stale = 0
    last_source = last_shot = -1
    reason = 'duration_complete'
    event_log = monitor = None
    try:
        from src.utils.input_evidence import EventLog, HumanMonitor
        event_log = EventLog(folder, origin_ns)
        hwnd = getattr(capture, 'window_hwnd', None)
        if hwnd:
            monitor = HumanMonitor(event_log, hwnd, cfg)
            manifest['input_recording'] = True
        else:
            manifest['input_recording_error'] = 'No target window handle; input not recorded'
        write_json(folder/'manifest.json', manifest)
        import tempfile
        with (folder/'frames.jsonl').open('w', encoding='utf-8') as stream:
            next_tick = started
            while time.monotonic()-started < duration:
                if stop.is_set():
                    reason = 'user_stop'; break
                now = time.monotonic()
                if now < next_tick:
                    stop.wait(min(.1, next_tick-now)); continue
                next_tick = now+.1
                if shutil.disk_usage(folder).free < 1024**3:
                    reason = 'low_disk_space'; break
                if hasattr(capture,'get_frame_with_timestamp'):
                    frame, source = capture.get_frame_with_timestamp()
                else:
                    frame = capture.get_frame()
                    source = capture.frame_time
                elapsed = now-started
                if frame is None or now-source > 1 or source == last_source:
                    stale += 1
                    progress(None, f'采集中 {elapsed:.0f}/{duration} 秒 | 等待新画面（请勿最小化游戏）')
                    continue
                last_source = source
                frame = client_frame(frame, cfg)
                if writer is None:
                    # ASCII temporary path avoids OpenCV's Windows Unicode-path limitation.
                    handle, video_tmp = tempfile.mkstemp(suffix='.mp4', prefix='manual_capture_')
                    import os
                    os.close(handle)
                    writer = cv2.VideoWriter(video_tmp, cv2.VideoWriter_fourcc(*'mp4v'),
                                             10, (frame.shape[1], frame.shape[0]))
                    if not writer.isOpened():
                        raise RuntimeError('无法创建录像文件')
                    first_frame = frame.copy()
                writer.write(frame)
                entry = dict(frame_id=count, video_index=count, t=elapsed,
                             source_monotonic=source, captured_monotonic=now)
                entry.update(t_ns=int((now-started)*1e9),
                             monotonic_ns=int(now*1e9),
                             source_monotonic_ns=int(source*1e9))
                event_log.emit('video_frame', frame_id=count, video_index=count,
                               source_monotonic_ns=int(source*1e9),
                               monotonic_ns=int(source*1e9),
                               recorded_monotonic_ns=time.monotonic_ns())
                if now-last_shot >= .5:
                    last_shot=now
                    name=f'frames/{count:06d}.jpg'
                    ok, encoded=cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY,95])
                    if not ok:raise RuntimeError('截图编码失败')
                    encoded.tofile(str(folder/name))
                    entry['image']=name;shots+=1
                    progress(frame, f'采集中 {elapsed:.0f}/{duration} 秒 | 截图 {shots} 张 | 不识别、不自动按键')
                stream.write(json.dumps(entry)+'\n');stream.flush()
                count+=1
                last_frame=frame.copy()
            if count:
                for name, frame in [('start.jpg',first_frame),('end.jpg',last_frame)]:
                    ok, encoded=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,95])
                    if ok:encoded.tofile(str(folder/name))
    except Exception as exc:
        reason='error';manifest['error']=str(exc)
    finally:
        if monitor is not None:monitor.close()
        if event_log is not None:event_log.close()
        if writer is not None:writer.release()
        if video_tmp and Path(video_tmp).exists():
            try:
                shutil.move(video_tmp,str(folder/'raw.mp4'))
            except OSError as exc:
                reason='error'
                manifest['error']=f'录像转存失败：{exc}'
                manifest['recoverable_video_path']=video_tmp
        manifest.update(status='finished' if reason!='error' else 'error',
            stop_reason=reason, duration_actual=time.monotonic()-started,
            video_frames=count, screenshots=shots, stale_capture_ticks=stale,
            video_timing='10fps encoded frames; frames.jsonl is authoritative for wall-clock timing')
        manifest['event_log_error'] = event_log.error if event_log is not None else None
        manifest['event_log_dropped'] = event_log.dropped if event_log is not None else 0
        write_json(folder/'manifest.json',manifest)
    return manifest


def analyze_session(folder, stop, progress):
    """Offline inference only, on saved 2fps originals; never instantiate the bot."""
    import copy
    from types import SimpleNamespace
    from src.utils.paths import APP_ROOT
    from src.utils.common import load_yaml, get_mask, get_player_location_on_minimap
    from src.utils.mapping_capture import locate_name, minimap_rect
    from src.navigation.map_graph import read_image
    from src.utils.monster_threshold import map_threshold
    from src.ui.monster_test import scan
    folder=Path(folder)
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    cfg=copy.deepcopy(manifest['cfg']);map_name=manifest['map_name']
    data=manifest.get('detection_registry')
    if data is None:data=load_yaml(str(Path(APP_ROOT)/'config/config_data.yaml')) or {}
    names=(data.get('map_mobs_mapping',{}) or {}).get(map_name,[])
    templates={}
    for name in names:
        images=[]
        for path in (Path(APP_ROOT)/'monster'/name).glob(f'{name}*.png'):
            tpl=read_image(path)
            if tpl is None:continue
            for image in (tpl,cv2.flip(tpl,1)):
                images.append((image,get_mask(image,(0,255,0))))
        if images:templates[name]=images
    threshold=map_threshold(data,map_name,cfg['monster_detect']['diff_thres'])
    cfg['monster_detect']['effective_diff_thres']=threshold
    namepath=Path(APP_ROOT)/'nametag'/f"{cfg.get('nametag',{}).get('name','')}.png"
    nametag=read_image(namepath) if namepath.exists() else None
    entries=[json.loads(line) for line in (folder/'frames.jsonl').read_text().splitlines()]
    entries=[e for e in entries if e.get('image')]
    output=folder/('analysis_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    output.mkdir(); (output/'annotated').mkdir()
    processed=0
    with (output/'observations.jsonl').open('w',encoding='utf-8') as stream:
        for entry in entries:
            if stop.is_set():break
            if shutil.disk_usage(folder).free < 1024**3:raise RuntimeError('剩余空间不足 1GB，停止录后识别')
            frame=read_image(folder/entry['image']);canvas=frame.copy()
            rect,score=locate_name(frame,nametag,cfg)
            point=None;mini=None;player=None
            if rect:
                x,y,w,h=map(int,rect)
                cv2.rectangle(canvas,(x,y),(x+w,y+h),(0,255,0),2)
                offset=cfg.get('nametag',{}).get('offset',[0,30])
                player=(x+w//2,y-offset[1]);cv2.circle(canvas,player,5,(0,0,255),2)
            try:
                mini=minimap_rect(frame);x,y,w,h=mini
                point=get_player_location_on_minimap(frame[y:y+h,x:x+w],cfg['minimap']['player_color'])
                cv2.rectangle(canvas,(x,y),(x+w,y+h),(255,255,0),1)
                if point is not None:cv2.circle(canvas,(x+int(point[0]),y+int(point[1])),4,(0,0,255),2)
            except ValueError:pass
            mobs=[]
            if templates:
                height=cfg.get('ui_coords',{}).get('ui_y_start',frame.shape[0])
                snapshot=SimpleNamespace(img_frame=frame[:height].copy(),cfg=cfg,
                    monsters_info=templates,loc_player=(-10000,-10000))
                _,mobs,*_=scan(snapshot,threshold,entry['t'],0)
                for m in mobs:
                    x,y=map(int,m['position']);w,h=map(int,m['size'])
                    cv2.rectangle(canvas,(x,y),(x+w,y+h),(0,200,255),2)
            record=dict(frame_id=entry['frame_id'],t=entry['t'],image=entry['image'],
                name_box=rect,name_score=score,player_screen_estimate=player,
                minimap_rect=mini,minimap_player_local=point,monsters=mobs)
            stream.write(json.dumps(record,ensure_ascii=False,default=lambda v:v.item() if hasattr(v,'item') else str(v))+'\n')
            ok,encoded=cv2.imencode('.jpg',canvas,[cv2.IMWRITE_JPEG_QUALITY,90])
            if ok:encoded.tofile(str(output/'annotated'/Path(entry['image']).name))
            processed+=1
            progress(canvas,f'录后识别 {processed}/{len(entries)}（不触发按键）')
    write_json(output/'summary.json',dict(processed=processed,total=len(entries),
        cancelled=stop.is_set(),threshold=threshold,monster_types=list(templates),
        name_template_available=nametag is not None,
        note='离线预测，不是真值；坐标是屏幕/小地图局部坐标，非整图平台坐标。'))
    return output
