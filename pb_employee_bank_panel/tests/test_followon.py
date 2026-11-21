# -*- coding: utf-8 -*-
"""FS-9 follow-on tests.

A  the joining checklist's "Bank account" follows the approved-account rule;
   a change waiting for approval is "Sent, waiting for HR", not missing;
C  the old Bank / Account Number boxes are not OFFERED as Mapping
   destinations; a saved mapping keeps working and says "No longer shown".
(B, the demo data step, is tested in pb_demo.)
"""

from odoo.tests import TransactionCase, tagged

from .test_bank_panel import BankFixture


@tagged('post_install', '-at_install', 'fs9_bank_panel')
class TestJoiningChecklistBank(BankFixture):

    def _lines(self, emp):
        self.env.invalidate_all()
        e = emp.sudo()
        return ([x.strip() for x in (e.profile_missing or '').split(',') if x.strip()],
                e.pb_profile_waiting or '', e.profile_complete_pct)

    def test_a1_approved_account_is_done(self):
        missing, waiting, _pct = self._lines(self.approved)
        self.assertNotIn('Bank account', missing)
        self.assertEqual(waiting, '')
        if self.has_vn:
            self.assertNotIn('Bank account', self._lines(self.vn_only)[0])

    def test_a2_waiting_change_is_sent_not_missing(self):
        if self.Req is None:
            self.skipTest('no bank change requests on this database')
        missing, waiting, pct = self._lines(self.waiting)
        self.assertNotIn('Bank account', missing)
        self.assertEqual(waiting, 'Bank account')
        # counted as done in the percentage (the person did their part)
        self.reqs[self.waiting.id].sudo().write({'state': 'refused'})
        missing2, waiting2, pct2 = self._lines(self.waiting)
        self.assertIn('Bank account', missing2)
        self.assertEqual(waiting2, '')
        self.assertLess(pct2, pct)

    def test_a3_old_box_alone_is_missing(self):
        missing, waiting, _pct = self._lines(self.none)
        self.assertIn('Bank account', missing, 'the old typed number still counted')
        self.assertEqual(waiting, '')

    def test_a4_one_rule_for_everybody(self):
        PL = self.env['pb.payment.list']
        for emp in (self.approved, self.vn_only, self.waiting, self.both, self.none, self.other):
            missing, waiting, _pct = self._lines(emp)
            approved = emp.sudo().pb_bank_on_record
            wait = bool(PL._pb_waiting_changes(emp).get(emp.id))
            self.assertEqual('Bank account' in missing, not approved and not wait, emp.name)
            self.assertEqual(waiting == 'Bank account', not approved and wait, emp.name)
            # every other line of the list is untouched
            for label in missing:
                self.assertNotEqual(label, '', emp.name)

    def test_a5_screens_carry_the_waiting_line(self):
        view = self.env.ref('pb_employee_bank_panel.portal_my_journey_waiting')
        self.assertIn('Sent, waiting for HR', view.arch_db)
        from lxml import etree
        combined = self.env.ref('pb_onboarding.portal_my_journey').sudo()._get_combined_arch()
        self.assertIn('Sent, waiting for HR', etree.tostring(combined, encoding='unicode'))
        Case = self.env.get('pb.journey.case')
        case = Case.sudo().search([('employee_id', '=', self.waiting.id)], limit=1) \
            if Case is not None else None
        if case:
            self.assertEqual(self.env['pb.onboarding']._row(case)['waiting'], 'Bank account')


@tagged('post_install', '-at_install', 'fs9_bank_panel')
class TestMappingRetiredBankBoxes(TransactionCase):

    OLD = ('f:hr.employee:bank_name', 'f:hr.employee:account_number')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.cfg = cls.env['hr.formula.config'].create({
            'name': 'DEMO FS9 mapping', 'code': 'DEMO_FS9_MAP', 'country_code': 'VN',
            'state': 'active'})
        Rule = cls.env['hr.formula.rule']
        cls.r_new = Rule.create({'config_id': cls.cfg.id, 'name': 'Bank', 'code': 'BANKNEW',
                                 'column_type': 'input', 'sequence': 10,
                                 'column_role': 'bank'})
        cls.r_old = Rule.create({'config_id': cls.cfg.id, 'name': 'Old bank', 'code': 'BANKOLD',
                                 'column_type': 'input', 'sequence': 20,
                                 'column_role': 'profile'})

    def test_c1_not_offered(self):
        ids = {i['id'] for i in self.Studio._ec_right_items('')}
        self.assertFalse(ids & set(self.OLD))
        self.assertIn('f:hr.employee:private_phone', ids, 'the catalogue lost ordinary fields')
        model_ids = {i['id'] for i in self.Studio.ec_model_fields('hr.employee')['fields']}
        self.assertFalse(model_ids & set(self.OLD))
        self.assertIn('f:hr.employee:private_phone', model_ids)
        for q in ('bank', 'account'):
            found = {i['id'] for i in self.Studio.ec_search_fields(q)['fields']}
            self.assertFalse(found & set(self.OLD), q)
        board = self.Studio.employee_mapping_data(self.cfg.id)
        self.assertFalse({i['id'] for i in board.get('right') or []} & set(self.OLD))
        # the Bank lane is still offered
        self.assertTrue({'b:acc_number', 'b:bank_name'} <= {i['id'] for i in board['right']})

    def test_c2_new_mapping_refused(self):
        Mapping = self.env['hr.payslip.import.mapping'].sudo()
        for spec in self.OLD:
            res = self.Studio.employee_mapping_create(self.cfg.id, False, self.r_new.id, spec)
            self.assertFalse(res.get('ok'), spec)
            self.assertIn('No longer shown', res['msg'])
        self.assertFalse(Mapping.search([('salary_structure_id', '=', self.cfg.id)]))
        res = self.Studio.employee_mapping_create(self.cfg.id, False, self.r_new.id, 'b:bank_name')
        self.assertTrue(res.get('ok'), res)

    def test_c3_saved_mapping_keeps_working(self):
        IMF = self.env['ir.model.fields'].sudo()
        fld = IMF.search([('model', '=', 'hr.employee'), ('name', '=', 'bank_name')], limit=1)
        Mapping = self.env['hr.payslip.import.mapping'].sudo()
        row = Mapping.create({
            'salary_structure_id': self.cfg.id, 'component_id': self.r_old.id,
            'destination_type': 'field',
            'target_model_id': self.env['ir.model']._get('hr.employee').id,
            'target_field_id': fld.id})
        before = row.read(['destination_type', 'target_field_id', 'component_id'])
        board = self.Studio.employee_mapping_data(self.cfg.id)
        cards = {i['id']: i for i in board['right']}
        card = cards.get('f:hr.employee:bank_name')
        self.assertTrue(card, 'the saved mapping lost its card')
        self.assertEqual(card['meta']['note']['text'], 'No longer shown — use Bank account')
        self.assertTrue(card['meta'].get('retired'))
        self.assertIn(self.r_old.id, {w['leftId'] for w in board['wires']})
        # still a destination the import writes; the row is unchanged
        self.assertTrue(self.Studio._ec_is_mappable('hr.employee', 'bank_name'))
        self.assertEqual(row.read(['destination_type', 'target_field_id', 'component_id']), before)
        # only where used: the other old box is still not on this board
        self.assertNotIn('f:hr.employee:account_number', cards)
