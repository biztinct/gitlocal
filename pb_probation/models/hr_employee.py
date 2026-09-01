# -*- coding: utf-8 -*-
"""Where somebody stands in their trial period.

ONE FIELD, AND IT IS THE ANSWER. Before this module the question "is this
person confirmed" was answered by reading a DATE off a contract and comparing
it to today, in three places, each of which got a slightly different answer for
somebody whose trial had been extended. `pb_probation_state` is the single
answer, it is written only by the review machine (or by HR, deliberately, on
the person's own record), and P6 and P10 both read it.

THE FIELD NAME IS A CONTRACT. `pb_probation_state`, with the values in
`probation_common.PROBATION_STATES`. It is prefixed because it is ours — unlike
`hrbp_user_id` and `buddy_id`, which P3 had to spell exactly as P0 probes for
them — and nothing outside this codebase reads it.

WHY THE TRIAL DATE STILL EXISTS BESIDE IT. The state says WHERE somebody is;
`trial_date_end` says WHEN it runs out, and the daily job needs both. The date
lives on the employment record (`hr.version` on this build, reached through the
employee — R14: never through raw SQL) and this module is the only thing
allowed to write it in place, which is the carve-out ruling D1 makes for
exactly this case.
"""

import logging
from datetime import date

from odoo import api, fields, models, _

from .probation_common import (
    NON_STAFF_TYPES, PROBATION_LIVE, PROBATION_STATE_LABEL, PROBATION_STATES,
)

_logger = logging.getLogger(__name__)

