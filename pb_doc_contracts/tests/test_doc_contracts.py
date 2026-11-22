# -*- coding: utf-8 -*-
"""DOCSTUDIO phase A2 — numbered tests of the handover.

Run: odoo-bin -i pb_doc_contracts --test-enable --test-tags /pb_doc_contracts
Reports render as HTML in test mode (no PDF engine), which is what is read
here; the real PDF (wkhtmltopdf, Vietnamese letters) is checked in the
browser walk and the report.
"""
import base64
import re

from lxml import etree

from odoo.exceptions import UserError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_doc_contracts.models.contract_common import (
    CONTRACT_KEYS, CONTRACT_KIND, SHIPPED_RULES,
)

PAY_REFUSAL = "This contract shows pay, and you may not see this person's pay."


def _text(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html or ''))


@tagged('post_install', '-at_install', 'pb_doc_contracts')
class ContractDocCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Lang = env['res.lang']
        for code in ('vi_VN', 'id_ID'):
            if not Lang._lang_get(code):
                Lang._activate_lang(code)
        cls.company = env.company
        cls.company_b = env['res.company'].create({'name': 'DEMO Contracts B'})
        env.user.company_ids = [(4, cls.company_b.id)]
        cls.vietnam = env.ref('base.vn')
        cls.indonesia = env.ref('base.id')
        Emp = env['hr.employee']
        cls.job = env['hr.job'].create({'name': 'DEMO Planner'})
        cls.dept = env['hr.department'].create({'name': 'DEMO Planning'})
        cls.boss = Emp.create({'name': 'DEMO Boss', 'company_id': cls.company.id})
        cls.calendar = env['resource.calendar'].create({'name': 'DEMO Office hours',
                                                         'company_id': cls.company.id})
        base = {'company_id': cls.company.id, 'job_id': cls.job.id, 'department_id': cls.dept.id,
                'parent_id': cls.boss.id}
        cls.emp_vn = Emp.create(dict(base, name='DEMO Nguyen An', lang='vi_VN',
                                     identification_id='DEMO079123', birthday='1990-04-15',
                                     private_street='DEMO 12 Le Loi', private_city='DEMO Hue',
                                     country_id=cls.vietnam.id))
        cls.emp_id = Emp.create(dict(base, name='DEMO Siti Rahma', lang='id_ID'))
        cls.emp_sg = Emp.create(dict(base, name='DEMO Tan Wei', lang='en_US'))
        cls.emp_empty = Emp.create({'name': 'DEMO Empty Person', 'company_id': cls.company.id})
        if 'payroll_country' in Emp._fields:
            cls.emp_vn.payroll_country = 'VN'
            cls.emp_id.payroll_country = 'ID'
            cls.emp_sg.payroll_country = 'SG'
            cls.emp_empty.payroll_country = 'SG'
        Contract = env['hr.contract']
        common = {'state': 'open', 'job_id': cls.job.id, 'department_id': cls.dept.id,
                  'resource_calendar_id': cls.calendar.id, 'company_id': cls.company.id}
        cls.c_vn = Contract.create(dict(common, name='DEMO-VN-1', employee_id=cls.emp_vn.id,
                                        wage=25000000.0, date_start='2025-03-01',
                                        date_end='2027-02-28', trial_date_end='2025-04-30'))
        cls.c_id = Contract.create(dict(common, name='DEMO-ID-1', employee_id=cls.emp_id.id,
                                        wage=9000000.0, date_start='2025-06-01'))
        cls.c_sg = Contract.create(dict(common, name='DEMO-SG-1', employee_id=cls.emp_sg.id,
                                        wage=6500.0, date_start='2024-01-15'))
        cls.c_empty = Contract.create({'name': 'DEMO-EMPTY', 'employee_id': cls.emp_empty.id,
                                       'wage': 1000.0, 'state': 'draft',
                                       'company_id': cls.company.id})
        cls.Panel = env['pb.contracts']
        cls.Studio = env['pb.doc.studio']
        cls.generic = env.ref('pb_doc_contracts.contract_template_generic')
        cls.vn_copy = env.ref('pb_doc_contracts.contract_template_vn')
        cls.id_copy = env.ref('pb_doc_contracts.contract_template_id')

    def doc(self, contract, panel=None, **kw):
        # an AbstractModel recordset is always empty, so never `panel or ...`
        res = (self.Panel if panel is None else panel).contract_document(contract.id, **kw)
        self.assertTrue(res['ok'], res.get('msg'))
        return res

    def user(self, login, groups, company=None):
        company = company or self.company
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'DEMO %s' % login, 'login': login,
            'company_id': company.id, 'company_ids': [(6, 0, [company.id])],
            'group_ids': [(6, 0, [self.env.ref(g).id for g in groups])]})


