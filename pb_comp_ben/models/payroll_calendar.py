# -*- coding: utf-8 -*-
"""`pb.payroll.calendar` — when inputs close, and when people are paid.

A payroll month has two dates that everybody needs and nobody writes down: the
day changes stop being accepted, and the day money arrives. They live in a
spreadsheet, in somebody's head, or in an email sent every month by hand.

THE REMINDERS ARE THE POINT. A calendar nobody is reminded by is a calendar
nobody reads. The daily job is idempotent per (month, offset): it searches for
the note it would leave before it leaves it, so a cron that runs twice, or a
server restarted mid-morning, sends one email and not two (the vault's
`_cron_expiry_check` shape).

IT SHIPS SWITCHED OFF (R54). The first night after an install would otherwise
email every HR manager about every cut-off already inside its window. Off, the
job COUNTS what it would have sent and logs the number, and the lens says the
same thing on screen with the same number.
"""

import logging
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .comp_common import GROUP_HEAD, GROUP_USER, P_REMINDERS, flag

_logger = logging.getLogger(__name__)

#: How many months "Build the year ahead" makes.
BUILD_MONTHS = 12


class PbPayrollCalendar(models.Model):
    _name = 'pb.payroll.calendar'
    _description = 'Payroll month'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'month desc, id desc'

    #: R3 — `activity_schedule()` lives on `mail.activity.mixin`, not on
    #: `mail.thread`; a model that inherits only the latter raises AttributeError
    #: inside the per-record try/except and reports zero nudges forever.

    name = fields.Char(compute='_compute_name', store=True, string='Month')
    month = fields.Date(string='Month', required=True, index=True,
                        help='Any day in the month; the first is what is kept.')
    cutoff_date = fields.Date(string='Changes close', required=True,
                              tracking=True)
    pay_date = fields.Date(string='People are paid', required=True,
                           tracking=True)
    country_id = fields.Many2one('res.country', string='Country')
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)
    reminder_offset_days = fields.Char(
        string='Remind this many days before', default='5,2,0',
        help='Days before the closing date to send a reminder, separated by '
             'commas. 0 means on the day itself.')
    state = fields.Selection(
        [('upcoming', 'Ahead'), ('closed', 'Closed')],
        default='upcoming', required=True, tracking=True, string='Status')
    notes = fields.Text(string='Notes')
    reminder_log = fields.Text(string='Reminders sent', readonly=True,
                               copy=False)

    _month_company_uniq = models.Constraint(
        'unique(month, company_id)',
        'There is already a payroll month for that month.')

    @api.depends('month')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.month.strftime('%B %Y') if rec.month else _('Month')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('month'):
                vals['month'] = fields.Date.to_date(vals['month']).replace(day=1)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('month'):
            vals['month'] = fields.Date.to_date(vals['month']).replace(day=1)
        return super().write(vals)

    # -------------------------------------------------------------- offsets
    def _offsets(self):
        """The reminder offsets, largest first, as clean integers."""
        self.ensure_one()
        raw = self.reminder_offset_days or '5,2,0'
        out = []
        for piece in str(raw).split(','):
            piece = piece.strip()
            if not piece:
                continue
            try:
                out.append(abs(int(float(piece))))
            except (TypeError, ValueError):
                continue
        return sorted(set(out), reverse=True)

    def action_close(self):
        for rec in self:
            rec.state = 'closed'
            rec.message_post(body=_("This month is closed to changes."))
        return True

    def action_reopen(self):
        for rec in self:
            rec.state = 'upcoming'
        return True

    # ------------------------------------------------------------ the builder
    @api.model
    def build_year(self, cutoff_day, pay_day, start_month=False,
                   company_id=False, country_id=False, months=BUILD_MONTHS,
                   offsets='5,2,0'):
        """Make the next twelve months from one pattern.

        Skips a month that already exists rather than refusing the whole batch —
        somebody who builds a year in March and again in April wants the nine
        months they have not got, not an error message.
        """
        try:
            cutoff_day = max(1, min(28, int(cutoff_day)))
            pay_day = max(1, min(28, int(pay_day)))
            months = max(1, min(24, int(months)))
        except (TypeError, ValueError):
            raise UserError(_(
                "The closing day and the pay day have to be day numbers "
                "between 1 and 28."))
        company = self.env['res.company'].browse(int(company_id)) \
            if company_id else self.env.company
        first = fields.Date.to_date(start_month) if start_month else \
            fields.Date.context_today(self)
        first = first.replace(day=1)
        made, skipped = [], 0
        for i in range(months):
            month = _add_months(first, i)
            if self.search_count([('month', '=', month),
                                  ('company_id', '=', company.id)]):
                skipped += 1
                continue
            cutoff = month.replace(day=cutoff_day)
            # The pay day is in the month AFTER the closing date when the
            # pattern says so — paying on the 1st against a cut-off on the 25th
            # means the 1st of the NEXT month, which is what everybody means and
            # nobody writes down.
            pay = month.replace(day=pay_day)
            if pay <= cutoff:
                pay = _add_months(month, 1).replace(day=pay_day)
            made.append(self.create({
                'month': month,
                'cutoff_date': cutoff,
                'pay_date': pay,
                'company_id': company.id,
                'country_id': int(country_id) if country_id else False,
                'reminder_offset_days': offsets or '5,2,0',
            }).id)
        return {'created': len(made), 'skipped': skipped, 'ids': made}

    # ----------------------------------------------------------- the reminders
    @api.model
    def _cron_payroll_calendar_reminders(self):
        """Daily. One mail per (month, offset), ever.

        R36 — "today" is taken from the SERVER, because a date written from a
        laptop a day ahead makes a date-driven job look broken when it is fine.
        """
        today = fields.Date.context_today(self)
        on = flag(self.env, P_REMINDERS)
        sent, would = 0, 0
        rows = self.search([('state', '=', 'upcoming'),
                            ('cutoff_date', '>=', today - timedelta(days=1))])
        for cal in rows:
            try:
                offset = cal._due_offset(today)
                if offset is None:
                    continue
                if cal._already_reminded(offset):
                    continue
                if not on:
                    would += 1
                    continue
                if cal._send_reminder(offset):
                    cal._note_reminder(offset)
                    sent += 1
            except Exception:               # noqa: BLE001 — one month, not all
                _logger.exception(
                    'pb_comp_ben: reminder failed for payroll month %s', cal.id)
        if on:
            _logger.info('pb_comp_ben: sent %s cut-off reminder(s)', sent)
        else:
            _logger.info(
                'pb_comp_ben: cut-off reminders are switched off — %s would '
                'have gone out today', would)
        return {'sent': sent, 'would': would, 'enabled': on}

    def _due_offset(self, today):
        """Which reminder is due today, if any."""
        self.ensure_one()
        if not self.cutoff_date:
            return None
        days = (self.cutoff_date - today).days
        return days if days in self._offsets() else None

    def _already_reminded(self, offset):
        self.ensure_one()
        return ('#%s' % offset) in (self.reminder_log or '')

    def _note_reminder(self, offset):
        self.ensure_one()
        stamp = '#%s %s' % (offset, fields.Date.to_string(
            fields.Date.context_today(self)))
        self.reminder_log = '\n'.join(
            filter(None, [self.reminder_log or '', stamp]))

    def _recipients(self):
        """Who is told. The pay team, by GROUP — transitively.

        R7 — `res.users.group_ids` is DIRECT membership only and misses everyone
        who holds a group through `implied_ids`, which is most administrators.
        `res.groups.all_user_ids` is the transitive set.
        """
        self.ensure_one()
        emails = []
        for xmlid in (GROUP_HEAD, GROUP_USER):
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if not group:
                continue
            for user in group.sudo().all_user_ids:
                if user.email and user.email not in emails:
                    emails.append(user.email)
        return emails

    def _send_reminder(self, offset):
        """One email to the pay team. Recipient passed EXPLICITLY (R6)."""
        self.ensure_one()
        template = self.env.ref('pb_comp_ben.mail_template_cutoff_reminder',
                                raise_if_not_found=False)
        if not template:
            _logger.warning('pb_comp_ben: the cut-off reminder email is missing')
            return False
        to = self._recipients()
        if not to:
            self.message_post(body=_(
                "Nobody in the pay team has an email address, so the reminder "
                "was not sent."))
            return False
        template.sudo().with_context(
            pb_cutoff_offset=offset).send_mail(
                self.id, force_send=False,
                email_values={'email_to': ','.join(to)})
        self.message_post(body=_(
            "Reminder sent — %(when)s.",
            when=(_("changes close today") if offset == 0
                  else _("%s days before changes close") % offset)))
        return True

    # -------------------------------------------------------------- the reads
    @api.model
    def next_cutoff(self, company_id=False):
        """The next month whose changes have not closed yet."""
        today = fields.Date.context_today(self)
        domain = [('state', '=', 'upcoming'), ('cutoff_date', '>=', today)]
        if company_id:
            domain.append(('company_id', '=', int(company_id)))
        return self.search(domain, order='cutoff_date, id', limit=1)


def _add_months(day, n):
    """The first of the month `n` months after `day`'s month."""
    month0 = day.month - 1 + n
    year = day.year + month0 // 12
    month = month0 % 12 + 1
    return date(year, month, 1)
