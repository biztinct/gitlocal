# -*- coding: utf-8 -*-
"""UPDATES P5 (owner decision D20) — year-to-date figures before Payobook.

What a person was paid and taxed THIS tax year before their company started
on Payobook, loaded from a sheet for many people at once, approved on the
pay route, and kept in ONE store (`pb.updates.ytd.line`). Rails (handover §5):

  * no tax formula, bracket table, country pack or scheme rule is changed,
    and there is no "opening payslip": these figures are never a payslip, so
    a bank file, pay totals, analytics, contribution reports and previous-run
    comparisons can never count them;
  * the tax year is the calendar year (ledger U42), and it is the year of the
    sheet's "Figures cover up to" date;
  * nothing reaches a pay run unless a payroll manager has mapped an INPUT pay
    item of a pay scheme to a figure (`pb.updates.ytd.map`); with no mapping,
    or no stored figure for a payslip's person, both pay-run seams return
    exactly what they returned before (test Y9, `updates_ytd_payrun.py`);
  * a figure a FINISHED payslip used (`pb.updates.ytd.use`, state `used`) can
    no longer be replaced, cleared or undone from Updates.

Figures (`FIGURES`): six fixed ones with translated labels, plus any pay item
of the company's schemes a payroll manager names as a figure — its key is
then the pay item's code, so "paid in Payobook" can be summed for it.

Approval: the named update's ONE `pb.records.apply` (flag `updates_ytd`), on
the records (pay) route — same process key, routes and inbox as every pay
change (clone of P2d / P4).

Loaded after `updates_leave_desk` (models/__init__.py). Constants live HERE,
in the file that defines the models (ledger G21); the desk and the pay-run
files import from it.
"""
import calendar
import json
import logging
import re
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date, formatLang

_logger = logging.getLogger(__name__)

#: Card ids of the sheet: `y:<figure key>`; the optional evidence column.
PREFIX = 'y:'
SOURCE_ID = 'y:_source'
GROUP = 'ytd'
#: The six fixed figures, in the sheet's order.
FIGURES = ('gross', 'taxable', 'tax', 'ee_social', 'er_social', 'months')
COUNT_FIGURES = ('months',)
#: Pay item codes that USUALLY carry a fixed figure. Only codes the company's
#: own employee tax summary shows, or its schemes have, are used — a default,
#: changed on the set-up screen (`pb.updates.ytd.figure.codes`).
DEFAULT_CODES = {
    'gross': ('GROSS', 'GROSSPAY', 'TOTALGROSS'),
    'taxable': ('TXBASE', 'TAXABLE', 'TAXABLEINCOME', 'PITBASE'),
    'tax': ('PIT', 'TAX', 'INCOMETAX', 'PPH21', 'TDS', 'PAYE'),
    'ee_social': ('SIEMP', 'HIEMP', 'UIEMP', 'BPJSEMP', 'EPFEMP', 'CPFEMP', 'SSEMP'),
    'er_social': ('SIER', 'HIER', 'UIER', 'SICOMP', 'HICOMP', 'UICOMP', 'BPJSER', 'EPFER',
                  'CPFER'),
    'months': (),
}
#: How a mapped pay item is filled (handover §4.4).
BASES = ('opening', 'before_period', 'with_period')
#: Rows that stand as a person's figure, or are about to.
LIVE = ('waiting', 'set')
#: Payslip states that mean "finished".
DONE_SLIP_STATES = ('done', 'paid')
#: How a value from Updates says so in a payslip's sources (`via`).
YTD_VIA = 'updates_ytd'
#: The furthest ahead a "Figures cover up to" date may be (a sheet made a few
#: weeks before the first Payobook pay period).
AHEAD_DAYS = 62
#: Who may name figures and send them to a pay run (a payroll manager; the
#: Tenant administrator role reaches it through "Payroll administrator").
SETUP_GROUPS = ('base.group_system', 'pb_hr_payroll_base.group_payroll_base_manager',
                'pb_hr_payroll_formula.group_formula_manager')
#: Who may see the figures (they are pay data): payroll officers and up.
READ_GROUPS = SETUP_GROUPS + ('pb_hr_payroll_base.group_payroll_base_officer',)

# Teach the "why" vocabulary the new word once (soft; the Source Atlas reads it).
try:  # pragma: no cover — import-time registration only
    from odoo.addons.pb_hr_payroll_formula.models import input_provenance as _ip
    if YTD_VIA not in _ip.VIAS:
        _ip.VIAS = tuple(_ip.VIAS) + (YTD_VIA,)
except Exception:  # noqa: BLE001
    pass
try:  # pragma: no cover
    from odoo.addons.pb_source_atlas.models import pb_source_atlas as _atlas
    _atlas.VIA_LABELS.setdefault(YTD_VIA, 'a year-to-date figure from Updates')
except Exception:  # noqa: BLE001
    pass


def card_id(key):
    return '%s%s' % (PREFIX, key)


def key_of(field_id):
    """The figure key of a card id, or ''."""
    text = str(field_id or '')
    if not text.startswith(PREFIX) or text == SOURCE_ID:
        return ''
    return text[len(PREFIX):]


