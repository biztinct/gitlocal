# -*- coding: utf-8 -*-
"""WDGAP IDB1-F — who may prepare / download the payment list = who may
make / download the bank file. No wider, no narrower.

Live finding (ledger IDB1M-2): a payroll officer with administrator rights
(payobook demo: QA Test) made the bank file but got an access error on
"Prepare the payment list" — the list's full-read rule was payroll manager
only. Each role below does the bank-file thing and the payment-list thing
on the same approved run; the two outcomes must be the same, and are also
pinned to what each role is expected to get, so a test that compares two
refusals cannot pass by accident.

The builder's safeguard is kept: a payroll officer who cannot download the
bank file reads a stored list only when asked to decide it.
"""

import importlib.util
import secrets

from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, tagged
from odoo.tools.misc import file_path

from .test_wdgap_idb1_payment_list import _Idb1Fixture

OK, NO = 'ok', 'refused'

#: A payroll officer as the product makes one: the payroll app's officer
#: group plus the pay screens' officer group (which carries the pay-run read;
#: QA Test on payobook holds both). '?' = only where that module is installed.
OFFICER = ('om_hr_payroll.group_hr_payroll_user',
           '?pb_hr_payroll_base.group_payroll_base_officer')

#: role -> (groups, make, download). "make" = prepare the bank file / the
#: payment list; "download" = download the approved bank file / list.
ROLES = {
    'pay manager': (('om_hr_payroll.group_hr_payroll_manager',), OK, OK),
    'payroll officer + administrator (QA Test)': (
        OFFICER + ('base.group_system',), OK, OK),
    'payroll officer + administrator + finance': (
        OFFICER + ('base.group_system', 'account.group_account_manager'), OK, OK),
    'payroll officer + finance': (
        OFFICER + ('account.group_account_invoice',), NO, OK),
    'payroll officer + access rights': (
        OFFICER + ('base.group_erp_manager',), NO, OK),
    'payroll officer': (OFFICER, NO, NO),
    'administrator without a payroll role': (('base.group_system',), NO, NO),
    'finance without a payroll role': (('account.group_account_invoice',), NO, NO),
    'HR officer': (('hr.group_hr_user',), NO, NO),
}


class _Idb1fRoles(_Idb1Fixture):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        companies = cls.home | cls.indo
        cls.role_users = {}
        for n, (role, (groups, make, download)) in enumerate(ROLES.items()):
            refs = [cls.env.ref(g, raise_if_not_found=False) for g in groups
                    if not g.startswith('?')]
            refs += [r for r in (cls.env.ref(g[1:], raise_if_not_found=False)
                                 for g in groups if g.startswith('?')) if r]
            if not all(refs):
                continue          # e.g. no finance app on this database
            cls.role_users[role] = Users.create({
                'name': 'IDB1F %s' % role, 'login': 'idb1f_role_%s' % n,
                'company_id': cls.home.id,
                'company_ids': [(6, 0, companies.ids)],
                'group_ids': [(6, 0, [cls.env.ref('base.group_user').id]
                               + [r.id for r in refs])]})
        cls.qa_like = cls.role_users['payroll officer + administrator (QA Test)']

    def _as(self, user):
        return self.env['pb.pay.delivery'].with_user(user).with_context(self._ctx(user))

    def _try(self, call):
        try:
            with self.env.cr.savepoint():
                call()
            result = OK
        except (AccessError, UserError):
            result = NO
        self.env.invalidate_all()
        return result

    def _approved_bank_file(self):
        record = self.env['pb.bank.file'].with_user(self.mgr).with_context(
            self._ctx(self.mgr)).prepare(self.payrun, 'vietcombank')
        self.Engine.with_user(self.mgr).with_context(self._ctx(self.mgr)).submit(record)
        self._approve_all(record)
        record.invalidate_recordset()
        self.assertEqual(record.state, 'approved')
        return record


