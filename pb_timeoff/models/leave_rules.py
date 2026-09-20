# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Three rules the time-off module never had, and one switch each.

**TIME OFF IN THE PAST IS HR'S TO ENTER, EXCEPT WHEN SOMEBODY WAS ILL.** The
stock module has no past-date guard on `create` at all (grep
`allows_request_in_past` — there is nothing), so anybody could book last month
off this morning and a pay run that had already been worked out would quietly
disagree with the record. Now a request dated before today is REFUSED with a
sentence that says what to do instead — unless the kind of time off is one the
business has marked as askable after the fact, which is what sick leave is.
When it is, HR is told, because somebody being off sick last Tuesday is a fact
the pay team needs and not a form they should have to find.

**A LEAVE THAT HAS ALREADY STARTED IS NOT EDITABLE BY THE PERSON WHO ASKED FOR
IT.** The stock rule (`hr_leave.py` `write`) lets a non-officer change a
begun leave while it is still `confirm`, and lets the employee's own leave
manager change one in any state — so "I was off three days, not five" was a
thing a person could type themselves, after the fact, over a period payroll
may already have paid. The lock is on the leave's SUBSTANCE only: its dates,
its kind, who it is for and what it says. A state change, an attachment, a
seat the approval route writes and a follower are all untouched, which is what
lets the route keep working over a backdated sick note.

**NOTHING HERE IS A SECOND APPROVAL.** Escalation is the engine's own late
block (`biz_approval_workflow`), not a chaser written here; this file only
tells the seed which responsibility to escalate to.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .hr_leave_approval import ENGINE_APPLY, OFFICER_GROUP

_logger = logging.getLogger(__name__)

#: Switches, with the default each ships with.
SWITCH_LOCK_PAST = 'pb_timeoff.lock_past'            # 1 — the lock is on
SWITCH_ESCALATE_DAYS = 'pb_timeoff.escalate_days'    # 2 — days past the due date

#: The fields that are the leave ITSELF. A write that touches none of them is
#: not a change to the time off — it is the route, the chatter or an
#: attachment doing its job — and the lock must not fire on it.
SUBSTANCE_FIELDS = frozenset({
    'request_date_from', 'request_date_to', 'date_from', 'date_to',
    'request_hour_from', 'request_hour_to', 'request_date_from_period',
    'request_unit_half', 'request_unit_hours', 'number_of_days',
    'holiday_status_id', 'employee_id', 'employee_ids', 'name',
    'private_name', 'holiday_type',
})

MANAGER_GROUP = 'hr_holidays.group_hr_holidays_manager'


class HrLeaveType(models.Model):
    """What a KIND of time off is allowed to do."""
    _inherit = 'hr.leave.type'

    pb_backdate_ok = fields.Boolean(
        string='Can be asked for after it happened',
        default=False,
        help='Tick this for the kinds of time off somebody cannot ask for in '
             'advance — sick leave above all. Everything else can only be '
             'entered for a past date by the HR team.')
    pb_backdate_alert = fields.Boolean(
        string='Tell HR when it is',
        default=True,
        help='When somebody asks for this kind of time off for a day that has '
             'already gone, the HR lead gets an email and a to-do. Turn it '
             'off for a kind of absence HR does not need to hear about one '
             'by one.')
    pb_carry_cap_days = fields.Float(
        string='Warn above this many days',
        default=0.0, digits=(6, 2),
        help='Leave this at zero and nothing is watched. Set it, and anybody '
             'still holding this many days or more as the cut-off comes round '
             'is emailed, and so is their manager, so the days get used '
             'rather than lost.')


