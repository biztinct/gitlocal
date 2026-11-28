# -*- coding: utf-8 -*-
"""Day one moves money exactly the way day zero did — and now says who agreed.

FOUR ROUTES, PUBLISHED PER COMPANY, ALL IDEMPOTENT.

  * Bank file creation — Payroll manager, then Finance approver. The file that
    pays a whole company is the one thing in this phase that has never had a
    second pair of eyes, and two is the ordinary safeguard.
  * Payment release — Finance approver AND Country director together, on one
    joint step. Two real signatures, which is what a bank mandate means. The
    engine's "any one of a pool" closes on the first answer and therefore
    cannot express "two of five"; a joint step over two named responsibilities
    can, so that is what ships (ledger AM71).
  * Payroll journal — the fast lane, because posting a payroll journal is off
    by default on this build and a route in front of something switched off is
    a route nobody can satisfy. A company that switches posting on can publish
    a real route in one press.
  * Payslip send-out — the fast lane with a Notify step to the HR lead. A
    payslip is the employee's own document; what a business wants here is to
    KNOW it went, not to gate it.

Every one of them is a published choice from the moment it exists: changing it
is a press in the Matrix, not a code change.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

BANKFILE_WORKFLOW_NAME = 'Bank file approval'
RELEASE_WORKFLOW_NAME = 'Payment release'
JOURNAL_WORKFLOW_NAME = 'Payroll journal'
PAYSLIPS_WORKFLOW_NAME = 'Payslip send-out'


def _safeguards(due_days=1):
    return {
        'independent': True,
        'self_exception': {'enabled': False},
        'repeated': 'different',
        'evidence': [],
        'due': {'kind': 'working_days', 'days': due_days, 'day': 15,
                'calendar_id': None},
        'late': {'remind_days': 1, 'escalate_days': 2, 'reassign': False},
    }


def _role_step(key, role, title, kind, scope='company'):
    return {'key': key, 'kind': kind, 'title': title,
            'who': {'mode': 'role', 'role': role, 'scope': scope},
            'min_amount': 0, 'condition': None}


def bankfile_definition():
    """Payroll manager checks it, Finance approves it."""
    return {
        'schema_version': 1,
        'steps': [
            _role_step('s1', 'payroll_mgr', 'Payroll check', 'review'),
            _role_step('s2', 'finance', 'Finance approval', 'approve'),
        ],
        'tiers': {'enabled': False, 'fact': None},
        'safeguards': _safeguards(1),
    }


def release_definition():
    """Two signatures, and neither of them alone releases money.

    TWO STEPS AND NOT ONE JOINT STEP, because a step names ONE responsibility
    and a responsibility is one person — so "joint" over a role is a step with
    one seat, which is one signature wearing the word "joint". Two approve
    steps are two real signatures from two different people, which is what a
    bank mandate means. When the engine grows "any M of these N", this becomes
    one step (ledger AM71).
    """
    return {
        'schema_version': 1,
        'steps': [
            _role_step('s1', 'finance', 'First signature · Finance',
                       'approve'),
            _role_step('s2', 'director', 'Second signature · Country director',
                       'approve'),
        ],
        'tiers': {'enabled': False, 'fact': None},
        'safeguards': _safeguards(1),
    }


def journal_definition():
    """No approval needed — and every one recorded."""
    return {
        'schema_version': 1,
        'steps': [{'key': 'fast', 'kind': 'fast',
                   'title': 'No approval needed', 'who': {},
                   'min_amount': 0, 'condition': None}],
        'tiers': {'enabled': False, 'fact': None},
        'safeguards': _safeguards(1),
    }


def payslips_definition():
    """Sent straight away, and the HR lead is told."""
    return {
        'schema_version': 1,
        'steps': [{
            'key': 'tell', 'kind': 'notify', 'title': 'Tell the HR lead',
            'who': {'mode': 'role', 'role': 'hr_lead', 'scope': 'area'},
            'min_amount': 0, 'condition': None,
        }, {
            'key': 'fast', 'kind': 'fast', 'title': 'No approval needed',
            'who': {}, 'min_amount': 0, 'condition': None,
        }],
        'tiers': {'enabled': False, 'fact': None},
        'safeguards': _safeguards(1),
    }


#: (model, process key, workflow name, definition, roles it needs, binding note)
MONEY_ROUTES = (
    ('pb.bank.file', 'bankfile', BANKFILE_WORKFLOW_NAME, bankfile_definition,
     ('payroll_mgr', 'finance'),
     'The route every bank file follows unless a pay scheme or a part of the '
     'business is given its own.'),
    ('pb.payment.release', 'release', RELEASE_WORKFLOW_NAME,
     release_definition, ('finance', 'director'),
     'The route every payment release follows unless a pay scheme or a part '
     'of the business is given its own.'),
    ('pb.payroll.journal', 'journal', JOURNAL_WORKFLOW_NAME,
     journal_definition, (),
     'Payroll journal entries are recorded, not checked, until somebody says '
     'otherwise.'),
    ('pb.payslip.delivery.batch', 'payslips', PAYSLIPS_WORKFLOW_NAME,
     payslips_definition, ('hr_lead',),
     'Payslips go out as soon as they are asked for, and the HR lead is told.'),
)


def _lay_one(env, company, model_name, process_key, workflow_name,
             definition_fn, roles, note):
    return env['biz.approval.seed'].lay(
        company, process_key, workflow_name, definition_fn(),
        binding_note=note, model_name=model_name, role_keys=roles,
        reason='Set up when money-out approvals were switched on')


class PbBankFileSeed(models.Model):
    _inherit = 'pb.bank.file'

    @api.model
    def _approval_seed_default(self, company):
        row = MONEY_ROUTES[0]
        return _lay_one(self.env, company, *row)


class PbPaymentReleaseSeed(models.Model):
    _inherit = 'pb.payment.release'

    @api.model
    def _approval_seed_default(self, company):
        row = MONEY_ROUTES[1]
        return _lay_one(self.env, company, *row)


class PbPayrollJournalSeed(models.Model):
    _inherit = 'pb.payroll.journal'

    @api.model
    def _approval_seed_default(self, company):
        row = MONEY_ROUTES[2]
        return _lay_one(self.env, company, *row)


class PbPayslipDeliveryBatchSeed(models.Model):
    _inherit = 'pb.payslip.delivery.batch'

    @api.model
    def _approval_seed_default(self, company):
        row = MONEY_ROUTES[3]
        return _lay_one(self.env, company, *row)


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        for row in MONEY_ROUTES:
            try:
                if _lay_one(env, company, *row):
                    done += 1
            except Exception:   # noqa: BLE001 — an install must not die here
                _logger.exception('pb_pay_delivery: %s has no "%s" route yet',
                                  company.name, row[1])
    _logger.info('pb_pay_delivery: %s money-out routes published', done)
    return done


def post_init_hook(env):
    seed_all(env)


class ResCompanyMoneySeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            for row in MONEY_ROUTES:
                try:
                    _lay_one(self.env, company, *row)
                except Exception:   # noqa: BLE001 — a company is still created
                    _logger.exception(
                        'pb_pay_delivery: %s has no "%s" route yet',
                        company.name, row[1])
        return companies