def day_label(env, day):
    return format_date(env, day, date_format='d MMM y') if day else ''


def month_floor(day):
    return day.replace(day=1)


def month_end(day):
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def months_between(first, last):
    """Every month (1st) from `first`'s month to `last`'s month, inclusive."""
    out = []
    if not first or not last or first > last:
        return out
    cur = month_floor(first)
    while cur <= last:
        out.append(cur)
        cur = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
    return out


def number_text(value):
    try:
        value = float(value or 0.0)
    except (TypeError, ValueError):
        return ''
    text = ('%.2f' % value).rstrip('0').rstrip('.')
    return text or '0'


class PbUpdatesYtdFigure(models.Model):
    """A company's set-up of one figure: which pay items "paid in Payobook"
    adds up for a fixed figure, or a pay item named as a figure of its own."""
    _name = 'pb.updates.ytd.figure'
    _description = 'Year-to-date figure set-up'
    _order = 'company_id, sequence, id'

    company_id = fields.Many2one('res.company', string='Company', required=True, index=True,
                                 default=lambda self: self.env.company, readonly=True)
    key = fields.Char(string='Figure', required=True, readonly=True)
    item = fields.Boolean(string='A pay item named as a figure', readonly=True)
    label = fields.Char(string='Name', readonly=True)
    #: Comma-separated pay item codes "paid in Payobook" adds up.
    codes = fields.Char(string='Pay items it adds up', readonly=True)
    sequence = fields.Integer(default=100, readonly=True)
    active = fields.Boolean(default=True, readonly=True)

    _company_key_uniq = models.Constraint(
        'UNIQUE(company_id, key)', 'This company already has this figure.')

    def code_list(self):
        self.ensure_one()
        return [c.strip() for c in (self.codes or '').split(',') if c.strip()]


class PbUpdatesYtdMap(models.Model):
    """D20 — the ONLY way a figure reaches a pay run: a payroll manager names an
    input pay item of a pay scheme and the figure it receives."""
    _name = 'pb.updates.ytd.map'
    _description = 'Year-to-date figure sent to a pay item'
    _order = 'config_id, code, id'

    company_id = fields.Many2one('res.company', string='Company', required=True, index=True,
                                 default=lambda self: self.env.company, readonly=True)
    config_id = fields.Many2one('hr.formula.config', string='Pay scheme', required=True,
                                index=True, ondelete='cascade', readonly=True)
    code = fields.Char(string='Pay item code', required=True, readonly=True)
    figure = fields.Char(string='Figure', required=True, readonly=True)
    basis = fields.Selection([
        ('opening', 'Before Payobook only'),
        ('before_period', 'Total so far this year, before this pay period'),
        ('with_period', 'Months so far this year, including this pay period'),
    ], string='What it receives', default='before_period', required=True, readonly=True)
    set_by_id = fields.Many2one('res.users', string='Set by', default=lambda self: self.env.user,
                                readonly=True)
    set_at = fields.Datetime(string='Set at', default=fields.Datetime.now, readonly=True)

    _scheme_code_uniq = models.Constraint(
        'UNIQUE(config_id, code)', 'This pay item already receives a figure.')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.cr.cache.pop(MAP_CACHE, None)
        return records

    def write(self, vals):
        result = super().write(vals)
        self.env.cr.cache.pop(MAP_CACHE, None)
        return result

    def unlink(self):
        result = super().unlink()
        self.env.cr.cache.pop(MAP_CACHE, None)
        return result


#: Per-cursor cache of the mappings: `{config id: [(code, figure, basis, id)]}`.
#: A pay run asks once per payslip; a scheme with none answers from here.
MAP_CACHE = 'pb_updates_ytd_maps'


