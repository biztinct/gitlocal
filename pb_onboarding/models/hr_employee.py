# -*- coding: utf-8 -*-
"""The two people every new joiner needs a name for, and how complete they are.

THE FIELD NAMES ARE A CONTRACT, NOT A PREFERENCE. `pb_lifecycle` shipped with
`_ROLE_EMPLOYEE_FIELDS = {'hrbp': ('hrbp_user_id', 'hrbp_id'),
'buddy': ('buddy_user_id', 'buddy_id')}` and PROBES `hr.employee._fields` for
those spellings when a journey opens, so that every checklist that already says
"HRBP" starts resolving to a person the day this module exists — without a line
changing in P0. Renaming either field to a `pb_`-prefixed one would leave that
probe answering nothing, the steps would silently fall back to HR, and the only
evidence would be a line in the case log. So: `hrbp_user_id` (a user) and
`buddy_id` (an employee), exactly as spelled there.

P5 (probation) reads the same two fields.
"""

import logging
from datetime import date

from odoo import api, fields, models, _

from .onboarding_common import initials

_logger = logging.getLogger(__name__)

#: What "a complete record" means, in the words of the person's own profile.
#: Each entry is (field name, screen label). Fields that are missing on a
#: build are skipped rather than counted against the person — a percentage
#: that punishes somebody for a column their database does not have is a
#: number nobody can act on.
PROFILE_FIELDS = [
    ('image_1920', 'Photo'),
    ('birthday', 'Date of birth'),
    ('sex', 'Gender'),
    ('private_street', 'Home address'),
    ('private_city', 'Town or city'),
    ('private_phone', 'Personal phone'),
    ('emergency_contact', 'Emergency contact'),
    ('emergency_phone', 'Emergency phone'),
    ('identification_id', 'ID number'),
    ('account_number', 'Bank account'),
]


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # ------------------------------------------------------- the two people
    hrbp_user_id = fields.Many2one(
        'res.users', string='HR business partner', tracking=True, index=True,
        ondelete='set null',
        help='The person in HR who looks after this employee. Filled in '
             'automatically from the HR partner rules when someone joins.')
    buddy_id = fields.Many2one(
        'hr.employee', string='Buddy', tracking=True, index=True,
        ondelete='set null',
        help='A colleague who shows a new joiner the ropes for their first '
             'few months.')
    buddy_temp_id = fields.Many2one(
        'hr.employee', string='Stand-in buddy', ondelete='set null',
        help='Someone covering the buddy while they are away.')
    buddy_temp_from = fields.Date(string='Stand-in from')
    buddy_temp_to = fields.Date(string='Stand-in until')
    buddy_for_ids = fields.One2many(
        'hr.employee', 'buddy_id', string='Buddy to')
    buddy_for_count = fields.Integer(
        compute='_compute_buddy_for_count', string='People they buddy')

    # ------------------------------------------------------- their journey
    onboarding_case_id = fields.Many2one(
        'pb.journey.case', compute='_compute_onboarding_case',
        string='Joining checklist')

    profile_complete_pct = fields.Integer(
        compute='_compute_profile_complete', string='Record complete (%)')
    profile_missing = fields.Char(
        compute='_compute_profile_complete', string='Still missing')

    # ------------------------------------------------------------- computes
    @api.depends('buddy_for_ids')
    def _compute_buddy_for_count(self):
        for rec in self:
            rec.buddy_for_count = len(rec.buddy_for_ids)

    def _compute_onboarding_case(self):
        """The joining checklist that is running, or the last one there was.

        Its own try/except per record: an employee whose journey table cannot
        be read must not blank the field for the other forty-nine (the
        every-probe-its-own-guard rule).
        """
        Case = self.env['pb.journey.case']
        for rec in self:
            found = Case.browse()
            try:
                found = Case.search(
                    [('employee_id', '=', rec.id),
                     ('case_type', '=', 'onboarding')],
                    order='state, anchor_date desc, id desc', limit=1)
            except Exception:           # noqa: BLE001
                _logger.debug('pb_onboarding: no journey readable for %s',
                              rec.id)
            rec.onboarding_case_id = found.id or False

    @api.depends('image_1920', 'birthday', 'sex', 'private_street',
                 'private_city', 'private_phone', 'emergency_contact',
                 'emergency_phone', 'identification_id', 'account_number')
    def _compute_profile_complete(self):
        for rec in self:
            filled, missing = 0, []
            present = 0
            for fname, label in PROFILE_FIELDS:
                if fname not in rec._fields:
                    continue
                present += 1
                try:
                    value = rec[fname]
                except Exception:       # noqa: BLE001 — a field-level ACL
                    # An HR-scoped field the reader may not see is neither
                    # filled nor missing FOR THEM; counting it either way
                    # would make the same person 60% to one colleague and
                    # 90% to another.
                    present -= 1
                    continue
                if value:
                    filled += 1
                else:
                    missing.append(label)
            rec.profile_complete_pct = int(
                round(filled * 100.0 / present)) if present else 100
            rec.profile_missing = ', '.join(missing)

    # ----------------------------------------------------------- the helpers
    def _pb_join_date(self):
        """The day this person started, best available.

        The onboarding journey's own key date wins when there is one — the
        person who opened it knew something the record did not (a re-hire, a
        transfer, a start not contracted yet). That is P0's ruling and this
        follows it rather than restating a second answer.
        """
        self.ensure_one()
        case = self.onboarding_case_id
        if case and case.anchor_date:
            return case.anchor_date
        d = self.first_contract_date
        if not d:
            try:
                starts = [c.date_start for c in self.contract_ids
                          if c.date_start]
                d = min(starts) if starts else False
            except Exception:           # noqa: BLE001
                d = False
        if not d and self.create_date:
            d = self.create_date.date()
        return d or False

    def _pb_tenure_months(self):
        self.ensure_one()
        start = self._pb_join_date()
        if not start:
            return 0
        today = date.today()
        return ((today.year - start.year) * 12 + today.month - start.month
                - (1 if today.day < start.day else 0))

    def _pb_buddy_now(self, on_day=None):
        """Who is actually looking after this joiner today.

        A stand-in inside its window OUTRANKS the named buddy — otherwise the
        connect that is due on Thursday goes to somebody on annual leave and
        the whole point of a temporary handover is lost.
        """
        self.ensure_one()
        day = on_day or date.today()
        temp = self.buddy_temp_id
        if temp and (not self.buddy_temp_from or self.buddy_temp_from <= day) \
                and (not self.buddy_temp_to or day <= self.buddy_temp_to):
            return temp
        return self.buddy_id

    def _pb_card(self):
        """One person, as a card the portal and the cockpit can both show.

        Deliberately a fixed, small field list: a name, a job, a photo URL and
        the two ways to reach them. Never a wage, never a private address —
        this dictionary is handed to a portal page.
        """
        self.ensure_one()
        return {
            'id': self.id,
            'name': self.name or '',
            'initials': initials(self.name),
            'job': self.job_title or (self.job_id.name if self.job_id else '')
            or '',
            'dept': self.department_id.name if self.department_id else '',
            'email': self.work_email or '',
            'phone': self.work_phone or '',
            'avatar': '/web/image/hr.employee/%s/avatar_128' % self.id,
        }

    # ------------------------------------------------------------- the button
    def action_backfill_hrbp(self):
        """Give everybody who has no HR partner the one the rules say.

        Existing staff joined before the rules existed. Without this the
        30-60-90 of every person already here would be owned by nobody and
        the board would show a column of dashes with no way to fill it in.
        """
        touched = self.env['pb.hrbp.rule'].backfill(self)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('HR partners filled in'),
                'message': _('%s person(s) now have an HR partner.', touched),
                'sticky': False,
            },
        }
