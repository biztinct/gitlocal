# -*- coding: utf-8 -*-
"""WDGAP W2-F — fund payments: one sign-off to start with (F-2) and
"Suggest" leaves out what is not a fund (F-3).
Handover `docs/handovers/wdgap/WDGAP_W2_F_HANDOVER.md` §F-2, §F-3.

  F2.1  a new company gets ONE step, the Head of pay (the seat pb_loans uses);
  F2.2  the migration rewrites a route that is still exactly the two-step
        route 19.0.1.0.0 seeded and was never used — once (idempotent);
  F2.3  … and leaves alone a route something was sent through;
  F2.4  … and a route the business changed (a later revision, another name);
  F3.1  a scheme with a loan input ("Loan repayments go into") and the
        mid-month advance (carry-over setting): neither the loan input, the
        repayment line it feeds, nor the advance is suggested; a real tax is;
  F3.2  without those settings the same items ARE suggested — the scheme's
        own settings decide, never a name or a code;
  F3.3  a component that reads the loan input AND something else is a
        real figure and stays.
"""
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.biz_approval_workflow.models import definition as D
from odoo.addons.pb_fund_payments.models import fund_approval
from odoo.addons.pb_fund_payments.models.fund_approval import (
    fund_definition, old_fund_definition, one_signature_all)

from .test_fund_payments import FundFixture


@tagged('post_install', '-at_install', 'pb_fund_payments', 'wdgap_w2f')
class TestW2fOneSignature(FundFixture):

    def _workflow(self, company):
        process = self.env['biz.approval.process']._by_key('fundpay')
        return self.env['biz.approval.workflow'].sudo().search([
            ('company_id', '=', company.id), ('process_id', '=', process.id)])

    def _old_company(self, name):
        """A company laid the way 19.0.1.0.0 laid it: two signatures."""
        with patch.object(fund_approval, 'fund_definition', old_fund_definition):
            company = self.env['res.company'].create({'name': name,
                                                      'currency_id': self.vnd.id})
        wf = self._workflow(company)
        self.assertEqual(len(wf.version_ids), 1)
        self.assertEqual(D.fingerprint(wf.published_version_id.definition),
                         D.fingerprint(old_fund_definition()))
        return company

    def test_F2_1_new_company_one_step_head_of_pay(self):
        company = self.env['res.company'].create({'name': 'W2F New Co',
                                                  'currency_id': self.vnd.id})
        wf = self._workflow(company)
        definition = wf.published_version_id.definition
        self.assertEqual(D.fingerprint(definition), D.fingerprint(fund_definition()))
        steps = D.normalise(definition)['steps']
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]['who'], {'mode': 'role', 'role': 'pay_head',
                                           'scope': 'company'})
        self.assertEqual(steps[0]['title'], 'Head of pay')
        # the same seat pb_loans uses — and someone holds it from day one
        role = self.env['biz.approval.role'].sudo().search([('key', '=', 'pay_head')])
        self.assertTrue(self.env['biz.approval.responsibility'].sudo().search_count([
            ('company_id', '=', company.id), ('role_id', '=', role.id)]))

    def test_F2_2_untouched_route_is_rewritten_once(self):
        company = self._old_company('W2F Old Co')
        Pay = self.env['pb.fund.payment']
        self.assertEqual(Pay._pb_one_signature(company), 'changed')
        wf = self._workflow(company)
        self.assertEqual(len(wf), 1, 'the same route, a new revision')
        self.assertEqual(sorted(wf.version_ids.mapped('status')), ['published', 'superseded'])
        self.assertEqual(D.fingerprint(wf.published_version_id.definition),
                         D.fingerprint(fund_definition()))
        self.assertEqual(wf.published_version_id.publish_reason,
                         'Set to one signature, the Head of pay')
        binding = self.env['biz.approval.binding'].sudo().search([
            ('company_id', '=', company.id), ('process_id', '=', wf.process_id.id),
            ('active', '=', True)])
        self.assertEqual(binding.workflow_id, wf)
        # idempotent: a second run leaves it
        self.assertEqual(Pay._pb_one_signature(company), 'changed by the business')
        self.assertEqual(len(wf.version_ids), 2)
        # the migration's own entry point, over every company
        out = one_signature_all(self.env)
        self.assertEqual(out[company.id], 'changed by the business')

    def test_F2_3_a_used_route_is_left_alone(self):
        company = self._old_company('W2F Used Co')
        wf = self._workflow(company)
        self.env['biz.approval.request'].sudo().create({
            'title': 'Pay W2F tax office', 'process_id': wf.process_id.id,
            'company_id': company.id, 'res_model': 'pb.fund.payment', 'res_id': 1})
        self.assertEqual(self.env['pb.fund.payment']._pb_one_signature(company),
                         'already used')
        self.assertEqual(len(wf.version_ids), 1)
        self.assertEqual(D.fingerprint(wf.published_version_id.definition),
                         D.fingerprint(old_fund_definition()))

    def test_F2_4_a_route_the_business_changed_is_left_alone(self):
        company = self._old_company('W2F Own Co')
        wf = self._workflow(company)
        wf.name = 'Our own fund route'
        self.assertEqual(self.env['pb.fund.payment']._pb_one_signature(company),
                         'changed by the business')
        wf.name = fund_approval.WORKFLOW_NAME
        # a later revision (even one that says the same) is the business's own
        draft = wf.action_new_draft()
        publisher = self.env['biz.approval.seed'].publisher_for(company)
        engine = self.env['biz.approval.engine'].with_user(publisher).sudo() \
            .with_context(approval_skip_coverage=True)
        engine.publish(draft.id, draft.draft_revision, None, 'ours',
                       [w['code'] for w in engine.validate_for_publish(draft.id)['warnings']])
        self.assertEqual(self.env['pb.fund.payment']._pb_one_signature(company),
                         'changed by the business')
        self.assertEqual(D.fingerprint(wf.published_version_id.definition),
                         D.fingerprint(old_fund_definition()))
