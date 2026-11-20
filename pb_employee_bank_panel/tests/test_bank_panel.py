# -*- coding: utf-8 -*-
"""FS-9 tests (numbered as in the handover, FS8_FS9_HANDOVER.md §FS-9).

1  approved account shown masked (last 4 only; the old box is not read)
2  a change waiting for approval (alone, and beside an approved account)
3  no account: "None" (the old box alone does not count)
4  another person's name + Mark as seen (HR / payroll only, who and when kept)
5  a role without bank visibility sees no block and the call refuses
6  Home's "no bank account" equals the Payroll-ready helper's count
7  the old Bank box is off the side panel and Full details; the value stays;
   the Mapping still offers it and a save keeps it
8  silent install: the module adds no stored field and no data
10 vi / id entries load for every new string; no vendor word anywhere
(9, payslips and the bank file byte-identical, is proven by the S2-C / IDB1
golden tests run with this module installed — see the report.)
"""

import json
import os
import re

from odoo.exceptions import AccessError
from odoo.tests import Form, TransactionCase, new_test_user, tagged
from odoo.tools.translate import PoFileReader

HERE = os.path.dirname(os.path.dirname(__file__))
FULL_A = '9704000011112222'     # approved account (full number must never leave)
FULL_VN = '0071000333444555'    # the Vietnamese bank file's account
FULL_NEW = '1903555666777888'   # a change waiting for approval
FULL_OLD = '5550009998887777'   # the old free-text box


def _bank_group(details):
    return next((g for g in details.get('pay') or [] if g.get('key') == 'bank'), None)


