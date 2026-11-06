import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('maintenance', Path(__file__).parents[1] / 'storage_maintenance.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class RetentionTests(unittest.TestCase):
    def test_backup_identity_latest_and_symlink_guards(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            def backup(name, database, age):
                path = root / name
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr('manifest.json', json.dumps({'db_name': database}))
                    archive.writestr('dump.sql', '-- test fixture')
                os.utime(path, (time.time() - age * 86400,) * 2)
                return path
            old = backup('nonprod-old.zip', 'payobook', 20)
            latest = backup('nonprod-latest.zip', 'payobook', 10)
            production = backup('misleading-payobook-name.zip', 'rize', 40)
            retired = backup('abm.zip', 'abm', 50)
            registered = backup('registered-final.zip', 'payobook', 30)
            (root / 'unknown.zip').write_text('unknown files survive')
            (root / 'linked.zip').symlink_to(old)
            config = {'backup_root': folder, 'nonproduction_databases': ['payobook', 'rize', 'abm'],
                'production_databases': ['rize'], 'permanent_archives': []}
            candidates = list(m.backup_candidates(config, time.time() + 1, {str(registered)}, set()))
            self.assertEqual([p for p, _ in candidates], [old])
            self.assertEqual(m.backup_database(production), 'rize')
            self.assertEqual(list(m.backup_candidates(config, time.time() + 1,
                {str(registered)}, {old})), [])
            self.assertTrue(latest.exists() and production.exists() and retired.exists())

    def test_temporary_customer_data_and_active_work_survive(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            addon = root / 'deploy' / 'pb_example'
            addon.mkdir(parents=True)
            (addon / '__manifest__.py').write_text('{}')
            workbook = root / 'customer.xlsx'
            workbook.write_bytes(b'customer data')
            completed = root / 'old.log'
            completed.write_text('completed')
            active = root / 'active.log'
            active.write_text('running')
            unknown = root / 'unknown.dat'
            unknown.write_bytes(b'unknown')
            cutoff = time.time() + 1
            candidates = {p for p, _ in m.temp_candidates(root, cutoff, {active})}
            self.assertEqual(candidates, {addon, completed})
            self.assertEqual({p for p, _ in m.temp_candidates(root, cutoff,
                {active, addon / '__manifest__.py'})}, {completed})


if __name__ == '__main__':
    unittest.main()