#: How many employees one backfill pass writes through the ORM before it stops
#: and leaves the rest to the next run. Only the EXCEPTIONS go through the ORM
#: (see `hooks.py`); the ordinary case is one statement.
BACKFILL_ORM_CAP = 2000


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    pb_probation_state = fields.Selection(
        PROBATION_STATES, string='Trial period', index=True, tracking=True,
        groups='hr.group_hr_user',
        help='Where this person stands in their trial period. Payobook keeps '
             'this up to date from the probation review; change it by hand '
             'only when you know something the review does not.')
    pb_probation_review_ids = fields.One2many(
        'pb.probation.review', 'employee_id', string='Probation reviews')
    pb_probation_review_id = fields.Many2one(
        'pb.probation.review', compute='_compute_pb_probation_review',
        string='Review running')

    # ------------------------------------------------------------- computes
    def _compute_pb_probation_review(self):
        """The review that is running, or the last one there was.

        Its own try/except per record (the every-probe-its-own-guard rule): an
        employee whose reviews cannot be read must not blank the field for the
        other forty-nine.
        """
        Review = self.env['pb.probation.review']
        for rec in self:
            found = Review.browse()
            try:
                found = Review.search(
                    [('employee_id', '=', rec.id)],
                    order='state, trial_end desc, id desc', limit=1)
            except Exception:           # noqa: BLE001
                _logger.debug('pb_probation: no review readable for %s', rec.id)
            rec.pb_probation_review_id = found.id or False

    # ------------------------------------------------------------- creation
    @api.model_create_multi
    def create(self, vals_list):
        """A new record arrives already knowing where it stands.

        Not a `default=`, because the answer depends on two other values on the
        same record (the employment type and the trial end date) and a default
        cannot see either. Anything explicitly passed in is left exactly as it
        came — a connected system that says "passed" is not second-guessed.
        """
        records = super().create(vals_list)
        for rec, vals in zip(records, vals_list):
            if vals.get('pb_probation_state'):
                continue
            try:
                rec.pb_probation_state = rec._pb_probation_default()
            except Exception:           # noqa: BLE001 — never lose a joiner
                _logger.exception(
                    'pb_probation: could not work out the trial state for %s',
                    rec.id)
        return records

    def _pb_probation_default(self):
        """Where a record stands when nobody has said.

        Not applicable for anybody who is not permanent staff; in probation
        while there is a trial end date still ahead; passed otherwise —
        including for everybody who has been here for years, which is the
        honest reading of a record with no trial date on it at all.
        """
        self.ensure_one()
        kind = ''
        try:
            kind = self.sudo().employee_type or ''
        except Exception:               # noqa: BLE001
            kind = ''
        if kind and kind in NON_STAFF_TYPES:
            return 'na'
        trial = False
        try:
            trial = self.sudo().trial_date_end
        except Exception:               # noqa: BLE001 — an HR-gated field
            trial = False
        if trial and trial >= date.today():
            return 'in_probation'
        return 'passed'

    # -------------------------------------------------------------- helpers
    def pb_probation_label(self):
        self.ensure_one()
        return PROBATION_STATE_LABEL.get(self.pb_probation_state or '', '')

    def _pb_in_probation(self):
        """Is this person still being looked at? The one place that decides."""
        self.ensure_one()
        return (self.pb_probation_state or '') in PROBATION_LIVE

    def _pb_set_probation_state(self, state, reason=None):
        """Write the state and say why in the chatter. Never raises.

        Sudo on the WRITE and not on the decision: the field is HR-gated, and
        the review machine has to be able to write it on behalf of a manager
        who is running a verdict from the lens.
        """
        self.ensure_one()
        if state not in PROBATION_STATE_LABEL:
            _logger.warning('pb_probation: %s is not a trial state', state)
            return False
        if self.pb_probation_state == state:
            return True
        try:
            self.sudo().write({'pb_probation_state': state})
            if reason:
                self.sudo().message_post(body=reason)
            return True
        except Exception:               # noqa: BLE001
            _logger.exception('pb_probation: could not set the trial state '
                              'on employee %s', self.id)
            return False

    def pb_set_trial_end(self, new_end, note=None):
        """Move the end of the trial period, IN PLACE.

        The one contract write this whole phase makes, and the carve-out ruling
        D1 exists for: extensions and conversions create a NEW linked contract
        everywhere else in RIZE, but a trial end date is a correction to the
        contract that is already running rather than a new agreement, and
        minting a second contract for it would double every headcount report.

        Through the ORM, always. On this build the employment fields live on a
        version record and are non-stored relateds, so raw SQL both fails on
        some columns and lies about others (R14).
        """
        self.ensure_one()
        if not new_end:
            return False
        try:
            had = self.sudo().trial_date_end
            self.sudo().write({'trial_date_end': new_end})
            self.sudo().message_post(body=note or _(
                "The trial period now ends on %(new)s%(was)s.",
                new=new_end, was=(_(' (it was %s)', had) if had else '')))
            return True
        except Exception:               # noqa: BLE001
            _logger.exception('pb_probation: could not move the trial end for '
                              'employee %s', self.id)
            return False

    # --------------------------------------------------------- the backfill
    @api.model
    def _pb_backfill_probation_state(self, cap=BACKFILL_ORM_CAP):
        """Give everybody already on this database a trial state.

        THE ORDER MATTERS AND IT IS THE WHOLE DESIGN.

        1. The EXCEPTIONS first, through the ORM, while they can still be
           recognised by having no state at all. There are two of them — people
           who are not permanent staff, and people whose trial end date is
           still ahead — and both are small sets on any real database.
        2. Then ONE STATEMENT for everybody else. `pb_probation_state` is this
           module's own column on `hr_employee`: a plain stored selection with
           no compute, no related and no inverse behind it, so a direct UPDATE
           is exactly what the ORM would have written and is the difference
           between a second and twenty minutes on a database of five thousand
           people. This is NOT a violation of R14 — that rule is about
           `hr.version`'s fields, which are not columns on this table at all,
           and neither the read nor the write below touches one.
        3. NEVER a downgrade. Every step is restricted to rows that have no
           state yet, so a second run writes nothing and a state somebody set
           by hand survives every upgrade.

        Returns the counts, and logs them, because a backfill that reports
        nothing is a backfill nobody can check.
        """
        counts = {'na': 0, 'in_probation': 0, 'passed': 0, 'skipped': 0}
        Emp = self.sudo().with_context(active_test=False)

        # ---- 1a. not permanent staff -> not applicable ----
        try:
            rows = Emp.search([('pb_probation_state', '=', False),
                               ('employee_type', 'in',
                                list(NON_STAFF_TYPES))], limit=cap)
            if rows:
                rows.write({'pb_probation_state': 'na'})
                counts['na'] = len(rows)
        except Exception:               # noqa: BLE001
            _logger.exception('pb_probation: backfill — the non-staff pass')

        # ---- 1b. a trial end date still ahead -> in probation ----
        try:
            rows = Emp.search([('pb_probation_state', '=', False),
                               ('trial_date_end', '!=', False),
                               ('trial_date_end', '>=', fields.Date.today())],
                              limit=cap)
            if rows:
                rows.write({'pb_probation_state': 'in_probation'})
                counts['in_probation'] = len(rows)
        except Exception:               # noqa: BLE001
            _logger.exception('pb_probation: backfill — the in-probation pass')

        # ---- 2. everybody else, in one statement ----
        try:
            self.env.flush_all()
            self.env.cr.execute(
                "UPDATE hr_employee SET pb_probation_state = 'passed' "
                "WHERE pb_probation_state IS NULL")
            counts['passed'] = self.env.cr.rowcount
            self.env.invalidate_all()
        except Exception:               # noqa: BLE001
            _logger.exception('pb_probation: backfill — the settled pass')

        _logger.info(
            'pb_probation backfill: %s not applicable, %s in probation, '
            '%s passed', counts['na'], counts['in_probation'],
            counts['passed'])
        return counts