class BankFixture(TransactionCase):
    """DEMO people for every FS-9 test class (no tests of its own)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        base = 'base.group_user,pb_hr_payroll_base.group_payroll_base_user,'
        cls.hr = new_test_user(
            cls.env, login='fs9_hr', name='DEMO FS9 HR',
            groups=base + 'hr.group_hr_user,om_hr_payroll.group_hr_payroll_user',
            company_id=cls.company.id, company_ids=[cls.company.id])
        cls.hr_only = new_test_user(
            cls.env, login='fs9_hr_only', name='DEMO FS9 HR only',
            groups=base + 'hr.group_hr_user',
            company_id=cls.company.id, company_ids=[cls.company.id])
        cls.plain = new_test_user(
            cls.env, login='fs9_plain', name='DEMO FS9 Line manager', groups='base.group_user',
            company_id=cls.company.id, company_ids=[cls.company.id])
        cls.portal = new_test_user(
            cls.env, login='fs9_portal', name='DEMO FS9 Portal', groups='base.group_portal',
            company_id=cls.company.id, company_ids=[cls.company.id])

        Emp = cls.env['hr.employee'].sudo()
        cls.bank = cls.env['res.bank'].sudo().create({'name': 'DEMO Vietcombank'})

        def person(name, **vals):
            emp = Emp.create(dict({'name': name, 'company_id': cls.company.id}, **vals))
            if not emp.work_contact_id:
                emp.work_contact_id = cls.env['res.partner'].sudo().create({'name': name})
            return emp

        def account(emp, number, holder):
            acc = cls.env['res.partner.bank'].sudo().create({
                'acc_number': number, 'partner_id': emp.work_contact_id.id,
                'bank_id': cls.bank.id, 'acc_holder_name': holder})
            emp.bank_account_ids = [(4, acc.id)]
            return acc

        cls.approved = person('DEMO Anh Nguyen', bank_name='DEMO OLD BANK', account_number=FULL_OLD)
        cls.acc_approved = account(cls.approved, FULL_A, 'DEMO Anh Nguyen')
        cls.vn_only = person('DEMO Binh Tran')
        cls.has_vn = 'vietnam_bank_account_number' in Emp._fields
        if cls.has_vn:
            cls.vn_only.write({'vietnam_bank_account_number': FULL_VN,
                               'vietnam_bank_name': 'DEMO BIDV',
                               'vietnam_bank_account_name': 'DEMO Binh Tran'})
        cls.waiting = person('DEMO Chi Le')
        cls.both = person('DEMO Dung Pham')
        account(cls.both, FULL_A[:-1] + '9', 'DEMO Dung Pham')
        cls.none = person('DEMO Em Vo', bank_name='DEMO OLD BANK', account_number=FULL_OLD)
        cls.other = person('DEMO Dewi Lestari')
        account(cls.other, '5550001111222', 'DEMO Joko Widodo')

        cls.Req = cls.env.get('pb.bank.change.request')
        cls.reqs = {}
        if cls.Req is not None:
            for emp in (cls.waiting, cls.both):
                att = cls.env['ir.attachment'].create({'name': 'DEMO letter.txt', 'raw': b'x'})
                req = cls.Req.sudo().create({
                    'employee_id': emp.id, 'attachment_id': att.id,
                    'x_bank_name': 'DEMO Vietcombank', 'x_account_name': emp.name,
                    'x_account_number': FULL_NEW, 'company_id': cls.company.id})
                req.sudo().write({'state': 'hr_review'})
                cls.reqs[emp.id] = req


@tagged('post_install', '-at_install', 'fs9_bank_panel')
class TestBankPanel(BankFixture):

    # ----------------------------------------------------------- helpers
    def panel(self, emp, user=None):
        People = self.env['pb.people'].with_user(user or self.hr)
        return People.get_employee_360(emp.id)

    def block(self, emp, user=None):
        group = _bank_group(self.panel(emp, user)['details'])
        self.assertTrue(group, 'no Bank block for %s' % emp.name)
        self.assertEqual(group['kind'], 'pb_bank')
        return group['pb_bank']

    def assertNoFullNumber(self, payload):
        text = json.dumps(payload, default=str)
        for full in (FULL_A, FULL_VN, FULL_NEW, FULL_OLD, '5550001111222'):
            self.assertNotIn(full, text, 'a whole account number left the server')
            self.assertNotIn(full[:-4], text, 'more than the last four digits left the server')

    # ------------------------------------------------------------ test 1
    def test_1_approved_account_shown_masked(self):
        payload = self.panel(self.approved)
        self.assertNoFullNumber(payload)
        group = _bank_group(payload['details'])
        bk = group['pb_bank']
        self.assertEqual(bk['status'], 'approved')
        self.assertEqual(bk['status_label'], 'Approved')
        self.assertEqual(bk['bank'], 'DEMO Vietcombank')
        self.assertEqual(bk['holder'], 'DEMO Anh Nguyen')
        self.assertEqual(bk['masked'], '•••• ' + FULL_A[-4:])
        self.assertEqual(bk['store'], 'account')
        self.assertIsNone(bk['waiting'])
        # the old box is not read anywhere in the block
        self.assertNotIn('DEMO OLD BANK', json.dumps(group))
        # the generic rows (what the Form builder's screen rule walks) are masked too
        self.assertEqual({r['key'] for r in group['rows']},
                         {'pb_bank_status', 'pb_bank_name', 'pb_bank_holder', 'pb_bank_number'})
        # one Bank group on the tab, where the old one was
        self.assertEqual(sum(1 for g in payload['details']['pay'] if g['key'] == 'bank'), 1)
        # the full page's bank badge names the approved account's bank
        detail = self.env['pb.people'].with_user(self.hr).get_employee_detail(self.approved.id)
        self.assertTrue(detail['statutory']['bank'])
        self.assertEqual(detail['statutory']['bank_name'], 'DEMO Vietcombank')
        none = self.env['pb.people'].with_user(self.hr).get_employee_detail(self.none.id)
        self.assertFalse(none['statutory']['bank'])
        self.assertEqual(none['statutory']['bank_name'], '', 'the old box named a bank')

    def test_1b_vietnamese_bank_file_account(self):
        if not self.has_vn:
            self.skipTest('no Vietnamese bank file on this database')
        bk = self.block(self.vn_only)
        self.assertEqual(bk['status'], 'approved')
        self.assertEqual(bk['store'], 'vn_file')
        self.assertEqual(bk['bank'], 'DEMO BIDV')
        self.assertEqual(bk['masked'], '•••• ' + FULL_VN[-4:])
        # the two stores disagree: said, last four digits only
        self.approved.sudo().vietnam_bank_account_number = FULL_VN
        payload = self.panel(self.approved)
        self.assertNoFullNumber(payload)
        bk = _bank_group(payload['details'])['pb_bank']
        self.assertEqual(bk['masked'], '•••• ' + FULL_A[-4:], 'the payment list account comes first')
        self.assertEqual(bk['vn_file_masked'], '•••• ' + FULL_VN[-4:])

    # ------------------------------------------------------------ test 2
    def test_2_change_waiting_for_approval(self):
        if self.Req is None:
            self.skipTest('no bank change requests on this database')
        payload = self.panel(self.waiting)
        self.assertNoFullNumber(payload)
        bk = _bank_group(payload['details'])['pb_bank']
        self.assertEqual(bk['status'], 'waiting')
        self.assertEqual(bk['status_label'], 'Waiting for approval')
        self.assertEqual(bk['masked'], '')
        self.assertEqual(bk['waiting']['count'], 1)
        self.assertEqual(bk['waiting']['new_masked'], '•••• ' + FULL_NEW[-4:])
        # the payroll team works the bank checks screen: a door to the request
        self.assertTrue(bk['waiting']['link'])
        self.assertIn(bk['waiting']['link']['kind'], ('inbox', 'bank_checks'))
        # beside an approved account: still Approved, the change is said
        both = self.block(self.both)
        self.assertEqual(both['status'], 'approved')
        self.assertTrue(both['waiting'])
        # one rule: the payment list's own answer, for every person
        PL = self.env['pb.payment.list']
        for emp in (self.approved, self.waiting, self.both, self.none, self.other):
            expected = bool(PL._pb_waiting_changes(emp).get(emp.id))
            self.assertEqual(bool(self.block(emp)['waiting']), expected, emp.name)
        # a decided request is no longer waiting
        self.reqs[self.waiting.id].sudo().write({'state': 'refused'})
        self.assertEqual(self.block(self.waiting)['status'], 'none')

    def test_2b_door_follows_the_reader(self):
        if self.Req is None:
            self.skipTest('no bank change requests on this database')
        # HR without the payroll role cannot open the bank checks screen nor
        # read the request: no door is offered
        bk = self.env['pb.people'].with_user(self.hr_only).pb_bank_panel(self.waiting.id)
        self.assertEqual(bk['status'], 'waiting')
        link = bk['waiting']['link']
        if link:
            self.assertEqual(link['kind'], 'inbox', 'a door this reader cannot use')

    # ------------------------------------------------------------ test 3
    def test_3_no_account(self):
        bk = self.block(self.none)
        self.assertEqual(bk['status'], 'none')
        self.assertEqual(bk['status_label'], 'None')
        self.assertEqual((bk['bank'], bk['holder'], bk['masked']), ('', '', ''))
        self.assertIsNone(bk['waiting'])
        self.assertIsNone(bk['other_name'])
        self.assertTrue(bk['can_add'], 'the payroll team is offered the bank checks screen')
        self.assertFalse(
            self.env['pb.people'].with_user(self.hr_only).pb_bank_panel(self.none.id)['can_add'])
        # the Payroll-ready helper agrees
        self.assertFalse(self.none.pb_bank_on_record)
        self.assertTrue(self.approved.pb_bank_on_record)

    # ------------------------------------------------------------ test 4
    def test_4_another_persons_name_and_mark_as_seen(self):
        if not hasattr(self.env['hr.employee'], '_pb_other_name_facts'):
            self.skipTest('no other-name flag on this database')
        bk = self.block(self.other)
        self.assertTrue(bk['other_name']['show'])
        self.assertEqual(bk['other_name']['holder'], 'DEMO Joko Widodo')
        self.assertTrue(bk['other_name']['can_mark'])
        self.assertEqual(self.block(self.approved)['other_name'], None)
        # the header chip's answer and the block's are the same
        Emp = self.env['hr.employee'].with_user(self.hr)
        self.assertEqual(Emp.pb_other_name_state(self.other.id)['show'], True)
        # nobody else may mark it
        for user in (self.plain, self.portal):
            with self.assertRaises(AccessError):
                self.env['hr.employee'].with_user(user).pb_other_name_mark_seen(self.other.id)
        self.assertFalse(self.other.sudo().pb_other_name_seen_by)
        # HR marks it seen (BL4's own action): recorded, and the block says so
        Emp.pb_other_name_mark_seen(self.other.id)
        self.env.invalidate_all()
        sudo = self.other.sudo()
        self.assertEqual(sudo.pb_other_name_seen_by, self.hr)
        self.assertTrue(sudo.pb_other_name_seen_on)
        trail = self.env['biz.audit.entry'].sudo().search([
            ('model_name', '=', 'hr.employee'), ('res_id', '=', self.other.id),
            ('field_name', '=', 'pb_other_name_seen')])
        self.assertEqual(len(trail), 1)
        self.assertFalse(re.search(r'\d{6,}', (trail.new_value or '') + (trail.old_value or '')))
        after = self.env['pb.people'].with_user(self.hr).pb_bank_panel(self.other.id)
        self.assertFalse(after['other_name']['show'])
        self.assertEqual(after['other_name']['seen_by'], 'DEMO FS9 HR')
        self.assertTrue(after['other_name']['seen_on'])
        self.assertFalse(after['other_name']['can_mark'])
        self.assertFalse(Emp.pb_other_name_state(self.other.id)['show'])
        # marking it seen changes nothing about the account
        self.assertEqual(after['status'], 'approved')
        self.assertEqual(after['masked'], '•••• 1222')

    # ------------------------------------------------------------ test 5
    def test_5_no_bank_visibility_no_block(self):
        for user in (self.plain, self.portal):
            People = self.env['pb.people'].with_user(user)
            with self.assertRaises(AccessError):
                People.get_employee_360(self.approved.id)
            with self.assertRaises(AccessError):
                People.pb_bank_panel(self.approved.id)
            # even reached directly, the details carry no Bank block
            details = People._e360_details(self.approved.sudo(), False)
            self.assertIsNone(_bank_group(details), 'a Bank block for %s' % user.login)
        # the people who saw the panel before still see it
        self.assertTrue(self.block(self.approved, user=self.hr))
        for user in (self.hr, self.hr_only):
            self.assertEqual(
                self.env['pb.people'].with_user(user).pb_bank_panel(self.approved.id)['status'],
                'approved')

    # ------------------------------------------------------------ test 6
    def test_6_home_figure_equals_the_payroll_ready_helper(self):
        Run = self.env['hr.payslip.run'].sudo()
        Slip = self.env['hr.payslip'].sudo()
        run = Run.create({'name': 'DEMO FS9 run', 'date_start': '2026-11-01',
                          'date_end': '2026-11-30'})
        people = self.approved | self.vn_only | self.waiting | self.none | self.other
        for emp in people:
            Slip.create({'name': 'DEMO FS9 %s' % emp.name, 'employee_id': emp.id,
                         'date_from': '2026-11-01', 'date_to': '2026-11-30',
                         'payslip_run_id': run.id, 'company_id': self.company.id})
        self.env.flush_all()
        Dash = self.env['pb.dashboard']
        got = Dash._home_no_bank(run.ids, [self.company.id]).get(run.id, 0)
        helper = self.env['hr.employee'].search_count(
            [('id', 'in', people.ids), ('pb_bank_on_record', '=', False)])
        self.assertEqual(got, helper)
        # the old box alone (self.none) is "no bank account" now
        expected = 2 if self.has_vn else 3          # waiting + none (+ vn_only without VN pack)
        self.assertEqual(got, expected)

    # ------------------------------------------------------------ test 7
    def test_7_old_bank_box_off_the_screens_value_kept(self):
        # side panel: no old row anywhere
        payload = self.panel(self.approved)
        keys = {r['key'] for tab in ('personal', 'job', 'pay')
                for g in payload['details'][tab] for r in g['rows']}
        self.assertFalse(keys & {'bank_name', 'account_number'})
        # Full details: the box is not shown to anybody
        from odoo.addons.pb_employee_form_tidy.models import form_rules
        self.assertEqual(form_rules.FORM_RULES.get('bank_name'), form_rules.REMOVE)
        arch = self.env['hr.employee'].with_user(self.hr).get_views(
            [(False, 'form')])['views']['form']['arch']
        for node in re.findall(r'<field[^>]*name="bank_name"[^>]*>', arch):
            self.assertRegex(node, r'invisible="(True|1)"', 'the Bank box still shows')
        # the value is still in the database
        self.env.invalidate_all()
        self.assertEqual(self.approved.sudo().bank_name, 'DEMO OLD BANK')
        self.assertEqual(self.approved.sudo().account_number, FULL_OLD)
        # a save of the form keeps it
        manager = new_test_user(
            self.env, login='fs9_mgr', name='DEMO FS9 HR manager',
            groups='base.group_user,hr.group_hr_user,hr.group_hr_manager,'
                   'pb_hr_payroll_base.group_payroll_base_user',
            company_id=self.company.id, company_ids=[self.company.id])
        with Form(self.approved.with_user(manager)) as form:
            form.work_phone = '0123456'
        self.env.invalidate_all()
        self.assertEqual(self.approved.sudo().bank_name, 'DEMO OLD BANK')
        # imports keep working: the Mapping still offers the box as a
        # destination, and a write to it is stored
        Studio = self.env.get('pb.formula.studio')
        if Studio is not None and hasattr(Studio, '_ec_is_mappable'):
            self.assertTrue(Studio._ec_is_mappable('hr.employee', 'bank_name'))
            self.assertTrue(Studio._ec_is_mappable('hr.employee', 'account_number'))
        self.none.sudo().write({'bank_name': 'DEMO FROM A FILE'})
        self.assertEqual(self.none.sudo().bank_name, 'DEMO FROM A FILE')
        self.assertEqual(self.block(self.none)['status'], 'none',
                         'the old box written by a file still is not an approved account')

    # ------------------------------------------------------------ test 8
    def test_8_silent_install(self):
        Data = self.env['ir.model.data'].sudo()
        fields = self.env['ir.model.fields'].sudo().browse(Data.search([
            ('module', '=', 'pb_employee_bank_panel'),
            ('model', '=', 'ir.model.fields')]).mapped('res_id'))
        # no column anywhere: every field it adds is computed when read, or
        # belongs to an abstract screen model (no table)
        for fld in fields:
            field = self.env[fld.model]._fields.get(fld.name)
            if field is None or self.env[fld.model]._abstract:
                continue
            if fld.name in ('id', 'display_name'):
                continue
            self.assertFalse(field.store, 'the module stores %s.%s' % (fld.model, fld.name))
        self.assertIn('pb_profile_waiting', self.env['hr.employee']._fields)
        self.assertFalse(self.env['hr.employee']._fields['pb_profile_waiting'].store)
        data = Data.search([
            ('module', '=', 'pb_employee_bank_panel'),
            ('model', 'not in', ('ir.module.module', 'ir.module.module.dependency',
                                 'ir.model', 'ir.model.fields', 'ir.ui.view',
                                 'ir.model.constraint', 'ir.model.relation'))])
        self.assertFalse(data, 'the module ships records: %s' % data.mapped('model'))

    # ----------------------------------------------------------- test 10
    def test_10_vi_and_id_entries_and_no_vendor_word(self):
        wanted = set()
        sources = {
            'models/bank_panel.py': re.compile(r"_\(['\"](.+?)['\"]\)"),
            'static/src/js/bank_panel.js': re.compile(r'_t\("(.+?)"'),
            'models/mapping_retired.py': re.compile(r"_\(['\"](.+?)['\"][,)]"),
        }
        wanted.add('Sent, waiting for HR')
        for rel, rx in sources.items():
            with open(os.path.join(HERE, rel), encoding='utf-8') as fh:
                wanted |= set(rx.findall(fh.read()))
        with open(os.path.join(HERE, 'static/src/xml/bank_panel.xml'), encoding='utf-8') as fh:
            xml = fh.read()
        for label in ('No approved bank account on record.', 'Change waiting for approval',
                      'Open the request', 'Mark as seen', 'Open Bank Verification'):
            self.assertIn(label, xml)
            wanted.add(label)
        for lang in ('vi_VN', 'id_ID'):
            path = os.path.join(HERE, 'i18n', '%s.po' % lang)
            with open(path, 'rb') as fh:
                rows = list(PoFileReader(fh))
            have = {r['src']: r['value'] for r in rows if r['value']}
            for src in wanted:
                self.assertIn(src, have, '%s: no entry for %r' % (lang, src))
            for row in rows:
                self.assertIn(row['module'], ('pb_employee_bank_panel',))
                self.assertNotRegex(row['value'], r'(?i)odoo', 'vendor word in %s' % lang)
        for root, _dirs, files in os.walk(HERE):
            if '/tests' in root:
                continue
            for name in files:
                if name.endswith(('.py', '.js', '.xml', '.scss', '.po')):
                    with open(os.path.join(root, name), encoding='utf-8') as fh:
                        for line in fh:
                            if re.search(r'(?i)odoo', line) and not re.search(
                                    r"from odoo|import odoo|@odoo|odoo\.|odoo-(python|javascript)|odoo-module|^\s*</?odoo>\s*$", line):
                                self.fail('vendor word in %s: %s' % (name, line.strip()))
