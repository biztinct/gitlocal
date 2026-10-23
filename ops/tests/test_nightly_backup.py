import datetime
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('nightly', Path(__file__).parents[1] / 'nightly_backup.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

TODAY = datetime.date(2026, 10, 23)


def make(root, days_ago, ok=True):
    path = root / (TODAY - datetime.timedelta(days=days_ago)).strftime(m.DAY_FORMAT)
    path.mkdir(parents=True)
    if ok:
        (path / 'OK').write_text('{}')
    return path


class NightlyRetentionTests(unittest.TestCase):
    def test_keeps_window_and_drops_older(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            keep = [make(root, d) for d in range(0, 8)]       # today .. 7 days ago
            old = [make(root, d) for d in (8, 15)]
            gone = m.expired(m.dated_copies(root), TODAY, 7)
            self.assertEqual(sorted(gone), sorted(old))
            self.assertTrue(all(p not in gone for p in keep))

    def test_newest_complete_copy_survives_any_age(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            newest = make(root, 40)
            older = make(root, 50)
            gone = m.expired(m.dated_copies(root), TODAY, 7)
            self.assertEqual(gone, [older])
            self.assertNotIn(newest, gone)

    def test_incomplete_never_counts_as_newest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            broken = make(root, 2, ok=False)
            last_good = make(root, 20)
            running = make(root, 0, ok=False)              # tonight's, still in progress
            gone = m.expired(m.dated_copies(root), TODAY, 7)
            self.assertEqual(gone, [broken])
            self.assertNotIn(last_good, gone)
            self.assertNotIn(running, gone)

    def test_foreign_names_and_symlinks_are_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'keep-me').mkdir()
            (root / 'notes.txt').write_text('x')
            target = make(root, 30)
            (root / '2026-01-01').symlink_to(target)
            self.assertEqual([p for _, p, _ in m.dated_copies(root)], [target])

    def test_thirty_day_database(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            inside = make(root, 30)
            outside = make(root, 31)
            make(root, 0)
            self.assertEqual(m.expired(m.dated_copies(root), TODAY, 30), [outside])
            self.assertTrue(inside.exists())


if __name__ == '__main__':
    unittest.main()
