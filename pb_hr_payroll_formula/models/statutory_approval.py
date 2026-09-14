# -*- coding: utf-8 -*-
"""Statutory rates, tax tables and legislation packs are proposed, not typed.

WHAT WAS TRUE BEFORE. The numbers that decide what every employee in the
country pays — the insurance rates, the ceilings, the tax bands, the personal
allowance — could be created or rewritten by one person on one screen, and two
of the doors had no permission check at all. An insurance adjustment could be
applied to payroll by an ordinary payroll user.

WHAT IS TRUE NOW. Every one of those doors writes down what it is about to do
and asks. The default route is the payroll manager and then the country
director, because a statutory number is a legal statement about the whole
company and getting it wrong is a filing error, not a payroll error.

ONE MODEL, NINE DOORS. A proposal carries a `kind` and the engine treats it as
an opaque word, so a business can answer "new tax table" differently from
"apply a legislation pack" without anybody writing a second model. What each
kind does when it is approved is one `_apply_<kind>` method below.

WHERE THIS LIVES, AND WHY. The doors are spread over three modules —
`pb_statutory` (the cockpit wizards), `pb_hr_payroll_vietnam` (the country
tables) and `pb_formula_studio` (packs and rate tables). A catalogue row names
ONE model, so the proposal has to sit somewhere all three can reach, and
`pb_hr_payroll_formula` is the only module all three depend on. It is also the
module that owns rate tables already.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    role_step, route,
)

_logger = logging.getLogger(__name__)

#: The catalogue row a statutory change is approved under.
STATUTORY_PROCESS_KEY = 'statutory'

#: What changing a statutory number has always needed. Two of the doors never
#: checked it; the rule is not new, the check is.
STATUTORY_GROUP = 'pb_hr_payroll_base.group_payroll_base_manager'

#: The context flag that says "this write IS the approved change". Without it
#: the write hooks below would propose their own apply, for ever.
STATUTORY_WRITE = 'pb_statutory_approved_write'


class PbStatutoryProposal(models.Model):
    _name = 'pb.statutory.proposal'
    _inherit = ['biz.approval.proposal.mixin']
    _description = 'Proposed statutory change'

    _approval_process_key = STATUTORY_PROCESS_KEY
    _proposal_prefix = 'ST'
    _proposal_gate_groups = (STATUTORY_GROUP,)
    _proposal_kind_labels = {
        'policy_create': 'New insurance policy',
        'policy_edit': 'Change an insurance policy',
        'tax_table_create': 'New tax table',
        'tax_slabs': 'Rebuild the tax bands',
        'slab_edit': 'Change a tax band',
        'insurance_adjust': 'Apply an insurance adjustment',
        'pack_publish': 'Publish a legislation pack',
        'pack_apply': 'Apply a legislation pack',
        'rate_table_save': 'Save a rate table',
        'rate_table_delete': 'Delete a rate table',
    }
    _proposal_fact_specs = {
        'rows_changed': {'type': 'int', 'label': 'Rows changed'},
        'effective_date': {'type': 'char', 'label': 'Takes effect'},
        'configs_affected': {'type': 'int', 'label': 'Pay schemes affected'},
    }

    # ==================================================================
    # What the world looks like now
    # ==================================================================
    def _live_snapshot(self):
        """Re-read the values this proposal overwrites, from the world.

        A CREATE has nothing to compare, and says so by returning nothing —
        which is the mixin's default and the honest answer. Everything that
        overwrites an existing row is listed here, or the rail is decoration
        (ledger AM46).
        """
        self.ensure_one()
        payload = self.payload()
        target = self._target()
        if self.kind == 'policy_edit' and target:
            return {k: target[k] for k in sorted(payload.get('values') or {})
                    if k in target._fields}
        if self.kind == 'slab_edit' and target:
            return {k: target[k] for k in sorted(payload.get('values') or {})
                    if k in target._fields}
        if self.kind == 'tax_slabs' and target:
            return {'bands': len(target.slab_ids)}
        if self.kind == 'insurance_adjust' and target:
            return {'state': target.state,
                    'difference': target.difference}
        if self.kind == 'pack_publish' and target:
            return {'state': target.state}
        if self.kind in ('rate_table_save', 'rate_table_delete'):
            table = self._rate_table()
            if table:
                return {'code': table.code or '',
                        'brackets': len(table.line_ids)}
        return {}

    def _target(self):
        """The record this proposal is about, or an empty recordset."""
        self.ensure_one()
        if not self.target_model or not self.target_id:
            return None
        if self.target_model not in self.env:
            return None
        record = self.env[self.target_model].sudo().browse(
            self.target_id).exists()
        return record or None

    def _rate_table(self):
        self.ensure_one()
        table_id = int((self.payload() or {}).get('table_id') or 0)
        if not table_id or 'hr.formula.rate.table' not in self.env:
            return None
        table = self.env['hr.formula.rate.table'].sudo().browse(
            table_id).exists()
        return table or None

    # ==================================================================
    # Carrying each kind out
    # ==================================================================
    def _model(self, name):
        if name not in self.env:
            raise UserError(_(
                "This part of the payroll is not installed on this database "
                "any more, so the change cannot be carried out."))
        return self.env[name]

    def _apply_policy_create(self):
        payload = self.payload()
        policy = self._model('vietnam.insurance.policy').create(
            payload.get('values') or {})
        return {'policy_id': policy.id, 'name': policy.name or ''}

    def _apply_policy_edit(self):
        target = self._target()
        if not target:
            raise UserError(_("That insurance policy no longer exists."))
        target.with_context(**{STATUTORY_WRITE: True}).write(
            (self.payload() or {}).get('values') or {})
        return {'policy_id': target.id}

    def _apply_tax_table_create(self):
        payload = self.payload()
        table = self._model('vietnam.tax.table').create(
            payload.get('values') or {})
        if payload.get('gen_slabs') and hasattr(
                table, 'action_create_default_slabs'):
            table.action_create_default_slabs()
        return {'tax_id': table.id, 'name': table.name or '',
                'slabs': len(table.slab_ids)}

    def _apply_tax_slabs(self):
        target = self._target()
        if not target:
            raise UserError(_("That tax table no longer exists."))
        target.action_create_default_slabs()
        return {'tax_id': target.id, 'slabs': len(target.slab_ids)}

    def _apply_slab_edit(self):
        target = self._target()
        if not target:
            raise UserError(_("That tax band no longer exists."))
        target.with_context(**{STATUTORY_WRITE: True}).write(
            (self.payload() or {}).get('values') or {})
        return {'slab_id': target.id}

    def _apply_insurance_adjust(self):
        target = self._target()
        if not target:
            raise UserError(_("That adjustment no longer exists."))
        target.with_context(**{STATUTORY_WRITE: True}).action_apply()
        return {'adjustment_id': target.id, 'state': target.state}

    def _apply_pack_publish(self):
        target = self._target()
        if not target:
            raise UserError(_("That legislation pack no longer exists."))
        target.with_context(**{STATUTORY_WRITE: True}).write(
            {'state': 'published'})
        return {'pack_id': target.id, 'state': target.state}

    def _apply_pack_apply(self):
        payload = self.payload()
        Studio = self._model('pb.formula.studio')
        answer = Studio.with_context(
            **{STATUTORY_WRITE: True}).legislation_apply(
                payload.get('pack_id'), config_ids=payload.get('config_ids'))
        if not (answer or {}).get('ok'):
            raise UserError((answer or {}).get('msg')
                            or _("The legislation pack could not be applied."))
        return answer

    def _apply_rate_table_save(self):
        payload = self.payload()
        Studio = self._model('pb.formula.studio')
        answer = Studio.with_context(**{STATUTORY_WRITE: True}).save_rate_table(
            payload.get('config_id'), payload.get('table') or {})
        if not (answer or {}).get('ok'):
            raise UserError((answer or {}).get('msg')
                            or _("The rate table could not be saved."))
        return answer

    def _apply_rate_table_delete(self):
        payload = self.payload()
        Studio = self._model('pb.formula.studio')
        answer = Studio.with_context(
            **{STATUTORY_WRITE: True}).delete_rate_table(
                payload.get('table_id'))
        if not (answer or {}).get('ok'):
            raise UserError((answer or {}).get('msg')
                            or _("The rate table could not be deleted."))
        return answer

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(
            company, 'payroll_mgr',
            ('pb_hr_payroll_base.group_payroll_base_manager',
             'pb_hr_payroll_base.group_payroll_base_officer'))
        Seed.fill_role_from_group(
            company, 'director',
            ('pb_hr_payroll_base.group_payroll_super_admin',
             'base.group_system'))
        return Seed.lay(
            company, STATUTORY_PROCESS_KEY, 'Statutory rates and tables',
            route(role_step(_('Payroll manager'), 'payroll_mgr'),
                  role_step(_('Country director'), 'director')),
            binding_note='The route every change to a statutory rate, band or '
                         'legislation pack follows.',
            model_name='pb.statutory.proposal',
            role_keys=('payroll_mgr', 'director'),
            reason='Set up when statutory approvals were switched on')


class HrFormulaLegislationPackApproval(models.Model):
    """Publishing a pack is the act; there was no button and no gate for it.

    A pack in `draft` is a reference nobody is bound by. `published` is the
    statement "these are the numbers the law says", and every scheme in the
    country is measured against it from that moment. It was reachable only as
    a raw `state` write on a list view — so it gains a real button AND the
    raw write is held, because a gate on a button that a form can go round is
    not a gate.
    """
    _inherit = 'hr.formula.legislation.pack'

    def action_publish(self):
        self.ensure_one()
        if self.state == 'published':
            raise UserError(_("This pack is already published."))
        if 'pb.statutory.proposal' not in self.env:
            self.with_context(**{STATUTORY_WRITE: True}).write(
                {'state': 'published'})
            return True
        proposal = self.env['pb.statutory.proposal'].propose(
            'pack_publish',
            _("Publish %(name)s %(version)s",
              name=self.name or '', version=self.version or ''),
            payload={'pack_id': self.id},
            snapshot={'state': self.state},
            facts={'rows_changed': {'value': self.item_count, 'unit': ''},
                   'effective_date': {'value': str(self.effective_date or ''),
                                      'unit': ''},
                   'configs_affected': {'value': 0, 'unit': ''}},
            target=self,
        )
        return proposal.answer()

    def write(self, vals):
        """A pack may not be published by editing its status field."""
        if vals.get('state') == 'published' \
                and not self.env.context.get(STATUTORY_WRITE) \
                and 'pb.statutory.proposal' in self.env:
            for pack in self:
                if pack.state != 'published':
                    raise UserError(_(
                        "A legislation pack is published with the Publish "
                        "button, so that somebody agrees to it first."))
        return super().write(vals)


class ResCompanyStatutorySeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['pb.statutory.proposal']._approval_seed_default(
                    company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('statutory: %s has no route yet',
                                  company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.statutory.proposal']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('statutory: %s has no route yet', company.name)
    return done
