# -*- coding: utf-8 -*-
"""WDGAP QF2 — saved Explorer views, the Excel download, regular email.

Numbered as the handover's §5 test cases (T1 … T12). The fixtures are the
fact-engine world (`test_fact_engine.TestFactEngine`): one company, two
departments, three people paid in April. Subclassed for its `setUpClass`
only — the Odoo 19 loader runs only the tests a class defines itself (G98).
"""
import base64
import io
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from freezegun import freeze_time

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .test_fact_engine import TestFactEngine


def _golden_csv(explorer, spec):
    """`export_csv` EXACTLY as it was before QF2 (pb_explorer 19.0.2.6.0),
    kept here as the golden for T6: the CSV must not change by one byte."""
    import csv
    from odoo import _
    from odoo.addons.pb_explorer.models.pb_explorer import _EXPORT_CAP
    payload = explorer.query(spec)
    buf = io.StringIO()
    w = csv.writer(buf)
    written = 0
    period = payload.get('period') or {}
    w.writerow([_('Period'), period.get('label') or _('Everything')])
    if period.get('date_from') or period.get('date_to'):
        w.writerow([_('From'), period.get('date_from') or '',
                    _('To'), period.get('date_to') or ''])
    w.writerow([])
    parts = payload.get('parts') or [payload]
    for part in parts:
        currency = (part.get('currency') or {}).get('name') or ''
        if currency:
            w.writerow([_('Amounts in %s', currency)])
        head = [payload['dimension_label']] + [c['label'] for c in
                                               part['categories']]
        w.writerow(head + [_('Total')])
        for s in part['series']:
            if written >= _EXPORT_CAP:
                break
            w.writerow([s['label']] + list(s['values']) + [s['total']])
            written += 1
        w.writerow([])
    money = payload.get('money') or {}
    if money.get('unconverted'):
        w.writerow([_('Not converted — no exchange rate on file')])
        w.writerow([_('Currency'), _('Period'), _('Amount'), _('Why')])
        for row in money['unconverted']:
            w.writerow([(row.get('currency') or {}).get('name') or '',
                        row.get('period') or '', row.get('amount') or 0.0,
                        row.get('note') or ''])
    return base64.b64encode(buf.getvalue().encode('utf-8-sig')).decode('ascii')


