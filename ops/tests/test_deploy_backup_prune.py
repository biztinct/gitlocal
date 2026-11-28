import importlib.util
import os
from pathlib import Path
import tempfile
import time
import unittest

spec = importlib.util.spec_from_file_location('prune', Path(__file__).parents[1] / 'deploy_backup_prune.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def make(root, name, age_days, inner_age=None):
    path = root / name
    path.mkdir()
    f = path / 'golive-rize.dump'
    f.write_bytes(b'x' * 10)
    t = time.time() - age_days * 86400
    ti = time.time() - (inner_age if inner_age is not None else age_days) * 86400
    os.utime(f, (ti, ti))
    os.utime(path, (t, t))
    return path


class PruneTests(unittest.TestCase):
    def test_old_removed_new_kept_keep_newest_and_guards(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            # ctime cannot be back-dated in a test, so use a cutoff in the future for "old"
            # and check the ordering/keep/guard logic.
            entries = [make(root, 'b%02d' % i, 10 + i) for i in range(8)]
            (root / 'link').symlink_to(entries[0])
            cutoff = time.time() + 60
            got = list(m.candidates(root, cutoff, set(), keep=5))
            self.assertEqual(len(got), 3)
            self.assertNotIn(root / 'link', got)
            # in-use entry is protected
            got2 = list(m.candidates(root, cutoff, {got[0].resolve()}, keep=5))
            self.assertNotIn(got[0], got2)
            # nothing is old when the cutoff is in the past
            self.assertEqual(list(m.candidates(root, time.time() - 86400, set(), keep=0)), [])

    def test_symlink_inside_counts_as_new(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            d = make(root, 'withlink', 30)
            (d / 'l').symlink_to('/etc/hostname')
            self.assertEqual(list(m.candidates(root, time.time() + 60, set(), keep=0)), [])

    def test_refuses_protected_roots(self):
        with self.assertRaises(ValueError):
            list(m.candidates('/odoo/archives', time.time(), set()))
        with self.assertRaises(ValueError):
            list(m.candidates('/odoo/nightly-backups', time.time(), set()))


if __name__ == '__main__':
    unittest.main()
