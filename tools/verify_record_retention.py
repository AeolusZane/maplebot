"""Run with python -m unittest tools.verify_record_retention."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from src.utils.record_retention import clean_records


class RetentionTests(unittest.TestCase):
    def test_training_collection_retained_for_sixty_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = time.time()
            for index, days in enumerate((30, 61)):
                p = Path(tmp) / f"debug/detection_traces/20260101_00000{index}_123456"
                p.mkdir(parents=True)
                f = p / "events.jsonl"
                f.write_text("{}")
                old = now-days*86400
                os.utime(f, (old, old))
                os.utime(p, (old, old))
            self.assertEqual(clean_records(tmp, now=now)[0], 1)
            self.assertTrue((Path(tmp) / "debug/detection_traces/20260101_000000_123456").exists())

    def test_age_active_and_unknown_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = root / "log"
            logs.mkdir()
            old = time.time() - 30*86400
            for name in ("MSBot_2026-01-01_00-00-00.log",
                         "MSBot_2026-01-02_00-00-00.log", "notes.txt"):
                p = logs / name
                p.write_text("test")
                os.utime(p, (old, old))
            active = logs / "MSBot_2026-01-02_00-00-00.log"
            self.assertEqual(clean_records(root, active)[0], 1)
            self.assertTrue(active.exists())
            self.assertTrue((logs / "notes.txt").exists())

    def test_budget_oldest_first_recent_protected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "debug/detection_traces"
            now = time.time()
            folders = []
            for index, age in enumerate((10000, 5000, 1)):
                p = base / f"20261020_12000{index}_123456"
                p.mkdir(parents=True)
                f = p / "0001_near.jpg"
                f.write_bytes(b"x"*20)
                os.utime(f, (now-age, now-age))
                os.utime(p, (now-age, now-age))
                folders.append(p)
            self.assertEqual(clean_records(tmp, now=now, trace_budget=40)[0], 1)
            self.assertFalse(folders[0].exists())
            self.assertTrue(folders[1].exists())
            self.assertTrue(folders[2].exists())

    def test_foreign_content_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "debug/detection_traces/20260101_000000_123456"
            p.mkdir(parents=True)
            f = p / "my_notes.txt"
            f.write_text("keep")
            self.assertEqual(clean_records(tmp, trace_budget=0)[0], 0)
            self.assertTrue(f.exists())


if __name__ == "__main__":
    unittest.main()