class HrLeaveRules(models.Model):
    _inherit = 'hr.leave'

    pb_backdated = fields.Boolean(
        string='Asked for after it happened', readonly=True, copy=False,
        help='Set when the request was made for a day that had already gone. '
             'A fact about the request, not about the dates: it is written '
             'once, when the request is made, and never recomputed — a '
             'request made in advance does not become backdated by getting '
             'old.')

    # ================================================================ gates
    @api.model
    def _pb_is_officer(self, user=None):
        user = user or self.env.user
        if self.env.is_superuser() or user.has_group('base.group_system'):
            return True
        for group in (OFFICER_GROUP, MANAGER_GROUP, 'hr.group_hr_manager'):
            try:
                if user.has_group(group):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    @api.model
    def _pb_switch(self, key, default):
        raw = self.env['ir.config_parameter'].sudo().get_param(key)
        if raw is None or raw == '':
            return default
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    def _pb_started(self):
        """Has this time off begun? The SERVER's today (R36/R154) — a lock
        that changes with the reader's timezone is not a lock."""
        self.ensure_one()
        start = self.request_date_from or (
            self.date_from.date() if self.date_from else None)
        return bool(start and start < fields.Date.today())

    # =========================================================== backdating
    @api.model_create_multi
    def create(self, vals_list):
        """A request for a day that has already gone.

        Refused, unless the kind of time off says otherwise. The engine's own
        writes and the fast-create path are exempt: `ENGINE_APPLY` is the
        route carrying out a decision somebody already made, and refusing
        THAT would strand a request half-approved (R132's shape).
        """
        engine = self.env.context.get(ENGINE_APPLY) \
            or self.env.context.get('leave_fast_create')
        officer = self._pb_is_officer()
        today = fields.Date.today()
        late = []
        if not engine:
            for index, vals in enumerate(vals_list):
                start = fields.Date.to_date(
                    vals.get('request_date_from') or vals.get('date_from'))
                if not start or start >= today:
                    continue
                # The FACT is written whoever wrote it, so the queue card can
                # say "backdated" about HR's own entry too — that is true and
                # worth seeing. Only the refusal and the alert ask who.
                vals['pb_backdated'] = True
                if officer:
                    continue
                leave_type = self.env['hr.leave.type'].sudo().browse(
                    vals.get('holiday_status_id') or 0).exists()
                if not (leave_type and leave_type.pb_backdate_ok):
                    raise UserError(_(
                        "Time off in the past can only be entered by HR. "
                        "Sick leave is the exception — pick a sick-leave "
                        "type, and add the certificate if you have one."))
                late.append(index)
        leaves = super().create(vals_list)
        # HR is told about the ones a PERSON entered after the fact. Nobody
        # needs an email about something they typed themselves.
        for index in late:
            leave = leaves[index] if index < len(leaves) else None
            if not leave:
                continue
            # Each leg under a savepoint INSIDE the try (R131): Postgres
            # aborts the whole transaction on an error, so a failed alert
            # would take the leave that was just created with it.
            try:
                with self.env.cr.savepoint():
                    leave._pb_alert_hr()
            except Exception:                               # noqa: BLE001
                _logger.warning(
                    'pb_timeoff: leave %s is backdated and HR was not told',
                    leave.id, exc_info=True)
        return leaves

    def _pb_hr_lead(self):
        """Who hears about a backdated request.

        The responsibility first — that is where the business says who looks
        after time off — then the officer group as the honest fallback, so a
        company that has not filled the seat in still gets told.
        """
        self.ensure_one()
        company = self.company_id or self.env.company
        Resp = self.env.get('biz.approval.responsibility')
        if Resp is not None:
            role = self.env['biz.approval.role'].sudo().search(
                [('key', '=', 'hr_lead')], limit=1)
            if role:
                row, _via = Resp.resolve(company, role, [''],
                                         fields.Date.today())
                if row and row.user_id:
                    return row.user_id
        group = self.env.ref(OFFICER_GROUP, raise_if_not_found=False)
        if not group:
            return self.env['res.users']
        # R7: `res.users.group_ids` is DIRECT membership only and misses
        # everyone who holds the group through `implied_ids`.
        return group.sudo().all_user_ids.filtered(
            lambda u: u.active and not u.share
            and company in u.company_ids)[:1]

    def _pb_alert_hr(self):
        """A to-do and an email, to one person, once."""
        self.ensure_one()
        if not self.holiday_status_id.sudo().pb_backdate_alert:
            return False
        who = self._pb_hr_lead()
        if not who:
            _logger.info('pb_timeoff: nobody holds time off for %s, so the '
                         'backdated request %s was not announced',
                         (self.company_id or self.env.company).name, self.id)
            return False
        leave = self.sudo()
        summary = _("Time off entered for a day that has gone")
        # R183: `mail.activity.create` emails the assignee itself unless this
        # context key is set — and we are sending our own, better-worded
        # message a line below. Two messages in the same second about one
        # thing is one message too many.
        try:
            with self.env.cr.savepoint():
                leave.with_context(mail_activity_quick_update=True) \
                    .activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=who.id, summary=summary,
                        note=self._pb_alert_body())
        except Exception:                                   # noqa: BLE001
            _logger.warning('pb_timeoff: the backdated to-do failed',
                            exc_info=True)
        template = self.env.ref('pb_timeoff.mail_backdated_leave',
                                raise_if_not_found=False)
        if template and who.email:
            try:
                with self.env.cr.savepoint():
                    # R6: a template's own rendered `email_to` can reach
                    # `mail.mail` EMPTY, addressed to nobody, with no error
                    # anywhere. Always pass the recipient explicitly.
                    template.sudo().send_mail(
                        self.id, force_send=False,
                        email_values={'email_to': who.email})
            except Exception:                               # noqa: BLE001
                _logger.warning('pb_timeoff: the backdated email failed',
                                exc_info=True)
        return True

    def _pb_alert_body(self):
        self.ensure_one()
        employee = self.employee_id.sudo()
        return _(
            "%(who)s asked for %(what)s from %(start)s to %(end)s, which has "
            "already gone. Check it against the pay for that period.",
            who=employee.name or '',
            what=self.holiday_status_id.sudo().name or _('time off'),
            start=self.request_date_from or '',
            end=self.request_date_to or '')

    # ======================================================== the past lock
    def _pb_lock_refusal(self):
        return _(
            "This time off has already started, so it cannot be changed "
            "here. Ask HR.")

    def write(self, vals):
        if self._pb_lock_applies(vals):
            raise UserError(self._pb_lock_refusal())
        return super().write(vals)

    def _pb_lock_applies(self, vals):
        """True when this write is an employee changing a leave that has
        begun. Every question is asked in the cheapest order — the switch,
        then the caller, then the fields, then the dates — so the ordinary
        write pays for one config read and nothing else."""
        if self.env.context.get(ENGINE_APPLY) \
                or self.env.context.get('leave_fast_create'):
            return False
        if not self._pb_switch(SWITCH_LOCK_PAST, 1):
            return False
        if not (set(vals or {}) & SUBSTANCE_FIELDS):
            return False
        if self._pb_is_officer():
            return False
        return any(leave._pb_started() for leave in self)

    def unlink(self):
        """Deleting a leave that has begun is the same act as editing one.

        The stock module already refuses a non-officer here, in words that
        are fine; this says the same thing in the sentence the rest of the
        product uses, and honours the switch so turning the lock off really
        does put the stock behaviour back.
        """
        if not (self.env.context.get(ENGINE_APPLY)
                or self.env.context.get('leave_fast_create')) \
                and self._pb_switch(SWITCH_LOCK_PAST, 1) \
                and not self._pb_is_officer() \
                and any(leave._pb_started() for leave in self):
            raise UserError(self._pb_lock_refusal())
        return super().unlink()
