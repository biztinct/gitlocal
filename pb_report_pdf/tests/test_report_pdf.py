# -*- coding: utf-8 -*-
"""DOCSTUDIO B — numbered tests (handover "Phase B"). The Explorer view and
the scheduled send live in `pb_report_pdf_send/tests` (they need the
Explorer's pay world); static and PO gates in test_static.py.

Real PDFs are made with the PDF engine when it is installed on the machine
running the tests (`force_report_rendering`); otherwise those tests read the
HTML the engine would be given — the same document.
"""
import base64
import io
import re
import time
from datetime import date, timedelta
from unittest.mock import patch

import lxml.html

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.misc import format_date

from odoo.addons.pb_report_pdf.models import layout as layout_module

MODEL = 'pb.report.definition'


def _pages(data):
    """The text of each page (a real PDF) or of the whole document (HTML)."""
    if data[:4] == b'%PDF':
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return [' '.join((page.extract_text() or '').split()) for page in reader.pages]
    return [' '.join(lxml.html.fromstring(data.decode('utf-8')).text_content().split())]


def _flat(text):
    return ' '.join(text.split())


@tagged('post_install', '-at_install', 'pb_report_pdf')
class TestReportPdf(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.co1 = env.company
        cur1 = cls.co1.currency_id
        other = env.ref('base.EUR') if cur1 != env.ref('base.EUR') else env.ref('base.VND')
        other.active = True
        cls.cur1, cls.cur2 = cur1, other
        cls.co2 = env['res.company'].with_context(chart_template_load=True).create({
            'name': 'DEMO PDF Second', 'currency_id': other.id})
        both = [(6, 0, [cls.co1.id, cls.co2.id])]
        pay = 'om_hr_payroll.group_hr_payroll_manager'
        base = 'base.group_user,hr.group_hr_user,hr_contract.group_hr_contract_manager'
        extra = ''
        for xmlid in ('pb_hr_payroll_formula.group_formula_user',):
            if env.ref(xmlid, raise_if_not_found=False):
                extra += ',' + xmlid
        cls.admin_u = new_test_user(env, 'pbrp_admin', name='DEMO PDF Admin',
                                    groups=base + extra + ',base.group_system,' + pay,
                                    company_id=cls.co1.id, company_ids=both)
        cls.hr_u = new_test_user(env, 'pbrp_hr', name='DEMO PDF HR', groups=base,
                                 company_id=cls.co1.id,
                                 company_ids=[(6, 0, [cls.co1.id])])
        cls.plain_u = new_test_user(env, 'pbrp_plain', name='DEMO PDF Plain',
                                    groups='base.group_user')
        Dept = env['hr.department']
        cls.dept_a = Dept.create({'name': 'DEMO PDF Sales', 'company_id': cls.co1.id})
        cls.dept_b = Dept.create({'name': 'DEMO PDF Ops', 'company_id': cls.co1.id})
        cls.dept_c = Dept.create({'name': 'DEMO PDF Abroad', 'company_id': cls.co2.id})
        cls.dept_x = Dept.create({'name': 'DEMO PDF Odd', 'company_id': cls.co1.id})
        Emp = env['hr.employee']
        cls.long_word = 'Supercalifragilistic' * 12
        today = fields.Date.today()
        rows = [('DEMO PDF Ana', cls.dept_a, today - timedelta(days=400)),
                ('DEMO PDF Ben', cls.dept_a, today - timedelta(days=300)),
                ('DEMO PDF Lê Thị Hoà', cls.dept_a, today - timedelta(days=200)),
                ('DEMO PDF Dao', cls.dept_b, today - timedelta(days=100)),
                ('<script>alert("pdf")</script> DEMO PDF', cls.dept_x, None),
                ('DEMO PDF ' + cls.long_word, cls.dept_x, None)]
        cls.emps = Emp.browse()
        for name, dept, _start in rows:
            cls.emps |= Emp.create({'name': name, 'department_id': dept.id,
                                    'company_id': cls.co1.id})
        cls.fen = Emp.create({'name': 'DEMO PDF Fen', 'department_id': cls.dept_c.id,
                              'company_id': cls.co2.id})
        cls.ana, cls.ben, cls.hoa, cls.dao, cls.hostile, cls.longname = cls.emps
        cls.mine = [cls.dept_a.id, cls.dept_b.id, cls.dept_c.id]
        Contract = env['hr.contract']
        cls.contracts = Contract.browse()
        for emp, wage in ((cls.ana, 1000.0), (cls.ben, 2000.0), (cls.fen, 3000.0)):
            c = Contract.create({'name': 'DEMO PDF C %s' % emp.name, 'employee_id': emp.id,
                                 'company_id': emp.company_id.id, 'wage': wage,
                                 'date_start': today - timedelta(days=30)})
            c.state = 'open'
            cls.contracts |= c
        cls.real = env['ir.actions.report'].get_wkhtmltopdf_state() == 'ok'

    # ------------------------------------------------------------ helpers
    def _builder(self, user):
        return self.env['pb.report.builder'].with_user(user).with_context(
            allowed_company_ids=user.company_ids.ids, lang='en_US')

    def _pdf(self, user, lang='en_US', real=False):
        ctx = {'allowed_company_ids': user.company_ids.ids, 'lang': lang}
        if real:
            ctx['force_report_rendering'] = True
        return self.env['pb.report.pdf'].with_user(user).with_context(**ctx)

    def _people_report(self, user=None, columns=None, filters=None, group_by=None,
                       totals=None, shared=False, name='DEMO PDF People'):
        user = user or self.admin_u
        spec = {'subject': 'people',
                'columns': columns or ['name', 'department'],
                'filters': filters if filters is not None else [
                    {'key': 'department', 'op': 'in', 'value': self.mine}],
                'group_by': group_by or [], 'totals': totals or {}}
        card = self._builder(user).save_report(name, spec, shared)
        return self.env[MODEL].browse(card['id'])

    def _download(self, user, report, look=None, lang='en_US', real=False):
        pdf = self._pdf(user, lang, real)
        if look is None:
            look = pdf.open(MODEL, report.id)['look']
        res = pdf.download(MODEL, report.id, look)
        self.assertTrue(res.get('ok'), res.get('msg'))
        return res, base64.b64decode(res['data'])

    def _need_real(self):
        if not self.real:
            self.skipTest('the PDF engine is not installed on this machine')

    def _synthetic(self, n, cols=4):
        columns = [{'key': 'k%d' % i, 'label': 'Heading %d' % i,
                    'type': 'number' if i == cols - 1 else 'text'} for i in range(cols)]
        rows = [['Row %05d' % r] + ['cell %d-%d' % (r, i) for i in range(1, cols - 1)] + [r]
                for r in range(n)]
        return {'title': 'DEMO PDF Big', 'columns': columns, 'rows': rows,
                'truncated': False, 'note': '', 'groups': [], 'group_only': [],
                'totals': None, 'summary': False, 'sub': ''}

    # ------------------------------------------------------------ 1
    def test_01_install_is_silent(self):
        """No look, no job, no mail template, no Print menu entry."""
        self.assertFalse(self.env['pb.report.pdf.look'].search_count([]))
        module = self.env['ir.module.module'].search([('name', '=', 'pb_report_pdf')])
        data = self.env['ir.model.data'].search([('module', '=', 'pb_report_pdf')])
        models_made = set(data.mapped('model'))
        self.assertFalse(models_made & {'ir.cron', 'mail.template', 'ir.ui.menu'},
                         models_made)
        for xmlid in ('action_report_pdf_a4', 'action_report_pdf_a3'):
            action = self.env.ref('pb_report_pdf.%s' % xmlid)
            self.assertFalse(action.binding_model_id, 'never on a Print menu')
        self.assertEqual(module.state, 'installed')

    # ------------------------------------------------------------ 2 + 9
    def test_02_pdf_equals_the_screen_with_groups_subtotals_and_total(self):
        report = self._people_report(columns=['name', 'department'],
                                     group_by=['department'], totals={'name': 'count'})
        screen = self._builder(self.admin_u).run(dict(report.spec, subject=report.subject))
        heads = [c['label'] for c in screen['columns']]
        groups = {g['label']: g for g in screen['groups']}
        self.assertEqual(set(groups), {'DEMO PDF Sales', 'DEMO PDF Ops', 'DEMO PDF Abroad'})
        table = self._builder(self.admin_u)._pbrb_table(dict(report.spec, subject=report.subject))
        first, last = table['rows'][0], table['rows'][-1]

        res, data = self._download(self.admin_u, report, real=self.real)
        text = _flat(' '.join(_pages(data)))
        for head in heads:
            self.assertIn(head, text)
        self.assertIn(_flat(first[table['columns'].index(next(
            c for c in table['columns'] if c['key'] == 'name'))]), text)
        self.assertIn(_flat(last[0]) if isinstance(last[0], str) else '', text)
        for label, grp in groups.items():
            self.assertIn('Department: %s' % label, text)
            self.assertIn('Total %s · %s' % (label, grp['count']), text)
        self.assertIn('Grand total · %s' % screen['total'], text)
        self.assertEqual(res['rows'], screen['total'])
        self.assertTrue(res['name'].endswith('.pdf') and 'odoo' not in res['name'].lower())

        # two levels: headings and subtotals for both, as on screen
        two = self._people_report(columns=['name', 'department', 'company'],
                                  group_by=['company', 'department'],
                                  totals={'name': 'count'}, name='DEMO PDF Two levels')
        doc = self._pdf(self.admin_u)._pbrp_doc(
            self._pdf(self.admin_u)._pbrp_table(two),
            self.env['pb.report.pdf.look']._pbrp_resolve(MODEL, two.id, self.admin_u)[0])
        kinds = [(e['t'], e.get('level')) for e in doc['entries'] if e['t'] != 'r']
        self.assertIn(('g', 1), kinds)
        self.assertIn(('g', 2), kinds)
        self.assertIn(('s', 2), kinds)
        self.assertIn(('s', 1), kinds)
        self.assertEqual(kinds[-1], ('t', 0))

    # ------------------------------------------------------------ 3
    def test_03_three_thousand_rows_repeat_the_heading_and_never_split(self):
        self._need_real()
        report = self._people_report(name='DEMO PDF Big')
        big = self._synthetic(3000)
        with patch.object(type(self.env['pb.report.pdf']), '_pbrp_table',
                          lambda self_, rec: big):
            started = time.monotonic()
            res, data = self._download(self.admin_u, report, real=True)
            seconds = time.monotonic() - started
        pages = _pages(data)
        print('PBRP T03: 3,000 rows -> %s pages in %.1f s' % (len(pages), seconds))
        self.assertTrue(20 <= len(pages) <= 150, len(pages))
        for page in pages:
            self.assertIn('Heading 0', page, 'the heading row repeats on every page')
        seen = re.findall(r'Row (\d{5})', ' '.join(pages))
        self.assertEqual(len(seen), 3000, 'every row once')
        self.assertEqual(len(set(seen)), 3000)
        for page in pages:
            for num in re.findall(r'Row (\d{5})', page):
                self.assertIn('cell %d-1' % int(num), _flat(page),
                              'a row is never split across two pages')
        self.assertLess(seconds, 240)

    # ------------------------------------------------------------ 4
    def test_04_six_thousand_rows_print_five_thousand_and_say_so(self):
        report = self._people_report(name='DEMO PDF Huge')
        huge = self._synthetic(6000)
        with patch.object(type(self.env['pb.report.pdf']), '_pbrp_table',
                          lambda self_, rec: huge):
            opened = self._pdf(self.admin_u).open(MODEL, report.id)
            res, data = self._download(self.admin_u, report)
        pv = opened['preview']
        self.assertTrue(pv['capped'])
        self.assertEqual((pv['rows'], pv['total_rows']), (5000, 6000))
        self.assertIn('5,000', pv['cap_note'])
        self.assertIn('6,000', pv['cap_note'])
        self.assertTrue(res['capped'])
        self.assertEqual(res['rows'], 5000)
        html = data.decode('utf-8')
        self.assertEqual(len(re.findall(r'Row \d{5}', html)), 5000)
        self.assertIn('Row 04999', html)
        self.assertNotIn('Row 05000', html)
        self.assertIn('Only the first 5,000 of 6,000 rows are printed', html)

    # ------------------------------------------------------------ 5
    def test_05_fit_turns_the_page_sideways_past_the_column_limit(self):
        P = self._pdf(self.admin_u)
        look = self.env['pb.report.pdf.look']._pbrp_resolve(MODEL, 0, self.admin_u)[0]
        for cols, paper, turn, sideways in ((7, 'A4', 'fit', False), (8, 'A4', 'fit', True),
                                            (8, 'A3', 'fit', False), (12, 'A3', 'fit', True),
                                            (12, 'A4', 'upright', False),
                                            (2, 'A4', 'sideways', True)):
            doc = P._pbrp_doc(self._synthetic(5, cols), dict(look, paper=paper, turn=turn))
            self.assertEqual(doc['sideways'], sideways, (cols, paper, turn))
            w, h = doc['paper_mm']
            self.assertEqual(w > h, sideways)
        if self.real:
            report = self._people_report(name='DEMO PDF Wide')
            with patch.object(type(self.env['pb.report.pdf']), '_pbrp_table',
                              lambda self_, rec: self._synthetic(10, 9)):
                _res, data = self._download(self.admin_u, report, real=True)
            from PyPDF2 import PdfReader
            box = PdfReader(io.BytesIO(data)).pages[0].mediabox
            self.assertGreater(float(box.width), float(box.height), 'sideways A4')

    # ------------------------------------------------------------ 6
    def test_06_letterhead_on_and_off(self):
        report = self._people_report(name='DEMO PDF Letterhead')
        P = self._pdf(self.admin_u)
        look = P.open(MODEL, report.id)['look']
        _r, on = self._download(self.admin_u, report, dict(look, letterhead=True))
        _r, off = self._download(self.admin_u, report, dict(look, letterhead=False))
        on, off = on.decode('utf-8'), off.decode('utf-8')
        self.assertIn('data-report-margin-top="40"', on)
        self.assertIn('o_report_layout', on, "the company's own letterhead")
        self.assertNotIn('o_report_layout', off)
        self.assertIn('data-report-margin-top="16"', off)
        self.assertIn('pbrp-footer', off)
        self.assertIn('Printed on', off)
        self.assertIn('class="topage"', off)
        if self.real:
            for flag in (True, False):
                _r, data = self._download(self.admin_u, report, dict(look, letterhead=flag),
                                          real=True)
                pages = _pages(data)
                self.assertIn('DEMO PDF Letterhead', pages[0])

    # ------------------------------------------------------------ 7 + 8
    def test_07_column_width_saved_and_applied_08_hidden_column_absent(self):
        report = self._people_report(columns=['name', 'department', 'job'],
                                     name='DEMO PDF Widths')
        P = self._pdf(self.admin_u)
        look = P.open(MODEL, report.id)['look']
        look['sub_on'] = False          # the second line names the filtered departments
        look['columns'] = {'name': {'w': 55}, 'department': {'w': 25}, 'job': {'w': 20}}
        saved = P.save(MODEL, report.id, look)
        self.assertEqual(saved['look']['columns']['name'], {'w': 55.0})
        again = P.open(MODEL, report.id)
        self.assertEqual(again['origin'], 'mine')
        self.assertEqual(again['preview']['widths'], {'name': 55.0, 'department': 25.0,
                                                      'job': 20.0})
        _r, data = self._download(self.admin_u, report, again['look'])
        self.assertIn('width: 55.0%', data.decode('utf-8'))

        look = dict(again['look'])
        look['columns'] = dict(look['columns'], department={'hide': True, 'w': 25})
        pv = P.preview(MODEL, report.id, look)
        self.assertNotIn('department', pv['widths'])
        self.assertNotIn('DEMO PDF Sales', pv['html'])
        res, data = self._download(self.admin_u, report, look, real=self.real)
        text = ' '.join(_pages(data))
        self.assertNotIn('Department', text)
        self.assertNotIn('DEMO PDF Sales', text)
        self.assertIn('DEMO PDF Ana', text)
        # all columns off: refused in words, nothing made
        look['columns'] = {k: {'hide': True} for k in ('name', 'department', 'job')}
        res = P.download(MODEL, report.id, look)
        self.assertFalse(res['ok'])
        self.assertEqual(res['msg'], 'Pick at least one column to print.')

    # ------------------------------------------------------------ 10
    def test_10_two_currencies_are_never_added(self):
        spec = {'subject': 'contracts', 'columns': ['employee', 'company', 'pay'],
                'filters': [{'key': 'employee', 'op': 'in', 'value': [
                    self.ana.id, self.ben.id, self.fen.id]}],
                'totals': {'pay': 'sum'}}
        card = self._builder(self.admin_u).save_report('DEMO PDF Pay', spec)
        report = self.env[MODEL].browse(card['id'])
        P = self._pdf(self.admin_u)
        info = P._pbrp_table(report)
        look = P.open(MODEL, report.id)['look']
        doc = P._pbrp_doc(info, look)
        total = doc['entries'][-1]
        self.assertEqual(total['t'], 't')
        pay_pos = [c['key'] for c in doc['columns']].index('pay')
        lines = total['cells'][pay_pos]
        self.assertEqual(len(lines), 2, lines)
        flat = ' '.join(lines)
        for amount in ('6,000', '4,000', '5,000'):
            self.assertNotIn(amount, flat, 'two currencies were added: %s' % flat)
        self.assertNotIn('pay__currency', [c['key'] for c in doc['columns']],
                         'the money cells carry their currency')

    # ------------------------------------------------------------ 11
    def test_11_a_reader_with_less_access_gets_less_in_the_same_shared_look(self):
        spec = {'subject': 'contracts', 'columns': ['employee', 'company', 'pay'],
                'filters': [{'key': 'employee', 'op': 'in', 'value': [
                    self.ana.id, self.ben.id, self.fen.id]}]}
        card = self._builder(self.admin_u).save_report('DEMO PDF Shared pay', spec, True)
        report = self.env[MODEL].browse(card['id'])
        P = self._pdf(self.admin_u)
        look = P.open(MODEL, report.id)['look']
        look.update({'title': 'DEMO PDF Board pack', 'color': 'ink', 'paper': 'A3'})
        P.save(MODEL, report.id, look, shared=True)

        mine = self._pdf(self.admin_u).open(MODEL, report.id)
        # a fresh request for the reader: nothing read by the owner is in the
        # record cache (ledger DS-8)
        self.env.invalidate_all()
        theirs = self._pdf(self.hr_u).open(MODEL, report.id)
        self.assertTrue(theirs['ok'], theirs.get('msg'))
        self.assertEqual(theirs['origin'], 'shared')
        self.assertEqual(theirs['shared_by'], 'DEMO PDF Admin')
        self.assertEqual((theirs['look']['title'], theirs['look']['color'],
                          theirs['look']['paper']), ('DEMO PDF Board pack', 'ink', 'A3'))
        self.assertIn('pay', [c['key'] for c in mine['columns']])
        self.assertNotIn('pay', [c['key'] for c in theirs['columns']], 'pay hidden')
        _r, mine_pdf = self._download(self.admin_u, report, mine['look'])
        self.env.invalidate_all()
        _r, their_pdf = self._download(self.hr_u, report, theirs['look'])
        mine_t, their_t = mine_pdf.decode(), their_pdf.decode()
        self.assertIn('DEMO PDF Fen', mine_t)
        self.assertNotIn('DEMO PDF Fen', their_t, 'other company: not theirs')
        self.assertIn('DEMO PDF Board pack', their_t, 'the same shared look')
        self.assertNotIn('2,000', their_t, 'no pay figure for a reader without pay')
        self.assertIn('2,000', mine_t)
        # they may keep their own copy, never share the owner's report
        with self.assertRaises(AccessError):
            self._pdf(self.hr_u).save(MODEL, report.id, theirs['look'], shared=True)
        own = self._pdf(self.hr_u).save(MODEL, report.id, dict(theirs['look'], color='slate'))
        self.assertEqual(own['origin'], 'mine')
        self.assertEqual(self._pdf(self.admin_u).open(MODEL, report.id)['look']['color'], 'ink')

    # ------------------------------------------------------------ 12
    def test_12_vietnamese_letters_and_dates(self):
        self.env['res.lang']._activate_lang('vi_VN')
        self.admin_u.lang = 'vi_VN'
        report = self._people_report(columns=['name', 'start_date'], name='DEMO PDF Hoà')
        start = date(2026, 3, 9)
        self.env['hr.contract'].create({'name': 'DEMO PDF C Hoa', 'employee_id': self.hoa.id,
                                        'date_start': start, 'wage': 1}).state = 'open'
        P = self._pdf(self.admin_u, lang='vi_VN', real=self.real)
        info = P._pbrp_table(report)
        look = P.open(MODEL, report.id)['look']
        look['title'] = 'Báo cáo nhân sự Hoà'
        res = P.download(MODEL, report.id, look)
        self.assertTrue(res['ok'], res.get('msg'))
        text = _flat(' '.join(_pages(base64.b64decode(res['data']))))
        self.assertIn('Lê Thị Hoà', text)
        self.assertIn('Báo cáo nhân sự Hoà', text)
        first = [r for r in info['rows'] if 'Hoà' in str(r[0])]
        if first and first[0][1]:
            vi_env = self.env(context=dict(self.env.context, lang='vi_VN'))
            self.assertIn(format_date(vi_env, first[0][1]), text)

    # ------------------------------------------------------------ 13
    def test_13_hostile_text_is_inert_and_long_words_wrap(self):
        report = self._people_report(name='DEMO PDF Hostile', filters=[
            {'key': 'department', 'op': 'in', 'value': [self.dept_x.id]}])
        P = self._pdf(self.admin_u)
        look = P.open(MODEL, report.id)['look']
        look['title'] = '<img src=x onerror=alert(1)> DEMO'
        look['note'] = '<script>alert(2)</script>'
        pv = P.preview(MODEL, report.id, look)
        res, data = self._download(self.admin_u, report, look)
        for html in (pv['html'], data.decode('utf-8')):
            self.assertNotIn('<script>alert', html)
            self.assertNotIn('<img src=x', html)
            self.assertIn('&lt;script&gt;alert(&#34;pdf&#34;)', html.replace('&quot;', '&#34;'))
            self.assertIn('table-layout: fixed', html)
        if self.real:
            res, data = self._download(self.admin_u, report, look, real=True)
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(data))
            box = reader.pages[0].mediabox
            self.assertLess(float(box.width), float(box.height), 'still upright A4')
            text = ' '.join(p.extract_text() for p in reader.pages)
            self.assertIn('Supercalifragilistic', text)
            self.assertNotIn(self.long_word, text.replace('\n', '§'),
                             'the very long word wraps inside its column')

    # ------------------------------------------------------------ rules
    def test_14_looks_follow_the_rules(self):
        report = self._people_report(name='DEMO PDF Rules')
        P = self._pdf(self.admin_u)
        look = P.open(MODEL, report.id)['look']
        P.save(MODEL, report.id, dict(look, color='soft'))
        mine = self.env['pb.report.pdf.look'].search([('source_id', '=', report.id)])
        Look_hr = self.env['pb.report.pdf.look'].with_user(self.hr_u)
        self.assertFalse(Look_hr.search([('id', '=', mine.id)]), 'a private look')
        with self.assertRaises(AccessError):
            mine.with_user(self.hr_u).write({'look': {}})
        with self.assertRaises(AccessError):
            Look_hr.create({'is_default': True, 'company_id': self.co1.id, 'look': {}})
        with self.assertRaises(AccessError):
            self._pdf(self.hr_u).set_default(look)
        # a private report of someone else is not there for them
        res = self._pdf(self.hr_u).open(MODEL, report.id)
        self.assertFalse(res['ok'])
        self.assertIn('no longer available', res['msg'])
        # the company default: new reports start with it
        P.set_default(dict(look, paper='A3', color='slate', title='never travels'))
        other = self._people_report(name='DEMO PDF Fresh')
        fresh = P.open(MODEL, other.id)
        self.assertEqual(fresh['origin'], 'default')
        self.assertEqual((fresh['look']['paper'], fresh['look']['color'],
                          fresh['look']['title']), ('A3', 'slate', ''))
        P.clear_default()
        self.assertEqual(P.open(MODEL, other.id)['origin'], 'builtin')
        # back to the standard look
        back = P.reset(MODEL, report.id)
        self.assertEqual(back['origin'], 'builtin')
        self.assertFalse(mine.exists())

    def test_15_refusals_are_sentences(self):
        P = self._pdf(self.admin_u)
        for model, rid in (('no.such.model', 1), ('res.partner', self.admin_u.partner_id.id),
                           (MODEL, 999999), ('pb.report.pdf', 1)):
            res = P.open(model, rid)
            self.assertFalse(res['ok'])
            self.assertTrue(res['msg'] and 'Traceback' not in res['msg'])
        report = self._people_report(name='DEMO PDF Gate')
        res = self._pdf(self.plain_u).open(MODEL, report.id)
        self.assertFalse(res['ok'])
        res = self._pdf(self.plain_u).download(MODEL, report.id, {})
        self.assertFalse(res['ok'])
        with self.assertRaises(UserError):     # AccessError is a UserError (DS-R6)
            self._pdf(self.plain_u).save(MODEL, report.id, {})

    def test_16_the_look_is_cleaned(self):
        from odoo.addons.pb_report_pdf.models.look import clean_look
        look = clean_look({'paper': 'Letter', 'turn': 'diagonal', 'size': 99, 'font': 'comic',
                           'color': '#ff0000', 'title': 'x' * 500, 'note': 'a\x00b',
                           'columns': {'ok_key': {'w': 500, 'hide': 1}, 'bad key!': {'w': 10},
                                       'k2': {'w': 30}}, 'stripes': 0, 'evil': 1})
        self.assertEqual((look['paper'], look['turn'], look['size'], look['font'],
                          look['color']), ('A4', 'fit', 10, 'clean', 'indigo'))
        self.assertEqual(len(look['title']), 160)
        self.assertEqual(look['note'], 'ab')
        self.assertEqual(look['columns'], {'ok_key': {'hide': True}, 'k2': {'w': 30.0}})
        self.assertFalse(look['stripes'])
        self.assertNotIn('evil', look)
        self.assertEqual(layout_module.ROW_CAP, 5000)
