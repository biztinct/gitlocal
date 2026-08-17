# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""``pb.wf.lock`` — one row per (company, day), and the guard everything asks.

WHAT A LOCK PROTECTS, AND WHAT IT DOES NOT (P4 §1, binding)
-----------------------------------------------------------
A locked day does NOT protect money. Nothing on the payroll path reads
``hr.attendance`` at all — the whole ``_get_formula_input_values`` chain
(``pb_hr_payroll_formula/models/hr_payslip_formula.py``:316 and the two bridges
above it) reads ``hr.overtime.request`` and trips, and OT hours are GRID-ENTERED
by design. A punch could be rewritten a year later and not one payslip figure
would move.

A locked day protects the AUDIT SUBSTRATE. The punches are the evidence behind
every decision the week produced: the OT that was approved because somebody
really was there until 20:00, the correction a manager signed off, the variance
an officer waived. Rewriting that evidence after the week was closed and handed
to payroll turns a defensible payroll into an undefensible one, and it does so
silently, because none of the numbers change. That is what this model exists to
prevent — and it is why the OT REQUEST transitions are guarded too: those DO
feed payroll, so a locked day must not be able to grow new approved overtime.

A ROW IS A LOCK — WITH A STATE, NOT A DELETION (deviation D1, documented)
-------------------------------------------------------------------------
The handover specified "unlink = unlock". That cannot be reconciled with the
handover's own audit requirement in the same paragraph ("both logged via
tracking + explicit ``message_post`` with the actor and reason") or with its test
T14 ("Reopen demands a reason and posts it — verify chatter row"): a
``mail.thread`` record's messages die with the record, so an unlock-by-deletion
destroys the only account of why the week was reopened, at exactly the moment
somebody will want to read it.

So the grain is unchanged — ``unique(company_id, date)``, and only a row in
state ``locked`` locks anything — but reopening FLIPS the state instead of
dropping the row. One row per day then accumulates that day's whole history in
its chatter: locked by A, reopened by B because C, re-locked by D. ``unlink()``
still exists and is still manager-gated, for genuine surgery; it is simply not
the unlock door.

