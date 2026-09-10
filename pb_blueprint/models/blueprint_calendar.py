# -*- coding: utf-8 -*-
"""The pay calendar and where the money goes — the server half.

Three decisions live here, and none of them is a payroll formula:

* **when inputs close**, so everybody knows the day after which a change waits
  for the next run;
* **which day is payday**, expressed as a rule rather than a date — "the second
  last working day" survives every month, a date does not — and shown as the
  real date it lands on next, worked out from the company's own working
  calendar and the public holidays on it;
* **what to do with a late input**, which is a policy, not a setting: carrying
  it forward, approving an off-cycle run, or reopening under two signatures are
  three different promises to the people being paid.

Payment currency is the configuration's own and is shown, never chosen: a
configuration that calculates in one currency and pays in another is a bank
conversion at release, not a payroll formula. The bank identifier type is a
preference the bank layouts read; no account number is ever invented here.
"""
import json
import logging
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .payday import DEFAULT_WORKDAYS, PAYDAY_RULES, next_month, payday_for

_logger = logging.getLogger(__name__)

LATE_POLICIES = ('next_cycle', 'off_cycle', 'reopen')
BANK_ID_TYPES = ('domestic', 'swift')

DEFAULT_CALENDAR = {
    'cutoff_day': 20,
    'payday_rule': 'last_working',
    'payday_day': 25,
    'late_inputs': 'next_cycle',
}

DEFAULT_PAYMENT = {
    'bank_id_type': 'domestic',
}