@tagged('post_install', '-at_install', 'pb_doc_contracts')
class TestDocContracts(ContractDocCase):

    # ------------------------------------------------------------ 1
    def test_01_install_is_silent(self):
        """The shipped contracts carry words only; no template of another
        module was written by the install; no job, no mail template."""
        mine = self.generic | self.vn_copy | self.id_copy
        for t in mine:
            self.assertFalse(t.pbds_edited or t.pbds_page or t.pbds_rules
                             or t.pbds_version_ids or t.pbds_original_json, t.name)
            self.assertFalse(t.company_id)
        self.assertEqual(self.vn_copy.pbds_replaces_id, self.generic)
        self.assertEqual(self.vn_copy.pbds_country_ids, self.vietnam)
        self.assertEqual(self.id_copy.pbds_country_ids, self.indonesia)
        installed = min(self.env['ir.model.data'].search(
            [('module', '=', 'pb_doc_contracts'), ('model', '=', 'pb.letter.template')]).mapped('create_date'))
        others = self.env['pb.letter.template'].with_context(active_test=False).search(
            [('id', 'not in', mine.ids)])
        for t in others:
            self.assertLessEqual(t.write_date, installed, t.name)
        self.assertFalse(self.env['ir.cron'].search([('cron_name', 'ilike', 'contract document')]))
        self.assertFalse(self.env['ir.model.data'].search(
            [('module', '=', 'pb_doc_contracts'), ('model', 'in', ('ir.cron', 'mail.template'))]))
        # vault category = the labour contract one
        cat = self.env.ref('pb_employee_vault.cat_labor_contract')
        self.assertEqual(mine.mapped('vault_category_id'), cat)

    # ------------------------------------------------------------ 2
    def test_02_right_copy_per_country(self):
        vn, idn, sg = self.doc(self.c_vn), self.doc(self.c_id), self.doc(self.c_sg)
        self.assertEqual(vn['document']['used_id'], self.vn_copy.id)
        self.assertEqual(idn['document']['used_id'], self.id_copy.id)
        self.assertEqual(sg['document']['used_id'], self.generic.id)
        self.assertEqual(vn['document']['id'], self.generic.id)
        self.assertIn('HỢP ĐỒNG LAO ĐỘNG', vn['html'])
        self.assertIn('PERJANJIAN KERJA', idn['html'])
        self.assertIn('This employment contract is made on', sg['html'])
        self.assertIn('DEMO Tan Wei', sg['html'])
        self.assertIn('Using the wording for Vietnam', vn['document']['note'])
        # bilingual copies read in their own language; the original in English
        self.assertEqual(vn['read_lang'], 'vi_VN')
        self.assertEqual(idn['read_lang'], 'id_ID')
        self.assertEqual(sg['read_lang'], 'en_US')
        self.assertEqual([l['code'] for l in sg['langs']], ['en_US'])
        # no field left unfilled as raw text
        for res in (vn, idn, sg):
            self.assertNotIn('${', res['html'])

    # ------------------------------------------------------------ 3
    def test_03_fixed_term_vs_open_ended(self):
        vn = _text(self.doc(self.c_vn)['html'])
        self.assertIn('Hợp đồng xác định thời hạn', vn)
        self.assertIn('28/02/2027', vn)
        self.assertNotIn('không xác định thời hạn', vn)
        idn = _text(self.doc(self.c_id)['html'])
        self.assertIn('waktu tidak tertentu', idn)
        self.assertNotIn('Fixed-term contract', idn)
        sg = _text(self.doc(self.c_sg)['html'])
        self.assertIn('has no end date', sg)
        self.assertNotIn('This is a fixed-term contract', sg)
        self.c_sg.date_end = '2026-12-31'
        sg2 = _text(self.doc(self.c_sg)['html'])
        self.assertIn('This is a fixed-term contract', sg2)
        self.assertIn('31, 2026', sg2)
        # the left-out paragraphs are named, with where to change them
        left = self.doc(self.c_sg)['left_out']
        self.assertTrue(left)
        self.assertTrue(all(r['sentence'].startswith('Only when') for r in left))

    # ------------------------------------------------------------ 4
    def test_04_trial_paragraph(self):
        self.assertIn('Thời gian thử việc kết thúc vào ngày 30/04/2025', _text(self.doc(self.c_vn)['html']))
        res = self.doc(self.c_sg)
        self.assertNotIn('Trial period', _text(res['html']))
        trial = [r for r in res['left_out'] if r['id'] == 'rtrial']
        self.assertTrue(trial)
        self.assertEqual(trial[0]['jump'], {'kind': 'term', 'name': 'trial_date_end'})
        self.c_sg.trial_date_end = '2024-03-15'
        self.assertIn('trial period that ends on', _text(self.doc(self.c_sg)['html']))

    # ------------------------------------------------------------ 5
    def test_05_bilingual_table_in_the_pdf(self):
        res = self.Panel.contract_document_pdf(self.c_vn.id)
        self.assertTrue(res['ok'], res.get('msg'))
        out = base64.b64decode(res['data']).decode('utf-8', 'ignore')
        # test mode: the report is HTML — the two-column clauses and the
        # contract page's CSS are in it, Vietnamese letters intact
        self.assertIn('pbdc-bi', out)
        self.assertIn('table.pbdc-bi td + td', out)
        self.assertIn('Người lao động', out)
        self.assertIn('Thời giờ làm việc', out)
        self.assertNotIn('Authorised signatory</div>', out, 'no letter signature block on a contract page')
        self.assertTrue(res['name'].endswith('DEMO Nguyen An.pdf'))
        # the clause tables are real two-cell rows
        tree = etree.HTML(out)
        rows = tree.xpath("//table[contains(@class,'pbdc-bi')]//tr")
        self.assertGreater(len(rows), 8)
        self.assertTrue(all(len(r.xpath('./td')) == 2 for r in rows))

    # ------------------------------------------------------------ 6
    def test_06_every_field_has_a_value_or_a_chip(self):
        self.generic.with_context(lang='en_US').body_html = ''.join(
            '<p>%s=${%s}</p>' % (k, k) for k in CONTRACT_KEYS + ('monthly_pay', 'contract_start'))
        full = self.doc(self.c_sg)
        missing = {m['key'] for m in full['missing']}
        for key in CONTRACT_KEYS:
            with self.subTest(key=key):
                shown = full['values'].get(key)
                self.assertTrue(shown or key in missing, '%s has neither a value nor a chip' % key)
        # the empty person: every empty field is an amber chip, nothing silent
        empty = self.doc(self.c_empty)
        chips = {m['key']: m for m in empty['missing']}
        for key in ('trial_end', 'contract_job', 'id_number', 'home_address', 'pay_scheme'):
            self.assertIn(key, chips)
        self.assertEqual(chips['trial_end']['text'], 'No trial period end date')
        self.assertEqual(chips['trial_end']['jump'], {'kind': 'term', 'name': 'trial_date_end'})
        self.assertEqual(chips['id_number']['jump']['kind'], 'employee')
        self.assertEqual(chips['id_number']['text'], 'No ID number')
        self.assertEqual(empty['values'].get('contract_end_text'), 'no end date')
        self.assertIn('pbds-miss', empty['html'])
        # the real PDF prints nothing in their place (never `${x}`, never a chip)
        pdf = base64.b64decode(self.Panel.contract_document_pdf(self.c_empty.id)['data']).decode('utf-8', 'ignore')
        self.assertNotIn('${', pdf)
        self.assertNotIn('class="pbds-miss', pdf)

    # ------------------------------------------------------------ 7
    def test_07_pay_rail_three_users(self):
        groups_hr = ['hr.group_hr_user', 'hr_contract.group_hr_contract_manager']
        payroll = self.user('demo_pbdc_pay', groups_hr + ['om_hr_payroll.group_hr_payroll_manager'])
        hr_only = self.user('demo_pbdc_hr', groups_hr)
        # 1. may see pay: the figure prints
        res = self.doc(self.c_vn, self.Panel.with_user(payroll))
        self.assertFalse(res['pay_blocked'])
        self.assertRegex(res['html'], r'25[.,]000[.,]000')
        self.assertTrue(self.Panel.with_user(payroll).contract_document_pdf(self.c_vn.id)['ok'])
        # 2. sees the panel's wage masked: plain refusal, never a figure
        res = self.doc(self.c_vn, self.Panel.with_user(hr_only))
        self.assertTrue(self.Panel.with_user(hr_only).get_contract_360(self.c_vn.id)['header']['wage_masked'])
        self.assertTrue(res['pay_blocked'])
        self.assertIn(PAY_REFUSAL, res['pay_msg'])
        self.assertNotRegex(res['html'], r'25[.,]000[.,]000')
        self.assertIn('You may not see pay', res['html'])
        pdf = self.Panel.with_user(hr_only).contract_document_pdf(self.c_vn.id)
        self.assertFalse(pdf['ok'])
        self.assertIn(PAY_REFUSAL, pdf['msg'])
        save = self.Panel.with_user(hr_only).contract_document_save(self.c_vn.id)
        self.assertFalse(save['ok'])
        self.assertFalse(self.env['pb.employee.document'].search([('pbdc_contract_id', '=', self.c_vn.id)]))
        # 3. the employee themself (a future self-service path): their own
        # pay on their own contract; a colleague's stays blocked
        me = self.user('demo_pbdc_me', ['base.group_user'])
        self.emp_vn.user_id = me
        Studio = self.Studio.with_user(me)
        own, blocked = Studio.with_context(pbdc_contract_id=self.c_vn.id)._pbdc_values(
            self.emp_vn, self.company, 'en_US', ['monthly_pay', 'contract_ref'])
        self.assertFalse(blocked)
        self.assertRegex(own['monthly_pay'], r'25[.,]000[.,]000')
        self.assertEqual(own['contract_ref'], 'DEMO-VN-1')
        other, blocked = Studio.with_context(pbdc_contract_id=self.c_sg.id)._pbdc_values(
            self.emp_sg, self.company, 'en_US', ['monthly_pay'])
        self.assertFalse(other['monthly_pay'])
        self.assertNotIn('6,500', str(other))
        # and the panel stays closed to them
        with self.assertRaises(UserError):
            self.Panel.with_user(me).contract_document(self.c_vn.id)

    # ------------------------------------------------------------ 8
    def test_08_save_makes_versions_and_keeps_them(self):
        r1 = self.Panel.contract_document_save(self.c_sg.id)
        self.assertTrue(r1['ok'], r1.get('msg'))
        self.assertEqual(r1['version'], 1)
        self.assertRegex(r1['name'], r'^Employment contract · v1 · \d+ \w+ \d{4}$')
        self.c_sg.wage = 7000.0           # a corrected contract printed again
        r2 = self.Panel.contract_document_save(self.c_sg.id)
        self.assertEqual(r2['version'], 2)
        docs = self.env['pb.employee.document'].search([('pbdc_contract_id', '=', self.c_sg.id)],
                                                       order='pbdc_version')
        self.assertEqual(docs.mapped('pbdc_version'), [1, 2])
        self.assertEqual(docs.mapped('employee_id'), self.emp_sg)
        self.assertEqual(docs.mapped('category_id'), self.env.ref('pb_employee_vault.cat_labor_contract'))
        self.assertEqual(len(docs.mapped('attachment_id')), 2)
        self.assertNotEqual(docs[0].attachment_id.datas, docs[1].attachment_id.datas)
        self.assertIn('7,000', base64.b64decode(docs[1].attachment_id.datas).decode('utf-8', 'ignore'))
        self.assertEqual(docs[1].attachment_id.res_model, 'pb.employee.document')
        res = self.doc(self.c_sg)
        self.assertEqual([v['version'] for v in res['versions']], [2, 1])
        self.assertEqual(res['next_version'], 3)
        # a user who may read the contract but not file documents: refused in words
        reader = self.user('demo_pbdc_read', ['pb_hr_payroll_base.group_payroll_base_officer',
                                              'hr_contract.group_hr_contract_manager',
                                              'om_hr_payroll.group_hr_payroll_manager'])
        if not self.env['pb.employee.document'].with_user(reader).has_access('create'):
            out = self.Panel.with_user(reader).contract_document_save(self.c_sg.id)
            self.assertFalse(out['ok'])
            self.assertIn('needs the HR or payroll role', out['msg'])

    # ------------------------------------------------------------ 9
    def test_09_customer_edits_the_vietnam_copy(self):
        payload = self.Studio.open(self.vn_copy.id)
        self.assertTrue(payload['pbdc_note'])
        self.assertEqual(set(payload['rules']), set(SHIPPED_RULES))
        self.assertEqual(payload['page']['sign'], 'off')
        self.assertEqual(payload['main_lang'], 'vi_VN')
        body = payload['body'].replace('Thời giờ làm việc', 'DEMO Giờ làm việc mới')
        self.Studio.save(self.vn_copy.id, {'body': body, 'rules': payload['rules'],
                                           'page': payload['page'], 'main_lang': payload['main_lang'],
                                           'name': payload['name'], 'subject': payload['subject']})
        res = self.doc(self.c_vn)
        self.assertIn('DEMO Giờ làm việc mới', res['html'])
        self.assertFalse(res['starting_wording'])
        # the saved copy keeps its rules: open-ended paragraph still chosen right
        self.assertNotIn('không xác định thời hạn', _text(res['html']))
        self.assertFalse(self.Studio.open(self.vn_copy.id)['pbdc_note'])
        # put back: built-in wording, rules and language again
        self.Studio.reset(self.vn_copy.id)
        again = self.doc(self.c_vn)
        self.assertNotIn('DEMO Giờ làm việc mới', again['html'])
        self.assertEqual(again['read_lang'], 'vi_VN')
        self.assertIn('Hợp đồng xác định thời hạn', _text(again['html']))

    # ------------------------------------------------------------ 10
    def test_10_company_copy_beats_country_copy(self):
        res = self.Studio.copy_for(self.vn_copy.id, self.company.id, [])
        mine = self.env['pb.letter.template'].browse(res['id'])
        self.assertEqual(mine.pbds_replaces_id, self.generic)
        # a copy of a shipped contract takes its rules, page and language along
        self.assertEqual(set(mine.pbds_rules), set(SHIPPED_RULES))
        self.assertEqual(mine.pbds_page['sign'], 'off')
        self.assertEqual(mine.pbds_main_lang, 'vi_VN')
        out = self.doc(self.c_vn)
        self.assertEqual(out['document']['used_id'], mine.id)
        self.assertIn(self.company.name, out['document']['note'])
        self.assertIn('Hợp đồng xác định thời hạn', _text(out['html']))
        # someone in another company keeps the shipped copy
        emp_b = self.env['hr.employee'].create({'name': 'DEMO Bao B', 'company_id': self.company_b.id})
        if 'payroll_country' in emp_b._fields:
            emp_b.payroll_country = 'VN'
        c_b = self.env['hr.contract'].create({'name': 'DEMO-B', 'employee_id': emp_b.id, 'wage': 1.0,
                                              'company_id': self.company_b.id, 'state': 'open',
                                              'date_start': '2025-01-01'})
        self.assertEqual(self.doc(c_b)['document']['used_id'], self.vn_copy.id)

    # ------------------------------------------------------------ 11
    def test_11_button_only_for_contract_readers(self):
        hr = self.user('demo_pbdc_hr2', ['hr.group_hr_user', 'hr_contract.group_hr_contract_manager'])
        payload = self.Panel.with_user(hr).get_contract_360(self.c_sg.id)
        self.assertTrue(payload['contract_document']['available'])
        nobody = self.user('demo_pbdc_nobody', ['base.group_user'])
        with self.assertRaises(UserError):
            self.Panel.with_user(nobody).get_contract_360(self.c_sg.id)
        with self.assertRaises(UserError):
            self.Panel.with_user(nobody).contract_document(self.c_sg.id)
        # another company's reader: the contract is not theirs
        hr_b = self.user('demo_pbdc_hrb', ['hr.group_hr_user', 'hr_contract.group_hr_contract_manager'],
                         company=self.company_b)
        gone = self.Panel.with_user(hr_b).get_contract_360(self.c_sg.id)
        self.assertNotIn('contract_document', gone)
        self.assertFalse(self.Panel.with_user(hr_b).contract_document(self.c_sg.id)['ok'])
        self.assertFalse(self.Panel.with_user(hr_b).contract_document_pdf(self.c_sg.id)['ok'])
        self.assertFalse(self.Panel.with_user(hr_b).contract_document_save(self.c_sg.id)['ok'])
        # every contract document switched off: no button, a plain sentence
        self.generic.active = False
        self.assertFalse(self.Panel.get_contract_360(self.c_sg.id)['contract_document']['available'])
        off = self.Panel.contract_document(self.c_sg.id)
        self.assertFalse(off['ok'])
        self.assertIn('Settings, Documents', off['msg'])

    # ------------------------------------------------------------ 12
    def test_12_designer_kind_fields_and_new_documents(self):
        board = self.Studio.board()
        kinds = [k['key'] for k in board['kinds']]
        self.assertIn(CONTRACT_KIND, kinds)
        self.assertEqual(kinds.index(CONTRACT_KIND), kinds.index('contract') + 1)
        cards = [c for c in board['cards'] if c['kind'] == CONTRACT_KIND]
        self.assertTrue({self.generic.id, self.vn_copy.id, self.id_copy.id} <= {c['id'] for c in cards})
        groups = self.Studio.catalogue(self.generic.id)
        doc_fields = {f['key']: f for g in groups if g['key'] == 'document' for f in g['fields']}
        for key in CONTRACT_KEYS:
            self.assertIn(key, doc_fields)
            self.assertFalse(doc_fields[key].get('later'), key)
        # the preview in the designer shows real values of the person's contract
        pv = self.Studio.preview(self.generic.id, {}, self.emp_sg.id, 'en_US')
        self.assertIn('DEMO-SG-1', pv['html'])
        self.assertEqual(pv['values'].get('contract_ref'), 'DEMO-SG-1')
        # conditions: contract length and trial period
        cond = {f['key'] for f in self.Studio.condition_fields()['fields']}
        self.assertTrue({'contract_term', 'trial_end'} <= cond)
        # a new document in the group is an employment contract
        new = self.env['pb.letter.template'].browse(self.Studio.create_blank(CONTRACT_KIND, 'DEMO Part-time')['id'])
        self.assertEqual(new.letter_type, 'employment_contract')
        self.assertEqual(new.pbds_kind, CONTRACT_KIND)
        self.assertEqual(new.vault_category_id, self.env.ref('pb_employee_vault.cat_labor_contract'))
        # ... offered in the panel next to the shipped one, which comes first
        res = self.doc(self.c_sg)
        self.assertEqual([d['id'] for d in res['documents']][:1], [self.generic.id])
        self.assertIn(new.id, [d['id'] for d in res['documents']])
        chosen = self.doc(self.c_sg, template_id=new.id)
        self.assertEqual(chosen['document']['used_id'], new.id)
        # the data file's rules are the module's built-in rules
        src = open(get_module_path('pb_doc_contracts') + '/data/contract_templates.xml').read()
        for rid in SHIPPED_RULES:
            self.assertIn('pbds-r-%s' % rid, src)

    # ------------------------------------------------------------ 13
    def test_13_made_as_a_letter_prints_the_same(self):
        letter = self.env['pb.hr.letter'].create({'employee_id': self.emp_sg.id,
                                                  'template_id': self.generic.id})
        letter.action_generate()
        html = _text(str(letter.rendered_html))
        self.assertIn('has no end date', html)
        self.assertNotIn('This is a fixed-term contract', html)
        self.assertTrue(letter.attachment_id)
        out = base64.b64decode(letter.attachment_id.datas).decode('utf-8', 'ignore')
        self.assertIn('pbds-page', out)
        self.assertNotIn('Authorised signatory</div>', out)

    # ------------------------------------------------------------ 14
    def test_14_hostile_text_is_inert(self):
        self.emp_sg.name = 'DEMO <script>alert(1)</script> Tan'
        if 'legal_name' in self.emp_sg._fields:
            self.emp_sg.legal_name = 'DEMO <script>alert(1)</script> Tan'
        self.c_sg.name = 'DEMO <img src=x onerror=alert(2)>'
        res = self.doc(self.c_sg)
        self.assertNotIn('<script>alert(1)', res['html'])
        self.assertNotIn('<img src=x', res['html'])
        self.assertIn('&lt;script&gt;', res['html'])

    # ------------------------------------------------------------ 15
    def test_15_language_picker(self):
        en = self.env['pb.doc.version'].create({'template_id': self.vn_copy.id, 'lang': 'en_US',
                                                'subject': 'DEMO English only',
                                                'body_html': '<p>DEMO English ${contract_ref}</p>'})
        res = self.doc(self.c_vn)
        self.assertEqual({l['code'] for l in res['langs']}, {'vi_VN', 'en_US'})
        self.assertEqual(res['lang'], 'vi_VN', 'the person\'s language first')
        english = self.doc(self.c_vn, lang='en_US')
        self.assertIn('DEMO English DEMO-VN-1', _text(english['html']))
        self.assertEqual(english['read_lang'], 'en_US')
        en.unlink()