THE BYPASS (§3.2)
-----------------
``wf_lock_bypass`` in the context, honoured ONLY when ``env.su`` — the C2/trip
precedent. A context key alone is forgeable over ``call_kw``; ``env.su`` is not
reachable from a JSON-RPC session at all, so the pair means "a server-side
process that has already crossed a real permission boundary". Two callers need
it: ``pb_demo``'s regenerator (which rewrites a year of historical punches and
must not be defeated by a lock a demo left behind — the key lives in its
``_GEN_CTX``) and emergency admin surgery from the shell.
"""

import logging

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

# The context key, and the ONLY key this module reads for a bypass.
BYPASS_KEY = 'wf_lock_bypass'

# Who may lock and reopen a day. Deliberately the two MANAGER tiers: an
# attendance OFFICER may read a lock (and see the Close board) but locking a
# week is the act that hands it to payroll, and reopening one is the act that
# takes it back — neither is an officer's decision (the W31 posture).
_MANAGE_GROUPS = (
    'hr_attendance.group_hr_attendance_manager',
    'om_hr_payroll.group_hr_payroll_manager',
)


class PbWfLock(models.Model):
    _name = 'pb.wf.lock'
    _description = 'Workforce Day Lock'
    _inherit = ['mail.thread']
    _order = 'date desc, company_id'
    _rec_name = 'date'

    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company, ondelete='cascade')
    date = fields.Date(
        string='Day', required=True, index=True, tracking=True,
        help='The calendar day this lock closes, in the employee-local sense.')
    state = fields.Selection(
        [('locked', 'Locked'), ('open', 'Reopened')],
        string='Status', default='locked', required=True, index=True,
        tracking=True)
    reason = fields.Char(
        string='Last reason', tracking=True,
        help='Why the day was last locked or reopened. Required to reopen.')
    locked_by_id = fields.Many2one(
        'res.users', string='Locked by', readonly=True,
        default=lambda self: self.env.user)
    locked_on = fields.Datetime(
        string='Locked on', readonly=True, default=fields.Datetime.now)

    # W33: `models.Constraint`, never `_sql_constraints = [...]` — on Odoo 19
    # the legacy form is one WARNING among hundreds and then silence, and the
    # constraint does not exist in PostgreSQL at all.
    _company_day_uniq = models.Constraint(
        'unique(company_id, date)',
        'That day already has a workforce lock row.')

    # ==================================================================
    #  gates
    # ==================================================================
    @api.model
    def _pb_can_manage(self):
        u = self.env.user
        if self.env.su or u._is_admin():
            return True
        for g in _MANAGE_GROUPS:
            try:
                if u.has_group(g):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    @api.model
    def _pb_check_manage(self):
        if not self._pb_can_manage():
            raise AccessError(_(
                "Locking or reopening a workforce day is restricted to "
                "attendance managers and payroll managers."))

    # The gate lives on the MODEL, not only on the facade that edits it (W31):
    # `pb.close` runs as an OFFICER, so a facade-side check would make every
    # future helper on that facade a new place to forget it.
    @api.model_create_multi
    def create(self, vals_list):
        self._pb_check_manage()
        recs = super().create(vals_list)
        for rec in recs:
            rec._post_lock_note('lock')
        return recs

    def write(self, vals):
        self._pb_check_manage()
        return super().write(vals)

    def unlink(self):
        self._pb_check_manage()
        return super().unlink()

    # ==================================================================
    #  the audit trail
    # ==================================================================
    def _post_lock_note(self, kind):
        """An explicit chatter line beside the tracked field change.

        Tracking says "state: Locked -> Reopened". It does not say WHO or WHY in
        a sentence a manager reading the day six weeks later can act on, and the
        reason field only ever holds the LAST one. The message is the durable
        record — which is the whole reason a reopen flips a state instead of
        deleting the row (see the module docstring).
        """
        self.ensure_one()
        who = self.env.user.name
        if kind == 'lock':
            body = _("Day %(d)s locked by %(who)s.%(why)s",
                     d=self.date, who=who,
                     why=(_(" Reason: %s", self.reason) if self.reason else ''))
        else:
            body = _("Day %(d)s REOPENED by %(who)s. Reason: %(why)s",
                     d=self.date, who=who, why=self.reason or '—')
        try:
            self.message_post(body=body)
        except Exception:                                      # pragma: no cover
            # The audit line must never be able to break the lock itself.
            _logger.exception("pb.wf.lock: could not post the %s note", kind)

    # ==================================================================
    #  reading locks
    # ==================================================================
    @api.model
    def _bypass(self):
        """su-ONLY. A bare context key is forgeable over call_kw (C18.24); the
        pair "superuser environment AND asked for it" is not."""
        return bool(self.env.su and self.env.context.get(BYPASS_KEY))

    @api.model
    def _locked_pairs(self, company_ids, dates):
        """{(company_id, date)} that are currently LOCKED, in ONE query.

        Every guard in this module funnels through here, so a punch batch of any
        size costs one search regardless of how many days it touches.
        """
        company_ids = [c for c in set(company_ids or []) if c]
        dates = [d for d in set(dates or []) if d]
        if not company_ids or not dates:
            return set()
        rows = self.sudo().search_read(
            [('company_id', 'in', company_ids),
             ('date', 'in', dates),
             ('state', '=', 'locked')],
            ['company_id', 'date'])
        return {(r['company_id'][0], r['date']) for r in rows}

    @api.model
    def _is_locked(self, company, day):
        cid = company.id if hasattr(company, 'id') else company
        day = fields.Date.to_date(day)
        return bool(self._locked_pairs([cid], [day]))

    @api.model
    def _locked_dates(self, company, dates):
        """The subset of `dates` that is locked for `company`."""
        cid = company.id if hasattr(company, 'id') else company
        pairs = self._locked_pairs([cid], dates)
        return {d for (_c, d) in pairs}

    # ------------------------------------------------------------ tz helper
    @api.model
    def _local_day(self, employee, dt_utc, _cache=None):
        """The EMPLOYEE-LOCAL calendar day of a UTC punch datetime.

        The same convention the exception engine uses (review G-M5 / C18.49):
        in VN (UTC+7) a 05:58 local punch is stored on the PREVIOUS UTC day, so
        keying a lock by the UTC date would guard the wrong day for exactly the
        early-shift punches a factory cares most about. Shift dates and the
        Close board are already local calendar days, so this is what makes the
        lock chip on screen and the guard in the ORM mean the same Tuesday.
        """
        if not dt_utc:
            return False
        cache = _cache if _cache is not None else {}
        tzinfo = cache.get(employee.id)
        if tzinfo is None:
            try:
                tzinfo = pytz.timezone(
                    employee.tz or employee.company_id.resource_calendar_id.tz
                    or 'UTC')
            except Exception:
                tzinfo = pytz.UTC
            cache[employee.id] = tzinfo
        return pytz.UTC.localize(dt_utc).astimezone(tzinfo).date()

    # ==================================================================
    #  the guard every writer calls
    # ==================================================================
    @api.model
    def _check_days_open(self, pairs, what):
        """Raise a friendly ValidationError when any (company_id, date) is locked.

        :param pairs: iterable of (company_id, date)
        :param what: a short noun phrase naming the thing being attempted, used
            in the message — an officer must be told WHICH day stopped them,
            not merely that something is locked.

        ValidationError rather than UserError on purpose: the correction
        workflow's `action_approve` catches exactly ValidationError/UserError
        and lands the request in `refused` with the message as its `apply_error`
        (attendance_correction.py:227), which is the behaviour §3.2 asks for —
        a refusal on the record, never a traceback in the middle of an apply.
        """
        if self._bypass():
            return
        pairs = [(c, fields.Date.to_date(d)) for (c, d) in pairs if c and d]
        if not pairs:
            return
        locked = self._locked_pairs([c for c, _d in pairs],
                                    [d for _c, d in pairs])
        hit = sorted({d for (c, d) in pairs if (c, d) in locked})
        if not hit:
            return
        raise ValidationError(_(
            "%(what)s is not possible: the week is closed for %(days)s. "
            "Ask an attendance or payroll manager to reopen the day first.",
            what=what,
            days=', '.join(d.strftime('%d %b %Y') for d in hit[:5])
            + (_(' and %s more', len(hit) - 5) if len(hit) > 5 else '')))

    # ==================================================================
    #  the doors (RPC, gated) — called from CLICK handlers only (W21)
    # ==================================================================
    @api.model
    def lock_day(self, company_id, day, reason=False):
        """Lock one day. Idempotent: locking a locked day is a no-op."""
        self._pb_check_manage()
        company_id = int(company_id)
        day = fields.Date.to_date(day)
        rec = self.sudo().search(
            [('company_id', '=', company_id), ('date', '=', day)], limit=1)
        if rec:
            if rec.state == 'locked':
                return rec.id
            rec.sudo().write({
                'state': 'locked', 'reason': reason or False,
                'locked_by_id': self.env.uid,
                'locked_on': fields.Datetime.now()})
            rec._post_lock_note('lock')
            return rec.id
        # create() posts the note and re-checks the gate
        return self.create({
            'company_id': company_id, 'date': day,
            'reason': reason or False}).id

    @api.model
    def unlock_day(self, company_id, day, reason):
        """Reopen one day. The reason is REQUIRED and it is RECORDED (W42).

        The strictness is derived from what the model stores, not asserted over
        it: this reason lands on `reason` AND in the chatter, so demanding it is
        honest. (Contrast the dock's refusal note, which is only required on the
        two sources whose refuse action actually keeps it.)
        """
        self._pb_check_manage()
        reason = (reason or '').strip()
        if not reason:
            raise UserError(_(
                "Reopening a closed day needs a reason — it is the only "
                "account anyone reviewing this payroll will have of why the "
                "week was taken back."))
        company_id = int(company_id)
        day = fields.Date.to_date(day)
        rec = self.sudo().search(
            [('company_id', '=', company_id), ('date', '=', day)], limit=1)
        if not rec or rec.state != 'locked':
            return False
        rec.sudo().write({'state': 'open', 'reason': reason})
        rec._post_lock_note('unlock')
        return rec.id
