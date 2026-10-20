"""Durable, map-and-level keyed experience samples."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

class ExperienceHistory:
    def __init__(self,path=None):
        self.path=Path(path or Path(__file__).resolve().parents[2]/'data'/'experience.sqlite3')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS samples (id INTEGER PRIMARY KEY, run TEXT, time REAL, map TEXT, level INTEGER, elapsed REAL, experience INTEGER, percent REAL, gain INTEGER, duration REAL, note TEXT)')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path)
        try:
            with db:yield db
        finally:db.close()
    def append(self,run,stamp,map_name,level,elapsed,experience,percent,gain,duration,note):
        with self.connect() as db:
            db.execute('INSERT INTO samples(run,time,map,level,elapsed,experience,percent,gain,duration,note) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (run,stamp,map_name,level,elapsed,experience,percent,gain,duration,note))
    def rows(self):
        with self.connect() as db:
            db.row_factory=sqlite3.Row
            return [dict(r) for r in db.execute('SELECT * FROM samples ORDER BY time,id')]

def efficiency(rows):
    valid=[r for r in rows if r['gain'] is not None and r['duration']>0]
    total=sum(r['gain'] for r in valid);duration=sum(r['duration'] for r in valid)
    return total,duration,total*60/duration if duration else None
