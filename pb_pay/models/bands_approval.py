# -*- coding: utf-8 -*-
"""A pay band is what the company says a job is worth. Moving one is a decision.

WHAT WAS TRUE BEFORE. Dragging an edge on the band picture and letting go
rewrote the band — and every position, every fairness figure and every
guidance suggestion computed from it — the moment the mouse came up. So did
saving a band, linking a job to one, accepting the suggested bands, importing
a spreadsheet of them, and typing a percentage into the guidance grid. Each of
those is a statement about what a whole family of people should be paid.

WHAT IS TRUE NOW. Each writes a proposal (`pb.bands.proposal`) and the change
happens when the route says yes. The default route is the head of pay, because
that is whose job it already was.

THE DRY RUN IS UNTOUCHED. `move_edge(dry_run=True)` computes what a move would
cost and writes nothing; it always did, and it still answers instantly while
somebody drags. Only the let-go is held — and the handover's note is right
that the gate belonged there: the dry-run branch had no `_require_write` at
all, so the write branch was the first place anybody was asked.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    role_step, route,
)

_logger = logging.getLogger(__name__)

BANDS_PROCESS_KEY = 'bands'

#: What changing a band has always needed.
BANDS_GROUP = 'pb_pay.group_pay_manager'

#: "This write IS the approved change."
BANDS_WRITE = 'pb_bands_approved_write'


class PbBandsProposal(models.Model):
    _name = 'pb.bands.proposal'
    _inherit = ['biz.approval.proposal.mixin']
    _description = 'Proposed pay band change'

    _approval_process_key = BANDS_PROCESS_KEY
    _proposal_prefix = 'BND'
    _proposal_gate_groups = (BANDS_GROUP, 'pb_group.group_group_admin')
    _proposal_kind_labels = {
        'move_edge': 'Move a band edge',
        'save_band': 'Save a band',
        'set_range': 'Put a band back',
        'link_job': 'Put a job in a band',
        'unlink_job': 'Take a job out of a band',
        'accept_suggestion': 'Accept the suggested bands',
        'import': 'Import bands from a spreadsheet',
        'guidance_cell': 'Change a guidance square',
        'guidance_default': 'Start a guidance grid',
        'limit': 'Change a pay review limit',
    }
    _proposal_fact_specs = {
        'bands_changed': {'type': 'int', 'label': 'Bands changed'},
        'max_move_pct': {'type': 'decimal', 'label': 'Biggest move (%)'},
        'employees_affected': {'type': 'int', 'label': 'People in those bands'},
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
        if self.kind in ('move_edge', 'set_range', 'save_band') \
                and 'min_amount' in target._fields:
            return {'min': target.min_amount, 'mid': target.mid_amount,
                    'max': target.max_amount}
        if self.kind == 'guidance_cell' and 'pct' in target._fields:
            return {'pct': target.pct}
        if self.kind == 'limit' and 'amount' in target._fields:
            return {'amount': target.amount}
        return {}

    # ------------------------------------------------------------ the rows
    def _proposal_rows(self):
        self.ensure_one()
        payload = self.payload() or {}
        snapshot = self.snapshot() or {}
        target = self._target()
        rows = []
        if target is not None:
            rows.append((_('Band') if self.kind != 'guidance_cell'
                         else _('Square'), '', target.display_name or ''))
        if self.kind == 'move_edge':
            side = _('Lowest') if payload.get('side') == 'min' \
                else _('Highest')
            rows.append((side, snapshot.get(payload.get('side') or 'min', ''),
                         payload.get('amount')))
        elif self.kind in ('set_range', 'save_band'):
            values = payload.get('values') or payload
            for key, label in (('min', _('Lowest')), ('mid', _('Middle')),
                               ('max', _('Highest'))):
                if key in values:
                    rows.append((label, snapshot.get(key, ''), values[key]))
            for key, label in (('min_amount', _('Lowest')),
                               ('mid_amount', _('Middle')),
                               ('max_amount', _('Highest'))):
                if key in values:
                    rows.append((label, snapshot.get(key[:3], ''),
                                 values[key]))
        elif self.kind == 'link_job':
            rows.append((_('Job'), '', self._row_label(
                'hr.job', payload.get('job_id'))))
        elif self.kind == 'unlink_job':
            rows.append((_('What happens'), '',
                         _('That job stops being paid from this band')))
        elif self.kind == 'accept_suggestion':
            rows.append((_('Bands suggested'), '',
                         str(len(payload.get('proposals') or []))))
        elif self.kind == 'import':
            rows.append((_('Bands in the file'), '',
                         str(len(payload.get('rows') or []))))
        elif self.kind == 'guidance_cell':
            rows.append((_('Guidance'), snapshot.get('pct', ''),
                         payload.get('pct')))
        elif self.kind == 'guidance_default':
            rows.append((_('What happens'), '',
                         _('A guidance grid is created and used by every '
                           'review from now on')))
        elif self.kind == 'limit':
            for key, value in sorted((payload.get('values') or {}).items()):
                rows.append((str(key), snapshot.get(key, ''), value))
        return rows

    # --------------------------------------------------------- the applies
    def _bands(self):
        return self.env['pb.pay.bands'].with_context(**{BANDS_WRITE: True})

    def _reviews(self):
        return self.env['pb.pay.reviews'].with_context(**{BANDS_WRITE: True})

    def _apply_move_edge(self):
        p = self.payload()
        return self._bands().move_edge(p.get('band_id'), p.get('side'),
                                       p.get('amount'), dry_run=False)

    def _apply_save_band(self):
        return self._bands().save_band((self.payload() or {}).get('values'))

    def _apply_set_range(self):
        p = self.payload()
        return self._bands().set_band_range(
            p.get('band_id'), p.get('min'), p.get('mid'), p.get('max'))

    def _apply_link_job(self):
        p = self.payload()
        return self._bands().link_job(p.get('band_id'), p.get('job_id'))

    def _apply_unlink_job(self):
        return self._bands().unlink_job((self.payload() or {}).get('link_id'))

    def _apply_accept_suggestion(self):
        return self._bands().accept_suggestion(
            (self.payload() or {}).get('proposals') or [])

    def _apply_import(self):
        return self._bands()._write_import(
            (self.payload() or {}).get('rows') or [])

    def _apply_guidance_cell(self):
        p = self.payload()
        self._reviews().save_guidance_cell(p.get('cell_id'), p.get('pct'))
        return {'cell_id': p.get('cell_id')}

    def _apply_guidance_default(self):
        return self._reviews().make_default_guidance()

    def _apply_limit(self):
        target = self._target()
        if not target:
            raise UserError(_("That limit no longer exists."))
        target.with_context(**{BANDS_WRITE: True}).write(
            (self.payload() or {}).get('values') or {})
        return {'limit_id': target.id}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'pay_head',
                                  ('pb_pay.group_pay_manager',))
        return Seed.lay(
            company, BANDS_PROCESS_KEY, 'Pay bands and guidance',
            route(role_step(_('Head of pay'), 'pay_head')),
            binding_note='The route a change to a pay band, a job link or the '
                         'guidance grid follows.',
            model_name='pb.bands.proposal',
            role_keys=('pay_head',),
            reason='Set up when pay band approvals were switched on')


class ResCompanyBandsSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['pb.bands.proposal']._approval_seed_default(company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('pay bands: %s has no route yet',
                                  company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.bands.proposal']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pay bands: %s has no route yet', company.name)
    return done
