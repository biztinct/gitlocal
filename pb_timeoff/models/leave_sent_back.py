# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Time off "Sent back": a mark, and "Ask again" (WORKFLOW-2 P6c, owner
decision D36, 16 Nov).

WHAT WAS TRUE BEFORE. A request an approver sent back was refused by
`HrLeaveApproval._approval_return` (hr_holidays has no "back to draft" while a
request is under approval). The email said "sent back" and why (P5a, D28);
every screen said "Refused", and the employee had to fill in a new request
from nothing.

WHAT IS TRUE NOW.

* **A mark, not a status.** `pb_sent_back` is set when the approval is sent
  back and never cleared. Time off's status field and every balance rule are
  exactly as they were: the request is still refused underneath, so no day is
  held. A screen says "Sent back" only while BOTH hold — state ``refuse`` and
  the mark (`_pb_is_sent_back`) — so a request an officer later moves back to
  waiting reads as waiting again.
* **"Ask again"** makes a NEW request, filled in from the sent-back one, through
  the same doors as any other request (the employee's own form, the staff
  "Apply for" drawer): every normal rule runs on it. The new request names the
  old one (`pb_again_of_id`); the old one finds its follow-up by search
  (`pb_again_id`). Once per sent-back request — checked here, in ``create``,
  for every door, and held by a unique index.
* The reason stays where it already is (the approval request's
  ``return_note``, read by `_pb_sent_back_note` in `leave_messages.py`).
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date

from odoo.addons.pb_me_portal.models.pb_me_home import REQUEST_BUCKETS


