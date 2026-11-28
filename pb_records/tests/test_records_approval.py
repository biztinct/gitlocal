# -*- coding: utf-8 -*-
"""Approval Matrix Phase 5 — the Records Desk half (cases M06, M07).

The desk's own suites run with "No approval needed" published, because they are
about what it WRITES. This one is about who says yes — and about the promise
that a value somebody else moved in the meantime is never quietly clobbered.
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRecordsApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Desk = cls.env['pb.records.desk']
        cls.Engine = cls.env['biz.approval.engine']
        cls.Apply = cls.env['pb.records.apply']
        cls.company = cls.env.company

        Users = cls.env['res.users'].with_context(no_reset_password=True)
        g_hr = cls.env.ref('hr.group_hr_user')
        g_user = cls.env.ref('base.group_user')
        cls.hr_lead = Users.create({
            'name': 'RA HR Lead', 'login': 'ra_hr_lead',
            'group_ids': [(6, 0, [g_user.id, g_hr.id])]})
        cls.finance = Users.create({
            'name': 'RA Finance', 'login': 'ra_finance',
            'group_ids': [(6, 0, [g_user.id, g_hr.id])]})
        cls._fill_role('hr_lead', cls.hr_lead)
        cls._fill_role('finance', cls.finance)
        # THE ROUTE, EXPLICITLY. `post_init_hook` runs on install only, and a
        # test database is usually reached by an upgrade — so a suite that
        # assumed the hook had run would pass or fail depending on how the
        # database was built. Idempotent; the migration lays the same route on
        # a real upgrade. Roles are filled FIRST: the whole-coverage check runs
        # at publish time.
        cls.env['pb.records.apply']._approval_seed_default(cls.env.company)

        cls.cfg = cls._config()
        cls.employee = cls.env['hr.employee'].create({
            'name': 'RA Person', 'company_id': cls.company.id,
            'job_title': 'Before'})

    @classmethod
    def _fill_role(cls, key, user):
        role = cls.env['biz.approval.role'].sudo().search(
            [('key', '=', key)], limit=1)
        if not role:
            return
        held = cls.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', cls.env.company.id),
            ('role_id', '=', role.id), ('scope_key', '=', '')], limit=1)
        if held:
            held.write({'user_id': user.id, 'active': True})
            return
        cls.env['biz.approval.responsibility'].sudo().create({
            'company_id': cls.env.company.id, 'role_id': role.id,
            'scope_key': '', 'scope_label': cls.env.company.name,
            'user_id': user.id, 'date_from': date(2020, 1, 1)})

    @classmethod
    def _config(cls):
        """One scheme that maps one plain employee field: `job_title`.

        Built exactly the way `test_records_r2_desk` builds one — a component
        with a mapping to a destination — because the desk only ever offers a
        field a scheme MAPS.
        """
        cfg = cls.env['hr.formula.config'].create({
            'name': 'RA Scheme', 'code': 'RASCHEME',
            'country_code': 'VN', 'state': 'active',
            'company_id': cls.company.id})
        rule = cls.env['hr.formula.rule'].create({
            'config_id': cfg.id, 'name': 'Job title', 'code': 'RAJOBTITLE',
            'column_type': 'input', 'sequence': 1, 'default_value': 0.0,
            'appears_on_payslip': False})
        model = cls.env['ir.model'].search(
            [('model', '=', 'hr.employee')], limit=1)
        field = cls.env['ir.model.fields'].search(
            [('model', '=', 'hr.employee'), ('name', '=', 'job_title')],
            limit=1)
        cls.env['hr.payslip.import.mapping'].create({
            'salary_structure_id': cfg.id, 'component_id': rule.id,
            'destination_type': 'field',
            'target_model_id': model.id, 'target_field_id': field.id,
        })
        return cfg

    def _field_id(self):
        cards = self.Desk._cards(self.cfg.id)
        for key, card in cards.items():
            if card.get('field') == 'job_title':
                return key
        self.fail('the fixture scheme does not map job_title')

    def _approve_all(self, apply_rec):
        for _guard in range(6):
            request = apply_rec.approval_request_id
            if not request or request.state not in ('pending', 'blocked'):
                return request
            step = request.step_ids.filtered(
                lambda s: s.status == 'active')[:1]
            self.assertTrue(step, 'stalled: %s' % (request.block_reason or ''))
            seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
            self.assertTrue(seat)
            self.Engine.with_user(seat.acting_user_id).decide(
                request.id, step.key, 'approve', 'ok')
            apply_rec.invalidate_recordset()
        self.fail('the proposal never finished')

    # ============================================================ M06
    def test_m06_apply_proposes_then_writes(self):
        field_id = self._field_id()
        result = self.Desk.apply_changes(
            self.cfg.id,
            [{'emp_id': self.employee.id, 'field_id': field_id,
              'value': 'After'}],
            note='M06')
        self.assertTrue(result['ok'])
        self.assertTrue(result['pending'], 'the desk wrote without asking')
        self.employee.invalidate_recordset()
        self.assertEqual(self.employee.job_title, 'Before',
                         'nothing may be written before it is approved')

        apply_rec = self.Apply.browse(result['apply_id'])
        self.assertEqual(apply_rec.state, 'pending')
        self.assertEqual(apply_rec.values_count, 1)
        self.assertEqual(apply_rec.people_count, 1)
        self.assertFalse(apply_rec.touches_bank)
        self.assertEqual(len(apply_rec.plan()), 1)
        self.assertEqual(apply_rec.plan()[0]['old'], 'Before')

        self._approve_all(apply_rec)
        self.employee.invalidate_recordset()
        self.assertEqual(self.employee.job_title, 'After')
        self.assertTrue(apply_rec.applied)
        self.assertEqual(apply_rec.state, 'applied')
        self.assertEqual(apply_rec.count_values, 1)
        self.assertTrue(apply_rec.change_ids,
                        'the per-value trail is still written')

    def test_m06b_a_value_moved_in_between_stops_the_whole_proposal(self):
        field_id = self._field_id()
        result = self.Desk.apply_changes(
            self.cfg.id,
            [{'emp_id': self.employee.id, 'field_id': field_id,
              'value': 'Proposed'}],
            note='M06b')
        apply_rec = self.Apply.browse(result['apply_id'])
        self.assertTrue(result['pending'])

        # somebody else gets there first
        self.employee.sudo().write({'job_title': 'Somebody else'})

        moved = self.Desk._plan_moved_since(apply_rec)
        self.assertEqual(len(moved), 1)
        self.assertIn('RA Person', moved[0])

        with self.assertRaises(UserError):
            apply_rec._approval_apply(apply_rec.approval_request_id)
        self.employee.invalidate_recordset()
        self.assertEqual(self.employee.job_title, 'Somebody else',
                         'the other person\'s change was overwritten')
        self.assertFalse(apply_rec.applied)

    def test_m06c_the_fast_lane_writes_at_once(self):
        self.env['biz.approval.seed'].sudo().set_no_approval_needed(
            self.company, 'records')
        field_id = self._field_id()
        result = self.Desk.apply_changes(
            self.cfg.id,
            [{'emp_id': self.employee.id, 'field_id': field_id,
              'value': 'Straight through'}],
            note='M06c')
        self.assertFalse(result['pending'])
        self.assertEqual(result['written'], 1)
        self.employee.invalidate_recordset()
        self.assertEqual(self.employee.job_title, 'Straight through')
        apply_rec = self.Apply.browse(result['apply_id'])
        self.assertTrue(apply_rec.applied)
        self.assertEqual(apply_rec.approval_request_id.state, 'applied',
                         'a fast lane is still recorded as a request')

    # ============================================================ M07
    def test_m07_an_imported_file_takes_the_same_road(self):
        field_id = self._field_id()
        result = self.Desk.apply_changes(
            self.cfg.id,
            [{'emp_id': self.employee.id, 'field_id': field_id,
              'value': 'From a file'}],
            note='M07', source='import')
        apply_rec = self.Apply.browse(result['apply_id'])
        self.assertEqual(apply_rec.source, 'import')
        self.assertTrue(result['pending'],
                        'a file must not be a way round the route')
        self._approve_all(apply_rec)
        self.employee.invalidate_recordset()
        self.assertEqual(self.employee.job_title, 'From a file')

    def test_m07b_undo_is_not_a_proposal(self):
        """Putting values back the way they were is never gated: every one of
        them was approved on the way in."""
        self.env['biz.approval.seed'].sudo().set_no_approval_needed(
            self.company, 'records')
        field_id = self._field_id()
        result = self.Desk.apply_changes(
            self.cfg.id,
            [{'emp_id': self.employee.id, 'field_id': field_id,
              'value': 'Changed'}], note='M07b')
        self.employee.invalidate_recordset()
        self.assertEqual(self.employee.job_title, 'Changed')

        undone = self.Desk.undo_apply(result['apply_id'])
        self.assertTrue(undone['ok'])
        self.assertEqual(undone['restored'], 1)
        self.employee.invalidate_recordset()
        self.assertEqual(self.employee.job_title, 'Before')
        undo_rec = self.Apply.browse(undone['apply_id'])
        self.assertTrue(undo_rec.applied)
        self.assertEqual(undo_rec.state, 'applied')
        self.assertFalse(undo_rec.approval_request_id,
                         'an undo never asks')

    def test_m06d_the_headline_survives_the_number_being_one(self):
        """Found on the browser walk: the queue read "1 people · 1 values"."""
        field_id = self._field_id()
        result = self.Desk.apply_changes(
            self.cfg.id,
            [{'emp_id': self.employee.id, 'field_id': field_id,
              'value': 'One of each'}], note='M06d')
        apply_rec = self.Apply.browse(result['apply_id'])
        headline = apply_rec._headline()
        self.assertIn('1 person', headline)
        self.assertIn('1 value', headline)
        self.assertNotIn('1 people', headline)
        self.assertNotIn('1 values', headline)

    def test_m07c_the_catalogue_row_points_at_the_proposal(self):
        row = self.env['biz.approval.process'].sudo()._by_key('records')
        self.assertEqual(row.model_name, 'pb.records.apply')
        self.assertTrue(row.connected)
