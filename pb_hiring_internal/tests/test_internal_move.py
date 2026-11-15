# -*- coding: utf-8 -*-
"""S6-B contract C-1 — an internal hire ends in a job change, never a second
person. Built on pb_hiring's own offer fixtures (imported as a MODULE so its
tests do not run twice, ledger W2BM-3). Numbered B30–B34 in the report."""
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.pb_hiring.tests import test_joining_p6 as base


class _FakeJobChange:
    """Stands in for Step 8's `pb.job.change` (absent on this database)."""

    def __init__(self):
        self.calls = []

    def pb_start_for_employee(self, employee_id, vals=None):
        self.calls.append((employee_id, dict(vals or {})))
        return {'type': 'ir.actions.client', 'tag': 'pb_job_change',
                'params': {'employee_id': employee_id, 'vals': vals}}


@tagged('post_install', '-at_install', 'wdgap_s6b')
class TestInternalMove(base.JoiningCase):

    def setUp(self):
        super().setUp()
        Emp = self.env['hr.employee']
        self.manager = Emp.create({'name': 'DEMO S6B Current manager',
                                   'company_id': self.company.id})
        self.mover = Emp.create({'name': 'DEMO S6B Internal mover',
                                 'company_id': self.company.id,
                                 'parent_id': self.manager.id,
                                 'work_email': 'demo.s6b.internal@example.com'})
        # The candidate the panel picked is the internal applicant.
        self.req.sudo().write({'pb_staff_posting': 'both'})
        app = self.env['hr.applicant'].sudo()._pbhi_apply(self.mover, self.req)
        self.applicant = app
        self.req.sudo().write({'selected_applicant_id': app.id})

    def _counts(self):
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        return (self.env['hr.employee'].sudo().with_context(active_test=False).search_count([]),
                self.env['hr.contract'].sudo().search_count([]) if 'hr.contract' in self.env else 0,
                Users.search_count([]),
                self.env['pb.journey.case'].sudo().search_count([])
                if 'pb.journey.case' in self.env else 0)

    # B30 — without the Change job flow (this database): no second person
    def test_b30_move_without_job_change_flow(self):
        offer = self._signed()
        self.assertEqual(self.applicant.stage_id.pb_key, 'post_offer')
        self.assertTrue(self.applicant.pb_manager_told_on, 'told at the offer')
        before = self._counts()
        self.assertNotIn('pb.job.change', self.env)
        result = offer.action_confirm_joined()
        self.assertIs(result, True)
        self.assertEqual(self._counts(), before,
                         'B30: no employee, contract, login or joining checklist made')
        self.assertEqual(offer.employee_id, self.mover)
        self.assertEqual(offer.state, 'joined')
        self.assertFalse(offer.contract_id)
        self.assertFalse(offer.login_user_id)
        self.assertFalse(offer.case_id)
        self.assertEqual(self.applicant.pb_job_change_state, 'to_do')
        self.assertEqual(self.applicant.stage_id.pb_key, 'joined')

    def test_b30b_board_reply_says_job_change_to_do(self):
        offer = self._signed()
        res = self.facade.act('confirm_joined', {'offer_id': offer.id})
        self.assertIn('Job change to do', res['note'])
        self.assertNotIn('pb_open_action', res)
        board = self.env['pb.hiring.internal'].with_user(self.recruiter).get_board()
        row = [a for a in board['applications'] if a['id'] == self.applicant.id][0]
        self.assertEqual(row['job_change'], 'to_do')
        self.assertFalse(board['job_change_available'])
        note = self.env['pb.hiring.internal'].with_user(self.recruiter).start_job_change(
            self.applicant.id)
        self.assertIn('employee record', note['note'])

    # B31 — with the Change job flow (simulated): it opens, prefilled
    def test_b31_move_opens_job_change(self):
        offer = self._signed()
        fake = _FakeJobChange()
        Offer = type(self.env['pb.hiring.offer'])
        with patch.object(Offer, '_pbhi_job_change_target', lambda self: fake):
            before = self._counts()
            res = self.facade.act('confirm_joined', {'offer_id': offer.id})
            self.assertEqual(self._counts(), before)
        self.assertEqual(len(fake.calls), 1)
        emp_id, vals = fake.calls[0]
        self.assertEqual(emp_id, self.mover.id)
        self.assertEqual(vals['job_id'], self.job.id)
        self.assertEqual(vals['department_id'], self.dept.id)
        self.assertEqual(vals['parent_id'], self.boss.id)
        self.assertEqual(vals['source'], 'internal_hire')
        self.assertEqual(vals['source_ref'], offer.name)
        self.assertIn('effective_date', vals)
        self.assertEqual(vals.get('wage'), 25000000.0)
        self.assertTrue(set(vals) <= {'job_id', 'job_title', 'department_id', 'parent_id',
                                      'work_location_id', 'resource_calendar_id', 'company_id',
                                      'wage', 'lines', 'effective_date', 'reason',
                                      'reason_kind', 'source', 'source_ref'},
                        'B31: only keys the S8-B draft accepts')
        self.assertEqual(res['pb_open_action']['tag'], 'pb_job_change')
        self.assertEqual(self.applicant.pb_job_change_state, 'opened')

    # B32 — the Change job flow refusing never undoes the move
    def test_b32_job_change_refusal_is_calm(self):
        offer = self._signed()

        class Refusing:
            def pb_start_for_employee(self, employee_id, vals=None):
                raise ValueError('refused')

        Offer = type(self.env['pb.hiring.offer'])
        with patch.object(Offer, '_pbhi_job_change_target', lambda self: Refusing()):
            result = offer.action_confirm_joined()
        self.assertIs(result, True)
        self.assertEqual(offer.state, 'joined')
        self.assertEqual(self.applicant.pb_job_change_state, 'to_do')

    # B33 — an OUTSIDE candidate still joins exactly as before
    def test_b33_outside_candidate_unchanged(self):
        outside = self.env['hr.applicant'].create({
            'partner_name': 'DEMO S6B Outsider', 'email_from': 'demo.s6b.out@example.com',
            'job_id': self.job.id, 'company_id': self.company.id,
            'pb_requisition_id': self.req.id})
        self.req.sudo().write({'selected_applicant_id': outside.id})
        offer = self._signed()
        self.assertEqual(offer.applicant_id, outside)
        before = self.env['hr.employee'].sudo().search_count([])
        offer.action_confirm_joined()
        self.assertEqual(self.env['hr.employee'].sudo().search_count([]), before + 1,
                         'B33: an outside joiner still gets their employee record')
        self.assertFalse(outside.pb_internal)