@tagged('post_install', '-at_install', 'wdgap_qf2')
class TestWdgapQf2(TestFactEngine):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.partner_id.tz = 'Asia/Ho_Chi_Minh'
        gate = cls.env.ref('pb_hr_payroll_base.group_payroll_analytics_user')
        cls.gate = gate
        internal = cls.env.ref('base.group_user')

        def mk(login, groups, email=True):
            return cls.env['res.users'].with_context(
                no_reset_password=True).create({
                    'name': 'QF2 %s' % login.title(),
                    'login': 'qf2_%s' % login,
                    'email': ('qf2_%s@qf2.test' % login) if email else False,
                    'company_id': cls.company.id,
                    'company_ids': [(6, 0, [cls.company.id])],
                    'group_ids': [(6, 0, [g.id for g in groups])],
                })
        cls.owner = mk('owner', [internal, gate])
        cls.other = mk('other', [internal, gate])
        cls.reader_one = mk('reader_one', [internal, gate])
        cls.reader_two = mk('reader_two', [internal, gate])
        cls.plain = mk('plain', [internal])

        # Two divisions, one per department, so two readers can be held to
        # different halves of the same company (R2).
        Division = cls.env['pb.division'].sudo()
        Link = cls.env['pb.division.link'].sudo()
        cls.div_one = Division.create({'name': 'QF2 North'})
        cls.div_two = Division.create({'name': 'QF2 South'})
        Link.create({'division_id': cls.div_one.id,
                     'department_id': cls.dept.id, 'date_from': '2020-01-01'})
        Link.create({'division_id': cls.div_two.id,
                     'department_id': cls.dept2.id, 'date_from': '2020-01-01'})
        cls.builder.build_runs([cls.april.id])

        # No outgoing mail server unless a test adds one (convention 9).
        cls.env['ir.mail_server'].sudo().search([]).write({'active': False})

    # ------------------------------------------------------------ helpers
    def _as(self, user, model='pb.explorer'):
        return self.env[model].with_user(user).with_context(
            allowed_company_ids=[self.company.id])

    def _view(self, user=None, name='Net by department', spec=None,
              shared=False):
        spec = spec or {'measure': 'net', 'dimension': 'department_id'}
        payload = self._as(user or self.owner, 'pb.explorer.view').pbx_save(
            name, spec, shared)
        return self.env['pb.explorer.view'].browse(payload['id'])

    def _mail_on(self):
        return self.env['ir.mail_server'].sudo().create({
            'name': 'QF2 test outbox (never used)',
            'smtp_host': 'localhost', 'smtp_port': 25,
            'smtp_encryption': 'none'})

    def _schedule(self, view, recipients, cadence='weekly', **kw):
        vals = {'cadence': cadence, 'weekday': kw.get('weekday', '0'),
                'monthday': kw.get('monthday', 1),
                'recipient_ids': [u.id for u in recipients]}
        payload = self._as(self.owner).schedule_save(view.id, vals)
        return self.env['pb.explorer.schedule'].browse(payload['id'])

    @staticmethod
    def _sheet(data):
        from openpyxl import load_workbook
        return load_workbook(io.BytesIO(data)).active

    @staticmethod
    def _cells(ws):
        return [[c.value for c in row] for row in ws.iter_rows()]

    def _fake_payload(self, parts, unconverted=None, truncated=0):
        vnd = self.env.ref('base.VND')
        return {
            'ok': True,
            'spec': {'measure': 'net', 'dimension': 'department_id',
                     'filters': {}},
            'period': {'key': '2026-04-01..2026-04-30', 'label': 'April 2026',
                       'date_from': '2026-04-01', 'date_to': '2026-04-30',
                       'preset': ''},
            'measure_label': 'Net pay', 'measure_kind': 'money',
            'dimension_label': 'Department', 'grain_label': 'Month',
            'parts': parts, 'series': parts[0]['series'] if parts else [],
            'categories': parts[0]['categories'] if parts else [],
            'grand_total': parts[0]['grand_total'] if parts else 0.0,
            'currency': {'id': vnd.id, 'name': 'VND'},
            'money': {'mode': 'own', 'unconverted': unconverted or []},
            'truncated': truncated, 'heads': {'people': 3, 'fte': 3.0},
        }

    def _two_currency_parts(self):
        vnd, usd = self.env.ref('base.VND'), self.env.ref('base.USD')
        cats = [{'key': '2026-04-01', 'label': 'April 2026'}]
        return [
            {'currency': {'id': vnd.id, 'name': 'VND'}, 'categories': cats,
             'series': [{'label': 'Retail', 'values': [1000000.0],
                         'total': 1000000.0},
                        {'label': 'Bakery', 'values': [500000.0],
                         'total': 500000.0}],
             'grand_total': 1500000.0},
            {'currency': {'id': usd.id, 'name': 'USD'}, 'categories': cats,
             'series': [{'label': 'Retail', 'values': [40.5],
                         'total': 40.5}],
             'grand_total': 40.5},
        ]

    def _patch_query(self, payload):
        return patch.object(type(self.env['pb.explorer']), 'query',
                            lambda self_, spec=None: payload)

    # ------------------------------------------------------------- T1
    def test_t01_save_rename_update_share_delete(self):
        view = self._view()
        mine = self._as(self.owner).my_views()
        self.assertIn(view.id, [v['id'] for v in mine['mine']])
        self.assertTrue(mine['mine'][0]['mine'])
        # the first paint carries them
        schema = self._as(self.owner).get_schema()
        self.assertIn(view.id, [v['id'] for v in schema['views']['mine']])

        as_owner = view.with_user(self.owner)
        self.assertEqual(as_owner.pbx_update({'name': '  Net   pay  '})['name'],
                         'Net pay')
        res = as_owner.pbx_update({'spec': {'measure': 'gross',
                                            'dimension': 'division_id'}})
        self.assertEqual(view.spec['measure'], 'gross')
        self.assertEqual(res['measure'], 'gross')

        # unshared: invisible to another analyst, and not theirs to change
        theirs = self._as(self.other).my_views()
        self.assertNotIn(view.id, [v['id'] for v in theirs['shared']])
        with self.assertRaises(AccessError):
            view.with_user(self.other).pbx_update({'name': 'Mine now'})

        # shared: they see it, with its owner, but still cannot change it
        as_owner.pbx_update({'shared': True})
        theirs = self._as(self.other).my_views()
        entry = [v for v in theirs['shared'] if v['id'] == view.id]
        self.assertTrue(entry)
        self.assertFalse(entry[0]['mine'])
        self.assertEqual(entry[0]['owner'], self.owner.name)
        with self.assertRaises(AccessError):
            view.with_user(self.other).pbx_update({'name': 'Mine now'})
        with self.assertRaises(AccessError):
            view.with_user(self.other).pbx_delete()
        # "Save as my own" is a plain save of the same question
        copy = self._view(user=self.other, name='My copy',
                          spec=view.spec)
        self.assertEqual(copy.user_id, self.other)

        self.assertTrue(as_owner.pbx_delete())
        self.assertFalse(view.exists())
        with self.assertRaises(UserError):
            self._view(name='   ')

    # ------------------------------------------------------------- T2
    def test_t02_no_gate_no_door(self):
        view = self._view(shared=True)
        sched = self._schedule(view, [self.owner])
        ex = self._as(self.plain)
        calls = [
            lambda: ex.my_views(),
            lambda: ex.open_view(view.id),
            lambda: ex.export_xlsx({'measure': 'net'}),
            lambda: ex.export_xlsx({'measure': 'net'}, view.id),
            lambda: ex.schedule_drawer(view.id),
            lambda: ex.schedule_save(view.id, {'cadence': 'weekly',
                                               'recipient_ids': [self.plain.id]}),
            lambda: ex.schedule_pause(sched.id, False),
            lambda: ex.schedule_delete(sched.id),
            lambda: ex.schedule_send_now(sched.id),
            lambda: self._as(self.plain, 'pb.explorer.view').pbx_save(
                'x', {}, False),
            lambda: view.with_user(self.plain).pbx_update({'name': 'x'}),
            lambda: view.with_user(self.plain).pbx_delete(),
        ]
        for i, call in enumerate(calls):
            with self.subTest(call=i), self.assertRaises(AccessError):
                call()

    # ------------------------------------------------------------- T3
    def test_t03_a_moving_period_moves_a_fixed_one_does_not(self):
        with freeze_time('2026-11-14 03:00:00'):
            moving = self._view(name='Last month', spec={
                'measure': 'net', 'dimension': 'department_id',
                'date_from': '2026-10-01', 'date_to': '2026-10-31'})
            fixed = self._view(name='Early April', spec={
                'measure': 'net', 'dimension': 'department_id',
                'date_from': '2026-04-03', 'date_to': '2026-04-20'})
            everything = self._view(name='All time', spec={'measure': 'net'})
            self.assertEqual(moving.period_preset, 'last_month')
            self.assertEqual(fixed.period_preset, '')
            self.assertEqual(everything.period_preset, 'all')
            label = moving.with_user(self.owner)._pbx_period_label()
            self.assertIn('moves with the calendar', label)
            self.assertIn('Fixed dates', fixed._pbx_period_label())
        with freeze_time('2026-12-05 03:00:00'):
            res = self._as(self.owner).open_view(moving.id)
            self.assertEqual(res['spec']['date_from'], '2026-11-01')
            self.assertEqual(res['spec']['date_to'], '2026-11-30')
            res = self._as(self.owner).open_view(fixed.id)
            self.assertEqual(res['spec']['date_from'], '2026-04-03')
            self.assertEqual(res['spec']['date_to'], '2026-04-20')
            res = self._as(self.owner).open_view(everything.id)
            self.assertIsNone(res['spec']['date_from'])
        with freeze_time('2027-01-02 03:00:00'):
            spec = moving._pbx_spec_now()
            self.assertEqual((spec['date_from'], spec['date_to']),
                             ('2026-12-01', '2026-12-31'))

    # ------------------------------------------------------------- T4
    def test_t04_a_stale_spec_opens_with_a_plain_note(self):
        view = self.env['pb.explorer.view'].create({
            'name': 'Old one', 'user_id': self.owner.id,
            'spec': {'measure': 'gone_measure', 'dimension': 'gone_dim',
                     'junk': {'deep': [1, 2]}, 'filters': {'nope': [1]}},
        })
        res = self._as(self.owner).open_view(view.id)
        self.assertTrue(res['ok'])
        self.assertEqual(res['spec']['measure'], 'net')
        self.assertEqual(res['spec']['dimension'], 'department_id')
        self.assertNotIn('junk', res['spec'])
        self.assertTrue(res['note'])
        self.assertNotIn('Odoo', res['note'])
        # not even a dict
        view.spec = ['a', 'list']
        res = self._as(self.owner).open_view(view.id)
        self.assertTrue(res['ok'])
        self.assertEqual(res['spec']['measure'], 'net')
        # gone, or never yours
        private = self._view(name='Private')
        res = self._as(self.other).open_view(private.id)
        self.assertFalse(res['ok'])
        self.assertTrue(res['msg'])
        res = self._as(self.owner).open_view(999999999)
        self.assertFalse(res['ok'])
        # a stored junk key is dropped before it is ever stored
        clean = self._view(name='Clean', spec={'measure': 'net',
                                               'evil': '1; DROP'})
        self.assertNotIn('evil', clean.spec)

    # ------------------------------------------------------------- T5
    def test_t05_the_workbook(self):
        res = self._scoped().export_xlsx({'measure': 'net',
                                          'dimension': 'department_id',
                                          'grain': 'none'})
        self.assertTrue(res['ok'])
        self.assertTrue(res['filename'].endswith('.xlsx'))
        self.assertNotIn('odoo', res['filename'].lower())
        ws = self._sheet(base64.b64decode(res['file_b64']))
        cells = self._cells(ws)
        firsts = [row[0] for row in cells]
        for label in ('Measure', 'Split by', 'Period', 'Filters', 'Made on'):
            self.assertIn(label, firsts)
        self.assertTrue(ws.freeze_panes)
        numeric = [v for row in cells for v in row[1:]
                   if isinstance(v, (int, float))]
        self.assertIn(4800.0, numeric, 'the grand total is a NUMBER cell')
        self.assertIn(2400.0, numeric)

        # own mode, two currencies: two blocks, two totals, never a sum
        payload = self._fake_payload(self._two_currency_parts())
        with self._patch_query(payload):
            data, _ex = self._scoped()._xlsx_bytes({}, title='Two monies')
        cells = self._cells(self._sheet(data))
        firsts = [row[0] for row in cells]
        self.assertIn('Amounts in VND', firsts)
        self.assertIn('Amounts in USD', firsts)
        totals = [row for row in cells if row[0] == 'Total']
        self.assertEqual(len(totals), 2)
        self.assertEqual(totals[0][2], 1500000.0)
        self.assertEqual(totals[1][2], 40.5)
        every = [v for row in cells for v in row if isinstance(v, float)]
        self.assertNotIn(1500040.5, every, 'two monies were added together')
        ws = self._sheet(data)
        vnd_cell = [c for row in ws.iter_rows() for c in row
                    if c.value == 1000000.0][0]
        self.assertEqual(vnd_cell.number_format, '#,##0')
        usd_cell = [c for row in ws.iter_rows() for c in row
                    if c.value == 40.5][0]
        self.assertEqual(usd_cell.number_format, '#,##0.00')

        # group mode with an unconverted currency, and a capped answer
        sgd = {'name': 'SGD'}
        payload = self._fake_payload(
            self._two_currency_parts()[:1],
            unconverted=[{'currency': sgd, 'period': 'April 2026',
                          'amount': 75.0, 'note': 'No rate on file'}],
            truncated=3)
        with self._patch_query(payload):
            data, ex = self._scoped()._xlsx_bytes({})
        cells = self._cells(self._sheet(data))
        firsts = [str(row[0] or '') for row in cells]
        self.assertIn('Not converted — no exchange rate on file', firsts)
        self.assertTrue([f for f in firsts if '3 more were left out' in f])
        self.assertIn(['SGD', 'April 2026', 75.0, 'No rate on file'],
                      [row[:4] for row in cells])
        self.assertEqual(ex['truncated'], 3)

    # ------------------------------------------------------------- T6
    def test_t06_the_csv_is_byte_identical(self):
        ex = self._scoped()
        specs = [{'measure': 'net', 'dimension': 'department_id'},
                 {'measure': 'headcount', 'dimension': 'division_id',
                  'grain': 'none'},
                 {'measure': 'net', 'date_from': '2026-04-01',
                  'date_to': '2026-04-30'},
                 {'measure': 'net', 'date_from': '2030-01-01',
                  'date_to': '2030-01-31'}]
        for spec in specs:
            with self.subTest(spec=spec):
                self.assertEqual(ex.export_csv(spec)['csv_b64'],
                                 _golden_csv(ex, spec))
        payload = self._fake_payload(
            self._two_currency_parts(),
            unconverted=[{'currency': {'name': 'SGD'}, 'period': 'Apr',
                          'amount': 1.5, 'note': 'none'}])
        with self._patch_query(payload):
            self.assertEqual(ex.export_csv({})['csv_b64'],
                             _golden_csv(ex, {}))

    # ------------------------------------------------------------- T7
    def test_t07_when_it_is_due(self):
        view = self._view()
        sched = self._schedule(view, [self.owner], weekday='0')
        utc = datetime
        # Saturday 10:00 in Ho Chi Minh City -> Monday 07:00 there
        self.assertEqual(sched._next_after(utc(2026, 11, 14, 3, 0)),
                         utc(2026, 11, 16, 0, 0))
        # exactly at the moment -> the week after, never the same moment
        self.assertEqual(sched._next_after(utc(2026, 11, 16, 0, 0)),
                         utc(2026, 11, 23, 0, 0))
        # week boundary: Sunday, sent Sunday morning, asked Sunday 07:30
        sched.weekday = '6'
        self.assertEqual(sched._next_after(utc(2026, 11, 15, 0, 30)),
                         utc(2026, 11, 22, 0, 0))
        self.assertEqual(sched._next_after(utc(2026, 11, 14, 23, 30)),
                         utc(2026, 11, 15, 0, 0))
        # month ends, day 28 rule
        sched.write({'cadence': 'monthly', 'monthday': 28})
        self.assertEqual(sched._next_after(utc(2027, 1, 28, 1, 0)),
                         utc(2027, 2, 28, 0, 0))
        self.assertEqual(sched._next_after(utc(2026, 12, 28, 5, 0)),
                         utc(2027, 1, 28, 0, 0))
        sched.monthday = 1
        self.assertEqual(sched._next_after(utc(2026, 11, 30, 18, 0)),
                         utc(2026, 12, 1, 0, 0))
        with self.assertRaises(UserError):
            self._as(self.owner).schedule_save(view.id, {
                'cadence': 'monthly', 'monthday': 31,
                'recipient_ids': [self.owner.id]})
        # another time zone: 07:00 in Sydney (UTC+11 in November)
        self.company.partner_id.tz = 'Australia/Sydney'
        sched.monthday = 15
        self.assertEqual(sched._next_after(utc(2026, 11, 10, 0, 0)),
                         utc(2026, 11, 14, 20, 0))
        # no zone named anywhere: UTC+7
        self.company.partner_id.tz = False
        self.company.resource_calendar_id.tz = 'UTC'
        self.assertEqual(sched._pbx_tz().zone, 'Asia/Ho_Chi_Minh')
        self.company.partner_id.tz = 'Asia/Ho_Chi_Minh'
        # after-each-pay-run has no clock time
        sched.cadence = 'payrun'
        self.assertFalse(sched._next_after(utc(2026, 11, 10, 0, 0)))

        # the cron sends ONCE; the same hour again sends nothing
        self._mail_on()
        sched.write({'cadence': 'weekly', 'weekday': '0'})
        sched.next_due = fields.Datetime.now() - timedelta(minutes=5)
        Mail = self.env['mail.mail'].sudo()
        before = Mail.search_count([])
        self.env['pb.explorer.schedule']._cron_send_due()
        self.assertEqual(Mail.search_count([]), before + 1)
        self.assertGreater(sched.next_due, fields.Datetime.now())
        self.env['pb.explorer.schedule']._cron_send_due()
        self.assertEqual(Mail.search_count([]), before + 1,
                         'a second run in the same hour sent again')
        # "Send now" sends and does not move the next send
        due = sched.next_due
        res = self._as(self.owner).schedule_send_now(sched.id)
        self.assertTrue(res['ok'])
        self.assertEqual(Mail.search_count([]), before + 2)
        self.assertEqual(sched.next_due, due)
        hist = res['schedule']['history']
        self.assertEqual(len(hist), 2)
        self.assertEqual(hist[0]['lines'][0]['label'], 'Sent')
        # pause: nothing is due while paused
        payload = self._as(self.owner).schedule_pause(sched.id, False)
        self.assertFalse(payload['active'])
        self.assertFalse(sched.with_context(active_test=False).next_due)

    # ------------------------------------------------------------- T8
    def test_t08_each_person_gets_their_own_numbers(self):
        Visibility = self.env['pb.group.visibility'].sudo()
        Visibility.set_for(self.reader_one.id, 'division', self.div_one.id)
        Visibility.set_for(self.reader_two.id, 'division', self.div_two.id)
        self._mail_on()
        view = self._view(name='People by department', spec={
            'measure': 'headcount', 'dimension': 'department_id',
            'grain': 'none'})
        sched = self._schedule(view, [self.reader_one, self.reader_two])
        # a company in the context that one reader may not see must not leak
        # in, and must not break the send (it is dropped, R2)
        sched.with_context(allowed_company_ids=[self.company_b.id])._send_one(
            'now')
        logs = sched.log_ids
        self.assertEqual(set(logs.mapped('state')), {'queued'})
        sheets = {}
        for log in logs:
            att = log.mail_id.attachment_ids
            self.assertEqual(len(att), 1)
            sheets[log.user_id.id] = self._cells(
                self._sheet(base64.b64decode(att.datas)))
        one, two = sheets[self.reader_one.id], sheets[self.reader_two.id]
        self.assertNotEqual(one, two)
        labels_one = {row[0] for row in one}
        labels_two = {row[0] for row in two}
        self.assertIn('Explorer Dept', labels_one)
        self.assertNotIn('Explorer Dept 2', labels_one)
        self.assertIn('Explorer Dept 2', labels_two)
        self.assertNotIn('Explorer Dept', labels_two)
        total_one = [row for row in one if row[0] == 'Total'][0][1]
        total_two = [row for row in two if row[0] == 'Total'][0][1]
        self.assertEqual((total_one, total_two), (2.0, 1.0))

    # ------------------------------------------------------------- T9
    def test_t09_skipped_people_are_written_down(self):
        self._mail_on()
        lost = self.reader_one
        no_mail = self.reader_two
        view = self._view()
        sched = self._schedule(view, [self.owner, lost, no_mail])
        lost.write({'group_ids': [(3, self.gate.id)]})
        no_mail.email = False
        summary = sched._send_one('now')
        self.assertEqual(summary, {'sent': 1, 'skipped': 2,
                                   'email_off': False})
        by_user = {l.user_id.id: l.state for l in sched.log_ids}
        self.assertEqual(by_user[self.owner.id], 'queued')
        self.assertEqual(by_user[lost.id], 'no_access')
        self.assertEqual(by_user[no_mail.id], 'no_email')
        hist = sched._pbx_payload()['history'][0]
        self.assertEqual(hist['summary'], 'Sent to 1 of 3')
        labels = {l['label'] for l in hist['lines']}
        self.assertIn('Skipped — can no longer open the Explorer', labels)
        self.assertIn('Skipped — no email address', labels)
        # a login that left is skipped too, not an error
        self.owner.active = False
        summary = sched._send_one('now')
        self.assertEqual(summary['sent'], 0)

    # ------------------------------------------------------------- T10
    def test_t10_no_email_here_is_normal(self):
        view = self._view()
        sched = self._schedule(view, [self.owner, self.other])
        drawer = self._as(self.owner).schedule_drawer(view.id)
        self.assertFalse(drawer['mail_on'])
        Mail = self.env['mail.mail'].sudo()
        before = Mail.search_count([])
        res = self._as(self.owner).schedule_send_now(sched.id)
        self.assertEqual(Mail.search_count([]), before)
        self.assertEqual(set(sched.log_ids.mapped('state')), {'email_off'})
        self.assertIn('Email is not switched on', res['msg'])
        self.assertEqual(res['schedule']['history'][0]['lines'][0]['label'],
                         'Not sent — email is switched off')
        sched.next_due = fields.Datetime.now() - timedelta(minutes=1)
        self.env['pb.explorer.schedule']._cron_send_due()    # no exception
        self.assertEqual(Mail.search_count([]), before)

        self._mail_on()
        self.assertTrue(self._as(self.owner).schedule_drawer(view.id)['mail_on'])
        sched._send_one('now')
        queued = sched.log_ids.filtered(lambda l: l.state == 'queued')
        self.assertEqual(len(queued), 2)
        for log in queued:
            mail = log.mail_id
            self.assertEqual(mail.state, 'outgoing', 'queued, never forced')
            self.assertEqual(len(mail.attachment_ids), 1)
            att = mail.attachment_ids
            self.assertTrue(att.name.endswith('.xlsx'))
            for text in (mail.subject, str(mail.body_html), att.name):
                self.assertNotIn('Odoo', text)
                self.assertNotIn('odoo', text.lower().replace(
                    'odoo-bin', ''))
            self.assertIn('#pbxv=%d' % view.id, str(mail.body_html))
            self.assertIn(log.user_id.email, mail.email_to)

    # ------------------------------------------------------------- T11
    def test_t11_after_each_pay_run(self):
        view = self._view()
        sched = self._schedule(view, [self.owner], cadence='payrun')
        self.assertFalse(sched.next_due)
        request = (self.env['biz.approval.request'].browse()
                   if 'biz.approval.request' in self.env
                   else SimpleNamespace(source_revision=''))

        run = self._mk_run('QF2 May', '2026-05-01', '2026-05-31',
                           state='draft')
        self._mk_slip(run, self.emp1, basic=1.0, net=1.0, emp_cost=0.0)
        result = run._approval_apply(request)
        self.assertTrue(result)
        self.assertEqual(run.state, 'done')
        self.assertTrue(sched.next_due)
        self.assertLessEqual(sched.next_due, fields.Datetime.now())

        # the demo path: a direct write
        sched.next_due = False
        run2 = self._mk_run('QF2 June', '2026-06-01', '2026-06-30',
                            state='draft')
        self._mk_slip(run2, self.emp1, basic=1.0, net=1.0, emp_cost=0.0)
        run2.write({'state': 'done'})
        self.assertTrue(sched.next_due)

        # a failing mark never blocks or undoes an approval (R4)
        sched.next_due = False
        run3 = self._mk_run('QF2 July', '2026-07-01', '2026-07-31',
                            state='draft')
        self._mk_slip(run3, self.emp1, basic=1.0, net=1.0, emp_cost=0.0)
        Sched = type(self.env['pb.explorer.schedule'])
        with patch.object(Sched, '_mark_due_after_run',
                          side_effect=RuntimeError('boom')):
            self.assertTrue(run3._approval_apply(request))
        self.assertEqual(run3.state, 'done')
        self.assertFalse(sched.next_due)

        # another company's run does not make this one due
        other_run = self._mk_run('QF2 B', '2026-05-01', '2026-05-31',
                                 state='draft')
        emp_b = self._mk_employee('QF2 B person', None, self.company_b)
        self._mk_slip(other_run, emp_b, basic=1.0, net=1.0, emp_cost=0.0,
                      company=self.company_b)
        other_run.write({'state': 'done'})
        self.assertFalse(sched.next_due)

    # ------------------------------------------------------------- T12
    def test_t12_one_failure_stops_nothing_and_the_caps_hold(self):
        self._mail_on()
        view = self._view()
        first = self._schedule(view, [self.owner])
        second = self._schedule(view, [self.owner])
        past = fields.Datetime.now() - timedelta(minutes=2)
        (first | second).write({'next_due': past})
        Sched = type(self.env['pb.explorer.schedule'])
        real = Sched._send_one

        def flaky(self_, trigger='schedule'):
            if self_.id == first.id:
                raise RuntimeError('boom')
            return real(self_, trigger)
        with patch.object(Sched, '_send_one', flaky):
            self.env['pb.explorer.schedule']._cron_send_due()
        self.assertFalse(first.log_ids)
        self.assertEqual(second.log_ids.mapped('state'), ['queued'])
        # the failed one still moved on: no retry storm
        self.assertGreater(first.next_due, fields.Datetime.now())

        ex = self._as(self.owner)
        with self.assertRaises(UserError):
            ex.schedule_save(view.id, {'cadence': 'weekly',
                                       'recipient_ids': list(range(1, 27))})
        with self.assertRaises(UserError):
            ex.schedule_save(view.id, {'cadence': 'weekly',
                                       'recipient_ids': []})
        # only people who can open the Explorer can receive it
        with self.assertRaises(UserError):
            ex.schedule_save(view.id, {'cadence': 'weekly',
                                       'recipient_ids': [self.plain.id]})
        # only the view's owner can schedule it
        shared = self._view(shared=True)
        with self.assertRaises(UserError):
            self._as(self.other).schedule_save(
                shared.id, {'cadence': 'weekly',
                            'recipient_ids': [self.other.id]})
        Model = self.env['pb.explorer.schedule'].sudo()
        for _i in range(18):
            Model.create({'view_id': view.id, 'user_id': self.owner.id,
                          'company_id': self.company.id,
                          'recipient_ids': [(6, 0, [self.owner.id])]})
        with self.assertRaises(UserError):
            ex.schedule_save(view.id, {'cadence': 'weekly',
                                       'recipient_ids': [self.owner.id]})
        # the drawer reads back cleanly, with a sentence in plain words
        drawer = ex.schedule_drawer(view.id)
        self.assertEqual(drawer['caps'], {'recipients': 25, 'schedules': 20})
        self.assertEqual(drawer['schedules'][0]['sentence'],
                         'Every Monday morning, to you, as an Excel file '
                         'with a link')
        offered = {p['id'] for p in drawer['people']}
        self.assertIn(self.other.id, offered)
        self.assertNotIn(self.plain.id, offered)
        # a schedule is not readable by a stranger
        stranger = self.env['pb.explorer.schedule'].with_user(self.other)
        self.assertFalse(stranger.search([('id', '=', first.id)]))
