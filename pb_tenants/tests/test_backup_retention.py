from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged
from ..models.backup_retention import expired_backup_ids


@tagged('post_install', '-at_install')
class TestBackupRetention(TransactionCase):
    def test_age_and_permanent_archive_guards(self):
        now = datetime(2026, 10, 20)
        rows = [(1, now - timedelta(days=20), 'manual'),
                (2, now - timedelta(days=10), 'nightly'),
                (3, now - timedelta(days=8), 'final')]
        self.assertEqual(expired_backup_ids(rows, now, 7), [2, 1])
        self.assertEqual(expired_backup_ids(rows[:2], now, 7), [1])
        self.assertEqual(expired_backup_ids(rows, now, 0), [])
        self.assertEqual(expired_backup_ids(rows, now, -1), [])

    def test_production_exemption_and_safe_paths(self):
        service = self.env['pb.tenants']
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('pb_tenants.backup_retention_days', '7')
        params.set_param('pb_tenants.backup_retention_exempt_slugs', '')
        tenant = self.env['pb.tenant'].create({'name': 'Retention check', 'slug': 'retentioncheck', 'state': 'live'})
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / tenant.slug).mkdir()
            records = self.env['pb.tenant.backup']
            for name, kind, age, outside in [('old', 'nightly', 20, False),
                    ('latest', 'manual', 8, False), ('final', 'final', 30, False),
                    ('outside', 'manual', 25, True)]:
                path = root / name if outside else root / tenant.slug / name
                path.write_bytes(b'backup fixture')
                rec = records.create({'tenant_id': tenant.id, 'filename': name,
                    'path': str(path), 'kind': kind, 'state': 'done'})
                self.env.cr.execute('UPDATE pb_tenant_backup SET create_date=%s WHERE id=%s',
                    [datetime.utcnow() - timedelta(days=age), rec.id])
                records |= rec
            records.invalidate_recordset(['create_date'])
            with patch.object(type(service), '_backup_root', return_value=folder):
                tenant.slug = 'rize'
                self.assertEqual(service._prune_nightly(tenant), 0)
                tenant.slug = 'retentioncheck'
                self.assertEqual(service._prune_nightly(tenant), 1)
            self.assertFalse((root / tenant.slug / 'old').exists())
            self.assertTrue((root / tenant.slug / 'latest').is_file())
            self.assertTrue((root / tenant.slug / 'final').is_file())
            self.assertTrue((root / 'outside').is_file())
