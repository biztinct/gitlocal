# -*- coding: utf-8 -*-
"""UPDATES P4 — leave opening balances from a sheet: what is stored, and how
it is written.

One row per person × leave type of a named update (`pb.updates.leave.line`):
the balance as at a date ("cutover"), what became of it, and the allocation
it made. Rails (handover §3):

  * ONE way to write a balance. A person on the leave policy layer (an
    absence policy assigned on their record — `pb_timeoff`) gets their
    opening balance ONLY through that layer's public
    `pb.leave.policy.edition.post_opening_balance`, so its own rails stay in
    force (overlap refusal, once-only posting key, frozen postings). Anybody
    else gets ONE validated `hr.leave.allocation`, created the way the
    standard allocation flow creates one (create, then approve), marked with
    the row that made it (`pb_updates_leave_line_id`).
  * never a second opening balance: every row is judged again at write time
    (`pb.updates.desk._leave_cell`, the same verdict the review showed) under
    the same advisory lock the policy layer takes for a person's balance;
  * never leave taken or requested, accrual, carry-over or the January
    rollover: no `hr.leave` is created or changed here, and an undo only
    refuses an allocation nothing has been taken or asked for against;
  * written as the PROPOSER (the precedent of `pb.records.apply._writer_desk`):
    the approver approves, and the audit names the proposer. A Time Off
    administrator writes with their own rights, as in P4. An HR officer
    (owner D23, 2026-11-13: HR officers may send; the approval route still
    decides) has no Time Off rights of their own, so for exactly the two
    writes below — the policy layer's `post_opening_balance` and one
    allocation's create + approve — the officer's own user runs with
    superuser rights (`su`), AFTER the row's verdict was read again and two
    officer-only rails held: the person works in one of the officer's
    companies, and it is not the officer's own balance (the native Time Off
    rule: only an administrator approves their own allocation). Nothing else
    runs elevated; undo stays with Time Off administrators;
  * no email: allocations from a sheet are created and approved quietly
    (no tracking messages, activities closed without notice).

Approval: the named update's ONE `pb.records.apply` (flag `updates_leave`),
on the records route — the same process key, routes and inbox as the pay lane
(a leave balance is a liability). Approving it writes the rows, all in one
transaction; a row whose rails refuse at write time is kept as "Could not be
set" with its reason, and the others still go through.

`pb_timeoff` is another session's module: nothing here imports it, and every
reach into it is a soft check (`'pb.leave.policy.edition' in env`).
"""
import json
import logging
import re

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)

#: Card ids: `l:<leave type id>:<part>`.
PREFIX = 'l:'
GROUP = 'leave'
#: The three figures of one opening balance. Only `avail` becomes leave a
#: person can take; `carry` and `taken` are recorded with a policy posting.
PARTS = ('avail', 'carry', 'taken')
#: The leave policy layer's own right (`pb_timeoff` `MANAGER`), which is also
#: the right that may approve any allocation: Time Off administrator.
MANAGER = 'hr_holidays.group_hr_holidays_manager'
#: Who may SEND a leave sheet (owner D23, 2026-11-13): an HR officer — the
#: Employees officer right, which Time Off officers and administrators hold
#: too (their groups imply it). It is the role that could already CHECK one.
SENDER = 'hr.group_hr_user'
#: A cell above this is refused (or the hour equivalent).
MAX_DAYS = 365.0
#: Hours in a day when the person has no working schedule to ask.
HOURS_DEFAULT = 8.0
#: The furthest back a "balances as at" date may be.
REACH_BACK_DAYS = 366
#: A row that stands as an opening balance (or is about to).
LIVE = ('waiting', 'set')
#: The context every write from a sheet runs with: no tracking messages, no
#: chatter line for the creation, activities closed without an email.
QUIET = {'mail_notrack': True, 'mail_create_nolog': True,
         'mail_activity_quick_update': True, 'mail_create_nosubscribe': True}


def card_id(type_id, part='avail'):
    return '%s%s:%s' % (PREFIX, int(type_id), part)


def parse_card(field_id):
    """`(leave type id, part)` of a card id, or `(0, '')`."""
    match = re.match(r'^l:(\d+):(avail|carry|taken)$', str(field_id or ''))
    if not match:
        return 0, ''
    return int(match.group(1)), match.group(2)


