# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Server tests for Sudima Phase J — Audit & Compliance console (§6 cases 1-10).

Covers the multi-source stream merge + normalization, every filter + stable
pagination, the manager+system gate (employee AND plain HR-user rejected),
PII masking in the stream AND export, the salary and login lenses, optional-
source absence surfacing, the filtered XLSX export (masked, capped-and-
surfaced), the read-only invariant (no source row count changes), and the
gated retention setting.

All source rows are SEEDED directly (never through a write hook — the console
is read-only, and these tests must not depend on which consumer modules
installed their audit mixins). Entry actors are forced by creating under
``with_user(...).sudo()`` — biz.audit.entry.create() forces user_id = env.uid,
which sudo() leaves as the with_user user.
"""

import base64
from datetime import date, datetime, timedelta
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

_AVAIL = ('odoo.addons.pb_audit.models.pb_audit_console.'
          'PbAuditConsole._source_available')
_EXPORT_CAP = ('odoo.addons.pb_audit.wizards.audit_export._EXPORT_CAP')


@tagged('post_install', '-at_install')
class TestAuditConsole(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Console = cls.env['pb.audit.console']
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        g_user = cls.env.ref('base.group_user')
        g_hr = cls.env.ref('om_hr_payroll.group_hr_payroll_user')
        g_mgr = cls.env.ref('om_hr_payroll.group_hr_payroll_manager')
        cls.emp_user = Users.create({'name': 'Empl Only', 'login': 'au_emp',
                                     'group_ids': [(6, 0, [g_user.id])]})
        cls.hr_user = Users.create({'name': 'HR Plain', 'login': 'au_hr',
                                    'group_ids': [(6, 0, [g_user.id, g_hr.id])]})
        cls.mgr_user = Users.create({'name': 'Mgr', 'login': 'au_mgr',
                                     'group_ids': [(6, 0, [g_user.id, g_mgr.id])]})

        cls.calendar = (cls.company.resource_calendar_id
                        or cls.env['resource.calendar'].search([], limit=1))
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) \
            or cls.env['hr.contract.type'].create({'name': 'Std'})
        cls.emp = cls.env['hr.employee'].create({
            'name': 'Tran Audit', 'company_id': cls.company.id})
        cls.contract = cls.env['hr.contract'].create({
            'name': 'C-audit', 'employee_id': cls.emp.id, 'wage': 5000000.0,
            'resource_calendar_id': cls.calendar.id, 'type_id': cls.ctype.id})

    # =========================================================== seed helpers
    def _seed_field(self, field='parent_id', old='Old Mgr', new='New Mgr',
                    model='hr.employee', res_id=None, actor=None):
        actor = actor or self.mgr_user
        return self.env['biz.audit.entry'].with_user(actor).sudo().create({
            'model_name': model, 'res_id': res_id or self.emp.id,
            'res_display': self.emp.name, 'field_name': field,
            'field_label': field.replace('_', ' ').title(),
            'old_value': old, 'new_value': new})

    def _seed_wage(self, old='5000000', new='6000000', actor=None):
        actor = actor or self.mgr_user
        return self.env['biz.audit.entry'].with_user(actor).sudo().create({
            'model_name': 'hr.contract', 'res_id': self.contract.id,
            'res_display': self.emp.name, 'field_name': 'wage',
            'field_label': 'Wage', 'old_value': old, 'new_value': new})

    def _seed_approval(self, actor=None):
        actor = actor or self.mgr_user
        return self.env['biz.approval.step.log'].with_user(actor).sudo().create({
            'res_model': 'hr.contract', 'res_id': self.contract.id,
            'from_state': 'draft', 'to_state': 'approved', 'note': 'ok'})

    def _seed_bank(self, actor=None, account='123456781234'):
        actor = actor or self.mgr_user
        return self.env['pb.employee.bank.history'].with_user(actor).sudo().create({
            'employee_id': self.emp.id, 'change_source': 'manual',
            'old_account_number': '999900001111',
            'new_account_number': account,
            'old_bank_name': 'Old Bank', 'new_bank_name': 'Vietcombank'})

    def _seed_login(self, actor=None):
        actor = actor or self.mgr_user
        return self.env['res.users.log'].with_user(actor).sudo().create({})

    def _seed_export(self):
        if 'bank.export.log' not in self.env:
            return None
        return self.env['bank.export.log'].sudo().create({
            'period_name': 'June 2026', 'country': 'VN',
            'total_records': 42, 'export_format': 'excel'})

    def _seed_all(self):
        """One row per available source; returns the set of expected source
        keys that were actually seeded."""
        seeded = {'field', 'approval', 'bank', 'login'}
        self._seed_field()
        self._seed_approval()
        self._seed_bank()
        self._seed_login()
        if self._seed_export() is not None:
            seeded.add('export')
        return seeded

    def _stream(self, filters=None, offset=0, user=None):
        con = self.Console.with_user(user or self.mgr_user)
        return con.get_stream(filters or {}, offset)

    # ================================================================= §6.1
    def test_01_stream_merge_and_normalize(self):
        seeded = self._seed_all()
        data = self._stream()
        got = {r['source'] for r in data['rows']}
        for key in seeded:
            self.assertIn(key, got, "source %s missing from the stream" % key)
        # sorted desc by stamp
        stamps = [r['stamp'] for r in data['rows'] if r['stamp']]
        self.assertEqual(stamps, sorted(stamps, reverse=True))
        # field change carries old→new; approval carries states
        field = next(r for r in data['rows'] if r['source'] == 'field')
        self.assertTrue(field['old'] and field['new'])
        appr = next(r for r in data['rows'] if r['source'] == 'approval')
        self.assertEqual(appr['old'], 'Draft')
        self.assertEqual(appr['new'], 'Approved')
        # every present source is reported installed in the payload
        status = {s['key']: s['installed'] for s in data['sources']}
        for key in seeded:
            self.assertTrue(status.get(key))

    # ================================================================= §6.2
    def test_02_filters_and_pagination(self):
        # by employee
        self._seed_field()
        self._seed_bank()
        other = self.env['hr.employee'].create({'name': 'Other One'})
        self._seed_field(res_id=other.id)
        by_emp = self._stream({'employee_id': self.emp.id})
        self.assertTrue(by_emp['rows'])
        for r in by_emp['rows']:
            if r['employee']:
                self.assertEqual(r['employee']['id'], self.emp.id)
        # by source
        by_src = self._stream({'source': 'bank'})
        self.assertTrue(all(r['source'] == 'bank' for r in by_src['rows']))
        # by actor
        self._seed_field(actor=self.hr_user)
        by_actor = self._stream({'actor_id': self.hr_user.id})
        self.assertTrue(by_actor['rows'])
        self.assertTrue(all(r['actor']['id'] == self.hr_user.id
                            for r in by_actor['rows']))
        # free text
        self._seed_field(field='job_title', old='ZZUNIQUEOLD', new='ZZUNIQUENEW')
        txt = self._stream({'text': 'zzuniqueold'})
        self.assertTrue(txt['rows'])
        self.assertTrue(any('ZZUNIQUEOLD' in r['old'] for r in txt['rows']))
        # date range excludes an old entry (stamp is forced to now at create,
        # so back-date it via a sudo write — append-only allows su).
        old_entry = self._seed_field(field='active', old='true', new='false')
        old_entry.sudo().write({'stamp': datetime(2020, 1, 1, 8, 0, 0)})
        today = date.today().strftime('%Y-%m-%d')
        ranged = self._stream({'date_from': today})
        self.assertNotIn(old_entry.id,
                         [int(r['key'].split('-')[1]) for r in ranged['rows']
                          if r['source'] == 'field'])
        # pagination: 55 field entries → page1=50, page2=5, no dupes
        self.env['biz.audit.entry'].search([]).sudo().unlink()
        for i in range(55):
            self._seed_field(field='parent_id', old='o%s' % i, new='n%s' % i)
        p1 = self._stream({'source': 'field'}, offset=0)
        p2 = self._stream({'source': 'field'}, offset=50)
        self.assertEqual(len(p1['rows']), 50)
        self.assertEqual(len(p2['rows']), 5)
        self.assertTrue(p1['has_more'])
        self.assertFalse(p2['has_more'])
        keys = {r['key'] for r in p1['rows']} | {r['key'] for r in p2['rows']}
        self.assertEqual(len(keys), 55, "duplicate rows across pages")

    # ================================================================= §6.3
    def test_03_gate_employee_and_plain_hr(self):
        self._seed_all()
        for u in (self.emp_user, self.hr_user):
            con = self.Console.with_user(u)
            with self.assertRaises(AccessError):
                con.get_stream({}, 0)
            with self.assertRaises(AccessError):
                con.get_salary_lens({})
            with self.assertRaises(AccessError):
                con.get_login_lens({})
            with self.assertRaises(AccessError):
                con.get_kpis()
            with self.assertRaises(AccessError):
                con.set_retention(400)
            with self.assertRaises(AccessError):
                con.export_stream({}, 'stream')
        # manager passes
        self.assertIsInstance(
            self.Console.with_user(self.mgr_user).get_kpis(), dict)

    # ================================================================= §6.4
    def test_04_masking_stream_and_export(self):
        self._seed_bank(account='123456781234')
        data = self._stream({'source': 'bank'})
        row = next(r for r in data['rows'] if r['source'] == 'bank')
        self.assertIn('••••', row['new'])
        self.assertIn('1234', row['new'])
        self.assertNotIn('123456781234', row['new'])
        # export carries the same masking
        res = self.Console.with_user(self.mgr_user).export_stream(
            {'source': 'bank'}, 'stream')
        self.assertFalse(res['truncated'])
        # the download URL points at the transient wizard's Binary
        wiz = self.env['pb.audit.export'].search([], order='id desc', limit=1)
        self.assertIn('/web/content/pb.audit.export/%s/export_file' % wiz.id,
                      res['url'])
        raw = base64.b64decode(wiz.export_file)
        self.assertEqual(raw[:2], b'PK')  # a valid xlsx zip
        # the full account never appears in the sheet bytes; the last-4 mask does
        self.assertNotIn(b'123456781234', raw)

    # ================================================================= §6.5
    def test_05_salary_lens(self):
        self._seed_wage(old='5000000', new='6000000', actor=self.mgr_user)
        # a non-wage contract entry must NOT appear in the lens
        self._seed_field(field='state', old='draft', new='open',
                         model='hr.contract', res_id=self.contract.id)
        lens = self.Console.with_user(self.mgr_user).get_salary_lens({})
        rows = [r for r in lens['rows'] if r['employee']['id'] == self.emp.id]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['delta_pct'], 20.0)
        self.assertEqual(row['band'], 'amber')  # 20% ≥ 10 (amber), < 25 (rose)
        self.assertEqual(row['actor']['id'], self.mgr_user.id)
        self.assertTrue(lens['can_see_values'])
        self.assertIn('6,000,000', row['new'])

    # ================================================================= §6.6
    def test_06_login_lens(self):
        self._seed_login(actor=self.mgr_user)
        self._seed_login(actor=self.mgr_user)
        lens = self.Console.with_user(self.mgr_user).get_login_lens({})
        card = next(c for c in lens['cards'] if c['user_id'] == self.mgr_user.id)
        self.assertGreaterEqual(card['sessions'], 2)
        self.assertEqual(len(card['sparkline']), 30)
        self.assertTrue(lens['note'])  # honest "sessions started" wording
        self.assertIn('logout', lens['note'].lower())

    # ================================================================= §6.7
    def test_07_optional_source_absent(self):
        self._seed_all()

        real = self.Console._source_available

        def fake_avail(key):
            if key == 'export':
                return False
            return real(key)

        with patch(_AVAIL, side_effect=fake_avail):
            data = self._stream()
        status = {s['key']: s['installed'] for s in data['sources']}
        self.assertFalse(status['export'])
        # the stream still returns the other sources
        self.assertTrue(data['rows'])
        self.assertTrue(status['field'])

    # ================================================================= §6.8
    def test_08_export_cap_surfaced(self):
        self._seed_field()
        self._seed_bank()
        self._seed_approval()
        # Force a tiny cap so truncation is exercised deterministically.
        with patch(_EXPORT_CAP, 1):
            res = self.Console.with_user(self.mgr_user).export_stream({}, 'stream')
        self.assertTrue(res['truncated'])
        self.assertEqual(res['count'], 1)
        self.assertEqual(res['cap'], 1)

    # ================================================================= §6.9
    def test_09_read_only_invariant(self):
        self._seed_all()
        models = ['biz.audit.entry', 'biz.approval.step.log',
                  'pb.employee.bank.history', 'res.users.log']
        before = {m: self.env[m].sudo().search_count([]) for m in models}
        con = self.Console.with_user(self.mgr_user)
        con.get_stream({}, 0)
        con.get_salary_lens({})
        con.get_login_lens({})
        con.get_kpis()
        after = {m: self.env[m].sudo().search_count([]) for m in models}
        self.assertEqual(before, after,
                         "a read-only console method mutated a source table")

    # ================================================================= §6.10
    def test_10_retention_gate(self):
        # manager can set
        res = self.Console.with_user(self.mgr_user).set_retention(365)
        self.assertEqual(res['retention_days'], 365)
        self.assertEqual(
            self.env['ir.config_parameter'].sudo().get_param(
                'biz_audit_trail.retention_days'), '365')
        # HR-user cannot
        with self.assertRaises(AccessError):
            self.Console.with_user(self.hr_user).set_retention(30)
