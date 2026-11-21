# -*- coding: utf-8 -*-
"""A change to somebody's own details travels the route the business chose.

The default every company gets is ONE step, the HR lead — the same rung as
the contact-details changes of `pb_me_portal` (process `master`). The kind of
change is a fact a route can condition on ("an ID paper", "a family member
who counts for tax"), so a business that wants photos checked by somebody
else can say so in the builder.
"""
import json
import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    register_chain, role_step, route,
)

_logger = logging.getLogger(__name__)

DETAILS_PROCESS_KEY = 'me_details'

register_chain(
    'pb.me.detail.request', DETAILS_PROCESS_KEY,
    submit_state='hr_review',
    driven=('approved',),
    # No date field (ledger PRB-W1): whoever holds the seat today decides.
)


class PbMeDetailRequestApproval(models.Model):
    _inherit = 'pb.me.detail.request'

    _approval_process_key = DETAILS_PROCESS_KEY

    def _chain_title(self):
        self.ensure_one()
        return _("%(what)s · %(who)s", what=self.pb_label(),
                 who=self.sudo().employee_id.name or '')

    def _chain_kind_key(self):
        self.ensure_one()
        return self.kind or 'any'

    @api.model
    def _chain_kinds(self):
        return [{'key': key, 'label': label} for key, label in
                self._fields['kind']._description_selection(self.env)]

    def _chain_facts(self):
        self.ensure_one()
        return {
            'kind': {'value': self.kind or '', 'unit': ''},
            'counts_for_tax': {'value': bool(self.f_counts_for_tax), 'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'kind': {'type': 'selection', 'label': _('What is changing')},
            'counts_for_tax': {'type': 'bool',
                               'label': _('A family member who counts for tax')},
        }

    def _chain_revision_values(self):
        """What was proposed is the thing being agreed."""
        self.ensure_one()
        rec = self.sudo()
        return {
            'employee': rec.employee_id.id, 'kind': rec.kind,
            'member': rec.member_id.id,
            'family': [rec.f_name or '', rec.f_relationship or '',
                       str(rec.f_birthdate or ''), rec.f_id_number or '',
                       bool(rec.f_counts_for_tax), bool(rec.f_insured)],
            'paper': [rec.paper_kind or '', rec.paper_number or '',
                      str(rec.paper_expiry or '')],
            'marital': rec.marital or '',
            'file': rec.attachment_id.checksum or '',
        }

    def _pb_rows(self):
        """`[(label, now, proposed)]` in the reader's language."""
        self.ensure_one()
        rec = self.sudo()
        try:
            before = json.loads(rec.before_json or '{}')
        except (TypeError, ValueError):
            before = {}
        yes, no = _('Yes'), _('No')

        def sel(field, value):
            return dict(rec._fields[field]._description_selection(self.env)).get(
                value, value or '')

        rows = []
        if rec.kind in ('family_add', 'family_change', 'family_remove'):
            gone = rec.kind == 'family_remove'
            spec = [
                (_('Name'), 'f_name', None),
                (_('Relationship'), 'f_relationship', 'sel'),
                (_('Date of birth'), 'f_birthdate', None),
                (_('ID or birth certificate number'), 'f_id_number', None),
                (_('Counts for tax'), 'f_counts_for_tax', 'bool'),
                (_('Covered by insurance'), 'f_insured', 'bool'),
            ]
            for label, field, how in spec:
                old = before.get(field) if rec.kind != 'family_add' else None
                new = None if gone else rec[field]
                if how == 'sel':
                    old, new = sel(field, old), sel(field, new)
                elif how == 'bool':
                    old = '' if old is None else (yes if old else no)
                    new = '' if new is None else (yes if new else no)
                rows.append((label, str(old or ''), str(new or '')))
        elif rec.kind == 'id_paper':
            rows.append((_('Paper'), '', rec._pb_paper_label()))
            rows.append((_('Number'), str(before.get('paper_number') or ''),
                         rec.paper_number or ''))
            if rec.paper_expiry:
                rows.append((_('Valid until'), str(before.get('paper_expiry') or ''),
                             str(rec.paper_expiry)))
        elif rec.kind == 'marital':
            rows.append((_('Marital status'), sel('marital', before.get('marital')),
                         sel('marital', rec.marital)))
        elif rec.kind == 'photo':
            rows.append((_('Photo'), _('The photo on file'), _('The new photo')))
        return rows

    def _approval_detail(self, request):
        self.ensure_one()
        rec = self.sudo()
        rows = [{'head': label, 'sub': '',
                 'cells': [old or _('Empty'), new or _('Empty')],
                 'tone': 'on' if (old or '') != (new or '') else 'off'}
                for label, old, new in rec._pb_rows()]
        chips = []
        if rec.attachment_id:
            chips.append({'label': _('File'), 'value': rec.attachment_id.name or ''})
        if rec.kind in ('family_add', 'family_change') and rec.f_counts_for_tax \
                and (rec.company_id.country_id.code or '') == 'VN':
            chips.append({'label': _('Tax'),
                          'value': _('Waits for the pay team to confirm')})
        return {'title': rec.pb_label(),
                'columns': [_('Now'), _('Proposed')],
                'rows': rows, 'chips': chips,
                'note': (rec.note or '')[:240]}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'hr_lead',
                                  'om_hr_payroll.group_hr_payroll_user')
        return Seed.lay(
            company, DETAILS_PROCESS_KEY, 'My details changes',
            route(role_step(_('HR lead'), 'hr_lead')),
            binding_note='The route every change somebody proposes to their '
                         'family, ID papers, photo or marital status follows.',
            model_name='pb.me.detail.request',
            role_keys=('hr_lead',),
            reason='Set up when My details approvals were switched on')


class ResCompanyDetailsSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                with self.env.cr.savepoint():
                    self.env['pb.me.detail.request'].sudo()._approval_seed_default(
                        company)
            except Exception:       # noqa: BLE001 — a company must still be made
                _logger.exception('pb_me_details: %s has no details route',
                                  company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            with env.cr.savepoint():
                if env['pb.me.detail.request']._approval_seed_default(company):
                    done += 1
        except Exception:       # noqa: BLE001 — an install must not die here
            _logger.exception('pb_me_details: %s has no details route',
                              company.name)
    return done
