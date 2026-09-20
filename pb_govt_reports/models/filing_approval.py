# -*- coding: utf-8 -*-
"""A statutory filing is produced once somebody has agreed to produce it.

WHAT WAS TRUE BEFORE. Anybody who could open the Government Reports board
could press Generate, and out came a file addressed to a social-insurance
office or a tax authority, with the company's numbers in it. There was no
permission check in this module at all — not a group, not an access rule —
and no record anywhere that the file had been made.

WHAT IS TRUE NOW. Two things, and the first matters more than the second:

  1. **A permission.** Generating a filing needs the payroll officer role. It
     always should have; the screen was newer than the rule.
  2. **A proposal.** The press writes down which filing, for which country,
     over which period and with which parameters, and asks. The file is
     produced when the route says yes — by the approver, as themselves, who
     must hold the same role.

The filing wizard is a TRANSIENT and is vacuumed after an hour, so the
proposal cannot hold on to one. It holds the values instead and builds a fresh
wizard at apply time from the same allow-list the flow itself uses. That is
also why there is nothing to snapshot: a filing READS the payroll and writes
no business record, so "has anything moved?" is answered by the figures inside
the file, which is what the approver is agreeing to produce.
"""

import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    role_step, route,
)

_logger = logging.getLogger(__name__)

#: The catalogue row a filing is approved under.
FILING_PROCESS_KEY = 'filing'

#: What producing a filing has always needed, and never checked.
FILING_GROUP = 'pb_hr_payroll_base.group_payroll_base_officer'


class PbFilingProposal(models.Model):
    _name = 'pb.filing.proposal'
    _inherit = ['biz.approval.proposal.mixin']
    _description = 'Proposed statutory filing'

    _approval_process_key = FILING_PROCESS_KEY
    _proposal_prefix = 'FIL'
    _proposal_gate_groups = (FILING_GROUP,)
    _proposal_kind_labels = {'filing': 'Statutory filing'}
    _proposal_fact_specs = {
        'country': {'type': 'char', 'label': 'Country'},
        'filing_key': {'type': 'char', 'label': 'Which filing'},
        'period': {'type': 'char', 'label': 'Period'},
    }

    # ------------------------------------------------------------- the rows
    def _proposal_rows(self):
        self.ensure_one()
        payload = self.payload() or {}
        facts = self.facts() or {}
        rows = [
            (_('Country'), '', str(payload.get('country') or '')),
            (_('Which filing'), '', str(payload.get('filing_key') or '')),
            (_('Period'), '', (facts.get('period') or {}).get('value', '')),
        ]
        values = payload.get('values') or {}
        for key in ('date_from', 'date_to', 'submission_period'):
            if values.get(key):
                rows.append((_('From') if key == 'date_from'
                             else _('To') if key == 'date_to'
                             else _('Period'), '', values[key]))
        if values.get('department_id'):
            rows.append((_('Team'), '', self._row_label(
                'hr.department', values['department_id'])))
        rows.append((_('What happens'), '',
                     _('The file is produced and kept, ready to send to the '
                       'authority')))
        return rows

    # ------------------------------------------------------------ the apply
    def _apply_filing(self):
        """Build the wizard again and press its own generate button."""
        self.ensure_one()
        payload = self.payload()
        country = str(payload.get('country') or '').upper()
        filing_key = str(payload.get('filing_key') or '')
        Flow = self.env['pb.filing.flow']
        spec = Flow._adapter(country)
        Wiz = self.env[spec['model']]
        vals = Flow._clean(Wiz, Flow._writable(spec, filing_key),
                           payload.get('values') or {})
        if spec['key_field']:
            vals[spec['key_field']] = filing_key
        wizard = Wiz.create(vals)
        outcome = Flow._press(wizard, country, filing_key)
        artifacts, message = Flow._materialise(wizard, outcome)
        return {'artifacts': artifacts, 'message': message,
                'country': country, 'filing_key': filing_key}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(
            company, 'payroll_mgr',
            ('pb_hr_payroll_base.group_payroll_base_manager',
             'pb_hr_payroll_base.group_payroll_base_officer'))
        return Seed.lay(
            company, FILING_PROCESS_KEY, 'Statutory filings',
            route(role_step(_('Payroll manager'), 'payroll_mgr')),
            binding_note='The route every statutory filing follows before it '
                         'is produced.',
            model_name='pb.filing.proposal',
            role_keys=('payroll_mgr',),
            reason='Set up when filing approvals were switched on')


class ResCompanyFilingSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['pb.filing.proposal']._approval_seed_default(company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('pb_govt_reports: %s has no filing route yet',
                                  company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.filing.proposal']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pb_govt_reports: %s has no filing route yet',
                              company.name)
    _logger.info('pb_govt_reports: %s companies have a filing route', done)
    return done


def post_init_hook(env):
    seed_all(env)