def day_label(env, day):
    """'1 Nov 2026' in the reader's language — the way the screens write a
    date (the Updates screen's `dayLabel`)."""
    return format_date(env, day, date_format='d MMM y') if day else ''


def number_text(value):
    """12 → '12', 12.5 → '12.5', 7.25 → '7.25' (never '12.0')."""
    try:
        value = float(value or 0.0)
    except (TypeError, ValueError):
        return ''
    text = ('%.2f' % value).rstrip('0').rstrip('.')
    return text or '0'


class _Refused(Exception):
    """A row the rails refuse at write time: its sentence."""


class PbUpdatesLeaveLine(models.Model):
    _name = 'pb.updates.leave.line'
    _description = 'Leave opening balance from Updates'
    _order = 'batch_id desc, id'

    batch_id = fields.Many2one('pb.updates.batch', string='Named update', required=True,
                               index=True, ondelete='cascade', readonly=True)
    apply_id = fields.Many2one('pb.records.apply', string='Approval proposal', index=True,
                               ondelete='set null', readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True,
                                  ondelete='cascade', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True,
                                 readonly=True)
    leave_type_id = fields.Many2one('hr.leave.type', string='Leave type', required=True,
                                    index=True, ondelete='cascade', readonly=True)
    type_name = fields.Char(string='Leave type name', readonly=True)
    unit = fields.Selection([('day', 'Days'), ('half_day', 'Half days'), ('hour', 'Hours')],
                            string='Unit', default='day', required=True, readonly=True)
    cutover_date = fields.Date(string='Balances as at', required=True, readonly=True)
    available = fields.Float(string='Available', readonly=True)
    carried = fields.Float(string='Carried from last year', readonly=True)
    taken = fields.Float(string='Already taken this year', readonly=True)
    way = fields.Selection([('policy', 'Absence policy'), ('allocation', 'Allocation')],
                           string='Written through', required=True, readonly=True)
    state = fields.Selection([
        ('waiting', 'Waiting for approval'),
        ('set', 'Set'),
        ('refused', 'Could not be set'),
        ('undone', 'Undone'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Sent back'),
        ('rejected', 'Turned down'),
    ], string='Status', default='waiting', required=True, index=True, readonly=True)
    allocation_id = fields.Many2one('hr.leave.allocation', string='Allocation made',
                                    index='btree_not_null', ondelete='set null', readonly=True)
    #: The policy posting made (`pb.leave.policy.posting`), by id — a soft
    #: reference, so this module never depends on the policy layer.
    posting_ref = fields.Integer(string='Policy posting', readonly=True)
    reason = fields.Text(string='Why', readonly=True)
    undone_at = fields.Datetime(string='Undone at', readonly=True)
    undone_by_id = fields.Many2one('res.users', string='Undone by', readonly=True)
    note = fields.Text(string='History', readonly=True)

    _available_positive = models.Constraint(
        'CHECK(available > 0)', 'An opening balance must be more than zero.')

    # =================================================================
    # Words
    # =================================================================
    @api.model
    def _qty_label(self, value, unit='day'):
        """'12.5 days', '1 day', '7.5 hours' — as a person reads it."""
        text = number_text(value)
        if unit == 'hour':
            return _("1 hour") if text == '1' else _("%s hours") % text
        return _("1 day") if text == '1' else _("%s days") % text

    def _balance_label(self):
        self.ensure_one()
        return self._qty_label(self.available, self.unit)

    def _log(self, text):
        stamp = fields.Datetime.now().strftime('%Y-%m-%d %H:%M')
        who = self.env.user.name or ''
        for row in self:
            line = '%s · %s · %s' % (stamp, who, text)
            row.sudo().write({'note': ((row.note + '\n') if row.note else '') + line})

    def _plan_row(self):
        """One row of the approval drawer's table."""
        self.ensure_one()
        bits = [self._balance_label()]
        if self.way == 'policy' and (self.carried or self.taken):
            bits.append(_("%(carried)s carried, %(taken)s taken", carried=number_text(self.carried),
                          taken=number_text(self.taken)))
        return {
            'emp_id': self.employee_id.id, 'emp_name': self.employee_id.name or '',
            'field_id': card_id(self.leave_type_id.id),
            'field_label': _("%(type)s · as at %(date)s", type=self.type_name or self.leave_type_id.name,
                             date=day_label(self.env, self.cutover_date)),
            'old_label': '',
            'new_label': ' · '.join(bits),
        }

    # =================================================================
    # Write (on approval)
    # =================================================================
    def _write_all(self, actor):
        """Write every waiting row as `actor`; `(set, people, refused)`.

        One transaction; every row in a savepoint of its own, so a row the
        rails refuse is kept with its reason and the others still go in."""
        rows = self.sudo().filtered(lambda r: r.state == 'waiting').sorted('id')
        if not rows:
            return 0, 0, 0
        apply_rec = rows.mapped('apply_id')[:1]
        own_rights = actor.id == SUPERUSER_ID or actor.has_group(MANAGER)
        if not own_rights and not actor.has_group(SENDER):
            why = _("%s no longer has the HR officer role, so no balance was set. "
                    "Ask somebody who has it to send the sheet again.") % (actor.name or '')
            rows.write({'state': 'refused', 'reason': why})
            rows._log(why)
            return 0, 0, len(rows)
        mine = actor.sudo().company_ids.ids
        wanted = [c for c in rows.mapped('company_id').ids if c in mine]
        companies = wanted + [c for c in mine if c not in wanted]
        ctx = dict(self.env.context, **QUIET)
        if companies:
            ctx['allowed_company_ids'] = companies
        # D23: an HR officer's balances are written as the officer with
        # superuser rights, for the two writes of `_write_one` only (module
        # docstring); a Time Off administrator keeps their own rights.
        aenv = self.env(user=actor.id, su=actor.id == SUPERUSER_ID or not own_rights,
                        context=ctx)
        officer = None if own_rights else actor
        Desk = self.env['pb.updates.desk'].sudo()
        reference = _("Updates: “%(name)s” (%(ref)s)", name=rows[:1].batch_id.name or '',
                      ref=(apply_rec.name if apply_rec else '') or '')
        done, people, refused = 0, set(), 0
        for row in rows:
            why = ''
            try:
                with self.env.cr.savepoint():
                    row._write_one(aenv, Desk, reference, officer=officer)
            except _Refused as error:
                why = str(error)
            except UserError as error:
                # The policy layer or the allocation flow said no: its own
                # sentence, kept on the row.
                why = _("It could not be set: %s") % (
                    (error.args[0] if error.args else '') or str(error))
            except Exception as error:   # noqa: BLE001 — one row never stops the rest
                _logger.warning('UPDATES P4: leave line %s not written: %s', row.id, error)
                why = _("It could not be set. Nothing was changed for this person and "
                        "leave type.")
            if why:
                row.invalidate_recordset()
                row._refuse(why)
                refused += 1
                continue
            done += 1
            people.add(row.employee_id.id)
        return done, len(people), refused

    def _refuse(self, why):
        self.ensure_one()
        self.sudo().write({'state': 'refused', 'reason': why})
        self._log(_("Could not be set: %s") % why)

    def _write_one(self, aenv, Desk, reference, officer=None):
        """Write ONE row as `aenv`'s user. Raises `_Refused` with a sentence
        when the rails say no; the caller's savepoint undoes any part of it.

        `officer`: the HR officer whose balances are written elevated (D23),
        or None for a Time Off administrator (own rights)."""
        self.ensure_one()
        row = self.sudo()
        self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                            ['pb.leave.balance:%s:%s' % (row.employee_id.id, row.leave_type_id.id)])
        verdict = Desk._leave_row_check(row, sender=officer)
        if verdict:
            raise _Refused(verdict)
        if officer is not None and row.company_id.id not in officer.sudo().company_ids.ids:
            raise _Refused(_("%(who)s works in %(company)s, which %(sender)s no longer works in, "
                             "so this balance was not set.", who=row.employee_id.name or '',
                             company=row.company_id.name or '', sender=officer.name or ''))
        employee = aenv['hr.employee'].browse(row.employee_id.id)
        leave_type = aenv['hr.leave.type'].browse(row.leave_type_id.id)
        Alloc = aenv['hr.leave.allocation']
        if row.way == 'policy':
            if 'pb.leave.policy.edition' not in self.env:
                raise _Refused(_("The absence policy is no longer installed, so this balance "
                                 "cannot be set through it."))
            edition = Desk._leave_edition_for(row.employee_id.sudo(), row.cutover_date)
            if not edition:
                raise _Refused(_("%(who)s's absence policy no longer covers %(date)s.",
                                 who=row.employee_id.name or '',
                                 date=day_label(self.env, row.cutover_date)))
            Posting = self.env['pb.leave.policy.posting'].sudo()
            before = set(Posting.search([('employee_id', '=', row.employee_id.id),
                                         ('leave_type_id', '=', row.leave_type_id.id),
                                         ('kind', '=', 'opening')]).ids)
            posting = aenv['pb.leave.policy.edition'].browse(edition.id).post_opening_balance(
                employee.id, leave_type.id, row.cutover_date, row.available,
                row.carried, row.taken, reference)
            if not posting or posting.id in before:
                raise _Refused(_("%(who)s already has an opening balance for %(type)s. Nothing "
                                 "was added on top.", who=row.employee_id.name or '',
                                 type=row.type_name or ''))
            allocation = posting.sudo().allocation_id
            if allocation:
                allocation.with_context(**QUIET).write({'pb_updates_leave_line_id': row.id})
            row.write({'state': 'set', 'posting_ref': posting.id,
                       'allocation_id': allocation.id or False, 'reason': False})
        else:
            days = row.available
            if row.unit == 'hour':
                per_day = employee.sudo()._get_hours_per_day(row.cutover_date) or HOURS_DEFAULT
                days = row.available / per_day
            allocation = Alloc.create({
                'name': _("Opening balance as at %s") % day_label(self.env, row.cutover_date),
                'employee_id': employee.id, 'holiday_status_id': leave_type.id,
                'allocation_type': 'regular', 'number_of_days': days,
                'date_from': row.cutover_date, 'date_to': False,
                'notes': _("Opening balance as at %(date)s, set from %(ref)s.",
                           date=day_label(self.env, row.cutover_date), ref=reference),
                'pb_updates_leave_line_id': row.id,
            })
            if allocation.state != 'validate':
                allocation.action_approve()
            if allocation.state != 'validate':
                raise _Refused(_("The allocation for %(type)s needs a second approval in Time Off, "
                                 "so it was not set from the sheet. Set it on the Time Off screen.",
                                 type=row.type_name or ''))
            row.write({'state': 'set', 'allocation_id': allocation.id, 'reason': False})
        row._log(_("Set: %(balance)s of %(type)s as at %(date)s.", balance=row._balance_label(),
                   type=row.type_name or '', date=day_label(self.env, row.cutover_date)))

    # =================================================================
    # Undo
    # =================================================================
    def _undo_one(self):
        """Take back ONE balance this sheet made, when nothing has drawn on
        it. Returns '' when it was taken back, else the sentence why it stays.

        A policy-layer balance is never taken back here: its postings are
        permanent and the layer offers no reversal."""
        self.ensure_one()
        row = self.sudo()
        who = row.employee_id.name or ''
        if row.state != 'set':
            return _("This balance is not set, so there is nothing to undo.")
        if row.way == 'policy':
            return _("%(who)s's %(type)s balance was set through the absence policy, which keeps "
                     "it permanently. It cannot be undone here.", who=who, type=row.type_name or '')
        self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                            ['pb.leave.balance:%s:%s' % (row.employee_id.id, row.leave_type_id.id)])
        allocation = row.allocation_id.exists()
        now = fields.Datetime.now()
        if not allocation or allocation.state == 'refuse':
            row.write({'state': 'undone', 'undone_at': now, 'undone_by_id': self.env.uid,
                       'reason': _("It had already been taken off on the Time Off screen.")})
            row._log(_("Undone: it had already been taken off on the Time Off screen."))
            return ''
        employee = row.employee_id
        leave_type = row.leave_type_id
        consumed = employee._get_consumed_leaves(leave_type)[0]
        used = consumed.get(employee, {}).get(leave_type, {}).get(allocation, {})
        drawn = float(used.get('virtual_leaves_taken') or 0.0)
        if drawn > 0.000001:
            # The time-off engine counts an hour-based leave type in hours,
            # every other one in days: the row's own unit.
            unit = row.unit
            return _("%(who)s has already taken or asked for %(qty)s of %(type)s against this "
                     "balance, so it stays.", who=who, qty=self._qty_label(drawn, unit),
                     type=row.type_name or '')
        allocation.with_context(**QUIET).action_refuse()
        row.write({'state': 'undone', 'undone_at': now, 'undone_by_id': self.env.uid,
                   'reason': False})
        row._log(_("Undone: the balance was taken off."))
        return ''