@tagged('post_install', '-at_install', 'wdgap_idb1', 'wdgap_idb1f')
class TestIdb1fAccess(_Idb1fRoles):

    def test_idb1f_1_prepare_equals_make_the_bank_file(self):
        self.assertIn('payroll officer + finance', self.role_users,
                      'the finance app is on the test database')
        for role, user in self.role_users.items():
            expected = ROLES[role][1]
            bank = self._try(lambda: self._as(user).prepare_bank_file(
                self.payrun.id, 'vietcombank'))
            listed = self._try(lambda: self._as(user).prepare_payment_list(
                self.payrun.id))
            self.assertEqual((bank, listed), (expected, expected), role)
        # portal: both refused
        self.assertEqual(self._try(lambda: self._as(self.portal).prepare_bank_file(
            self.payrun.id, 'vietcombank')), NO)
        self.assertEqual(self._try(lambda: self._as(self.portal).prepare_payment_list(
            self.payrun.id)), NO)

    def test_idb1f_2_download_equals_download_the_bank_file(self):
        self._approved_bank_file()
        listed = self.approved_list()
        for role, user in list(self.role_users.items()) + [('portal', self.portal)]:
            expected = ROLES[role][2] if role in ROLES else NO
            bank = self._try(lambda: self._as(user).download_bank_file(self.payrun.id))
            check = self._try(lambda: self._as(user).payment_list_check(
                self.payrun.id, 'csv'))
            download = self._try(lambda: self.List.with_user(user).with_context(
                self._ctx(user))._pb_download(self.payrun.id, 'xlsx'))
            self.assertEqual((bank, check, download), (expected,) * 3, role)
            # the safeguard: the stored list (every account number) opens
            # exactly for those who may download the bank file
            seen = self._try(lambda: self.File.with_user(user).with_context(
                self._ctx(user)).browse(listed.id).read(['row_count']))
            self.assertEqual(seen, expected, '%s opens the stored list' % role)

    def test_idb1f_3_qa_like_prepares_and_sees_it_waiting(self):
        """The live case: prepares, the screen shows it waiting with the
        bank file's steps, download still off until a second person
        approves; after the approval it downloads."""
        Delivery = self._as(self.qa_like)
        Delivery.prepare_payment_list(self.payrun.id)
        screen = Delivery.get_delivery_data(self.payrun.id)['payment_list']
        self.assertEqual(screen['count'], 10)
        self.assertEqual(screen['file']['state'], 'pending')
        self.assertFalse(screen['file']['downloadable'])
        with self.assertRaises(UserError):
            Delivery.payment_list_check(self.payrun.id, 'csv')
        record = self.File.sudo().search([('run_id', '=', self.payrun.id),
                                          ('state', '=', 'pending')], limit=1)
        self.assertEqual(record.generated_by, self.qa_like)
        self.assertEqual(record.approval_request_id.process_id.key, 'bankfile')
        self._approve_all(record)
        self.assertTrue(Delivery.payment_list_check(self.payrun.id, 'csv')['ok'])
        name, _mime, payload = self.List.with_user(self.qa_like).with_context(
            self._ctx(self.qa_like))._pb_download(self.payrun.id, 'csv')
        self.assertTrue(payload)

    def test_idb1f_4_officer_reads_a_list_only_when_asked_to_decide_it(self):
        record = self.prepared_list()
        Files = self.File.with_user(self.officer).with_context(self._ctx(self.officer))
        self.assertFalse(Files.search([('id', '=', record.id)]))
        record.sudo().write({'seat_user_ids': [(4, self.officer.id)]})
        self.env.invalidate_all()
        self.assertEqual(Files.search([('id', '=', record.id)]), record)
        # ...and still may not download it (the bank file's own gate)
        with self.assertRaises(AccessError):
            self.List.with_user(self.officer)._pb_download(self.payrun.id, 'csv')

    def test_idb1f_5_one_rule_as_declared(self):
        rule = self.env.ref('pb_pay_delivery.rule_payment_list_file_payroll')
        bank_rule = self.env.ref('pb_pay_delivery.rule_bank_file_payroll')
        self.assertEqual(rule.groups, bank_rule.groups, 'the bank file\'s own groups')
        self.assertIn('_pay_groups_held', rule.domain_force)
        # an upgraded database ends with the same rule as a fresh install
        path = file_path('pb_pay_delivery/migrations/19.0.1.8.1/'
                         'post-idb1f_payment_list_rule.py')
        spec = importlib.util.spec_from_file_location('idb1f_migration', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        self.assertEqual(migration.DOMAIN, rule.domain_force)
        self.assertEqual(migration.NAME, rule.name)
        # and running it (as the upgrade does) changes nothing further
        migration.migrate(self.env.cr, '19.0.1.8.0')
        rule.invalidate_recordset()
        self.assertEqual(rule.groups, bank_rule.groups)
        self.assertEqual(migration.DOMAIN, rule.domain_force)


@tagged('post_install', '-at_install', 'wdgap_idb1', 'wdgap_idb1f')
class TestIdb1fAccessUrl(_Idb1fRoles, HttpCase):
    """The direct address, for the live case and the refused ones."""

    def _login(self, user):
        password = secrets.token_urlsafe(18)    # made here, kept nowhere
        user.sudo().password = password
        self.authenticate(user.login, password)

    def _get(self, fmt='csv'):
        return self.url_open('/pb_pay_delivery/payment_list?run_id=%s&fmt=%s'
                             % (self.payrun.id, fmt))

    def test_idb1f_url(self):
        record = self.prepared_list()
        self._approve_all(record)
        self._login(self.qa_like)
        response = self._get('csv')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'0012345678', response.content)
        for role in ('payroll officer', 'administrator without a payroll role',
                     'HR officer'):
            self._login(self.role_users[role])
            response = self._get('csv')
            self.assertNotEqual(response.status_code, 200, role)
            self.assertNotIn(b'0012345678', response.content, role)
            self.assertNotIn(b'odoo', response.content.lower(), role)
        self._login(self.portal)
        response = self._get('csv')
        self.assertNotEqual(response.status_code, 200)
        self.assertNotIn(b'0012345678', response.content)