class HrLeaveSentBack(models.Model):
    _inherit = 'hr.leave'

    pb_sent_back = fields.Boolean(
        string='Sent back', copy=False, readonly=True,
        help='The approver sent this request back to the employee instead of '
             'refusing it. It is still refused underneath, so no day is held.')
    pb_again_of_id = fields.Many2one(
        'hr.leave', string='Asked again after', copy=False, readonly=True,
        ondelete='set null',   # indexed by the unique index below
        help='The request that was sent back and that this one asks again.')
    pb_again_id = fields.Many2one(
        'hr.leave', string='Asked again as', compute='_compute_pb_again_id',
        compute_sudo=True,
        help='The new request made when this one was asked again.')
    pb_sent_back_note = fields.Char(
        string='Sent back note', compute='_compute_pb_sent_back_note',
        compute_sudo=True)

    #: One "ask again" per sent-back request, whatever door it came through.
    _pb_again_once = models.UniqueIndex(
        '(pb_again_of_id) WHERE pb_again_of_id IS NOT NULL',
        'This request was already asked again.')

    # ------------------------------------------------------------ computes
    def _compute_pb_again_id(self):
        found = {}
        ids = [i for i in self.ids if isinstance(i, int)]
        if ids:
            for leave in self.sudo().search([('pb_again_of_id', 'in', ids)],
                                            order='id'):
                found.setdefault(leave.pb_again_of_id.id, leave)
        for leave in self:
            leave.pb_again_id = found.get(leave.id, False)

    @api.depends('state', 'pb_sent_back')
    def _compute_pb_sent_back_note(self):
        for leave in self:
            if not (leave.id and leave._pb_is_sent_back()):
                leave.pb_sent_back_note = False
                continue
            reason = leave._pb_sent_back_note()
            leave.pb_sent_back_note = _(
                "Sent back to the employee, not refused: %s", reason) \
                if reason else _("Sent back to the employee, not refused.")

    # ------------------------------------------------------------- helpers
    def _pb_is_sent_back(self):
        """Refused underneath AND marked sent back: what our screens call
        "Sent back"."""
        self.ensure_one()
        return self.state == 'refuse' and bool(self.pb_sent_back)

    def _pb_can_ask_again(self):
        self.ensure_one()
        return self._pb_is_sent_back() and not self.sudo().pb_again_id

    def _pb_dates_label(self):
        """'3 Dec 2026' or '3 Dec 2026 – 5 Dec 2026', in the reader's
        language."""
        self.ensure_one()
        start = self.request_date_from or (
            self.date_from.date() if self.date_from else None)
        end = self.request_date_to or (
            self.date_to.date() if self.date_to else start)
        if not start:
            return ''
        if not end or end == start:
            return format_date(self.env, start)
        return '%s – %s' % (format_date(self.env, start),
                            format_date(self.env, end))

    def _pb_again_lines(self):
        """The two link lines, as ``{'of': {...}, 'as': {...}}`` (either may
        be ``None``): on a new request, the one it asks again; on a sent-back
        request, the one that asked it again. Each ``{'id', 'label'}``."""
        self.ensure_one()
        leave = self.sudo()
        out = {'of': None, 'as': None}
        old = leave.pb_again_of_id
        if old:
            out['of'] = {'id': old.id, 'label': _(
                "Asked again after the request for %s was sent back",
                old._pb_dates_label())}
        new = leave.pb_again_id
        if new:
            out['as'] = {'id': new.id, 'label': _(
                "Asked again on %s",
                format_date(self.env, fields.Date.to_date(new.create_date)))}
        return out

    @staticmethod
    def _pb_hhmm_value(value):
        """9.5 -> '09:30' for an <input type=time>; '' when unset."""
        if value in (None, False):
            return ''
        value = float(value)
        hours, minutes = int(value), int(round((value - int(value)) * 60))
        if minutes == 60:
            hours, minutes = hours + 1, 0
        return '%02d:%02d' % (hours, minutes)

    def _pb_again_prefill(self):
        """What the request form is filled in with when this one is asked
        again: the kind, the dates, the part of the day or the times, the
        note. Documents are not copied."""
        self.ensure_one()
        leave = self.sudo()
        start = leave.request_date_from or (
            leave.date_from.date() if leave.date_from else None)
        end = leave.request_date_to or (
            leave.date_to.date() if leave.date_to else start)
        unit = leave.holiday_status_id.request_unit or 'day'
        period_from = period_to = 'full'
        hour_from = hour_to = ''
        if unit == 'half_day' and leave.request_unit_half:
            pf, pt = leave.request_date_from_period, leave.request_date_to_period
            if start and start == end:
                if pf == pt and pf in ('am', 'pm'):
                    period_from = pf
            else:
                period_from = 'pm' if pf == 'pm' else 'full'
                period_to = 'am' if pt == 'am' else 'full'
        elif unit == 'hour' and leave.request_unit_hours:
            hour_from = self._pb_hhmm_value(leave.request_hour_from)
            hour_to = self._pb_hhmm_value(leave.request_hour_to)
        return {
            'id': leave.id,
            'employee_id': leave.employee_id.id,
            'employee_name': leave.employee_id.name or '',
            'type_id': leave.holiday_status_id.id,
            'type_name': leave.holiday_status_id.name or '',
            'unit': unit,
            'date_from': start.isoformat() if start else '',
            'date_to': end.isoformat() if end else '',
            'period_from': period_from,
            'period_to': period_to,
            'hour_from': hour_from,
            'hour_to': hour_to,
            'part_label': leave._pb_day_part_label(),
            'note': leave.name or '',
            'reason': leave._pb_sent_back_note(),
            'dates_label': leave._pb_dates_label(),
            'had_documents': bool(leave._pb_documents()),
        }

    def _pb_again_carry(self, vals):
        """The part of the day / the times of this request, written into
        ``vals`` for a new request of the same kind and the same days — the
        staff drawer has no controls for them, so "as before" is kept rather
        than silently dropped. Nothing changes when the kind or the days
        changed (the new request is then whatever was chosen)."""
        self.ensure_one()
        leave = self.sudo()
        same = (int(vals.get('holiday_status_id') or 0) == leave.holiday_status_id.id
                and fields.Date.to_date(vals.get('request_date_from')) == leave.request_date_from
                and fields.Date.to_date(vals.get('request_date_to')) == leave.request_date_to)
        if not same:
            return vals
        if leave.request_unit_half:
            vals.setdefault('request_date_from_period',
                            leave.request_date_from_period)
            vals.setdefault('request_date_to_period',
                            leave.request_date_to_period)
        elif leave.request_unit_hours:
            vals.setdefault('request_hour_from', leave.request_hour_from)
            vals.setdefault('request_hour_to', leave.request_hour_to)
        return vals

    # --------------------------------------------------------------- doors
    @api.model
    def _pb_check_ask_again(self, vals):
        """Every door that names a request to ask again passes here: it must
        be sent back, for the same person, and not asked again before."""
        try:
            old_id = int(vals.get('pb_again_of_id') or 0)
        except (TypeError, ValueError):
            old_id = 0
        old = self.sudo().browse(old_id).exists() if old_id else self.sudo()
        if not old or not old._pb_is_sent_back():
            raise UserError(_(
                "Only a request that was sent back can be asked again."))
        employee = vals.get('employee_id')
        if employee and int(employee) != old.employee_id.id:
            raise UserError(_(
                "A request can only be asked again for the same person."))
        old.invalidate_recordset(['pb_again_id'])
        if old.pb_again_id:
            raise UserError(_("This request was already asked again."))
        return old

    @api.model_create_multi
    def create(self, vals_list):
        olds = {}
        for index, vals in enumerate(vals_list):
            if vals.get('pb_again_of_id'):
                olds[index] = self._pb_check_ask_again(vals)
        leaves = super().create(vals_list)
        for index, old in olds.items():
            old.invalidate_recordset(['pb_again_id'])
            new = leaves[index]
            try:
                with self.env.cr.savepoint():
                    old.message_post(
                        body=_("Asked again as a new request (%s).",
                               new.sudo()._pb_dates_label()),
                        subtype_xmlid='mail.mt_note')
            except Exception:   # noqa: BLE001 — a note never stops a request
                pass
        return leaves


