"""Clean only application diagnostic records; never traverse linked directories."""
import re
import stat
import threading
import time
from pathlib import Path

LOG_PATTERN = re.compile(r"(?:MSBot_\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d\.log(?:\.\d+)?|startup_\d{8}_\d{6}\.(?:out|err)\.log|启动失败_\d{8}_\d{6}\.log)")
TRACE_PATTERN = re.compile(r"\d{8}_\d{6}_\d{6}")
IMAGE_PATTERN = re.compile(r"\d{4}_[a-z_]+\.jpg")


def plain(path):
    info = path.lstat()
    return not (stat.S_ISLNK(info.st_mode) or
                getattr(info, "st_file_attributes", 0) & 0x400)


def clean_records(root, active_log=None, now=None, log_budget=200*1024**2,
                  trace_budget=10*1024**3):
    now = time.time() if now is None else now
    root = Path(root).resolve()
    removed = 0
    freed = 0
    for relative, days, budget, pattern in (
        ("log", 14, log_budget, LOG_PATTERN),
        ("debug/detection_traces", 60, trace_budget, TRACE_PATTERN),
    ):
        directory = root / relative
        # Check every ancestor too: debug itself could be a junction.
        if not directory.exists() or any(not plain(p) for p in
                (directory, *list(directory.parents)[:len(Path(relative).parts)-1])):
            continue
        entries = []
        for path in directory.iterdir():
            try:
                if not plain(path) or not pattern.fullmatch(path.name):
                    continue
                if path.is_dir():
                    files = list(path.iterdir())
                    if any(not plain(f) or not f.is_file() or
                           not (f.name == "events.jsonl" or IMAGE_PATTERN.fullmatch(f.name))
                           for f in files):
                        continue
                else:
                    files = [path]
                modified = max([path.stat().st_mtime] + [f.stat().st_mtime for f in files])
                size = sum(f.stat().st_size for f in files)
                protected = now - modified < 3600 or (
                    active_log is not None and
                    path.name.startswith(Path(active_log).name))
                entries.append((modified, size, path, files, protected))
            except OSError:
                continue
        total = sum(e[1] for e in entries)
        for modified, size, path, files, protected in sorted(entries):
            if protected or (now - modified <= days*86400 and total <= budget):
                continue
            # No recursive deletion: only the exact validated diagnostic files.
            try:
                for file in files:
                    if file.parent.resolve() != (path if path.is_dir() else directory).resolve():
                        raise OSError("record path changed")
                    file_size = file.stat().st_size
                    file.unlink()
                    freed += file_size
                if path.is_dir():
                    path.rmdir()
                removed += 1
                total -= size
            except OSError:
                continue
    return removed, freed


def start_cleanup(root, logger):
    def run():
        while True:
            try:
                count, size = clean_records(root, logger._file_handler.baseFilename)
                logger.info(f"[记录清理] 清理 {count} 项，释放 {size/1024**2:.1f} MB；"
                            "日志保留14天/200MB，检测截图保留60天/10GB")
            except Exception as exc:
                logger.warning(f"[记录清理] 本次跳过：{exc}")
            time.sleep(3600)
    thread = threading.Thread(target=run, name="record-cleanup", daemon=True)
    thread.start()
    return thread
