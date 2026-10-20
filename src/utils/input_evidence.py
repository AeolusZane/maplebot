"""Timestamped passive input and automation-call evidence; never sends input."""
import json
import queue
import threading
import time
from pathlib import Path


def normalize(key):
    key=str(key).lower().removeprefix('key.')
    return {'ctrl_l':'ctrl','ctrl_r':'ctrl','control':'ctrl','alt_l':'alt',
            'alt_r':'alt','shift_l':'shift','shift_r':'shift','page_up':'pageup',
            'page_down':'pgdn','pgdown':'pgdn','esc':'esc'}.get(key,key)


def allowed_keys(cfg):
    keys={'left','right','up','down'}
    keys.update(normalize(v) for v in cfg.get('key',{}).values() if isinstance(v,str) and v)
    keys.update(normalize(v) for v in cfg.get('buff_skill',{}).get('keys',[]) if isinstance(v,str))
    def walk(value):
        if isinstance(value,dict):
            for k,v in value.items():
                if k=='key' and isinstance(v,str) and v:keys.add(normalize(v))
                elif isinstance(v,(dict,list)):walk(v)
        elif isinstance(value,list):
            for v in value:walk(v)
    for section in ('potions','potion','auto_potion'):
        walk(cfg.get(section,{}))
    return keys


class EventLog:
    def __init__(self,folder,origin_ns=None):
        self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True)
        self.origin_ns=time.monotonic_ns() if origin_ns is None else origin_ns
        self.queue=queue.Queue(32768);self.lock=threading.Lock()
        self.closed=False;self.dropped=0;self.sequence=0;self.error=None
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()

    def emit(self,kind,**fields):
        with self.lock:
            if self.closed:return None
            self.sequence+=1
            stamp=fields.pop('monotonic_ns',time.monotonic_ns())
            event=dict(event_id=self.sequence,kind=kind,monotonic_ns=stamp,t_ns=stamp-self.origin_ns,**fields)
            try:self.queue.put_nowait(event)
            except queue.Full:self.dropped+=1
            return self.sequence

    def run(self):
        try:
            with (self.folder/'events.jsonl').open('w',encoding='utf-8') as f:
                while not self.closed or not self.queue.empty():
                    try:event=self.queue.get(timeout=.05)
                    except queue.Empty:continue
                    f.write(json.dumps(event,ensure_ascii=False,default=str)+'\n')
        except Exception as exc:self.error=str(exc)

    def close(self):
        with self.lock:self.closed=True
        self.thread.join()
        (self.folder/'event_quality.json').write_text(json.dumps(dict(
            origin_monotonic_ns=self.origin_ns,dropped=self.dropped,error=self.error,
            skill_success='unknown_until_visual_review'),ensure_ascii=False,indent=2),encoding='utf-8')


class HumanState:
    def __init__(self,log,allowed):
        self.log=log;self.allowed=allowed;self.held={};self.focus=None;self.lock=threading.RLock()

    def update_focus(self,focused):
        with self.lock:
            if focused!=self.focus:
                self.log.emit('focus',focused=focused)
                if not focused:self.cancel('focus_lost')
                self.focus=focused

    def key(self,key,down,focused,physical=None):
        with self.lock:
            self.update_focus(focused)
            key=normalize(key)
            if not focused or key not in self.allowed:return
            physical=physical or key
            now=time.monotonic_ns();previous=self.held.get(physical)
            if down:
                if not previous:self.held[physical]=(key,now)
                self.log.emit('human_key',key=key,physical_key=physical,
                    edge='repeat' if previous else 'down',monotonic_ns=now,
                    focused=True,held=sorted(v[0] for v in self.held.values()),
                    source='human_observed',skill_success='unknown')
            else:
                self.held.pop(physical,None)
                self.log.emit('human_key',key=key,physical_key=physical,edge='up',
                    monotonic_ns=now,focused=True,held=sorted(v[0] for v in self.held.values()),
                    held_duration_ns=now-previous[1] if previous else None,
                    unmatched_release=previous is None,source='human_observed')

    def cancel(self,reason):
        with self.lock:
            for physical,(key,started) in self.held.items():
                self.log.emit('hold_truncated',key=key,physical_key=physical,
                    held_duration_ns=time.monotonic_ns()-started,reason=reason)
            self.held.clear()

    def snapshot(self):
        with self.lock:
            now=time.monotonic_ns()
            self.log.emit('held_snapshot',focused=self.focus,monotonic_ns=now,
                held=[dict(key=k,physical_key=p,held_duration_ns=now-t) for p,(k,t) in self.held.items()])