class PbUpdatesYtdLine(models.Model):
    _name = 'pb.updates.ytd.line'
    _description = 'Year-to-date figure before Payobook'
    _order = 'tax_year desc, batch_id desc, id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True,
                                  ondelete='cascade', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True,
                                 readonly=True)
    tax_year = fields.Integer(string='Tax year', required=True, index=True, readonly=True)
    figure = fields.Char(string='Figure', required=True, index=True, readonly=True)
    label = fields.Char(string='Figure name', readonly=True)
    amount = fields.Float(string='Before Payobook', readonly=True)
    covers_to = fields.Date(string='Figures cover up to', required=True, readonly=True)
    source_note = fields.Char(string='Source', readonly=True)
    action = fields.Selection([('set', 'Set this figure'), ('clear', 'Remove')],
                              string='What it does', default='set', required=True, readonly=True)
    batch_id = fields.Many2one('pb.updates.batch', string='Named update', required=True,
                               index=True, ondelete='cascade', readonly=True)
    apply_id = fields.Many2one('pb.records.apply', string='Approval proposal', index=True,
                               ondelete='set null', readonly=True)
    replaces_id = fields.Many2one('pb.updates.ytd.line', string='Replaces',
                                  ondelete='set null', readonly=True)
    state = fields.Selection([
        ('waiting', 'Waiting for approval'),
        ('set', 'Set'),
        ('replaced', 'Replaced by a later update'),
        ('cleared', 'Removed'),
        ('undone', 'Undone'),
        ('refused', 'Could not be set'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Sent back'),
        ('rejected', 'Turned down'),
    ], string='Status', default='waiting', required=True, index=True, readonly=True)
    reason = fields.Text(string='Why', readonly=True)
    undone_at = fields.Datetime(string='Undone at', readonly=True)
    undone_by_id = fields.Many2one('res.users', string='Undone by', readonly=True)
    note = fields.Text(string='History', readonly=True)
    use_ids = fields.One2many('pb.updates.ytd.use', 'line_id', string='Used by payslips')

    _one_set = models.UniqueIndex(
        "(employee_id, tax_year, figure) WHERE state = 'set'",
        "This person already has this year-to-date figure for that tax year.")
    _amount_not_negative = models.Constraint(
        'CHECK(amount >= 0)', 'A year-to-date figure cannot be negative.')

    # ------------------------------------------------------------ words
    @api.model
    def _figure_label(self, key, company=None):
        labels = {
            'gross': _("Gross pay"),
            'taxable': _("Taxable pay"),
            'tax': _("Income tax withheld"),
            'ee_social': _("Employee social contributions"),
            'er_social': _("Employer social contributions"),
            'months': _("Months counted"),
        }
        if key in labels:
            return labels[key]
        company = company or self.env.company
        row = self.env['pb.updates.ytd.figure'].sudo().search(
            [('company_id', '=', company.id), ('key', '=', key)], limit=1)
        return row.label or key

    @api.model
    def _is_count(self, key):
        return key in COUNT_FIGURES

    @api.model
    def _value_label(self, key, value, currency=None):
        if self._is_count(key):
            n = int(round(float(value or 0.0)))
            return _("1 month") if n == 1 else _("%s months") % n
        currency = currency or self.env.company.currency_id
        return formatLang(self.env, float(value or 0.0), currency_obj=currency)

    def _log(self, text):
        stamp = fields.Datetime.now().strftime('%Y-%m-%d %H:%M')
        who = self.env.user.name or ''
        for row in self:
            line = '%s · %s · %s' % (stamp, who, text)
            row.sudo().write({'note': ((row.note + '\n') if row.note else '') + line})

    def _used_in(self):
        """The finished pay run that used this figure, as a person reads it,
        or ''."""
        self.ensure_one()
        use = self.sudo().use_ids.filtered(lambda u: u.state == 'used')[:1]
        if not use:
            return ''
        slip = use.payslip_id
        return (slip.payslip_run_id.name or slip.name or '') if slip else (use.run_name or '')

    def _plan_row(self):
        self.ensure_one()
        old = self.replaces_id
        cur = self.employee_id.company_id.currency_id
        return {
            'emp_id': self.employee_id.id, 'emp_name': self.employee_id.name or '',
            'field_id': card_id(self.figure),
            'field_label': _("%(figure)s · %(year)s, up to %(date)s",
                             figure=self.label or self._figure_label(self.figure),
                             year=self.tax_year, date=day_label(self.env, self.covers_to)),
            'old_label': self._value_label(old.figure, old.amount, cur) if old else '',
            'new_label': _("Removed") if self.action == 'clear' else
            self._value_label(self.figure, self.amount, cur),
        }

    # ------------------------------------------------------------ approve
    def _approve_all(self):
        """`(set, people, refused)` — waiting rows become the figures.

        A later sheet REPLACES a figure (the old row is kept as "Replaced");
        CLEAR removes it. A figure a finished pay run has used is never
        changed: the new row is refused with the reason."""
        done, people, refused = 0, set(), 0
        for row in self.sudo().filtered(lambda r: r.state == 'waiting').sorted('id'):
            current = self.sudo().search([
                ('employee_id', '=', row.employee_id.id), ('tax_year', '=', row.tax_year),
                ('figure', '=', row.figure), ('state', '=', 'set'), ('id', '!=', row.id)], limit=1)
            run = current._used_in() if current else ''
            if run:
                why = _("%(figure)s for %(who)s was used in pay run %(run)s. It can no longer be "
                        "changed here.", figure=row.label or row._figure_label(row.figure),
                        who=row.employee_id.name or '', run=run)
                row.write({'state': 'refused', 'reason': why})
                row._log(why)
                refused += 1
                continue
            if current:
                current.write({'state': 'replaced'})
                current._log(_("Replaced by “%s”.") % (row.batch_id.name or '')
                             if row.action == 'set' else
                             _("Removed by “%s”.") % (row.batch_id.name or ''))
                current.flush_recordset(['state'])
                row.write({'replaces_id': current.id})
            if row.action == 'clear':
                row.write({'state': 'cleared', 'reason': False})
                row._log(_("Removed the figure."))
            else:
                row.write({'state': 'set', 'reason': False})
                row._log(_("Set."))
            done += 1
            people.add(row.employee_id.id)
        return done, len(people), refused

    def _undo_rows(self):
        """`(undone, kept)` — take back what these rows set or removed, unless
        a finished pay run used it; the figure each one replaced comes back."""
        undone, kept = 0, []
        for row in self.sudo().filtered(lambda r: r.state in ('set', 'cleared')).sorted('id'):
            run = row._used_in() if row.state == 'set' else ''
            old = row.replaces_id
            run = run or (old._used_in() if old and row.state == 'cleared' else '')
            if run:
                kept.append(_("%(figure)s for %(who)s was used in pay run %(run)s, so it stays.",
                              figure=row.label or row._figure_label(row.figure),
                              who=row.employee_id.name or '', run=run))
                continue
            row.write({'state': 'undone', 'undone_at': fields.Datetime.now(),
                       'undone_by_id': self.env.uid})
            row.flush_recordset(['state'])
            row._log(_("Undone."))
            if old and old.state == 'replaced' and not self.sudo().search_count([
                    ('employee_id', '=', old.employee_id.id), ('tax_year', '=', old.tax_year),
                    ('figure', '=', old.figure), ('state', '=', 'set')]):
                old.write({'state': 'set'})
                old._log(_("Back in place: “%s” was undone.") % (row.batch_id.name or ''))
            undone += 1
        return undone, kept

    # ------------------------------------------------------------ the numbers
    @api.model
    def _figure_codes(self, company, key):
        """The pay item codes "paid in Payobook" adds up for `key` in
        `company`: the set-up's own list, else the default — the codes the
        company's employee tax summary shows or its schemes have."""
        Figure = self.env['pb.updates.ytd.figure'].sudo()
        row = Figure.with_context(active_test=False).search(
            [('company_id', '=', company.id), ('key', '=', key)], limit=1)
        if row:
            return row.code_list() if row.active else []
        if key not in DEFAULT_CODES:
            return [key]
        known = self._known_codes(company)
        return [c for c in DEFAULT_CODES[key] if c in known]

    @api.model
    def _known_codes(self, company):
        cache = self.env.cr.cache.setdefault('pb_updates_ytd_known', {})
        if company.id not in cache:
            codes = set(self.env['hr.payslip'].sudo()._ess_tax_codes()) \
                if hasattr(self.env['hr.payslip'], '_ess_tax_codes') else set()
            Rule = self.env['hr.formula.rule'].sudo()
            for rec in Rule.search_read([('config_id.company_id', '=', company.id),
                                         ('config_id.state', '=', 'active')], ['code']):
                if rec['code']:
                    codes.add(rec['code'])
            cache[company.id] = codes
        return cache[company.id]

    @api.model
    def _flush_for_sql(self):
        """The few fields the grouped queries read, written out first (a
        payslip finished in this transaction must count)."""
        self.env['hr.payslip'].flush_model(['state', 'date_from', 'date_to', 'employee_id'])
        self.env['hr.payslip.line'].flush_model(['code', 'total', 'slip_id'])
        self.env['pb.updates.ytd.line'].flush_model()

    @api.model
    def _paid_rows(self, emp_ids, start, end, codes):
        """`{(emp_id, code): total}` over DONE payslips that start on or after
        `start` and end on or before `end` — one grouped query on the payslip
        lines; `{emp_id: {month 1st, ...}}` too, for months counted and gaps."""
        emp_ids = [int(e) for e in (emp_ids or []) if e]
        sums, months = {}, {}
        if not emp_ids or not start or not end or start > end:
            return sums, months
        self._flush_for_sql()
        cr = self.env.cr
        cr.execute("""
            SELECT s.employee_id, date_trunc('month', s.date_to)::date
              FROM hr_payslip s
             WHERE s.employee_id = ANY(%s) AND s.state IN %s
               AND s.date_from >= %s AND s.date_to <= %s
             GROUP BY 1, 2""", [emp_ids, DONE_SLIP_STATES, start, end])
        for emp, month in cr.fetchall():
            months.setdefault(emp, set()).add(month)
        for emp, _start, code, total in self._paid_sums(emp_ids, start, end, codes):
            sums[(emp, code)] = sums.get((emp, code), 0.0) + total
        return sums, months

    @api.model
    def _paid_sums(self, emp_ids, start, end, codes):
        """`[(emp_id, payslip start, code, amount)]` over DONE payslips that
        start on or after `start` and end on or before `end`.

        Amounts are what was paid or taken, so a deduction's line (stored as a
        negative number) counts as a positive amount. A code with no payslip
        line at all (a figure the payslip computes but does not print, like a
        taxable base) is read from the payslip's computed values instead."""
        codes = sorted({c for c in (codes or []) if c})
        emp_ids = [int(e) for e in (emp_ids or []) if e]
        if not codes or not emp_ids or not start or not end or start > end:
            return []
        cr = self.env.cr
        cr.execute("""
            SELECT s.employee_id, s.date_from, l.code, SUM(ABS(l.total))
              FROM hr_payslip_line l JOIN hr_payslip s ON s.id = l.slip_id
             WHERE s.employee_id = ANY(%s) AND s.state IN %s
               AND s.date_from >= %s AND s.date_to <= %s AND l.code = ANY(%s)
             GROUP BY 1, 2, 3""", [emp_ids, DONE_SLIP_STATES, start, end, codes])
        rows = [(e, d, c, float(t or 0.0)) for e, d, c, t in cr.fetchall()]
        lined = {r[2] for r in rows}
        for code in codes:
            if code in lined or not re.fullmatch(r'[A-Za-z0-9_]+', code):
                continue
            cr.execute("""
                SELECT s.employee_id, s.date_from,
                       substring(s.formula_computed_values from %s)
                  FROM hr_payslip s
                 WHERE s.employee_id = ANY(%s) AND s.state IN %s
                   AND s.date_from >= %s AND s.date_to <= %s
                   AND s.formula_computed_values LIKE %s""",
                       [r'"%s":\s*(-?[0-9][0-9.eE+-]*)' % code, emp_ids, DONE_SLIP_STATES,
                        start, end, '%%"%s"%%' % code])
            for emp, day, text in cr.fetchall():
                try:
                    rows.append((emp, day, code, abs(float(text))))
                except (TypeError, ValueError):
                    continue
        return rows

    @api.model
    def _maps_of(self, config):
        """`[(code, figure, basis, id)]` of a scheme — from the per-cursor cache."""
        cache = self.env.cr.cache.setdefault(MAP_CACHE, {})
        if config.id not in cache:
            self.env['pb.updates.ytd.map'].flush_model(['config_id', 'code', 'figure', 'basis'])
            self.env.cr.execute(
                "SELECT code, figure, basis, id FROM pb_updates_ytd_map WHERE config_id = %s "
                "ORDER BY id", [config.id])
            cache[config.id] = self.env.cr.fetchall()
        return cache[config.id]

    @api.model
    def _plan_for_slip(self, employee, config, date_from, date_to):
        """`{CODE: plan}` — what a payslip of `employee` on `config` for
        `date_from`–`date_to` receives from year-to-date figures. EMPTY (and
        then the pay run reads exactly what it read before) when the scheme
        has no mapping, or the person has no figure for that tax year that
        covers a time before this pay period."""
        if not employee or not config or not date_to:
            return {}
        maps = self._maps_of(config)
        if not maps:
            return {}
        date_from = fields.Date.to_date(date_from) if date_from else None
        date_to = fields.Date.to_date(date_to)
        date_from = date_from or month_floor(date_to)
        year = date_to.year
        lines = self.sudo().search([
            ('employee_id', '=', employee.id), ('tax_year', '=', year), ('state', '=', 'set'),
            ('figure', 'in', list({m[1] for m in maps}))])
        if not lines:
            return {}
        by_figure = {l.figure: l for l in lines}
        out = {}
        for code, figure, basis, map_id in maps:
            line = by_figure.get(figure)
            if not line or not line.covers_to or line.covers_to >= date_from:
                continue
            info = {'code': code, 'figure': figure, 'basis': basis, 'map_id': map_id,
                    'line_id': line.id, 'covers_to': fields.Date.to_string(line.covers_to),
                    'before': float(line.amount or 0.0), 'paid': 0.0, 'gap': [], 'unknown': False,
                    'label': line.label or self._figure_label(figure, employee.company_id)}
            if basis != 'opening':
                start = line.covers_to + timedelta(days=1)
                end = date_from - timedelta(days=1)
                codes = [] if self._is_count(figure) else self._figure_codes(
                    employee.company_id, figure)
                sums, months = self._paid_rows([employee.id], start, end, codes)
                had = months.get(employee.id, set())
                info['gap'] = [fields.Date.to_string(m) for m in months_between(start, end)
                               if m not in had]
                if self._is_count(figure):
                    info['paid'] = float(len(had))
                    if basis == 'with_period':
                        info['paid'] += 1.0
                else:
                    info['paid'] = sum(sums.get((employee.id, c), 0.0) for c in codes)
                    # Finished payslips, but none carries the figure's pay
                    # items: "paid in Payobook" is not known — never a silent 0.
                    info['unknown'] = bool(had) and not any(
                        (employee.id, c) in sums for c in codes)
            info['value'] = round(info['before'] + info['paid'], 2)
            out[code] = info
        return out

    @api.model
    def _tax_summary_opening(self, emp, qcontext):
        """The employee's own tax summary (`/my/taxsheet`, U43): add the
        figures before Payobook to the year's totals, in place, for the codes
        a figure is EXACTLY one of; the rest are listed apart, never split.
        Leaves `qcontext` untouched for a person without figures."""
        year = qcontext.get('ytd_year')
        domain = [('employee_id', '=', emp.id), ('state', '=', 'set')]
        if year:
            domain.append(('tax_year', '=', year))
        lines = self.sudo().search(domain, order='tax_year desc, id')
        if not year and lines:
            year = lines[0].tax_year
            lines = lines.filtered(lambda l: l.tax_year == year)
        lines = lines.filtered(lambda l: l.figure not in COUNT_FIGURES and l.amount)
        if not lines:
            return qcontext
        codes = list(qcontext.get('codes') or [])
        company = emp.company_id
        opening, apart = {}, []
        for line in lines:
            mine = self._figure_codes(company, line.figure)
            if len(mine) == 1 and mine[0] in codes:
                opening[mine[0]] = opening.get(mine[0], 0.0) + line.amount
            else:
                apart.append({'label': line.label or self._figure_label(line.figure, company),
                              'amount': line.amount})
        ytd = dict(qcontext.get('ytd') or {})
        for code in list(opening):
            # Shown with the summary's own sign: a deduction line is stored as
            # a negative number there.
            if self._code_is_negative(emp, code, ytd.get(code)):
                opening[code] = -opening[code]
            ytd[code] = (ytd.get(code) or 0.0) + opening[code]
        qcontext.update({
            'ytd': ytd, 'ytd_year': year, 'ytd_opening': opening,
            'ytd_opening_apart': apart,
            'ytd_opening_label': day_label(self.env, max(lines.mapped('covers_to'))),
        })
        qcontext['ytd_opening_title'] = _("Before Payobook (up to %s)") % qcontext['ytd_opening_label']
        qcontext['ytd_opening_also'] = _("Also before Payobook (up to %s)") % qcontext['ytd_opening_label']
        return qcontext

    @api.model
    def _code_is_negative(self, emp, code, current):
        if current:
            return current < 0
        self.env.cr.execute("""
            SELECT l.total FROM hr_payslip_line l JOIN hr_payslip s ON s.id = l.slip_id
             WHERE s.employee_id = %s AND l.code = %s AND l.total <> 0 AND s.state IN %s
             ORDER BY s.date_to DESC LIMIT 1""", [emp.id, code, DONE_SLIP_STATES])
        row = self.env.cr.fetchone()
        return bool(row and row[0] < 0)

    @api.model
    def _gap_sentence(self, employee, info):
        item = info.get('item_label') or info['code']
        if not info['gap'] and info.get('unknown'):
            return _("Year-to-date figures for %(who)s: none of %(who)s's finished payslips since "
                     "%(date)s has the pay items that make up %(figure)s, so %(item)s cannot be "
                     "worked out. Choose those pay items in Updates › Year-to-date figures › Set "
                     "up, then calculate again.", who=employee.name or '',
                     date=day_label(self.env, fields.Date.to_date(info['covers_to'])),
                     figure=info['label'], item=item)
        months = ', '.join(format_date(self.env, fields.Date.to_date(m), date_format='MMMM y')
                           for m in info['gap'][:4])
        return _("Year-to-date figures for %(who)s: there is no finished payslip for %(months)s, "
                 "between the figures before Payobook (up to %(date)s) and this pay period, so "
                 "%(item)s cannot be worked out. Finish that pay run, or load figures that cover "
                 "up to a later date, then calculate again.",
                 who=employee.name or '', months=months,
                 date=day_label(self.env, fields.Date.to_date(info['covers_to'])),
                 item=item)


class PbUpdatesYtdUse(models.Model):
    """Which payslip used which figure. `in_run` while the payslip is open,
    `used` once it is finished (the figure is then locked); released (row
    deleted) when the payslip is cancelled, deleted or no longer uses it."""
    _name = 'pb.updates.ytd.use'
    _description = 'Year-to-date figure used by a payslip'
    _order = 'id desc'

    line_id = fields.Many2one('pb.updates.ytd.line', string='Figure', required=True, index=True,
                              ondelete='cascade', readonly=True)
    payslip_id = fields.Many2one('hr.payslip', string='Payslip', index=True,
                                 ondelete='cascade', readonly=True)
    run_name = fields.Char(string='Pay run', readonly=True)
    code = fields.Char(string='Pay item', readonly=True)
    value = fields.Float(string='Value sent', readonly=True)
    before = fields.Float(string='Before Payobook', readonly=True)
    paid = fields.Float(string='Paid in Payobook', readonly=True)
    state = fields.Selection([('in_run', 'In a pay run'), ('used', 'Used by a finished payslip')],
                             string='Status', default='in_run', required=True, readonly=True)

    @api.model
    def _sync_slips(self, slips):
        """After a real compute: hold the figures each payslip used (read off
        its own input sources), let go of the ones it no longer uses."""
        slips = slips.sudo().exists()
        if not slips:
            return
        held = self.sudo().search([('payslip_id', 'in', slips.ids)])
        for slip in slips:
            text = slip.formula_input_sources or ''
            mine = held.filtered(lambda u: u.payslip_id == slip)
            if YTD_VIA not in text and 'ytd' not in text:
                mine.unlink()
                continue
            try:
                sources = json.loads(text)
            except (TypeError, ValueError):
                continue
            wanted = {}
            for code, entry in (sources or {}).items():
                parts = (entry or {}).get('ytd') if isinstance(entry, dict) else None
                if not isinstance(parts, dict) or not parts.get('line_id'):
                    continue
                if (entry.get('ignored') or {}).get('key', '').startswith('updates_ytd:'):
                    continue   # the file's amount was chosen instead
                wanted[(int(parts['line_id']), code)] = parts
            done = slip.state in DONE_SLIP_STATES
            for use in mine:
                if (use.line_id.id, use.code) not in wanted:
                    use.unlink()
            for (line_id, code), parts in wanted.items():
                use = mine.filtered(lambda u: u.line_id.id == line_id and u.code == code)[:1]
                vals = {'value': parts.get('value') or 0.0, 'before': parts.get('before') or 0.0,
                        'paid': parts.get('paid') or 0.0,
                        'run_name': slip.payslip_run_id.name or slip.name or '',
                        'state': 'used' if done else 'in_run'}
                if use.exists():
                    use.write(vals)
                else:
                    self.sudo().create(dict(vals, line_id=line_id, payslip_id=slip.id, code=code))


class PbUpdatesYtdAsk(models.Model):
    """D11 for a year-to-date figure: the pay data file carries a different
    number for a mapped pay item. The pay run stops and asks; never one or the
    other silently, never the sum. Same field names as a one-off's question,
    so the pay run's own "choose and calculate again" step serves both."""
    _name = 'pb.updates.ytd.ask'
    _description = 'Year-to-date figure: the pay run asks which amount'
    _order = 'id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True,
                                  ondelete='cascade', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True,
                                 readonly=True)
    code = fields.Char(string='Pay item code', required=True, readonly=True)
    label = fields.Char(string='Pay item', readonly=True)
    figure = fields.Char(string='Figure', readonly=True)
    line_id = fields.Many2one('pb.updates.ytd.line', string='Figure row', ondelete='set null',
                              readonly=True)
    updates_amount = fields.Float(string='From Updates', readonly=True)
    clash_run_id = fields.Many2one('hr.payslip.run', string='Pay run', index=True,
                                   ondelete='cascade', readonly=True)
    clash_batch_id = fields.Many2one('hr.payroll.import.batch', string='Pay data file',
                                     ondelete='set null', readonly=True)
    clash_file_amount = fields.Float(string='In the pay data file', readonly=True)
    clash_file_key = fields.Char(string='Column in the pay data file', readonly=True)
    clash_choice = fields.Selection([('updates', 'The Updates amount'),
                                     ('file', "The file's amount")], string='Chosen',
                                    readonly=True)
    clash_by = fields.Many2one('res.users', string='Chosen by', readonly=True)
    clash_at = fields.Datetime(string='Chosen at', readonly=True)

    def _amount(self, value):
        self.ensure_one()
        return self.env['pb.updates.ytd.line']._value_label(
            self.figure or '', value, self.employee_id.company_id.currency_id)

    def _sentence(self):
        self.ensure_one()
        return _("%(item)s for %(name)s: %(updates)s from the year-to-date figures in Updates, "
                 "%(file)s in the pay data file. Choose which one to use in this pay run.",
                 item=self.label or self.code, name=self.employee_id.name or '',
                 updates=self._amount(self.updates_amount),
                 file=self._amount(self.clash_file_amount))

    def _payload(self):
        out = []
        Oneoff = self.env['pb.updates.oneoff']
        for ask in self:
            run = ask.clash_run_id
            month = run.date_end or run.date_start if run else False
            out.append({
                'id': 'y:%s' % ask.id, 'emp': ask.employee_id.name or '',
                'emp_id': ask.employee_id.id, 'item': ask.label or ask.code,
                'month': Oneoff._month_label(month) if month else '',
                'updates': ask._amount(ask.updates_amount),
                'file': ask._amount(ask.clash_file_amount),
                'run': run.name or '', 'run_id': run.id,
                'chosen': ask.clash_choice or '', 'sentence': ask._sentence(),
                'ytd': True,
            })
        return out

    @api.model
    def _open(self, clash, run=None, batch=None):
        domain = [('employee_id', '=', clash.employee_id), ('code', '=', clash.code)]
        if run:
            domain.append(('clash_run_id', '=', run.id))
        elif batch:
            domain.append(('clash_batch_id', '=', batch.id))
        else:
            return self.browse()
        ask = self.sudo().search(domain, limit=1)
        try:
            amount = float(clash.file_value or 0.0)
        except (TypeError, ValueError):
            amount = 0.0
        vals = {'clash_file_amount': amount, 'clash_file_key': clash.file_key or False,
                'updates_amount': clash.ours, 'label': clash.label, 'figure': clash.figure,
                'line_id': clash.line_id or False}
        if batch:
            vals['clash_batch_id'] = batch.id
        if ask:
            if not ask.clash_choice:
                ask.write(vals)
            return ask
        employee = self.env['hr.employee'].sudo().browse(clash.employee_id)
        return self.sudo().create(dict(vals, employee_id=clash.employee_id, code=clash.code,
                                       company_id=employee.company_id.id,
                                       clash_run_id=run.id if run else False))

    @api.model
    def _for(self, run, batch, employee, code):
        if not employee or not (run or batch):
            return self.browse()
        domain = [('employee_id', '=', employee.id), ('code', '=', code)]
        if run:
            domain.append(('clash_run_id', '=', run.id))
        else:
            domain.append(('clash_batch_id', '=', batch.id))
        return self.sudo().search(domain, limit=1)


