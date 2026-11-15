# -*- coding: utf-8 -*-
"""The default route a fund payment travels — ONE signature, the Head of pay.

WDGAP W2-F (F-2), owner ruling 2026-11-15: "Fund payments: one sign-off to
start with." The amounts come straight from approved payslips, so the default
is the one step `pb_loans` ships for loans (`pb_loans/models/loan_approval.py`):
Head of pay, filled from whoever holds the payroll manager group today. It is
a published choice from the moment it exists; the business changes it in the
Approval Matrix, never in code. (W2-B shipped the payment release's two
signatures — Finance, then Country director; `old_fund_definition`.)

EXISTING DATABASES (`migrations/19.0.1.1.0`). A company's route is rewritten
to the one signature ONLY when it is still exactly what W2-B seeded — one
workflow, one published revision, the two-signature definition, the default
binding — AND no fund payment of that company has ever been sent for approval.
Anything else is the business's own choice, or has already been used, and is
left alone (`_pb_one_signature`).

The catalogue row (`data/approval_process.xml`) is marked as money, so the one
Approvals inbox never offers a fund payment for "approve selected" (WDGAP QF1
`_can_bulk`; `biz.approval.process` refuses bulk_ok on a money process).
"""
import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models import definition as D
from odoo.addons.biz_approval_workflow.models.chain_shim import role_step, route
from odoo.addons.pb_pay_delivery.models.approval_seed import release_definition

from .fund_payment import FUNDPAY_PROCESS_KEY

_logger = logging.getLogger(__name__)

WORKFLOW_NAME = 'Fund and tax payments'
ROLES = ('pay_head',)
PAY_HEAD_GROUPS = ('pb_hr_payroll_base.group_payroll_base_manager',)
BINDING_NOTE = ('The route every payment to a fund or tax office follows unless '
                'somebody publishes another one.')
ONE_SIGNATURE_REASON = 'Set to one signature, the Head of pay'


def fund_definition():
    """One step: the Head of pay (the seat pb_loans uses)."""
    return route(role_step(_('Head of pay'), 'pay_head'))


def old_fund_definition():
    """What W2-B (pb_fund_payments 19.0.1.0.0) seeded: the payment release's
    two signatures, verbatim. Only read to recognise an untouched route."""
    return release_definition()


class PbFundPaymentSeed(models.Model):
    _inherit = 'pb.fund.payment'

    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'pay_head', PAY_HEAD_GROUPS)
        return Seed.lay(
            company, FUNDPAY_PROCESS_KEY, WORKFLOW_NAME, fund_definition(),
            binding_note=BINDING_NOTE, model_name='pb.fund.payment',
            role_keys=ROLES,
            reason='Set up when fund and tax payments were switched on')

    # ------------------------------------------------ W2-F (F-2) migration
    @api.model
    def _pb_one_signature(self, company):
        """Rewrite one company's fund-payment route to the one signature when
        it is still exactly the two-signature route W2-B seeded and nothing
        was ever sent for approval. Returns 'changed' or the reason it was
        left alone."""
        Process = self.env['biz.approval.process'].sudo()
        process = Process._by_key(FUNDPAY_PROCESS_KEY)
        if not process:
            return 'no process'
        Workflow = self.env['biz.approval.workflow'].sudo().with_context(active_test=False)
        workflows = Workflow.search([('company_id', '=', company.id),
                                     ('process_id', '=', process.id)])
        if len(workflows) != 1:
            return 'no route' if not workflows else 'several routes'
        workflow = workflows
        if not workflow.active or workflow.name != WORKFLOW_NAME:
            return 'changed by the business'
        versions = workflow.version_ids
        if len(versions) != 1 or versions.status != 'published' \
                or versions.revision != 1:
            return 'changed by the business'
        if D.fingerprint(versions.definition) != D.fingerprint(old_fund_definition()):
            return 'changed by the business'
        bindings = self.env['biz.approval.binding'].sudo().with_context(
            active_test=False).search([('company_id', '=', company.id),
                                       ('process_id', '=', process.id)])
        if len(bindings) != 1 or not bindings.active \
                or bindings.workflow_id != workflow or bindings.scope_key:
            return 'changed by the business'
        Request = self.env['biz.approval.request'].sudo()
        if 'active' in Request._fields:
            Request = Request.with_context(active_test=False)
        if Request.search_count([('company_id', '=', company.id),
                                 ('process_id', '=', process.id)], limit=1):
            return 'already used'
        Seed = self.env['biz.approval.seed']
        if not Seed.roles_exist(ROLES):
            return 'no Head of pay responsibility'
        Seed.fill_role_from_group(company, 'pay_head', PAY_HEAD_GROUPS)
        draft = workflow.action_new_draft()
        draft.write({'definition': fund_definition()})
        publisher = Seed.publisher_for(company)
        engine = self.env['biz.approval.engine'].with_user(publisher).sudo() \
            .with_context(approval_skip_coverage=True)
        checks = engine.validate_for_publish(draft.id)
        if checks['errors']:
            _logger.warning('pb_fund_payments: one-signature route refused for %s: %s',
                            company.name, [e['code'] for e in checks['errors']])
            draft.unlink()
            return 'refused'
        engine.publish(draft.id, draft.draft_revision, None, ONE_SIGNATURE_REASON,
                       [w['code'] for w in checks['warnings']])
        return 'changed'


class ResCompanyFundSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                with self.env.cr.savepoint():
                    self.env['pb.fund.payment'].sudo()._approval_seed_default(company)
            except Exception:       # noqa: BLE001 — a company must still be made
                _logger.exception('pb_fund_payments: %s has no fund-payment route',
                                  company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            with env.cr.savepoint():
                if env['pb.fund.payment'].sudo()._approval_seed_default(company):
                    done += 1
        except Exception:       # noqa: BLE001 — an install must not die here
            _logger.exception('pb_fund_payments: %s has no fund-payment route',
                              company.name)
    _logger.info('pb_fund_payments: %s fund-payment routes published', done)
    return done


def one_signature_all(env):
    """The 19.0.1.1.0 migration: every company, each in its own savepoint."""
    out = {}
    for company in env['res.company'].sudo().with_context(active_test=False).search(
            [], order='id'):
        try:
            with env.cr.savepoint():
                verdict = env['pb.fund.payment'].sudo()._pb_one_signature(company)
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pb_fund_payments: %s route left as it was', company.name)
            verdict = 'error'
        out[company.id] = verdict
        _logger.info('pb_fund_payments W2-F: company %s (%s) — %s',
                     company.id, company.name, verdict)
    return out