class PbBlueprintCalendar(models.AbstractModel):
    _inherit = 'pb.blueprint.studio'

    # ==================================================================
    # Reading the tab
    # ==================================================================
    @api.model
    def bp_calendar_data(self, config_id):
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        calendar, payment = self._calendar_prefs(blueprint)
        return {
            'ok': True,
            'calendar': calendar,
            'payment': dict(payment, currency=config.currency_id.name or '',
                            currency_symbol=config.currency_id.symbol or ''),
            'preview': self._payday_preview(config, blueprint, calendar),
            'doors': {'pay_delivery': self._has_pay_delivery()},
            'cycle_label': self._cycle_label(config),
            'editable': config.state == 'draft' and not self._has_payslips(config),
            'readonly_reason': self._tax_readonly_reason(config),
            'revision': blueprint.revision if blueprint else 0,
        }

    def _cycle_label(self, config):
        from .blueprint_studio import cycle_label
        return cycle_label(config.cycle_type)

    def _has_pay_delivery(self):
        return bool(self.env.ref('pb_pay_delivery.action_pb_pay_delivery',
                                 raise_if_not_found=False))

    def _calendar_prefs(self, blueprint):
        stored = blueprint.calendar() if blueprint else {}
        calendar = dict(DEFAULT_CALENDAR)
        payment = dict(DEFAULT_PAYMENT)
        calendar.update({k: v for k, v in (stored.get('calendar') or {}).items()
                         if k in DEFAULT_CALENDAR})
        payment.update({k: v for k, v in (stored.get('payment') or {}).items()
                        if k in DEFAULT_PAYMENT})
        calendar['cutoff_day'] = self._clamp(calendar['cutoff_day'], 1, 28,
                                             DEFAULT_CALENDAR['cutoff_day'])
        calendar['payday_day'] = self._clamp(calendar['payday_day'], 1, 31,
                                             DEFAULT_CALENDAR['payday_day'])
        if calendar['payday_rule'] not in PAYDAY_RULES:
            calendar['payday_rule'] = DEFAULT_CALENDAR['payday_rule']
        if calendar['late_inputs'] not in LATE_POLICIES:
            calendar['late_inputs'] = DEFAULT_CALENDAR['late_inputs']
        if payment['bank_id_type'] not in BANK_ID_TYPES:
            payment['bank_id_type'] = DEFAULT_PAYMENT['bank_id_type']
        return calendar, payment

    @staticmethod
    def _clamp(value, low, high, fallback):
        """Pull a stored number back into range — for READING a preference."""
        try:
            number = int(value)
        except (TypeError, ValueError):
            return fallback
        return min(high, max(low, number))

    @staticmethod
    def _whole(value, low, high):
        """A whole number inside the range, or None — for SAVING one.

        Deliberately not the same function as `_clamp`: silently pulling a
        person's 31 back to 28 changes what they asked for without telling
        them, and a cut-off day is a promise to everybody being paid.
        """
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if low <= number <= high else None

    # ==================================================================
    # The payday preview
    # ==================================================================
    @api.model
    def bp_calendar_preview(self, config_id, month=None, rule=None, day=None):
        """The real date the chosen rule lands on, before anything is saved."""
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        calendar, _payment = self._calendar_prefs(blueprint)
        if rule in PAYDAY_RULES:
            calendar['payday_rule'] = rule
        if day is not None:
            calendar['payday_day'] = self._clamp(day, 1, 31,
                                                 calendar['payday_day'])
        return {'ok': True,
                'preview': self._payday_preview(config, blueprint, calendar, month)}

    def _payday_preview(self, config, blueprint, calendar, month=None):
        """When the next run pays, and what it stepped over to get there."""
        year, month_no = self._target_month(blueprint, month)
        workdays, holidays, calendar_name, has_calendar = self._company_calendar(
            config, year, month_no)
        when, weekends, holiday_count = payday_for(
            calendar['payday_rule'], calendar['payday_day'], year, month_no,
            workdays, holidays)
        if not when:
            return None
        return {
            'date': str(when),
            'weekday': self._weekday_name(when),
            'long': self._long_date(when),
            'skipped_weekends': weekends,
            'skipped_holidays': holiday_count,
            'calendar_name': calendar_name,
            'has_calendar': has_calendar,
            'month_label': self._month_name(month_no),
            'year': year,
        }

    def _target_month(self, blueprint, month=None):
        """The month the preview is about.

        The month the configuration is meant to start in, unless that is
        already behind us — in which case the month after this one, because a
        payday that has been and gone tells nobody anything.
        """
        if month:
            try:
                parts = str(month).split('-')
                return int(parts[0]), int(parts[1])
            except (ValueError, IndexError):
                pass
        today = fields.Date.context_today(self)
        start = blueprint.effective_from if blueprint else None
        if start and (start.year, start.month) >= (today.year, today.month):
            return start.year, start.month
        return next_month(today.year, today.month)

    def _company_calendar(self, config, year, month_no):
        """``(workdays, holidays, name, has_calendar)`` for one company.

        Working days come from the company's own working calendar; public
        holidays are the closures on that calendar that belong to nobody in
        particular (a leave with no person on it is a day the company is shut,
        which is exactly what a public holiday is).
        """
        company = config.company_id
        work_calendar = getattr(company, 'resource_calendar_id', False)
        if not work_calendar:
            return set(DEFAULT_WORKDAYS), set(), '', False
        days = set()
        for attendance in work_calendar.attendance_ids:
            try:
                days.add(int(attendance.dayofweek))
            except (TypeError, ValueError):
                continue
        if not days:
            days = set(DEFAULT_WORKDAYS)
        holidays = self._public_holidays(work_calendar, year, month_no)
        return days, holidays, work_calendar.name or '', True

    def _public_holidays(self, work_calendar, year, month_no):
        Leave = self.env.get('resource.calendar.leaves')
        if Leave is None:
            return set()
        first = date(year, month_no, 1)
        last_year, last_month = next_month(year, month_no)
        last = date(last_year, last_month, 1)
        try:
            leaves = Leave.sudo().search([
                ('resource_id', '=', False),
                '|', ('calendar_id', '=', work_calendar.id),
                ('calendar_id', '=', False),
                ('date_from', '<', fields.Datetime.to_datetime(str(last))),
                ('date_to', '>=', fields.Datetime.to_datetime(str(first))),
            ])
        except Exception as exc:            # pragma: no cover - defensive
            _logger.info("Guided setup: public holidays unavailable: %s", exc)
            return set()
        out = set()
        for leave in leaves:
            start = fields.Date.to_date(leave.date_from)
            end = fields.Date.to_date(leave.date_to)
            if not start or not end:
                continue
            cursor = start
            while cursor <= end and (cursor - start).days < 40:
                if cursor.year == year and cursor.month == month_no:
                    out.add(cursor)
                cursor += timedelta(days=1)
        return out

    @api.model
    def _weekday_name(self, when):
        return [_("Monday"), _("Tuesday"), _("Wednesday"), _("Thursday"),
                _("Friday"), _("Saturday"), _("Sunday")][when.weekday()]

    @api.model
    def _month_name(self, month_no):
        return [_("January"), _("February"), _("March"), _("April"), _("May"),
                _("June"), _("July"), _("August"), _("September"),
                _("October"), _("November"), _("December")][month_no - 1]

    def _long_date(self, when):
        return _("%(weekday)s %(day)s %(month)s %(year)s",
                 weekday=self._weekday_name(when), day=when.day,
                 month=self._month_name(when.month), year=when.year)

    # ==================================================================
    # Saving
    # ==================================================================
    @api.model
    def bp_calendar_save(self, config_id, calendar=None, payment=None,
                         revision=None):
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        conflict = self._revision_guard(blueprint, revision)
        if conflict:
            return conflict
        if config.state != 'draft' or self._has_payslips(config):
            return {'ok': False, 'reason': self._tax_readonly_reason(config)}

        current, current_payment = self._calendar_prefs(blueprint)
        calendar = calendar or {}
        payment = payment or {}

        cutoff = self._whole(calendar.get('cutoff_day', current['cutoff_day']),
                             1, 28)
        if cutoff is None:
            return {'ok': False, 'reason': _(
                "The cut-off day is a day between 1 and 28, so it exists in "
                "every month.")}
        rule = calendar.get('payday_rule', current['payday_rule'])
        if rule not in PAYDAY_RULES:
            return {'ok': False, 'reason': _(
                "Choose one of the three payday rules.")}
        day = self._whole(calendar.get('payday_day', current['payday_day']), 1, 31)
        if day is None:
            return {'ok': False, 'reason': _(
                "A fixed payday is a day between 1 and 31.")}
        late = calendar.get('late_inputs', current['late_inputs'])
        if late not in LATE_POLICIES:
            return {'ok': False, 'reason': _(
                "Choose what happens to an input that arrives late.")}
        bank = payment.get('bank_id_type', current_payment['bank_id_type'])
        if bank not in BANK_ID_TYPES:
            return {'ok': False, 'reason': _(
                "Choose how the bank identifies an account.")}

        clean = {'cutoff_day': cutoff, 'payday_rule': rule, 'payday_day': day,
                 'late_inputs': late}
        try:
            blueprint.write({
                'calendar_json': json.dumps(
                    {'calendar': clean, 'payment': {'bank_id_type': bank}},
                    sort_keys=True),
                'revision': blueprint.revision + 1,
            })
        except AccessError:
            raise
        except Exception as exc:
            return {'ok': False, 'reason': self._plain(exc)}
        return {'ok': True, 'calendar': clean,
                'payment': {'bank_id_type': bank,
                            'currency': config.currency_id.name or '',
                            'currency_symbol': config.currency_id.symbol or ''},
                'preview': self._payday_preview(config, blueprint, clean),
                'revision': blueprint.revision}

    # ==================================================================
    # The door to the bank layouts
    # ==================================================================
    @api.model
    def bp_pay_delivery_action(self, config_id):
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        action = self.env.ref('pb_pay_delivery.action_pb_pay_delivery',
                              raise_if_not_found=False)
        if not action:
            return {'ok': False, 'reason': _(
                "Bank file layouts are not available on this database.")}
        back = {'label': _("New configuration"), 'tag': 'pb_blueprint',
                'context': {'config_id': config.id}}
        return {
            'ok': True,
            'action': {
                'type': 'ir.actions.client',
                'tag': action.tag,
                'name': action.name,
                'target': 'current',
                'context': {'pb_back': back},
            },
        }
