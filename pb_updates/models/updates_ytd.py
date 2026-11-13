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
#: P5c — pay roles whose amounts are money taken off pay or paid on top by the
#: employer: counted as an amount, whatever sign the scheme writes them with
#: (the one pay-band rule, `om_hr_payroll/models/pay_bands.py` `pb_pay_totals`).
MAGNITUDE_ROLES = ('deduction', 'employer_cost')
#: The same rule's fallback for a line written before pay roles existed.
MAGNITUDE_CATEGORIES = ('DED', 'DEDUCTION', 'COMP')
#: P5c — a scheme of this kind is a mid-month advance (`hr.formula.config.cycle_type`).
ADVANCE_CYCLE = 'mid_cycle'
#: A pay item code the stored-results reader may look for.
CODE_RE = re.compile(r'[A-Za-z0-9_]+')
#: Per-cursor cache of each scheme's usual sign for a pay item, and how many of
#: the scheme's latest finished payslips of the tax year decide it.
CONV_CACHE = 'pb_updates_ytd_conv'
CONV_SAMPLE = 100
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
        self.env['hr.payslip'].flush_model(['state', 'date_from', 'date_to', 'employee_id',
                                            'formula_config_id', 'payslip_run_id', 'name',
                                            'formula_computed_values'])
        self.env['hr.payslip.line'].flush_model(['code', 'total', 'slip_id', 'pay_role',
                                                 'category_id'])
        self.env['hr.payslip.run'].flush_model(['name'])
        self.env['hr.formula.rule'].flush_model(['code', 'config_id', 'net_role'])
        self.env['pb.updates.ytd.line'].flush_model()

    # ------------------------------------------------------------ paid in Payobook (P5c)
    #
    # ONE computation behind every "paid in Payobook" number: the year-to-date
    # view, its download, "Download for the pay run" and the value a mapped pay
    # item receives in a pay run. Three rules (UPDATES P5c, report §1-§3):
    #
    #   1. COVERAGE. A sum is a total only when EVERY finished payslip that
    #      should carry the figure does. A payslip should carry it when its pay
    #      scheme has one of the figure's pay items (a payslip of a scheme that
    #      does not have the item at all is not expected to). Fewer → the
    #      amount is shown as incomplete ("3 of 11 payslips have this figure")
    #      and a pay run refuses the person with a sentence.
    #   2. SIGN. A payslip line and its stored result carry the same signed
    #      number (`hr_payslip_formula.py` `_create_payslip_lines_from_formulas`,
    #      `payroll_import_batch.py` `normalize_payslip_amount`). Money taken off
    #      or paid on top by the employer (pay role deduction / employer cost)
    #      counts as an amount, however the scheme signs it — the one pay-band
    #      rule (`om_hr_payroll/models/pay_bands.py` `pb_pay_totals`) — but a
    #      month whose sign is the OPPOSITE of the scheme's usual sign for that
    #      pay item (a tax refund in a final month) reduces the year. Everything
    #      else (gross, taxable pay, net, a pay item of its own) is summed with
    #      its own sign; a month below zero is shown, never hidden.
    #   3. ONCE. A mid-month advance (a scheme whose kind is mid-month advance,
    #      `cycle_type = 'mid_cycle'`) is a part payment of the month: the
    #      month-end payslip of the scheme it is carried to
    #      (`hr.payroll.cycle.component.mapping`) carries the whole month and
    #      takes the advance back off. Such an advance is never added. If the
    #      two cannot be matched, the advance is shown apart, not added, and a
    #      pay run refuses. Every other finished payslip (a top-up, an awards
    #      or bonus run, full and final) is pay and is counted.

    @api.model
    def _ledger(self, emp_ids, first, last, codes):
        """Everything "paid in Payobook" reads for `emp_ids`: their finished
        payslips whose END date falls in `first`..`last`, the stored amounts of
        `codes` on them, which pay items each scheme has, how advances are
        carried, and each scheme's usual sign. A fixed number of queries, never
        one per person."""
        emp_ids = sorted({int(e) for e in (emp_ids or []) if e})
        codes = sorted({c for c in (codes or []) if c and CODE_RE.fullmatch(c)})
        out = {'slips': {}, 'by_emp': {}, 'values': {}, 'scheme_codes': {}, 'roles': {},
               'links': set(), 'conv': {}, 'codes': codes}
        if not emp_ids or not first or not last or first > last:
            return out
        self._flush_for_sql()
        cr = self.env.cr
        cr.execute("""
            SELECT s.id, s.employee_id, s.date_from, s.date_to, s.formula_config_id,
                   COALESCE(fc.cycle_type, ''), s.payslip_run_id, COALESCE(r.name, ''),
                   COALESCE(s.name, ''),
                   COALESCE(s.formula_computed_values, '') NOT IN ('', '{}')
              FROM hr_payslip s
              LEFT JOIN hr_formula_config fc ON fc.id = s.formula_config_id
              LEFT JOIN hr_payslip_run r ON r.id = s.payslip_run_id
             WHERE s.employee_id = ANY(%s) AND s.state IN %s
               AND s.date_to >= %s AND s.date_to <= %s
             ORDER BY s.employee_id, s.date_to, s.id""",
                   [emp_ids, DONE_SLIP_STATES, first, last])
        for sid, emp, dfrom, dto, config, cycle, run, run_name, name, fcv in cr.fetchall():
            slip = {'id': sid, 'emp': emp, 'date_from': dfrom or dto, 'date_to': dto,
                    'month': month_floor(dto), 'config': config or 0, 'cycle': cycle,
                    'run_id': run or 0, 'run': run_name or name or '', 'fcv': bool(fcv)}
            out['slips'][sid] = slip
            out['by_emp'].setdefault(emp, []).append(slip)
        slip_ids = list(out['slips'])
        configs = sorted({s['config'] for s in out['slips'].values() if s['config']})
        if slip_ids and codes:
            cr.execute("""
                SELECT l.slip_id, l.code, l.total, COALESCE(l.pay_role, ''), COALESCE(c.code, '')
                  FROM hr_payslip_line l
                  LEFT JOIN hr_salary_rule_category c ON c.id = l.category_id
                 WHERE l.slip_id = ANY(%s) AND l.code = ANY(%s)""", [slip_ids, codes])
            for sid, code, total, role, category in cr.fetchall():
                key = (sid, code)
                old = out['values'].get(key)
                amount = float(total or 0.0) + (old[0] if old else 0.0)
                out['values'][key] = (amount, role or ('deduction' if (category or '').upper()
                                                       in MAGNITUDE_CATEGORIES else ''))
            # A pay item the payslip computes but does not print (a taxable
            # base) is read from its stored results.
            with_fcv = [sid for sid in slip_ids if out['slips'][sid]['fcv']]
            for code in codes:
                missing = [sid for sid in with_fcv if (sid, code) not in out['values']]
                if not missing:
                    continue
                cr.execute("""
                    SELECT s.id, substring(s.formula_computed_values from %s)
                      FROM hr_payslip s
                     WHERE s.id = ANY(%s) AND s.formula_computed_values LIKE %s""",
                           [r'"%s":\s*(-?[0-9][0-9.eE+-]*)' % code, missing, '%%"%s"%%' % code])
                for sid, text in cr.fetchall():
                    try:
                        out['values'][(sid, code)] = (float(text), None)
                    except (TypeError, ValueError):
                        continue
        if configs and codes:
            cr.execute("""
                SELECT config_id, code, COALESCE(net_role, '') FROM hr_formula_rule
                 WHERE config_id = ANY(%s) AND code = ANY(%s)""", [configs, codes])
            for config, code, role in cr.fetchall():
                out['scheme_codes'].setdefault(config, set()).add(code)
                out['roles'][(config, code)] = role
        advances = sorted({s['config'] for s in out['slips'].values()
                           if s['cycle'] == ADVANCE_CYCLE and s['config']})
        if advances:
            # The engine's own link from an advance scheme to the month-end
            # scheme it is carried to (an archived row still says so).
            cr.execute("""
                SELECT DISTINCT mid_cycle_config_id, end_cycle_config_id
                  FROM hr_payroll_cycle_component_mapping
                 WHERE mid_cycle_config_id = ANY(%s)""", [advances])
            out['links'] = set(cr.fetchall())
        out['conv'] = self._conventions(configs, codes, out, last.year)
        return out

    @api.model
    def _conventions(self, configs, codes, ledger, year):
        """`{(scheme, code): +1 | -1}` — the usual sign of a pay item that is
        money taken off or paid on top: the sign most of the scheme's latest
        `CONV_SAMPLE` finished payslips of the tax year carry for it, whoever
        they belong to (so the view, the downloads and a pay run all read the
        same answer). Absent when the scheme has no clear usual sign; such an
        amount counts as its size (the one pay-band rule)."""
        wanted = sorted({c for (cfg, c), r in ledger['roles'].items() if r in MAGNITUDE_ROLES}
                        | {c for (_s, c), v in ledger['values'].items()
                           if v[1] in MAGNITUDE_ROLES})
        if not configs or not wanted:
            return {}
        cache = self.env.cr.cache.setdefault(CONV_CACHE, {})
        todo = [(cfg, c) for cfg in configs for c in wanted if (year, cfg, c) not in cache]
        if todo:
            todo_cfgs = sorted({t[0] for t in todo})
            todo_codes = sorted({t[1] for t in todo})
            for key in todo:
                cache[(year, key[0], key[1])] = 0
            # The scheme's latest finished payslips of the tax year (a sample
            # of CONV_SAMPLE each: a whole year of lines would cost a second
            # per page), then their lines through the payslip index.
            self.env.cr.execute("""
                SELECT id, formula_config_id FROM (
                    SELECT id, formula_config_id,
                           row_number() OVER (PARTITION BY formula_config_id
                                              ORDER BY date_to DESC, id DESC) AS rn
                      FROM hr_payslip
                     WHERE formula_config_id = ANY(%s) AND state IN %s
                       AND date_to >= %s AND date_to <= %s) recent
                 WHERE rn <= %s""", [todo_cfgs, DONE_SLIP_STATES, first_of_year(year),
                                     last_of_year(year), CONV_SAMPLE])
            config_of = dict(self.env.cr.fetchall())
            counts = {}
            if config_of:
                self.env.cr.execute("""
                    SELECT slip_id, code, total FROM hr_payslip_line
                     WHERE slip_id = ANY(%s) AND code = ANY(%s) AND total <> 0""",
                                    [list(config_of), todo_codes])
                for sid, code, total in self.env.cr.fetchall():
                    pair = counts.setdefault((config_of[sid], code), [0, 0])
                    pair[0 if total > 0 else 1] += 1
            for (cfg, code), (pos, neg) in counts.items():
                cache[(year, cfg, code)] = 1 if pos > neg else (-1 if neg > pos else 0)
        return {(cfg, c): cache[(year, cfg, c)] for cfg in configs for c in wanted
                if cache.get((year, cfg, c))}

    @api.model
    def _slip_amount(self, ledger, slip, codes):
        """`(amount or None, below zero?)` — what one finished payslip adds to a
        figure made of `codes` (None: it carries none of them)."""
        total, carried = 0.0, False
        for code in codes:
            entry = ledger['values'].get((slip['id'], code))
            if entry is None:
                continue
            carried = True
            value, role = entry
            if role is None:
                role = ledger['roles'].get((slip['config'], code), '')
            if role in MAGNITUDE_ROLES:
                conv = ledger['conv'].get((slip['config'], code))
                value = value * conv if conv else abs(value)
            total += value
        if not carried:
            return None, False
        total = round(total, 2)
        return total, total < 0

    @api.model
    def _person_window(self, ledger, emp_id, covers_to=None, upper=None):
        """How each finished payslip of one person stands for "paid in
        Payobook": `{'rows': [...], 'counted': [...], 'months': {...},
        'overlap': [...], 'split': [...], 'twice': [...]}`.

        `covers_to` — the figures before Payobook cover up to this day: a
        payslip that ends on or before it is already in those figures; one that
        starts on or before it and ends after it overlaps them. `upper` — a pay
        period's first day: only payslips that end before it count."""
        rows, counted, overlap, split = [], [], [], []
        slips = [s for s in ledger['by_emp'].get(emp_id, [])
                 if not upper or s['date_to'] < upper]
        regular = [s for s in slips if s['cycle'] != ADVANCE_CYCLE]
        for slip in slips:
            row = dict(slip, state='counted')
            if covers_to and slip['date_to'] <= covers_to:
                row['state'] = 'before'
            elif slip['cycle'] == ADVANCE_CYCLE:
                ends = [s for s in regular if s['month'] == slip['month']
                        and not (covers_to and s['date_to'] <= covers_to)]
                if any((slip['config'], s['config']) in ledger['links'] for s in ends):
                    row['state'] = 'advance'
                elif ends:
                    row['state'] = 'split'
                    split.append(row)
                else:
                    row['state'] = 'advance_only'
            elif covers_to and slip['date_from'] <= covers_to:
                row['state'] = 'overlap'
                overlap.append(row)
            else:
                counted.append(row)
            rows.append(row)
        seen, twice = {}, []
        for row in counted:
            key = (row['config'], row['date_from'], row['date_to'])
            if key in seen and row['config']:
                twice.append(row)
            seen.setdefault(key, row)
        return {'rows': rows, 'counted': counted, 'overlap': overlap, 'split': split,
                'twice': twice, 'months': {r['month'] for r in counted}}

    @api.model
    def _figure_paid(self, ledger, window, codes):
        """One figure for one person: `{'state', 'paid', 'expected', 'have',
        'below_zero', 'advance', 'amounts'}`.

        state: `none` (no finished payslip counts yet), `complete`, `partial`
        (some payslips that should carry it do not), `unknown` (none does, or
        no pay item is chosen for it), `overlap`, `split` (see
        `_person_window`)."""
        amounts, below, expected, have, paid = {}, [], 0, 0, 0.0
        for row in window['counted']:
            amount, negative = self._slip_amount(ledger, row, codes) if codes else (None, False)
            should = amount is not None or not row['config'] or bool(
                set(codes) & ledger['scheme_codes'].get(row['config'], set()))
            if should:
                expected += 1
            if amount is not None:
                have += 1
                paid += amount
                amounts[row['id']] = amount
                if negative:
                    below.append(row['month'])
        advance = 0.0
        for row in window['split']:
            amount, _neg = self._slip_amount(ledger, row, codes) if codes else (None, False)
            if amount is not None:
                amounts[row['id']] = amount
                advance += amount
        if not window['counted']:
            state = 'none'
        elif not codes or not have:
            state = 'unknown'
        elif have < expected:
            state = 'partial'
        else:
            state = 'complete'
        if state in ('none', 'complete', 'partial') and window['overlap']:
            state = 'overlap'
        if state in ('none', 'complete', 'partial') and window['split']:
            state = 'split'
        return {'state': state, 'paid': round(paid, 2), 'expected': expected, 'have': have,
                'below_zero': sorted(set(below)), 'advance': round(advance, 2),
                'amounts': amounts}

    @api.model
    def _months_paid(self, window, covers_to=None):
        """Months counted in Payobook: each month once, after the month the
        figures before Payobook end in (that month is already in them)."""
        floor = month_floor(covers_to) if covers_to else None
        return sorted(m for m in window['months'] if not floor or m > floor)

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
        # UPDATES P5d (D31) — a person who joined this tax year (the employee
        # record's joining date, never the contract start) and has no figure
        # before Payobook may still receive "paid in Payobook" alone.
        joined = self._joined_in(employee, year)
        if joined and joined > date_to:
            joined = None       # a pay period before the person joined: nothing
        if not lines and not joined:
            return {}
        by_figure = {l.figure: l for l in lines}
        out = {}
        ledger = None
        for code, figure, basis, map_id in maps:
            line = by_figure.get(figure)
            if not line:
                if joined:
                    if ledger is None:
                        ledger = self._plan_ledger(employee, maps, year, date_from)
                    info = self._joiner_plan(employee, joined, ledger, code, figure, basis,
                                             map_id, date_from)
                    if info:
                        out[code] = info
                continue
            if not line.covers_to or line.covers_to >= date_from:
                continue
            info = {'code': code, 'figure': figure, 'basis': basis, 'map_id': map_id,
                    'line_id': line.id, 'covers_to': fields.Date.to_string(line.covers_to),
                    'before': float(line.amount or 0.0), 'paid': 0.0, 'gap': [], 'unknown': False,
                    'incomplete': '', 'below_zero': [], 'slips': [],
                    'label': line.label or self._figure_label(figure, employee.company_id)}
            if basis != 'opening':
                start = line.covers_to + timedelta(days=1)
                end = date_from - timedelta(days=1)
                if ledger is None:
                    ledger = self._plan_ledger(employee, maps, year, date_from)
                window = self._person_window(ledger, employee.id, line.covers_to, date_from)
                info['gap'] = [fields.Date.to_string(m) for m in months_between(start, end)
                               if m not in window['months']]
                info['overlap'] = [{'from': fields.Date.to_string(r['date_from']),
                                    'to': fields.Date.to_string(r['date_to']), 'run': r['run']}
                                   for r in window['overlap']]
                info['split'] = [fields.Date.to_string(r['month']) for r in window['split']]
                # Two finished payslips of one scheme for the same dates: both
                # are counted (a second run may be real pay) but never quietly.
                info['twice'] = sorted({fields.Date.to_string(r['month'])
                                        for r in window['twice']})
                if window['overlap']:
                    info['incomplete'] = 'overlap'
                elif window['split'] and not self._is_count(figure):
                    info['incomplete'] = 'split'
                if self._is_count(figure):
                    info['paid'] = float(len(self._months_paid(window, line.covers_to)))
                    if basis == 'with_period':
                        info['paid'] += 1.0
                else:
                    codes = self._figure_codes(employee.company_id, figure)
                    res = self._figure_paid(ledger, window, codes)
                    info['paid'] = res['paid']
                    info['have'], info['expected'] = res['have'], res['expected']
                    info['below_zero'] = [fields.Date.to_string(m) for m in res['below_zero']]
                    info['slips'] = [r['id'] for r in window['counted']]
                    # Finished payslips, but none carries the figure's pay
                    # items: "paid in Payobook" is not known — never a silent 0.
                    info['unknown'] = res['state'] == 'unknown'
                    if res['state'] == 'partial' and not info['incomplete']:
                        # Only some of them carry it: the sum would be too low.
                        info['incomplete'] = 'partial'
            info['value'] = round(info['before'] + info['paid'], 2)
            out[code] = info
        return out

    @api.model
    def _plan_ledger(self, employee, maps, year, date_from):
        """One ledger read for every mapped figure of one payslip: the
        person's finished payslips from 1 January to the day before the pay
        period, and the pay items of every mapped money figure."""
        wanted = set()
        for _c, fig, bas, _m in maps:
            if bas != 'opening' and not self._is_count(fig):
                wanted |= set(self._figure_codes(employee.company_id, fig))
        return self._ledger([employee.id], first_of_year(year), date_from - timedelta(days=1),
                            wanted)

    # ------------------------------------------------------------ joined this year (P5d)
    #
    # Owner decision D31 (2026-11-13): a person with NO figure before Payobook
    # who joined after the company started on Payobook is paid in Payobook
    # alone. "Before Payobook" is then 0 and the sum is complete ONLY when
    #   (a) the employee record's joining date is filled in and falls in the
    #       tax year (never the contract start: a blank joining date stays
    #       "not known", D27);
    #   (b) finished payslips cover every month from the first one up to the
    #       month needed, with no gap, and the figure itself is complete under
    #       P5c's rules (every payslip that should carry it does, nothing
    #       overlapping, no advance that cannot be matched);
    #   (c) the first payslip counted starts on or before the joining month —
    #       nothing can have been paid elsewhere in between.
    # Anything else stays exactly as P5c ("Known so far", "Not covered", and
    # nothing reaches a pay run).

    @api.model
    def _joined_in(self, employee, year):
        """The joining date on the employee record when it falls in `year`,
        else None. Never the contract start (D27)."""
        if not employee or 'date_of_joining' not in employee._fields:
            return None
        joined = employee.date_of_joining
        return joined if joined and year and joined.year == int(year) else None

    @api.model
    def _joiner_covered(self, joined, window, upto=None):
        """True when finished payslips in Payobook alone cover a person who
        joined on `joined`: rule (b) and (c) above for the months up to the
        one before `upto` (a pay period's first day) or, without `upto`, up
        to the latest month counted. `window` = `_person_window` with no
        figures before Payobook."""
        if not joined:
            return False
        counted = window['counted']
        if not counted:
            # Nothing finished yet: complete only for the pay period the
            # person joined in (or before it) — there is nothing in between.
            return bool(upto) and month_floor(upto) <= month_floor(joined)
        first = counted[0]
        if month_floor(first['date_from']) > month_floor(joined):
            return False
        end = month_floor(upto - timedelta(days=1)) if upto else max(window['months'])
        return all(m in window['months'] for m in months_between(first['month'], end))

    @api.model
    def _joiner_label(self, joined):
        """"Joined 1 May 2026 — Payobook payslips only"."""
        return _("Joined %s — Payobook payslips only") % day_label(self.env, joined)

    @api.model
    def _joiner_plan(self, employee, joined, ledger, code, figure, basis, map_id, date_from):
        """The value a mapped pay item receives for a person with no figure
        before Payobook under rule D31, or None (then nothing is sent, as in
        P5c)."""
        window = self._person_window(ledger, employee.id, None, date_from)
        if not self._joiner_covered(joined, window, date_from):
            return None
        info = {'code': code, 'figure': figure, 'basis': basis, 'map_id': map_id,
                'line_id': 0, 'covers_to': '', 'joined': fields.Date.to_string(joined),
                'before': 0.0, 'paid': 0.0, 'gap': [], 'unknown': False, 'incomplete': '',
                'below_zero': [], 'slips': [], 'overlap': [], 'split': [],
                'label': self._figure_label(figure, employee.company_id)}
        if basis != 'opening':
            info['twice'] = sorted({fields.Date.to_string(r['month']) for r in window['twice']})
            if self._is_count(figure):
                info['paid'] = float(len(self._months_paid(window)))
                if basis == 'with_period':
                    info['paid'] += 1.0
            else:
                codes = self._figure_codes(employee.company_id, figure)
                res = self._figure_paid(ledger, window, codes)
                if res['state'] not in ('complete', 'none'):
                    return None
                info['paid'] = res['paid']
                info['have'], info['expected'] = res['have'], res['expected']
                info['below_zero'] = [fields.Date.to_string(m) for m in res['below_zero']]
                info['slips'] = [r['id'] for r in window['counted']]
        info['value'] = round(info['before'] + info['paid'], 2)
        return info

    @api.model
    def _tax_summary_counted(self, emp, qcontext):
        """UPDATES P5d (owner decision D29) — the employee's own tax summary
        (`/my/taxsheet`) counts the year the way "paid in Payobook" does
        (P5c): a mid-month advance is never added on top of the month-end
        payslip that carries the whole month; one that cannot be matched is
        shown apart, not added; money taken off or paid on top counts as an
        amount in the scheme's usual sign, so a refund month reduces.

        The page's own rows and their amounts are untouched; only the year
        totals change, and only for a person whose year on the page includes
        a mid-month advance. Everyone else's page stays exactly as before.
        Totals are shown in the page's own sign (a deduction line the scheme
        writes as a negative number stays negative there)."""
        year = qcontext.get('ytd_year')
        codes = [c for c in (qcontext.get('codes') or []) if c and CODE_RE.fullmatch(c)]
        rows = [r for r in (qcontext.get('rows') or []) if year and r.get('year') == year]
        if not emp or not year or not codes or not rows:
            return qcontext
        page = {r['id']: r for r in rows}
        ledger = self._ledger([emp.id], first_of_year(year), last_of_year(year), codes)
        if not any(ledger['slips'].get(sid, {}).get('cycle') == ADVANCE_CYCLE for sid in page):
            return qcontext
        # Only what the page itself shows: its own payslips, and amounts read
        # off payslip lines (never a stored result the page does not print).
        ledger = dict(ledger, values={k: v for k, v in ledger['values'].items()
                                      if v[1] is not None and k[0] in page})
        window = self._person_window(ledger, emp.id)
        state = {r['id']: r['state'] for r in window['rows'] if r['id'] in page}
        counted = [r for r in window['counted'] if r['id'] in page]
        split = [r for r in window['split'] if r['id'] in page]
        ytd = dict(qcontext.get('ytd') or {})
        apart = {}
        for code in codes:
            sign = self._summary_sign(ledger, counted, code)
            total = 0.0
            for row in counted:
                amount, _neg = self._slip_amount(ledger, row, [code])
                if amount is not None:
                    total += amount * self._row_sign(ledger, row, code, sign)
            ytd[code] = round(total, 2)
            shown = [self._slip_amount(ledger, row, [code])[0] for row in split]
            shown = [a * self._row_sign(ledger, row, code, sign)
                     for a, row in zip(shown, split) if a is not None]
            if shown:
                apart[code] = round(sum(shown), 2)
        words = {
            'advance': _("Mid-month advance · not added"),
            'advance_only': _("Mid-month advance · waits for month end"),
            'split': _("Mid-month advance · shown apart"),
        }
        qcontext.update({
            'ytd': ytd,
            'ytd_not_added': {sid: words[s] for sid, s in state.items() if s in words},
            'ytd_advance_apart': apart,
            'ytd_advance_note': _("Each month is counted once in the year to date: a mid-month "
                                  "advance is part of that month's month-end payslip, so it is "
                                  "not added again. An advance whose month-end payslip is not "
                                  "finished yet is counted with it."),
            'ytd_advance_apart_title': _("Mid-month advances not matched to a month-end payslip "
                                         "· shown apart, not added to the year"),
        })
        return qcontext

    @api.model
    def _summary_sign(self, ledger, counted, code):
        """The sign the tax summary shows money taken off (or paid on top)
        with: the scheme's usual sign for the pay item on the latest payslip
        that has it, else the sign of the page's own sum."""
        raw = 0.0
        for row in reversed(counted):
            entry = ledger['values'].get((row['id'], code))
            if entry is None:
                continue
            conv = ledger['conv'].get((row['config'], code))
            if conv:
                return conv
            raw += entry[0]
        return -1 if raw < 0 else 1

    @api.model
    def _row_sign(self, ledger, row, code, sign):
        """Back to the page's sign: an amount (deduction / employer cost) is
        shown with `sign`; everything else is already signed."""
        entry = ledger['values'].get((row['id'], code))
        role = entry[1] if entry else None
        if role is None:     # the same rule as `_slip_amount`
            role = ledger['roles'].get((row['config'], code), '')
        return sign if role in MAGNITUDE_ROLES else 1

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
    def _plan_blocked(self, info):
        """True when a mapped pay item's value cannot be worked out, so a pay
        run must stop for that person ("no silent zero", extended in P5c to an
        incomplete or doubtful sum)."""
        return bool(info.get('gap') or info.get('unknown') or info.get('incomplete'))

    @api.model
    def _gap_sentence(self, employee, info):
        item = info.get('item_label') or info['code']
        covers = day_label(self.env, fields.Date.to_date(info['covers_to']))
        if info.get('incomplete') == 'overlap' and info.get('overlap'):
            first = info['overlap'][0]
            return _("Year-to-date figures for %(who)s: the payslip for %(start)s to %(end)s "
                     "(%(run)s) overlaps the figures before Payobook, which cover up to %(date)s, "
                     "so part of it may be counted twice and %(item)s cannot be worked out. Load "
                     "figures that cover up to the day before that payslip starts, then calculate "
                     "again.", who=employee.name or '',
                     start=day_label(self.env, fields.Date.to_date(first['from'])),
                     end=day_label(self.env, fields.Date.to_date(first['to'])),
                     run=first.get('run') or '', date=covers, item=item)
        if not info['gap'] and info.get('incomplete') == 'split':
            months = ', '.join(format_date(self.env, fields.Date.to_date(m), date_format='MMMM y')
                               for m in info.get('split', [])[:4])
            return _("Year-to-date figures for %(who)s: the mid-month advance for %(months)s "
                     "cannot be matched to that month's month-end payslip, so it is not known "
                     "whether the month is already counted in full and %(item)s cannot be worked "
                     "out. Link the advance's pay scheme to its month-end pay scheme in "
                     "Mid-Cycle to End-Cycle Mapping, then calculate again.",
                     who=employee.name or '', months=months, item=item)
        if not info['gap'] and info.get('incomplete') == 'partial':
            return _("Year-to-date figures for %(who)s: only %(have)s of the %(expected)s "
                     "finished payslips since %(date)s have the pay items that make up "
                     "%(figure)s, so %(item)s would be too low and cannot be worked out. Check "
                     "which pay items make up %(figure)s in Updates › Year-to-date figures › Set "
                     "up, or load figures that cover up to a later date, then calculate again.",
                     who=employee.name or '', have=info.get('have', 0),
                     expected=info.get('expected', 0), date=covers, figure=info['label'],
                     item=item)
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
