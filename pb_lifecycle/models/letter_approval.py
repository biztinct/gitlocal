# -*- coding: utf-8 -*-
"""Generating a letter is a draft. Sending it is the act.

WHAT WAS TRUE BEFORE. Press Send and an offer, a confirmation of salary or a
warning left the building in the company's name, with a PDF attached, to
somebody's personal email address. Nobody else had to agree.

WHAT IS TRUE NOW. Generating is untouched — a draft binds nobody and the
person writing it needs to be able to read it back. SENDING travels a route
(`letters`, HR lead by default) and the email goes out when it says yes, sent
by the approver.

WHY THE LETTER ITSELF IS THE RECORD. Unlike most of Phase 7 there is already
an object here that holds everything the approval is about — who it is to,
which template, the rendered text and the PDF. A proposal would have been a
second copy of a letter, and the second copy is always the one that goes
stale.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    role_step, route,
)

from .letter import LETTER_WRITE

_logger = logging.getLogger(__name__)

LETTERS_PROCESS_KEY = 'letters'

#: The letter types that quote what somebody is paid. A route almost always
#: wants to answer those differently from a simple confirmation of employment.
PAY_LETTER_TYPES = ('offer', 'salary', 'increment', 'promotion', 'bonus')


class PbHrLetterApproval(models.Model):
    _name = 'pb.hr.letter'
    _inherit = ['pb.hr.letter', 'biz.approval.adapter.mixin']

    _approval_process_key = LETTERS_PROCESS_KEY

    #: A seat is also a read (ledger AM60).
    seat_user_ids = fields.Many2many(
        'res.users', 'pb_hr_letter_seat_rel', 'letter_id', 'user_id',
        string='Asked to decide', copy=False)

    # ==================================================================
    # The adapter
    # ==================================================================
    def _approval_validate(self):
        self.ensure_one()
        if self.state == 'sent':
            raise UserError(_("This letter has already been sent."))
        return True

    def _has_pay_figures(self):
        self.ensure_one()
        return (self.letter_type or '') in PAY_LETTER_TYPES

    def _approval_context(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        employee = self.employee_id.sudo()
        return {
            'company_id': company.id,
            'title': _("%(what)s for %(who)s",
                       what=dict(self._fields['letter_type'].selection or []
                                 ).get(self.letter_type) or _('Letter'),
                       who=employee.name or ''),
            'scope_keys': [''],
            'scope_label': company.name,
            'kind_key': self.letter_type or 'any',
            'facts': {
                'letter_type': {'value': self.letter_type or '', 'unit': ''},
                'has_pay_figures': {'value': self._has_pay_figures(),
                                    'unit': ''},
            },
            'amount': 0.0,
            'currency_id': company.currency_id.id,
            'maker_uids': [self.generated_by.id] if self.generated_by
                          else [self.env.uid],
            'submitter_uid': self.env.uid,
            'subject_uids': employee.user_id.ids,
            # What everybody agrees to is the TEXT. A letter re-rendered after
            # it was sent in is not the letter they read.
            'source_revision': self._approval_revision_of({
                'to': employee.work_email or employee.private_email or '',
                'subject': self.subject or '',
                'body': self.rendered_html or '',
            }),
            'evidence': [{'key': 'pdf_ready', 'name': _('The PDF is ready'),
                          'ok': bool(self.attachment_id),
                          'note': self.attachment_id.name or ''}],
        }

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': {
                'letter_type': {'type': 'selection',
                                'label': _('Kind of letter')},
                'has_pay_figures': {'type': 'bool',
                                    'label': _('Quotes what they are paid')},
            },
            'kinds': [{'key': key, 'label': label}
                      for key, label in (
                          self._fields['letter_type'].selection or [])],
            'evidence': [{'key': 'pdf_ready',
                          'label': _('The PDF is ready')}],
            'scope_levels': [_('Whole company')],
            'manager_mode': True,
        }

    @api.model
    def _approval_coverage_scopes(self, company):
        return [{'scope_key': '', 'scope_keys': [''], 'label': company.name,
                 'headcount': 0, 'kind_key': 'any', 'facts': {}}]

    def _approval_card_count(self, request):
        self.ensure_one()
        return self.employee_id.name or ''

    def _approval_detail(self, request):
        self.ensure_one()
        employee = self.employee_id.sudo()
        chips = [
            {'label': _('To'), 'value': employee.work_email
             or employee.private_email or _('No email on record')},
            {'label': _('Subject'), 'value': self.subject or self.name or ''},
        ]
        if self._has_pay_figures():
            chips.append({'label': _('Quotes pay'), 'value': _('Yes')})
        return {'title': _('The letter'), 'columns': [], 'rows': [],
                'chips': chips, 'note': ''}

    def _approval_apply(self, request):
        """Send it — by the approver, as themselves."""
        self.ensure_one()
        if self.state == 'sent':
            return True
        self.with_context(**{LETTER_WRITE: True}).action_send()
        return True

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'hr_lead', ('hr.group_hr_manager',))
        return Seed.lay(
            company, LETTERS_PROCESS_KEY, 'Letters to people',
            route(role_step(_('HR lead'), 'hr_lead')),
            binding_note='The route a letter follows before it leaves the '
                         'building.',
            model_name='pb.hr.letter',
            role_keys=('hr_lead',),
            reason='Set up when letter approvals were switched on')


class BizApprovalRequestSeatLetter(models.Model):
    """A seat on a letter is also a permission to READ it (AM60)."""
    _inherit = 'biz.approval.request.seat'

    @api.model_create_multi
    def create(self, vals_list):
        seats = super().create(vals_list)
        for seat in seats:
            request = seat.step_id.request_id
            if request.res_model != 'pb.hr.letter' or not request.res_id:
                continue
            record = self.env['pb.hr.letter'].sudo().browse(
                request.res_id).exists()
            people = {seat.acting_user_id.id, seat.user_id.id}
            people.discard(False)
            if record and people:
                record.write({
                    'seat_user_ids': [(4, uid) for uid in sorted(people)]})
        return seats


class ResCompanyLetterSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['pb.hr.letter']._approval_seed_default(company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('letters: %s has no route yet', company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.hr.letter']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('letters: %s has no route yet', company.name)
    return done
