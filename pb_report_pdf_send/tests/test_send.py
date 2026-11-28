# -*- coding: utf-8 -*-
"""DOCSTUDIO B — the saved Explorer view as a PDF (test 14) and the regular
send "PDF in my look" (test 15). The world is the QF2 one (`pb_explorer`
tests): one company, two departments in two divisions, people paid in April,
an owner and a reader of each half. Subclassed for its `setUpClass` and
helpers only — the loader runs only the tests a class defines itself."""
import base64
import re
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.pb_explorer.tests.test_wdgap_qf2 import TestWdgapQf2

VIEW = 'pb.explorer.view'


@tagged('post_install', '-at_install', 'pb_report_pdf')
class TestReportPdfExplorer(TestWdgapQf2):

    def _pdf(self, user):
        return self.env['pb.report.pdf'].with_user(user).with_context(
            allowed_company_ids=[self.company.id], lang='en_US')

    # ------------------------------------------------------------ 14
    def test_14_a_saved_explorer_view_prints(self):
        view = self._view(name='DEMO Net by department')
        P = self._pdf(self.owner)
        opened = P.open(VIEW, view.id)
        self.assertTrue(opened['ok'], opened.get('msg'))
        keys = [c['key'] for c in opened['columns']]
        self.assertEqual((keys[0], keys[1], keys[-1]), ('name', 'currency', 'total'))
        cur = next(c for c in opened['columns'] if c['key'] == 'currency')
        self.assertTrue(cur['hide'], 'the money cells carry their currency')
        self.assertTrue(opened['sub_default'], 'the period in words')
        res = P.download(VIEW, view.id, opened['look'])
        self.assertTrue(res['ok'], res.get('msg'))
        html = base64.b64decode(res['data']).decode('utf-8')
        self.assertIn('DEMO Net by department', html)
        self.assertIn('>Explorer Dept<', html)

        # without pb_excel_layout the same table is built here
        table = view.with_user(self.owner).with_context(
            allowed_company_ids=[self.company.id])._pbxl_table()
        own = P._pbrp_table_view(view.with_user(self.owner))
        self.assertEqual([c['key'] for c in own['columns']], [c['key'] for c in table['columns']])
        self.assertEqual(own['rows'], table['rows'])

        # a reader who may not open the Explorer gets a sentence
        res = self._pdf(self.plain).open(VIEW, view.id)
        self.assertFalse(res['ok'])

    def test_14b_two_currencies_in_a_view_are_never_added(self):
        view = self._view(name='DEMO Two monies')
        P = self._pdf(self.owner)
        with self._patch_query(self._fake_payload(self._two_currency_parts())):
            info = P._pbrp_table(view.with_user(self.owner))
            look = P.open(VIEW, view.id)['look']
            doc = P._pbrp_doc(info, look)
        total = doc['entries'][-1]
        self.assertEqual(total['t'], 't')
        pos = [c['key'] for c in doc['columns']].index('total')
        lines = total['cells'][pos]
        self.assertEqual(len(lines), 2, lines)
        self.assertTrue(any('1,500,000' in ln for ln in lines))
        self.assertTrue(any('40.5' in ln for ln in lines))
        self.assertFalse(any('1,500,040' in ln for ln in lines))

    # ------------------------------------------------------------ 15
    def test_15_regular_send_as_a_pdf_in_my_look(self):
        Visibility = self.env['pb.group.visibility'].sudo()
        Visibility.set_for(self.reader_one.id, 'division', self.div_one.id)
        Visibility.set_for(self.reader_two.id, 'division', self.div_two.id)
        view = self._view(name='People by department', spec={
            'measure': 'headcount', 'dimension': 'department_id', 'grain': 'none'})
        P = self._pdf(self.owner)
        look = P.open(VIEW, view.id)['look']
        P.save(VIEW, view.id, dict(look, title='DEMO Board pack', color='ink', letterhead=False))
        vals = {'cadence': 'weekly', 'weekday': '0', 'monthday': 1,
                'recipient_ids': [self.reader_one.id, self.reader_two.id],
                'pbrp_pdf': True}
        payload = self._as(self.owner).schedule_save(view.id, vals)
        self.assertTrue(payload['pbrp_pdf'])
        self.assertFalse(payload['layout_id'])
        sched = self.env['pb.explorer.schedule'].browse(payload['id'])
        with self.assertRaises(UserError):
            self._as(self.owner).schedule_save(view.id, dict(vals, layout_id=1),
                                               schedule_id=sched.id)

        # mail off: logged as today, nothing built
        sched._send_one('now')
        self.assertEqual(set(sched.log_ids.mapped('state')), {'email_off'})

        self._mail_on()
        built_as = []
        real = type(self.env['pb.report.pdf'])._pbrp_pdf

        def spy(self_, info, look, company=None):
            built_as.append((self_.env.uid, look['title']))
            return real(self_, info, look, company=company)

        with patch.object(type(self.env['pb.report.pdf']), '_pbrp_pdf', spy):
            sched._send_one('now')
        self.assertEqual(sorted(built_as), sorted([
            (self.reader_one.id, 'DEMO Board pack'), (self.reader_two.id, 'DEMO Board pack')]),
            'built as each person, in the look of the person who set it up')
        logs = sched.log_ids.filtered(lambda l: l.batch == sched.send_count)
        self.assertEqual(set(logs.mapped('state')), {'queued'})
        seen = {}
        for log in logs:
            att = log.mail_id.attachment_ids
            self.assertEqual(len(att), 1)
            self.assertEqual(att.mimetype, 'application/pdf')
            self.assertTrue(att.name.endswith('.pdf'))
            self.assertNotIn('odoo', att.name.lower())
            body = base64.b64decode(att.datas).decode('utf-8')
            self.assertIn('DEMO Board pack', body)
            self.assertIn('Printed on', body)
            self.assertIn(log.user_id.name, body)
            seen[log.user_id.id] = set(re.findall(r'>(Explorer Dept(?: 2)?)<', body))
            self.assertIn('attached PDF', str(log.mail_id.body_html))
        self.assertEqual(seen[self.reader_one.id], {'Explorer Dept'})
        self.assertEqual(seen[self.reader_two.id], {'Explorer Dept 2'})

        # the PDF cannot be made: the standard Excel goes, the history says why
        def broken(self_, info, look, company=None):
            raise ValueError('DEMO broken look')

        with patch.object(type(self.env['pb.report.pdf']), '_pbrp_pdf', broken):
            summary = sched._send_one('now')
        self.assertEqual(summary['sent'], 2)
        logs = sched.log_ids.filtered(lambda l: l.batch == sched.send_count)
        self.assertEqual(set(logs.mapped('state')), {'layout_failed'})
        self.assertEqual(set(logs.mapped('reason')), {'pdf_failed|'})
        for log in logs:
            att = log.mail_id.attachment_ids
            self.assertTrue(att.name.endswith('.xlsx'))
            self.assertIn('attached Excel file', str(log.mail_id.body_html))
        hist = sched._pbx_payload()['history'][0]
        self.assertEqual(hist['summary'], 'Sent to 2 of 2')
        self.assertEqual(hist['lines'][0]['label'],
                         'Sent as the standard Excel — the PDF could not be made')

        # back to the standard Excel
        payload = self._as(self.owner).schedule_save(view.id, dict(vals, pbrp_pdf=False),
                                                     schedule_id=sched.id)
        self.assertFalse(payload['pbrp_pdf'])