class PbUpdatesBatchLeave(models.Model):
    _inherit = 'pb.updates.batch'

    kind = fields.Selection(selection_add=[('leave', 'Leave opening balances')],
                            ondelete={'leave': 'set default'})
    leave_date = fields.Date(string='Balances as at')
    leave_line_ids = fields.One2many('pb.updates.leave.line', 'batch_id',
                                     string='Leave opening balances')


class PbUpdatesLayoutLeave(models.Model):
    _inherit = 'pb.updates.layout'

    kind = fields.Selection(selection_add=[('leave', 'Leave opening balances')],
                            ondelete={'leave': 'set default'})


class HrLeaveAllocationUpdates(models.Model):
    """The mark that tells an opening balance from Updates apart from every
    other allocation."""
    _inherit = 'hr.leave.allocation'

    pb_updates_leave_line_id = fields.Many2one(
        'pb.updates.leave.line', string='Opening balance from Updates', readonly=True,
        copy=False, index='btree_not_null', ondelete='set null')


class PbRecordsApplyLeave(models.Model):
    """The named update's ONE approval proposal, when it carries leave
    opening balances. Same process key, routes and inbox as every records
    change; approving it writes the rows instead of a record."""
    _inherit = 'pb.records.apply'

    updates_leave = fields.Boolean(string='Leave opening balances', readonly=True, copy=False)
    leave_line_ids = fields.One2many('pb.updates.leave.line', 'apply_id',
                                     string='Leave opening balances')

    def _headline(self):
        self.ensure_one()
        if not self.updates_leave:
            return super()._headline()
        rows = self.sudo().leave_line_ids
        n = len(rows)
        day = rows[:1].cutover_date
        return _("Leave opening balances as at %(date)s · %(n)s",
                 date=day_label(self.env, day) if day else '',
                 n=_("1 balance") if n == 1 else _("%s balances") % n)

    def _approval_detail(self, request):
        detail = super()._approval_detail(request)
        if self.updates_leave and detail:
            detail['title'] = _('Leave opening balances')
            detail['columns'] = [_('Now'), _('In this update')]
        return detail

    def _approval_freeze(self, request):
        result = super()._approval_freeze(request)
        if self.updates_leave:
            # Sent in again after it was sent back: its rows wait again.
            rows = self.sudo().leave_line_ids.filtered(lambda r: r.state == 'returned')
            if rows:
                rows.write({'state': 'waiting'})
                rows._log(_("Sent in again."))
        return result

    def _approval_apply(self, request):
        self.ensure_one()
        if not self.updates_leave:
            return super()._approval_apply(request)
        if self.applied:
            return True
        if self.state == 'cancelled' or self.undone:
            raise UserError(_("This change was cancelled, so nothing was written."))
        rec = self.sudo()
        actor = rec.user_id if rec.user_id.id == SUPERUSER_ID else rec._start_user()
        done, people, refused = rec.leave_line_ids._write_all(actor)
        rec.write({
            'applied': True, 'applied_at': fields.Datetime.now(), 'state': 'applied',
            'count_values': done, 'count_people': people,
            'block_note': (_("1 balance could not be set.") if refused == 1 else
                           _("%s balances could not be set.") % refused) if refused else False,
        })
        return True

    def write(self, vals):
        result = super().write(vals)
        state = vals.get('state')
        if state in ('cancelled', 'rejected', 'returned') and 'leave_line_ids' in self._fields:
            for rec in self.filtered('updates_leave'):
                rows = rec.sudo().leave_line_ids.filtered(lambda r: r.state == 'waiting')
                if rows:
                    rows.write({'state': state})
                    rows._log({'cancelled': _("Cancelled before it was approved."),
                               'rejected': _("Turned down."),
                               'returned': _("Sent back.")}[state])
        return result


def json_dumps(value):
    return json.dumps(value, default=str)
