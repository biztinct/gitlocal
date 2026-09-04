# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""``pb.shift.pulse`` — how the shift went, from someone we deliberately cannot name.

THE PRIVACY CONTRACT (read this before adding a field)
======================================================
This table has NO link to an employee, and it never will. Not a many2one, not
an id in a comment, and not a `create_uid` — the row is written under
`with_user(SUPERUSER_ID)` precisely so the ORM's own audit stamp is the system
rather than the person who submitted it. `sudo()` is NOT enough and was the
first version of this file: it raises the `su` flag but leaves `env.uid` alone,
so every row carried its rater's id until the live test run said so.
The columns are: company, department, date, rating, optional comment, and a
hash. That is the whole record.

WHAT THE HASH IS, AND WHAT IT IS NOT
-------------------------------------
A rating has to be one per person per day, or a bad afternoon becomes a
campaign. Proving "this person has not submitted today" without storing who they
are needs a value that is derived from them but does not contain them:

    uniq_hash = sha256(salt || company || employee_id || date)

with the salt in a system parameter generated once at first use. The hash is
covered by a UNIQUE index, so the SECOND submission fails at the database rather
than at a check somebody can race.

Its limits, stated rather than implied:

  * it is not anonymity against a SYSTEM ADMINISTRATOR. Anyone who can read
    `ir.config_parameter` can read the salt, and with the salt plus the employee
    table a row can be attributed. That is not a hole this design can close —
    an administrator can read the database — and it is why the salt lives in a
    system-only parameter rather than in the module's source;
  * against everyone else, including HR, including the department manager, and
    including the aggregation surface itself, the row carries nothing. The
    reader sees a department, a day and a number;
  * `create_date` remains. It says a rating was submitted at 17:42, which in a
    department of six people on a shared shift is not nothing — which is why the
    aggregate has a FLOOR (below five ratings the server returns nothing at all,
    not a smaller number), and why the department, not the person, is the
    smallest scope anything is ever reported at.