class PbMeHomeSentBack(models.AbstractModel):
    """The employee home's "My requests" list (pb_me_portal) says "Sent back"
    for a sent-back request — "your turn" until it is asked again — instead
    of "Refused". Extended here, by inheritance, rather than in pb_me_portal
    (ledger G76)."""
    _inherit = 'pb.me.home'

    @api.model
    def _my_requests_rows(self, src, emp):
        rows = super()._my_requests_rows(src, emp)
        if src.get('model') != 'hr.leave':
            return rows
        refused = [r['id'] for r in rows if r.get('state') == 'refuse']
        if not refused:
            return rows
        Leave = self.env['hr.leave'].sudo()
        back = set(Leave.browse(refused).filtered('pb_sent_back').ids)
        if not back:
            return rows
        asked = set(Leave.search([('pb_again_of_id', 'in', list(back))])
                    .mapped('pb_again_of_id').ids)
        for row in rows:
            if row['id'] not in back:
                continue
            if row['id'] in asked:
                label, tone = _('Sent back — asked again'), 'off'
            else:
                label, tone = _('Sent back — your turn'), 'act'
            row.update(state_label=label, tone=tone,
                       bucket=REQUEST_BUCKETS[tone])
            if row.get('url'):
                row['url'] = '/my/work/leave#pbew-lv-%s' % row['id']
        return rows

    @api.model
    def _pbme_needs_extra(self, emp, put):
        """WF2 P6d: the employee home's "Needs you" row for time off that was
        sent back and not yet asked again — the same reminder sent-back trips
        and refused expense claims carry (pb_me_portal's T3a hook, no second
        mechanism). It goes away the way theirs do: when the person acts
        (here: asks again, which links the new request to the old one)."""
        super()._pbme_needs_extra(emp, put)
        _ = self.env._
        Leave = self.env['hr.leave'].sudo()
        back = Leave.search([('employee_id', '=', emp.id),
                             ('state', '=', 'refuse'),
                             ('pb_sent_back', '=', True)],
                            order='request_date_from asc, id asc')
        if not back:
            return
        asked = set(Leave.search([('pb_again_of_id', 'in', back.ids)])
                    .mapped('pb_again_of_id').ids)
        back = back.filtered(lambda leave: leave.id not in asked)
        n = len(back)
        if not n:
            return
        first = back[:1]
        # the employee's own form lives in pb_ess_workforce (a soft read, as
        # `_my_requests_sources` does); without it, My requests lists the row
        has_workforce = 'pb.ess.workforce' in self.env
        if n == 1:
            label = _('1 time off request sent back — ask again')
            sentence = _('Your time off request was sent back to you. '
                         'Change what is needed and ask again.')
            url = ('/my/work/leave?again=%s#pbew-ask' % first.id
                   if has_workforce else '/my/requests')
        else:
            label = _('%s time off requests sent back — ask again', n)
            sentence = _('%s time off requests were sent back to you. '
                         'Change what is needed and ask again.', n)
            url = ('/my/work/leave#pbew-lv-%s' % first.id
                   if has_workforce else '/my/requests')
        kind = first.holiday_status_id.name or _('Time off')
        put('leave_sent_back', n, url, label=label,
            sub='%s · %s' % (kind, first._pb_dates_label()),
            icon='umbrella', tone='amber', sentence=sentence)