class PbUpdatesBatchYtd(models.Model):
    _inherit = 'pb.updates.batch'

    kind = fields.Selection(selection_add=[('ytd', 'Year-to-date figures before Payobook')],
                            ondelete={'ytd': 'set default'})
    ytd_covers_to = fields.Date(string='Figures cover up to')
    ytd_line_ids = fields.One2many('pb.updates.ytd.line', 'batch_id',
                                   string='Year-to-date figures')


class PbUpdatesLayoutYtd(models.Model):
    _inherit = 'pb.updates.layout'

    kind = fields.Selection(selection_add=[('ytd', 'Year-to-date figures before Payobook')],
                            ondelete={'ytd': 'set default'})


class PbRecordsApplyYtd(models.Model):
    """The named update's ONE approval proposal, when it carries year-to-date
    figures: the records (pay) route, the same inbox; approving it sets the
    figures instead of writing a record."""
    _inherit = 'pb.records.apply'

    updates_ytd = fields.Boolean(string='Year-to-date figures', readonly=True, copy=False)
    ytd_line_ids = fields.One2many('pb.updates.ytd.line', 'apply_id',
                                   string='Year-to-date figures')

    def _headline(self):
        self.ensure_one()
        if not self.updates_ytd:
            return super()._headline()
        rows = self.sudo().ytd_line_ids
        n = len(rows)
        first = rows[:1]
        return _("Year-to-date figures for %(year)s, up to %(date)s · %(n)s",
                 year=first.tax_year or '', date=day_label(self.env, first.covers_to),
                 n=_("1 figure") if n == 1 else _("%s figures") % n)

    def _approval_detail(self, request):
        detail = super()._approval_detail(request)
        if self.updates_ytd and detail:
            detail['title'] = _('Year-to-date figures before Payobook')
            detail['columns'] = [_('Now'), _('In this update')]
        return detail

    def _approval_freeze(self, request):
        result = super()._approval_freeze(request)
        if self.updates_ytd:
            rows = self.sudo().ytd_line_ids.filtered(lambda r: r.state == 'returned')
            if rows:
                rows.write({'state': 'waiting'})
                rows._log(_("Sent in again."))
        return result

    def _approval_apply(self, request):
        self.ensure_one()
        if not self.updates_ytd:
            return super()._approval_apply(request)
        if self.applied:
            return True
        if self.state == 'cancelled' or self.undone:
            raise UserError(_("This change was cancelled, so nothing was written."))
        rec = self.sudo()
        done, people, refused = rec.ytd_line_ids._approve_all()
        rec.write({
            'applied': True, 'applied_at': fields.Datetime.now(), 'state': 'applied',
            'count_values': done, 'count_people': people,
            'block_note': (_("1 figure could not be set.") if refused == 1 else
                           _("%s figures could not be set.") % refused) if refused else False,
        })
        return True

    def write(self, vals):
        result = super().write(vals)
        state = vals.get('state')
        if state in ('cancelled', 'rejected', 'returned') and 'ytd_line_ids' in self._fields:
            for rec in self.filtered('updates_ytd'):
                rows = rec.sudo().ytd_line_ids.filtered(lambda r: r.state == 'waiting')
                if rows:
                    rows.write({'state': state})
                    rows._log({'cancelled': _("Cancelled before it was approved."),
                               'rejected': _("Turned down."),
                               'returned': _("Sent back.")}[state])
        return result


