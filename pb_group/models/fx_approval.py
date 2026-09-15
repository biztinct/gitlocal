# -*- coding: utf-8 -*-
"""Exchange rates, group policy and budgets are agreed before they are typed.

WHAT WAS TRUE BEFORE. An exchange rate is one number that re-prices a whole
group's reporting — every comparison, every budget, every fairness figure.
Anybody who could open the currency list could type one. The group's own
policy (which rate to use, which currency to read in, when the financial year
starts, how a split payment is treated) was a form. A budget upload wrote
hundreds of lines on Apply, and an expense was added by pressing Add.

WHAT IS TRUE NOW. Each of those writes a proposal (`pb.fx.proposal`) and the
change happens when the route says yes. The default route is the finance
approver and then the finance controller — the new responsibility this phase
adds, because the person who releases a payment and the person who owns the
numbers behind it are not always the same person and a business should be
able to say so.

MANAGED RATES ONLY. The rate hook holds a rate for a currency this database
actually reports in — a group's presentation currency, or a company's. A rate
row for a currency nothing here reads is somebody else's business and is left
alone, because a gate that stops an unrelated import is a gate that gets
switched off.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    role_step, route,
)

_logger = logging.getLogger(__name__)

FX_PROCESS_KEY = 'fx'

#: What changing a rate or a group policy has always needed.
FX_GROUP = 'pb_group.group_group_admin'

#: "This write IS the approved change."
FX_WRITE = 'pb_fx_approved_write'


class PbFxProposal(models.Model):
    _name = 'pb.fx.proposal'
    _inherit = ['biz.approval.proposal.mixin']
    _description = 'Proposed rate, policy or budget change'

    _approval_process_key = FX_PROCESS_KEY
    _proposal_prefix = 'FX'
    _proposal_gate_groups = (FX_GROUP, 'base.group_system')
    _proposal_kind_labels = {
        'rate': 'Change an exchange rate',
        'policy': 'Change a group\'s money policy',
        'budget_upload': 'Upload a budget',
        'budget_expense': 'Add an expense to a budget',
    }
    _proposal_fact_specs = {
        'rates_changed': {'type': 'int', 'label': 'Rates changed'},
        'budget_lines': {'type': 'int', 'label': 'Budget lines'},
        'amount_total': {'type': 'decimal', 'label': 'Amount'},
        'policy_changed': {'type': 'bool', 'label': 'Policy changed'},
    }

    # ------------------------------------------------------- the snapshot
    def _target(self):
        self.ensure_one()
        if not self.target_model or not self.target_id \
                or self.target_model not in self.env:
            return None
        record = self.env[self.target_model].sudo().browse(
            self.target_id).exists()
        return record or None

    def _live_snapshot(self):
        self.ensure_one()
        target = self._target()
        if target is None:
            return {}
        values = (self.payload() or {}).get('values') or {}
        return {k: target[k] for k in sorted(values) if k in target._fields}

    # ------------------------------------------------------------ the rows
    _POLICY_WORDS = {
        'presentation_currency_id': 'Reads in',
        'fx_policy': 'Which rate to use',
        'fiscal_start_month': 'Financial year starts in month',
        'split_pay_policy': 'How a split payment is treated',
    }

    def _proposal_rows(self):
        self.ensure_one()
        payload = self.payload() or {}
        snapshot = self.snapshot() or {}
        target = self._target()
        rows = []
        if self.kind == 'rate' and target is not None:
            rows.append((_('Currency'), '', target.currency_id.name or ''))
            rows.append((_('On'), '', str(target.name or '')))
            for key, value in sorted((payload.get('values') or {}).items()):
                rows.append((_('Rate') if key == 'rate' else str(key),
                             snapshot.get(key, ''), value))
        elif self.kind == 'policy':
            values = payload.get('values') or {}
            if target is not None:
                rows.append((_('Group'), '', target.display_name or ''))
            for key, label in self._POLICY_WORDS.items():
                if key not in values:
                    continue
                before, after = snapshot.get(key, ''), values[key]
                if key == 'presentation_currency_id':
                    before = self._row_label('res.currency', before)
                    after = self._row_label('res.currency', after)
                rows.append((_(label), before, after))
        elif self.kind == 'budget_upload':
            rows.append((_('What it is for'), '',
                         str(payload.get('budget_type') or '')))
            rows.append((_('Financial year'), '', str(payload.get('fy') or '')))
            rows.append((_('Total'), '', self.amount))
        elif self.kind == 'budget_expense':
            values = payload.get('values') or {}
            rows.append((_('What the money was for'), '',
                         str(values.get('name') or '')))
            rows.append((_('Amount'), '', self.amount))
            rows.append((_('When'), '', str(values.get('spend_date') or '')))
            if values.get('supplier'):
                rows.append((_('Supplier'), '', str(values['supplier'])))
        return rows

    # --------------------------------------------------------- the applies
    def _apply_rate(self):
        target = self._target()
        if not target:
            raise UserError(_("That exchange rate no longer exists."))
        target.with_context(**{FX_WRITE: True}).write(
            (self.payload() or {}).get('values') or {})
        return {'rate_id': target.id}

    def _apply_policy(self):
        return self.env['pb.group.room'].with_context(
            **{FX_WRITE: True}).save_group(
                (self.payload() or {}).get('values') or {}) and {
                    'group_id': (self.payload() or {}).get('values', {}).get(
                        'id') or 0}

    def _apply_budget_upload(self):
        payload = self.payload()
        return self.env['pb.budget.upload.wizard'].with_context(
            **{FX_WRITE: True}).apply(
                payload.get('file'), payload.get('fy'),
                payload.get('budget_type') or 'manpower')

    def _apply_budget_expense(self):
        return self.env['pb.budget'].with_context(
            **{FX_WRITE: True}).add_expense(
                (self.payload() or {}).get('values') or {})

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'finance',
                                  ('pb_group.group_group_admin',
                                   'account.group_account_manager'))
        Seed.fill_role_from_group(company, 'finance_controller',
                                  ('pb_group.group_group_admin',
                                   'base.group_system'))
        return Seed.lay(
            company, FX_PROCESS_KEY, 'Rates, policy and budgets',
            route(role_step(_('Finance approver'), 'finance'),
                  role_step(_('Finance controller'), 'finance_controller')),
            binding_note='The route a change to an exchange rate, a group\'s '
                         'money policy or a budget follows.',
            model_name='pb.fx.proposal',
            role_keys=('finance', 'finance_controller'),
            reason='Set up when rate and budget approvals were switched on')


class ResCurrencyRateApproval(models.Model):
    """One number that re-prices a whole group."""
    _inherit = 'res.currency.rate'

    _FX_HELD_FIELDS = ('rate', 'inverse_company_rate', 'company_rate', 'name')

    def _fx_managed(self):
        """Is this a currency this database actually reports in?"""
        currencies = self.mapped('currency_id')
        if not currencies:
            return False
        reported = self.env['res.company'].sudo().search(
            []).mapped('currency_id')
        Group = self.env.get('pb.group')
        if Group is not None:
            reported |= Group.sudo().search([]).mapped(
                'presentation_currency_id')
        return bool(currencies & reported)

    def write(self, vals):
        held = [f for f in (vals or {}) if f in self._FX_HELD_FIELDS]
        if not held or not self or self.env.context.get(FX_WRITE) \
                or self.env.context.get('install_mode') \
                or 'pb.fx.proposal' not in self.env \
                or not self._fx_managed():
            return super().write(vals)
        Proposal = self.env['pb.fx.proposal']
        if Proposal.route_mode(company=self.env.company,
                               kind_key='rate') != 'route':
            return super().write(vals)
        values = {f: vals[f] for f in held}
        Proposal.precheck(self, values)
        for rate in self:
            Proposal.propose(
                'rate',
                _("Exchange rate · %(currency)s · %(when)s",
                  currency=rate.currency_id.name or '', when=rate.name or ''),
                payload={'values': values},
                snapshot={f: rate[f] for f in sorted(values)
                          if f in rate._fields},
                facts={'rates_changed': {'value': 1, 'unit': ''},
                       'budget_lines': {'value': 0, 'unit': ''},
                       'amount_total': {'value': 0.0, 'unit': ''},
                       'policy_changed': {'value': False, 'unit': ''}},
                target=rate,
            )
        rest = {k: v for k, v in (vals or {}).items() if k not in values}
        if rest:
            return super().write(rest)
        return True


class ResCompanyFxSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['pb.fx.proposal']._approval_seed_default(company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('fx: %s has no route yet', company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.fx.proposal']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('fx: %s has no route yet', company.name)
    return done
