# -*- coding: utf-8 -*-
"""WDGAP W2-A — the tax year of a pay scheme, in ONE place.

Before this, three places hard-coded the calendar year (UPDATES ledger U42):
the engine's ``history.ytd.<CODE>`` source, the Updates year-to-date sheet and
the employee's tax sheet on My Payobook. A scheme now says in which month its
tax year starts (``hr.formula.config.tax_year_start_month``, default January).

Every caller asks the helpers below; nobody re-derives a year start:

* ``tax_year_key(month, day)`` — the tax year a day belongs to, as the calendar
  year it STARTS in (``2026`` for 1 Apr 2026 – 31 Mar 2027 with an April start;
  for January it is simply ``day.year``, so every stored integer year keeps
  meaning exactly what it meant before);
* ``tax_year_bounds_for_key(month, key)`` / ``tax_year_bounds(month, day)`` —
  ``(first_day, last_day)``;
* ``tax_year_label_for_key(month, key)`` — ``"2026"`` for a calendar tax year,
  ``"2026–27"`` otherwise;
* ``tax_quarter_bounds(month, day)`` — the quarter of the TAX year.

With the default (January) every answer is the calendar-year answer used
before — the governing rule of W2-A ("no figure anywhere changes").

The group's financial-year month (``pb_group.fiscal_start_month``) is NOT used:
a company's books year and its tax year differ in several countries.
"""
from datetime import date, timedelta

from odoo import _, api, fields, models

#: Selection keys are text ('1'..'12'); helpers take the month as an int.
MONTHS = [
    ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
    ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
    ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December'),
]
DEFAULT_MONTH = 1
#: Payslip states that mean "finished" (the Updates desk's set).
DONE_STATES = ('done', 'paid')


def month_of(value):
    """The start month as an int 1..12 from a config, a selection key or an
    int. Anything unreadable (an empty recordset, None, '') is January."""
    if hasattr(value, '_name'):
        value = value.tax_year_start_month if len(value) == 1 else None
    try:
        month = int(value)
    except (TypeError, ValueError):
        return DEFAULT_MONTH
    return month if 1 <= month <= 12 else DEFAULT_MONTH


def _add_months(day, months):
    """The first of the month `months` after `day`'s month (day must be a 1st)."""
    index = day.year * 12 + (day.month - 1) + months
    return date(index // 12, index % 12 + 1, 1)


def tax_year_key(month, day):
    """The calendar year the tax year containing `day` starts in."""
    month = month_of(month)
    day = fields.Date.to_date(day)
    return day.year if day.month >= month else day.year - 1


def tax_year_bounds_for_key(month, key):
    month = month_of(month)
    first = date(int(key), month, 1)
    return first, _add_months(first, 12) - timedelta(days=1)


def tax_year_bounds(month, day):
    """`(first_day, last_day)` of the tax year that contains `day`."""
    return tax_year_bounds_for_key(month, tax_year_key(month, day))


def tax_year_label_for_key(month, key):
    """"2026" for a calendar tax year, "2026–27" for one that starts later."""
    month, key = month_of(month), int(key)
    if month == 1:
        return str(key)
    return '%d–%02d' % (key, (key + 1) % 100)


def tax_year_label(month, day):
    return tax_year_label_for_key(month, tax_year_key(month, day))


def tax_quarter_bounds(month, day):
    """`(first_day, last_day)` of the quarter of the TAX year containing `day`
    (quarters of three months counted from the tax year's first month)."""
    month = month_of(month)
    day = fields.Date.to_date(day)
    first, _last = tax_year_bounds(month, day)
    offset = (day.year * 12 + day.month) - (first.year * 12 + first.month)
    q_first = _add_months(first, (offset // 3) * 3)
    return q_first, _add_months(q_first, 3) - timedelta(days=1)


class HrFormulaConfigTaxYear(models.Model):
    _inherit = 'hr.formula.config'

    tax_year_start_month = fields.Selection(
        MONTHS, string='Tax year starts in', default='1', required=True, tracking=True,
        help="The month this scheme's tax year starts in. Year-to-date figures "
             "(earlier this year, earlier this quarter) are counted from it. "
             "January means the calendar year.")

    # ------------------------------------------------------------------
    # The helpers, on the scheme (an empty recordset is January)
    # ------------------------------------------------------------------
    def _pb_tax_year_month(self):
        return month_of(self[:1]) if self else DEFAULT_MONTH

    def _pb_tax_year_key(self, on_date):
        return tax_year_key(self._pb_tax_year_month(), on_date)

    def _pb_tax_year_bounds(self, on_date):
        return tax_year_bounds(self._pb_tax_year_month(), on_date)

    def _pb_tax_year_label(self, on_date):
        return tax_year_label(self._pb_tax_year_month(), on_date)

    def _pb_tax_quarter_bounds(self, on_date):
        return tax_quarter_bounds(self._pb_tax_year_month(), on_date)

    # Month-based twins for callers that hold a month, not a scheme (the
    # Updates desk, the employee tax sheet), reached through the registry so
    # no other module imports this file.
    @api.model
    def _pb_tax_year_key_for(self, month, on_date):
        return tax_year_key(month, on_date)

    @api.model
    def _pb_tax_year_bounds_for(self, month, key):
        return tax_year_bounds_for_key(month, key)

    @api.model
    def _pb_tax_year_label_for(self, month, key):
        return tax_year_label_for_key(month, key)

    # ------------------------------------------------------------------
    # R2 — changing the month on a scheme with finished payslips
    # ------------------------------------------------------------------
    def _pb_tax_year_month_name(self, month):
        names = dict(self._fields['tax_year_start_month']._description_selection(self.env))
        return names.get(str(month_of(month)), '')

    def _pb_tax_year_change_warning(self, new_month):
        """The plain sentence shown when a scheme that already has finished
        payslips moves its tax year start, or ''. Nothing is recomputed: the
        change is allowed and only counts from now on."""
        self.ensure_one()
        if not self.id or month_of(new_month) == self._pb_tax_year_month():
            return ''
        done = self.env['hr.payslip'].sudo().search_count(
            [('formula_config_id', '=', self.id), ('state', 'in', DONE_STATES)], limit=1)
        if not done:
            return ''
        return _("Year-to-date figures for this scheme will be counted from %(month)s from "
                 "now on. Finished payslips are not changed.",
                 month=self._pb_tax_year_month_name(new_month))

    @api.onchange('tax_year_start_month')
    def _onchange_pb_tax_year_start_month(self):
        origin = self._origin
        if not origin or not origin.id:
            return None
        message = origin._pb_tax_year_change_warning(self.tax_year_start_month)
        if message:
            return {'warning': {'title': _("Tax year"), 'message': message}}
        return None