WHY THE RATING IS 1..5 AND THE COMMENT IS OPTIONAL
---------------------------------------------------
Because the entry points are a phone at the end of a shift and a portal page
somebody opened for another reason. A required comment turns a two-second
gesture into a task, and a task at the end of a shift is a blank dataset.
"""

import hashlib
import logging
import secrets
from datetime import timedelta

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_SALT_PARAM = 'pb_ess_workforce.pulse_salt'

# The anonymity floor. Below this many ratings the aggregate is not "small", it
# is IDENTIFYING — in a team of six, two ratings and a roster is a name. The
# server refuses below it; the client is never in a position to decide.
PULSE_FLOOR = 5

# The aggregation window. A week, so a single bad Tuesday neither disappears nor
# defines the department.
PULSE_WINDOW_DAYS = 7

_MAX_COMMENT = 500


class PbShiftPulse(models.Model):
    _name = 'pb.shift.pulse'
    _description = 'Anonymous Shift Pulse'
    _order = 'date desc, id desc'
    # No mail.thread: a chatter has authors, and this record must not have one.

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 index=True, ondelete='cascade')
    department_id = fields.Many2one('hr.department', string='Department',
                                    index=True, ondelete='set null')
    date = fields.Date(string='Day', required=True, index=True)
    rating = fields.Integer(string='Rating', required=True,
                            help="1 (bad) to 5 (great).")
    comment = fields.Text(string='Comment')
    uniq_hash = fields.Char(
        string='Uniqueness Hash', required=True, index=True,
        groups='base.group_system',
        help="A salted one-way digest that makes one rating per person per day "
             "provable without recording who they are. See the model docstring "
             "for exactly what this does and does not protect.")

    # W33.1: `_sql_constraints = [...]` is silently ignored on Odoo 19 and the
    # index simply does not exist. The double-submit guard has to be a real
    # database constraint — a Python check loses the race by construction.
    _uniq_per_person_per_day = models.Constraint(
        'unique(uniq_hash)',
        'A pulse rating has already been recorded for that day.')

    @api.constrains('rating')
    def _check_rating(self):
        for rec in self:
            if not 1 <= (rec.rating or 0) <= 5:
                raise UserError(_("A rating runs from 1 to 5."))

    # ============================================================ the salt
    @api.model
    def _pulse_salt(self):
        """Generate once, then reuse. Stored in a system-only parameter rather
        than in the source, so the digest cannot be reproduced from a copy of
        this repository."""
        Param = self.env['ir.config_parameter'].sudo()
        salt = Param.get_param(_SALT_PARAM)
        if not salt:
            salt = secrets.token_hex(32)
            Param.set_param(_SALT_PARAM, salt)
        return salt

    @api.model
    def _pulse_hash(self, company_id, employee_id, day):
        raw = '%s|%s|%s|%s' % (self._pulse_salt(), company_id, employee_id,
                               fields.Date.to_string(day))
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    # ========================================================== submission
    @api.model
    def submit_pulse(self, rating, comment=False, **kw):
        """Record one rating for the CALLER's day.

        The signature is the security boundary: there is no employee, no
        department, no company and no date on it. Everything the row needs is
        derived server-side from the session, and `**kw` exists so a caller that
        sends an identity anyway is silently ignored rather than obeyed — which
        is what the adversarial test forges.
        """
        emp = self.env['pb.ess.workforce']._require_own_employee()
        try:
            rating = int(rating)
        except (TypeError, ValueError):
            raise UserError(_("Pick a rating from 1 to 5."))
        if not 1 <= rating <= 5:
            raise UserError(_("Pick a rating from 1 to 5."))

        day = fields.Date.context_today(self)
        company = emp.company_id or self.env.company
        digest = self._pulse_hash(company.id, emp.id, day)

        # WITH_USER(SUPERUSER_ID), NOT sudo(). This one line is the anonymity.
        #
        # `sudo()` sets the `su` FLAG and leaves `env.uid` alone — it has worked
        # that way since Odoo 13 — so a row created under `self.sudo()` is still
        # stamped `create_uid = <the person who rated their own shift>`, in a
        # table whose entire purpose is that no row is about a person. The live
        # test run caught it: `create_uid` came back 1903, the rater's id, from
        # a method whose docstring claimed the opposite.
        # `with_user(SUPERUSER_ID)` moves the uid AND raises su, so both audit
        # columns say "the system". Never soften this to sudo() again.
        Pulse = self.with_user(SUPERUSER_ID)
        if Pulse.search_count([('uniq_hash', '=', digest)]):
            raise UserError(_("You have already rated today. Thank you."))
        note = (comment or '').strip()[:_MAX_COMMENT] or False
        try:
            Pulse.create({
                'company_id': company.id,
                'department_id': emp.department_id.id or False,
                'date': day,
                'rating': rating,
                'comment': note,
                'uniq_hash': digest,
            })
        except Exception:
            # The UNIQUE index is the real guard and it can fire on a race the
            # search above lost. A second rating is not an error worth showing.
            self.env.cr.rollback()
            raise UserError(_("You have already rated today. Thank you."))
        return {'ok': True}

    # ============================================================== prompt
    @api.model
    def get_my_prompt(self):
        """Should the caller be asked? ``{'show': bool, 'shift': label}``.

        Asked ONLY after a shift the caller actually worked has ended today, and
        only once — a prompt on a day somebody did not work is a survey, and a
        prompt that comes back after they answered is nagging.

        The "already rated" test uses the same digest the write uses, so the
        prompt and the guard can never disagree about who has answered.
        """
        Ess = self.env['pb.ess.workforce']
        emp = Ess._own_employee()
        if not emp:
            return {'show': False}
        day = fields.Date.context_today(self)
        now = fields.Datetime.now()
        shift = self.env['hr.shift.planning'].sudo().search([
            ('employee_id', '=', emp.id),
            ('date', '=', day),
            ('state', 'in', ('published', 'completed')),
            ('end_datetime', '<=', now),
        ], order='end_datetime desc', limit=1)
        if not shift:
            return {'show': False}
        company = emp.company_id or self.env.company
        digest = self._pulse_hash(company.id, emp.id, day)
        if self.sudo().search_count([('uniq_hash', '=', digest)]):
            return {'show': False}
        tz = Ess._tzinfo(emp)
        return {
            'show': True,
            'shift': '%s – %s' % (Ess._hhmm(shift.start_datetime, tz),
                                  Ess._hhmm(shift.end_datetime, tz)),
        }

    # ========================================================= aggregation
    @api.model
    def get_pulse_tile(self, department_id=False):
        """The Today board's Team pulse tile, or nothing.

        "Nothing" is the important half. Below the floor this returns
        ``{'shown': False}`` and NO figures — not a rounded average, not the
        count, not the department. A client cannot be trusted to hide a number
        it has been handed, and a number that arrives is a number that leaks.
        """
        co_ids = self.env.companies.ids or [self.env.company.id]
        since = fields.Date.context_today(self) - timedelta(
            days=PULSE_WINDOW_DAYS - 1)
        domain = [('company_id', 'in', co_ids), ('date', '>=', since)]
        if department_id:
            domain.append(('department_id', '=', int(department_id)))
        rows = self.sudo().search_read(domain, ['rating'])
        count = len(rows)
        if count < PULSE_FLOOR:
            return {'shown': False, 'floor': PULSE_FLOOR, 'window': PULSE_WINDOW_DAYS}
        total = sum(r['rating'] or 0 for r in rows)
        return {
            'shown': True,
            'avg': round(total / float(count), 1),
            'count': count,
            'window': PULSE_WINDOW_DAYS,
            'floor': PULSE_FLOOR,
        }