class HumanMonitor:
    def __init__(self,log,hwnd,cfg):
        from pynput import keyboard
        import win32gui
        self.log=log;self.hwnd=hwnd;self.stop_event=threading.Event()
        self.state=HumanState(log,allowed_keys(cfg))
        self.foreground=lambda:bool(hwnd) and win32gui.GetForegroundWindow()==hwnd
        def event(key,down):
            physical=getattr(key,'name',None) or getattr(key,'char',None)
            vk=getattr(key,'vk',None)
            if not getattr(key,'name',None) and vk is not None and 48<=vk<=90:
                physical=chr(vk).lower()
            if physical:self.state.key(physical,down,self.foreground(),physical=physical)
        def event_filter(msg,data):
            # Ignore Windows-marked injected events; kernel-driver inputs cannot always be distinguished.
            if data.flags & 0x10:return False
            return True
        self.listener=keyboard.Listener(on_press=lambda k:event(k,True),
            on_release=lambda k:event(k,False),win32_event_filter=event_filter)
        self.listener.start();self.listener.wait()
        self.log.emit('input_monitor',allowed_keys=sorted(self.state.allowed),
            limitation='Already-held keys at start/focus return are unknown until an observed edge; kernel injected input may be indistinguishable.')
        self.thread=threading.Thread(target=self.poll,daemon=True);self.thread.start()

    def poll(self):
        while not self.stop_event.is_set():
            try:
                if not self.listener.is_alive():
                    self.log.emit('monitor_error',error='Keyboard listener exited; subsequent input missing')
                    break
                self.state.update_focus(self.foreground());self.state.snapshot()
            except Exception as exc:self.log.emit('monitor_error',error=str(exc))
            self.stop_event.wait(.05)

    def close(self):
        self.stop_event.set();self.listener.stop();self.listener.join(timeout=2)
        self.thread.join(timeout=2);self.state.cancel('session_end')
        self.log.emit('monitor_stopped',listener_alive=self.listener.is_alive())


_auto=None
_context=threading.local()


def action_context(command_stamp=None):
    _context.command_stamp=command_stamp


def auto_active():
    return _auto is not None

def auto_event(kind,**fields):
    log=_auto
    if log is not None:return log.emit(kind,**fields)


def begin_auto(folder,cfg,hwnd=None):
    global _auto
    end_auto()
    from src.utils.session_provenance import save_provenance
    provenance = save_provenance(folder, cfg)
    _auto=EventLog(folder)
    _auto.target_hwnd=hwnd
    _auto.emit('session',mode='auto_capture',cfg=cfg,
        provenance=provenance,
        target_hwnd=hwnd,
        skill_success='unknown_until_visual_review',note='Backend return means call completed, not skill released.')
    return _auto


def end_auto():
    global _auto
    log=_auto;_auto=None
    if log is not None:log.close()


def backend_call(api,key,fn):
    log=_auto
    if log is None:return fn()
    started=time.monotonic_ns()
    try:
        import win32gui
        foreground_hwnd=win32gui.GetForegroundWindow()
    except Exception:foreground_hwnd=None
    call_id=log.emit('key_call_start',api=api,key=key,monotonic_ns=started,
                     command_stamp=getattr(_context,'command_stamp',None),
                     foreground_hwnd=foreground_hwnd,
                     focused=(foreground_hwnd==log.target_hwnd) if getattr(log,'target_hwnd',None) else None)
    try:
        value=fn()
    except Exception as exc:
        if log:log.emit('key_call_end',call_id=call_id,api=api,key=key,status='error',error=str(exc),skill_success='unknown')
        raise
    if log:log.emit('key_call_end',call_id=call_id,api=api,key=key,status='returned',
        duration_ns=time.monotonic_ns()-started,skill_success='unknown')
    return value