def parse_amount(raw):
    """A typed number: 1234567, "1,234,567", "1.234.567", "1 234 567",
    "12,5" (a decimal comma) — or None."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw or '').strip()
    text = re.sub(r'[\s ]', '', text)
    text = re.sub(r'^(?:[A-Za-z]{1,3}|[₫$€£¥₹])', '', text)
    text = re.sub(r'(?:[A-Za-z]{1,3}|[₫$€£¥₹])$', '', text)
    if not text:
        return None
    if re.fullmatch(r'-?\d{1,3}(,\d{3})+(\.\d+)?', text):
        text = text.replace(',', '')
    elif re.fullmatch(r'-?\d{1,3}(\.\d{3}){2,}(,\d+)?', text):
        text = text.replace('.', '').replace(',', '.')
    elif re.fullmatch(r'-?\d+,\d{1,2}', text):
        text = text.replace(',', '.')
    try:
        return float(text)
    except ValueError:
        return None


def json_dumps(value):
    return json.dumps(value, default=str)


def first_of_year(year):
    return date(int(year), 1, 1)


def last_of_year(year):
    return date(int(year), 12, 31)


def may(env, groups):
    user = env.user
    if user._is_superuser():
        return True
    for group in groups:
        try:
            if user.has_group(group):
                return True
        except Exception:   # noqa: BLE001 — a group a build does not have is a "no"
            continue
    return False


def refuse_access(msg):
    raise AccessError(msg)
