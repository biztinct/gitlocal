# -*- coding: utf-8 -*-
"""WDGAP W2-D1 — re-work finished payslips with today's figures (read-only).

THE QUESTION. "If we had known in September what we know now, what would
September's payslips have said?" — answered item by item, for every finished
payslip of the months picked, WITHOUT changing anything that pays people.

HOW ONE PAYSLIP IS RE-WORKED (`_RetroWork.slip`):

1. BASE = the payslip's STORED inputs (`formula_input_values`): exactly what the
   month was computed from, loan instalments and one-offs included, as they
   were then. Nothing is re-read from a feed, a file or a reservation, so
   nothing is reserved or consumed again (R1).
2. THE SANITY GATE (R2): the stored inputs are evaluated with NO overlay. If
   that does not give back the payslip's stored lines (today's scheme or data
   moved since), the payslip is "cannot be compared exactly", the items that
   moved are named, and every difference is measured against that baseline —
   never against the stored line — and labelled so.
3. THE OVERLAY = only what changed since, from two listed sources:
   * a contract amount change (`hr.contract.advantage.change`) effective in or
     before the payslip's month and ENTERED AFTER the payslip was computed —
     read the way the existing retro reads it (`_prepare_retro_adjustments`:
     (new − old) × days covered ÷ days in the period), with Excel rounding
     (C12). A change the existing retro flow already paid back for this
     payslip is listed and NOT applied again;
   * the "what if" grid: a value a person typed for one person, one month and
     one pay item, with a note. It replaces the stored value (and any contract
     change of the same item).
4. EVALUATION through the scheme's compiled read-only program
   (`formula_program.run_payslip` — the loop the payslip path itself runs,
   column letters and passes included) on the W2-C engine
   (`pb_formula_studio.models.take_home._Engine`: the payslip line set, the
   one pay-band reading on in-memory lines, and the error probe). In-memory
   only (`.new()`); nothing is saved.
5. A formula that raises (the compiled path turns every error into 0, PR facts
   §3) is found by the W2-C probe; the payslip is "could not be worked out",
   naming the pay item, and the rest continue (R6).

THE SCHEME VERSION (handover 2c). A finished run's formula set is NOT
recoverable in full: the payslip stores only a stamp of the rules that computed
it (`formula_content_hash`), the per-component history (`hr.formula.rule.
version`) holds formula text but not default values, removed components lose
their history with them, and nothing records the rules as a set. So every
payslip is re-worked with TODAY's scheme, and the stamp says, per payslip,
whether today's scheme is the one that computed it ("Worked out with today's
version of the scheme" when it is not, or when the payslip has no stamp).
"""
import json
import logging
import time
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.pb_hr_payroll_formula.formula_engine import excel_semantics

_logger = logging.getLogger(__name__)

#: Who may make, work out and read re-works: the people who may approve or
#: reopen a pay run — payroll managers (and administrators).
MANAGER_GROUP = 'om_hr_payroll.group_hr_payroll_manager'
#: Finished payslips.
DONE_SLIP_STATES = ('done', 'paid')
#: Caps per re-work (handover §1.6).
MONTH_CAP = 12
PEOPLE_CAP = 500
#: Payslips per working-out request — the pay run driver's chunk.
CHUNK = 40
#: Contract-change rows that are not a change of the amount: a person saying
#: "that is right", and Payobook filling a blank from the scheme's usual
#: answer (which the payslip already used, so applying it would count it twice).
NOT_A_CHANGE = ('checked', 'auto_default')
#: Band (pb_pay_band) -> what a line is called on screen.
BAND_KIND = {'GROSS': 'earning', 'BASIC': 'earning', 'ALW': 'earning',
             'DED': 'deduction', 'NET': 'net', 'ERCOST': 'employer'}
TOTAL_KEYS = ('gross', 'deductions', 'net', 'employer_cost')

STATES = [
    ('draft', 'Draft'),
    ('done', 'Worked out'),
    ('closed', 'Closed'),
    ('cancelled', 'Cancelled'),
]
SLIP_STATUS = [
    ('same', 'No difference'),
    ('changed', 'Would change'),
    ('drift', 'Cannot be compared exactly'),
    ('error', 'Could not be worked out'),
    ('skipped', 'Not re-worked'),
]


def month_start(value):
    if not value:
        return False
    value = fields.Date.to_date(value)
    return value.replace(day=1)


def month_end(value):
    start = month_start(value)
    return start + relativedelta(months=1, days=-1) if start else False


def months_between(first, last):
    """Months from `first` to `last`, both counted (0 when the order is wrong)."""
    if not first or not last or last < first:
        return 0
    return (last.year - first.year) * 12 + last.month - first.month + 1


def _num(value):
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _loads_list(text):
    try:
        data = json.loads(text or '[]')
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _loads(text):
    try:
        data = json.loads(text or '{}')
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


class PbRetroReview(models.Model):
    _name = 'pb.retro.review'
    _description = 'Past-month re-work'
    _order = 'create_date desc, id desc'

    name = fields.Char(string='Re-work', readonly=True, copy=False)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda s: s.env.company, index=True)
    config_id = fields.Many2one('hr.formula.config', string='Pay scheme', required=True,
                                ondelete='restrict', index=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    month_from = fields.Date(string='From month', required=True)
    month_to = fields.Date(string='To month', required=True)
    people = fields.Selection([
        ('all', 'Everyone in those pay runs'),
        ('picked', 'Only the people picked'),
    ], string='People', default='all', required=True)
    employee_ids = fields.Many2many('hr.employee', 'pb_retro_review_employee_rel',
                                    'review_id', 'employee_id', string='People picked')
    excluded_change_ids = fields.Many2many(
        'hr.contract.advantage.change', 'pb_retro_review_change_rel', 'review_id',
        'change_id', string='Contract changes left out')
    reason = fields.Text(string='Why', required=True)
    state = fields.Selection(STATES, string='Status', default='draft', required=True,
                             index=True, readonly=True)
    whatif_ids = fields.One2many('pb.retro.whatif', 'review_id', string='What if')
    slip_ids = fields.One2many('pb.retro.slip', 'review_id', string='Payslips')
    line_ids = fields.One2many('pb.retro.line', 'review_id', string='Differences')
    worked_out_on = fields.Datetime(string='Worked out on', readonly=True, copy=False)
    worked_out_by = fields.Many2one('res.users', string='Worked out by', readonly=True,
                                    copy=False)
    work_ms = fields.Integer(string='Time to work out (ms)', readonly=True, copy=False)
    scheme_hash = fields.Char(string='Scheme stamp when worked out', readonly=True,
                              copy=False)
    closed_on = fields.Datetime(string='Closed on', readonly=True, copy=False)
    closed_by = fields.Many2one('res.users', string='Closed by', readonly=True, copy=False)
    cancelled_on = fields.Datetime(string='Cancelled on', readonly=True, copy=False)

    # ------------------------------------------------------------ the gate
    @api.model
    def _pb_may_use(self):
        user = self.env.user
        return bool(self.env.su or user._is_admin() or user.has_group(MANAGER_GROUP))

    @api.model
    def _pb_require(self):
        if not self._pb_may_use():
            raise AccessError(_(
                "Re-working past months is for the people who approve pay runs. "
                "Ask your administrator for the payroll manager role."))

    # ------------------------------------------------------------ naming
    def _pb_month_label(self, day):
        if not day:
            return ''
        from odoo.tools.misc import format_date
        return format_date(self.env, day, date_format='MMM y')

    def _pb_months_label(self):
        self.ensure_one()
        a = self._pb_month_label(self.month_from)
        b = self._pb_month_label(self.month_to)
        return a if a == b else '%s – %s' % (a, b)

    def _pb_set_name(self):
        for rec in self:
            scheme = rec.config_id.sudo().name or ''
            rec.name = '%s · %s' % (rec._pb_months_label(), scheme) if scheme \
                else rec._pb_months_label()

    @api.model_create_multi
    def create(self, vals_list):
        self._pb_require()
        for vals in vals_list:
            for key in ('month_from', 'month_to'):
                if vals.get(key):
                    vals[key] = month_start(vals[key])
            if vals.get('config_id') and not vals.get('currency_id'):
                cfg = self.env['hr.formula.config'].sudo().browse(vals['config_id'])
                vals['currency_id'] = cfg.scheme_currency().get('id') or False
        recs = super().create(vals_list)
        recs._pb_check_shape()
        recs._pb_set_name()
        return recs

    def write(self, vals):
        vals = dict(vals)
        for key in ('month_from', 'month_to'):
            if vals.get(key):
                vals[key] = month_start(vals[key])
        shape = {'config_id', 'month_from', 'month_to', 'people', 'employee_ids'}
        if shape & set(vals) and not self.env.context.get('pb_retro_internal'):
            for rec in self:
                if rec.state not in ('draft', 'done'):
                    raise UserError(_("A closed or cancelled re-work cannot be changed."))
        if vals.get('config_id'):
            cfg = self.env['hr.formula.config'].sudo().browse(vals['config_id'])
            vals['currency_id'] = cfg.scheme_currency().get('id') or False
        res = super().write(vals)
        if shape & set(vals):
            self._pb_check_shape()
            self._pb_set_name()
        return res

    def _pb_check_shape(self):
        for rec in self:
            if not (rec.reason or '').strip():
                raise ValidationError(_("Say why this re-work is needed, in a few words."))
            if rec.month_to < rec.month_from:
                raise ValidationError(_("The last month comes before the first month."))
            n = months_between(rec.month_from, rec.month_to)
            if n > MONTH_CAP:
                raise ValidationError(_(
                    "A re-work covers at most %(cap)s months; %(n)s were picked. "
                    "Split it into two re-works.", cap=MONTH_CAP, n=n))
            cfg = rec.config_id.sudo()
            if cfg.company_id and cfg.company_id != rec.company_id:
                raise ValidationError(_("This pay scheme belongs to another company."))
            if rec.company_id not in self.env.companies and not self.env.su:
                raise ValidationError(_("This re-work belongs to a company you do not work in."))

    # =================================================================
    # the payslips in scope
    # =================================================================
    def _pb_scope_slips(self, ids=None):
        """Every finished payslip of the scheme, the months and the people.

        All kinds of run: the caller splits regular (re-worked) from Extra and
        top-up (listed as not re-worked). A payslip belongs to the month its
        period ENDS in (the pay run board's reading). `ids` narrows it to those
        payslips (a chunk) — still only the ones the re-work covers.
        """
        self.ensure_one()
        domain = [('id', 'in', list(ids))] if ids is not None else []
        domain += [
            ('formula_config_id', '=', self.config_id.id),
            ('company_id', '=', self.company_id.id),
            ('state', 'in', list(DONE_SLIP_STATES)),
            ('date_to', '>=', self.month_from),
            ('date_to', '<=', month_end(self.month_to)),
        ]
        if self.people == 'picked':
            domain.append(('employee_id', 'in', self.employee_ids.ids or [0]))
        return self.env['hr.payslip'].sudo().search(domain, order='date_to, employee_id, id')

    @api.model
    def _pb_regular(self, slip):
        run = slip.payslip_run_id
        kind = (run.pb_run_kind if run and 'pb_run_kind' in run._fields else '') or 'regular'
        return kind == 'regular'

    def _pb_split(self, slips=None):
        self.ensure_one()
        slips = self._pb_scope_slips() if slips is None else slips
        regular = slips.filtered(self._pb_regular)
        return regular, slips - regular

    def _pb_check_caps(self, regular):
        people = len(set(regular.mapped('employee_id').ids))
        if people > PEOPLE_CAP:
            raise UserError(_(
                "A re-work covers at most %(cap)s people; these months have %(n)s. "
                "Pick the people, or fewer months.", cap=PEOPLE_CAP, n=people))

    # =================================================================
    # what changed — the overlay
    # =================================================================
    def _pb_computed_at(self, slips):
        """{slip id: when it was last computed} — its lines are re-made on every
        compute, so their newest create date IS that moment; a payslip with no
        line falls back to its own last write."""
        out = {s.id: s.write_date for s in slips}
        if not slips:
            return out
        self.env['hr.payslip.line'].flush_model(['slip_id', 'pb_backpay'])
        # WDGAP W2-D2: a back-pay line can be re-made without the payslip being
        # computed again (a cancelled back pay) — it never says "computed".
        self.env.cr.execute("""
            SELECT slip_id, MAX(create_date) FROM hr_payslip_line
             WHERE slip_id IN %s AND pb_backpay IS NOT TRUE GROUP BY slip_id
        """, (tuple(slips.ids),))
        for slip_id, when in self.env.cr.fetchall():
            if when:
                out[slip_id] = when
        return out

    def _pb_input_codes(self):
        self.ensure_one()
        return {r.code: r for r in self.config_id.sudo().rule_ids
                if r.code and r.column_type == 'input'}

    def _pb_contract_changes(self, slips):
        """{slip id: [overlay row]} — contract amount changes entered after each
        payslip was computed, effective in or before its period.

        The reading of `payroll_import_batch._prepare_retro_adjustments`:
        (new − old) × days of the period on or after the change ÷ days in the
        period (the scheme's proration basis), rounded the Excel way to the
        scheme's proration places. Read-only.
        """
        self.ensure_one()
        if not slips:
            return {}
        cfg = self.config_id.sudo()
        codes = self._pb_input_codes()
        if not codes:
            return {}
        Change = self.env['hr.contract.advantage.change'].sudo()
        changes = Change.search([
            ('employee_id', 'in', slips.mapped('employee_id').ids),
            ('advantage_template_code', 'in', list(codes)),
            ('effective_date', '<=', max(slips.mapped('date_to'))),
            ('change_source', 'not in', list(NOT_A_CHANGE)),
        ], order='effective_date, id')
        changes = changes.filtered(lambda c: (c.new_amount or 0.0) != (c.old_amount or 0.0))
        if not changes:
            return {}
        computed = self._pb_computed_at(slips)
        Batch = self.env['hr.payroll.import.batch'].sudo()
        basis = cfg.proration_basis or 'calendar'
        places = int(cfg.proration_rounding or 0)
        Retro = self.env['hr.payroll.retro.adjustment'].sudo()
        paid_back = {}
        for adj in Retro.search([('original_payslip_id', 'in', slips.ids),
                                 ('advantage_change_id', 'in', changes.ids),
                                 ('state', '!=', 'cancelled')]):
            paid_back[(adj.original_payslip_id.id, adj.advantage_change_id.id)] = adj
        # WDGAP W2-D2: a change another re-work already paid as back pay for a
        # payslip is never paid again for that payslip.
        paid_bp = {}
        if 'pb.retro.backpay' in self.env:
            mine = self._origin.id if self._origin else 0
            live = self.env['pb.retro.backpay'].sudo().search([
                ('source_payslip_id', 'in', slips.ids), ('state', '!=', 'cancelled'),
                ('review_id', '!=', mine or 0)])
            for other in live.mapped('review_id'):
                for row in other.slip_ids.filtered(lambda r: r.payslip_id.id in slips.ids):
                    for item in _loads_list(row.overlay_json):
                        if item.get('kind') == 'contract' and item.get('applied'):
                            paid_bp[(row.payslip_id.id, item.get('change_id'))] = other
        left_out = set(self.sudo().excluded_change_ids.ids)
        by_emp = {}
        for change in changes:
            by_emp.setdefault(change.employee_id.id, []).append(change)
        out = {}
        for slip in slips:
            rows = []
            when = computed.get(slip.id)
            for change in by_emp.get(slip.employee_id.id, []):
                if not slip.date_from or not slip.date_to:
                    continue
                if change.effective_date > slip.date_to:
                    continue
                if when and change.changed_at and change.changed_at <= when:
                    continue        # known when the payslip was computed
                start = max(change.effective_date, slip.date_from)
                period = Batch._get_proration_days(slip.employee_id, slip.date_from,
                                                   slip.date_to, basis)
                covered = Batch._get_proration_days(slip.employee_id, start,
                                                    slip.date_to, basis)
                if not period or not covered:
                    continue
                delta = excel_semantics.excel_round(
                    ((change.new_amount or 0.0) - (change.old_amount or 0.0))
                    * (covered / period), places)
                if not delta:
                    continue
                rule = codes.get(change.advantage_template_code)
                adj = paid_back.get((slip.id, change.id))
                other_bp = paid_bp.get((slip.id, change.id))
                if other_bp and not adj:
                    rows.append({
                        'kind': 'contract', 'change_id': change.id, 'code': rule.code,
                        'name': rule.name or rule.code, 'old': change.old_amount or 0.0,
                        'new': change.new_amount or 0.0,
                        'effective': fields.Date.to_string(change.effective_date),
                        'entered': fields.Datetime.to_string(change.changed_at)
                        if change.changed_at else '',
                        'covered': covered, 'period': period, 'delta': delta,
                        'paid_back': True, 'paid_back_in': other_bp.name or '',
                        'left_out': change.id in left_out, 'note': change.notes or '',
                    })
                    continue
                rows.append({
                    'kind': 'contract',
                    'change_id': change.id,
                    'code': rule.code,
                    'name': rule.name or rule.code,
                    'old': change.old_amount or 0.0,
                    'new': change.new_amount or 0.0,
                    'effective': fields.Date.to_string(change.effective_date),
                    'entered': fields.Datetime.to_string(change.changed_at)
                    if change.changed_at else '',
                    'covered': covered, 'period': period,
                    'delta': delta,
                    'paid_back': bool(adj),
                    'paid_back_in': (adj.applied_in_batch_id.display_name
                                     or adj.applied_in_payslip_id.display_name or '')
                    if adj else '',
                    'left_out': change.id in left_out,
                    'note': change.notes or '',
                })
            if rows:
                out[slip.id] = rows
        return out

    def _pb_whatifs(self):
        self.ensure_one()
        out = {}
        for row in self.whatif_ids:
            if not row.payslip_id or not row.code:
                continue
            out.setdefault(row.payslip_id.id, []).append({
                'kind': 'whatif', 'whatif_id': row.id, 'code': row.code,
                'name': row.name or row.code, 'value': row.value,
                'note': row.note or '',
            })
        return out

    # =================================================================
    # working it out
    # =================================================================
    def _pb_clear(self):
        self.mapped('line_ids').with_context(pb_retro_internal=True).unlink()
        self.mapped('slip_ids').with_context(pb_retro_internal=True).unlink()

    def pb_work_start(self):
        """Clear the snapshot, list the Extra/top-up payslips, and return the
        regular payslips to work out (in the order they will be worked)."""
        self.ensure_one()
        self._pb_require()
        if self.state not in ('draft', 'done'):
            raise UserError(_("A closed or cancelled re-work cannot be worked out again."))
        regular, other = self._pb_split()
        self._pb_check_caps(regular)
        self._pb_clear()
        Slip = self.env['pb.retro.slip'].with_context(pb_retro_internal=True)
        currency = self.currency_id.id
        vals = []
        for slip in other:
            run = slip.payslip_run_id
            kind = run.pb_run_kind if run and 'pb_run_kind' in run._fields else ''
            vals.append(dict(self._pb_slip_head(slip), status='skipped',
                             currency_id=currency,
                             skip_reason='extra' if kind == 'extra' else 'topup'))
        if vals:
            Slip.create(vals)
        return {'slip_ids': regular.ids, 'total': len(regular), 'skipped': len(other),
                'chunk': CHUNK}

    def _pb_slip_head(self, slip):
        run = slip.payslip_run_id
        return {
            'review_id': self.id, 'payslip_id': slip.id,
            'employee_id': slip.employee_id.id,
            'employee_name': slip.employee_id.sudo().name or '',
            'month': month_start(slip.date_to),
            'date_from': slip.date_from, 'date_to': slip.date_to,
            'run_name': run.name if run else '',
        }

    def pb_work_chunk(self, slip_ids):
        """Work out these payslips (at most one chunk) and store their rows.

        Only payslips the re-work covers are taken, whatever the browser sent.
        """
        self.ensure_one()
        self._pb_require()
        if self.state not in ('draft', 'done'):
            raise UserError(_("A closed or cancelled re-work cannot be worked out again."))
        ids = [int(i) for i in (slip_ids or [])][:CHUNK]
        if not ids:
            return {'done': 0}
        slips = self._pb_scope_slips(ids).filtered(self._pb_regular)
        done_already = set(self.env['pb.retro.slip'].search([
            ('review_id', '=', self.id), ('payslip_id', 'in', slips.ids)]).mapped('payslip_id').ids)
        slips = slips.filtered(lambda s: s.id not in done_already)
        if not slips:
            return {'done': 0}
        work = _RetroWork(self)
        overlay = self._pb_contract_changes(slips)
        whatifs = self._pb_whatifs()
        SlipRow = self.env['pb.retro.slip'].with_context(pb_retro_internal=True)
        Line = self.env['pb.retro.line'].with_context(pb_retro_internal=True)
        counts = {}
        for slip in slips:
            rows = list(overlay.get(slip.id, [])) + list(whatifs.get(slip.id, []))
            try:
                res = work.slip(slip, rows)
            except Exception:       # noqa: BLE001 — R6: one payslip never stops the rest
                _logger.warning('pb_retro: payslip %s could not be worked out', slip.id,
                                exc_info=True)
                res = {'status': 'error', 'error_item': '', 'error_why': 'other',
                       'lines': [], 'overlay': rows}
            head = dict(self._pb_slip_head(slip), currency_id=self.currency_id.id)
            head.update({k: v for k, v in res.items() if k not in ('lines', 'overlay')})
            head['overlay_json'] = json.dumps(res.get('overlay') or [], sort_keys=True)
            row = SlipRow.create(head)
            if res.get('lines'):
                Line.create([dict(line, review_id=self.id, slip_row_id=row.id,
                                  employee_id=slip.employee_id.id,
                                  month=head['month'],
                                  currency_id=self.currency_id.id)
                             for line in res['lines']])
            counts[res['status']] = counts.get(res['status'], 0) + 1
        return {'done': len(slips), 'counts': counts}

    def pb_work_finish(self, ms=0):
        self.ensure_one()
        self._pb_require()
        self.with_context(pb_retro_internal=True).write({
            'state': 'done',
            'worked_out_on': fields.Datetime.now(),
            'worked_out_by': self.env.uid,
            'work_ms': int(ms or 0),
            'scheme_hash': self.config_id.sudo()._content_hash(),
        })
        return True

    def action_work_out(self):
        """The whole working-out in one call (tests, and a fallback door).
        The screen drives the same three steps in chunks with a progress bar."""
        for rec in self:
            started = time.monotonic()
            plan = rec.pb_work_start()
            ids = plan['slip_ids']
            for i in range(0, len(ids), CHUNK):
                rec.pb_work_chunk(ids[i:i + CHUNK])
            rec.pb_work_finish(int((time.monotonic() - started) * 1000))
        return True

    def action_close(self):
        self._pb_require()
        for rec in self:
            if rec.state != 'done':
                raise UserError(_("Only a worked-out re-work can be closed."))
        self.with_context(pb_retro_internal=True).write({
            'state': 'closed', 'closed_on': fields.Datetime.now(), 'closed_by': self.env.uid})
        return True

    def action_cancel(self):
        self._pb_require()
        for rec in self:
            if rec.state not in ('draft', 'done'):
                raise UserError(_("Only a draft or worked-out re-work can be cancelled."))
        self.with_context(pb_retro_internal=True).write({
            'state': 'cancelled', 'cancelled_on': fields.Datetime.now()})
        return True

    def action_back_to_draft(self):
        """A changed overlay makes the snapshot out of date: it goes back to
        draft until it is worked out again."""
        self._pb_require()
        for rec in self:
            if rec.state == 'done':
                rec._pb_clear()
                rec.with_context(pb_retro_internal=True).write({'state': 'draft'})
        return True

    # =================================================================
    # the result, rolled up (per currency — R4)
    # =================================================================
    def _pb_rollup(self):
        """Per currency: totals of the differences and the people behind them.

        A re-work has one scheme and so one currency; the roll-up is still
        keyed by currency so that nothing anywhere adds two (R4).
        """
        self.ensure_one()
        out = {}
        for row in self.slip_ids:
            cur = row.currency_id
            bucket = out.setdefault(cur.id, {
                'currency': cur, 'diff': dict.fromkeys(TOTAL_KEYS, 0.0),
                'people': set(), 'items': {}})
            if row.status in ('changed', 'drift'):
                for key in TOTAL_KEYS:
                    bucket['diff'][key] += row['diff_%s' % key] or 0.0
                if any(row['diff_%s' % key] for key in TOTAL_KEYS) or row.line_ids:
                    bucket['people'].add(row.employee_id.id)
        for line in self.line_ids:
            bucket = out.get(line.currency_id.id)
            if bucket is None or not line.counts or line.band != 'deduction':
                continue
            item = bucket['items'].setdefault(line.name, 0.0)
            bucket['items'][line.name] = item + (line.diff or 0.0)
        decimals = {cid: (b['currency'].decimal_places or 0) for cid, b in out.items()}
        for cid, bucket in out.items():
            for key in TOTAL_KEYS:
                bucket['diff'][key] = excel_semantics.excel_round(bucket['diff'][key],
                                                                  decimals[cid])
            bucket['items'] = {k: excel_semantics.excel_round(v, decimals[cid])
                               for k, v in bucket['items'].items()}
        return out


class PbRetroWhatif(models.Model):
    """One typed correction: this person, this month, this pay item = value."""
    _name = 'pb.retro.whatif'
    _description = 'Past-month re-work: a what-if value'
    _order = 'review_id, sequence, id'

    review_id = fields.Many2one('pb.retro.review', required=True, ondelete='cascade',
                                index=True)
    company_id = fields.Many2one(related='review_id.company_id', store=True, index=True)
    sequence = fields.Integer(default=10)
    payslip_id = fields.Many2one('hr.payslip', string='Payslip', required=True,
                                 ondelete='cascade')
    employee_id = fields.Many2one(related='payslip_id.employee_id', store=True)
    code = fields.Char(string='Pay item code', required=True)
    name = fields.Char(string='Pay item')
    value = fields.Float(string='Value', digits=(16, 4))
    note = fields.Char(string='Note', required=True)

    @api.constrains('payslip_id', 'code', 'review_id')
    def _pb_check(self):
        for row in self:
            review = row.review_id.sudo()
            slip = row.payslip_id.sudo()
            if slip.formula_config_id != review.config_id:
                raise ValidationError(_("A what-if value must be for a payslip of the "
                                        "re-work's pay scheme."))
            codes = review._pb_input_codes()
            if row.code not in codes:
                raise ValidationError(_("“%s” is not a pay item a value can be typed for.",
                                        row.code))


class PbRetroSlip(models.Model):
    """One payslip of a re-work — the stored snapshot of what was found."""
    _name = 'pb.retro.slip'
    _description = 'Past-month re-work: one payslip'
    _order = 'review_id, month, employee_name, payslip_id, id'

    review_id = fields.Many2one('pb.retro.review', required=True, ondelete='cascade',
                                index=True)
    company_id = fields.Many2one(related='review_id.company_id', store=True, index=True)
    payslip_id = fields.Many2one('hr.payslip', string='Payslip', ondelete='set null',
                                 index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', ondelete='set null',
                                  index=True)
    employee_name = fields.Char(string='Employee name')
    month = fields.Date(string='Month')
    date_from = fields.Date()
    date_to = fields.Date()
    run_name = fields.Char(string='Pay run')
    currency_id = fields.Many2one('res.currency')
    status = fields.Selection(SLIP_STATUS, string='Result', required=True, index=True)
    skip_reason = fields.Selection([('extra', 'Extra run'), ('topup', 'Top-up run')])
    no_inputs = fields.Boolean(string='No stored figures')
    scheme_changed = fields.Boolean(string='Scheme changed since')
    scheme_unknown = fields.Boolean(string='No scheme stamp')
    drift_json = fields.Text(string='Items that do not reproduce')
    error_item = fields.Char(string='Pay item with an error')
    error_why = fields.Char()
    overlay_json = fields.Text(string='What changed')
    line_ids = fields.One2many('pb.retro.line', 'slip_row_id')
    was_gross = fields.Float(digits=(16, 4))
    was_deductions = fields.Float(digits=(16, 4))
    was_net = fields.Float(digits=(16, 4))
    was_employer_cost = fields.Float(digits=(16, 4))
    diff_gross = fields.Float(digits=(16, 4))
    diff_deductions = fields.Float(digits=(16, 4))
    diff_net = fields.Float(digits=(16, 4))
    diff_employer_cost = fields.Float(digits=(16, 4))


class PbRetroLine(models.Model):
    """One pay item of one payslip that would change."""
    _name = 'pb.retro.line'
    _description = 'Past-month re-work: one difference'
    _order = 'review_id, month, employee_id, sequence, id'

    review_id = fields.Many2one('pb.retro.review', required=True, ondelete='cascade',
                                index=True)
    company_id = fields.Many2one(related='review_id.company_id', store=True, index=True)
    slip_row_id = fields.Many2one('pb.retro.slip', required=True, ondelete='cascade',
                                  index=True)
    employee_id = fields.Many2one('hr.employee', ondelete='set null', index=True)
    month = fields.Date()
    sequence = fields.Integer()
    code = fields.Char(string='Pay item code')
    name = fields.Char(string='Pay item')
    band = fields.Char(string='Kind of line')
    counts = fields.Boolean(string='Counted in totals')
    was = fields.Float(string='Was', digits=(16, 4))
    baseline = fields.Float(string='Worked out again, nothing changed', digits=(16, 4))
    would_be = fields.Float(string='Would be', digits=(16, 4))
    diff = fields.Float(string='Difference', digits=(16, 4))
    currency_id = fields.Many2one('res.currency')
    cause = fields.Text(string='Why')


# =====================================================================
# the per-payslip engine
# =====================================================================
class _RetroWork:
    """One scheme compiled once; every payslip of a chunk worked through it."""

    def __init__(self, review):
        from odoo.addons.pb_formula_studio.models.take_home import _Engine
        from odoo.addons.pb_hr_payroll_formula.models import formula_program
        self.review = review
        self.env = review.env
        self.config = review.config_id.sudo()
        self.engine = _Engine(review.env(su=True), self.config)
        self._run = formula_program.run_payslip
        currency = self.config.scheme_currency()
        self.decimals = int(currency.get('decimals') or 0)
        self.hash_now = self.config._content_hash()
        self.names = {r.code: (r.name or r.code) for r in self.engine.rules if r.code}
        self.spec_by_code = {s['code']: s for s in self.engine.specs}
        # Every formula a payslip line depends on (inclusive): a formula that
        # raises anywhere upstream makes that payslip untrustworthy.
        self.feeding = self.engine.upstream(list(self.spec_by_code))
        self._up = {}

    # ------------------------------------------------------------- helpers
    def r(self, value):
        return excel_semantics.excel_round(value or 0.0, self.decimals)

    def evaluate(self, inputs):
        return self._run(self.engine.steps, inputs)[0]

    def amounts(self, results):
        """{code: line total} of the lines a payslip would get."""
        return {line.code: line.total or 0.0 for line in self.engine.lines(results)}

    def upstream(self, code):
        if code not in self._up:
            self._up[code] = self.engine.upstream([code])
        return self._up[code]

    def broken(self, results):
        errs = self.engine.diagnose(results)
        hit = sorted(code for code in errs if code in self.feeding)
        return (hit[0], errs[hit[0]]) if hit else (None, None)

    # ------------------------------------------------------------- one payslip
    def slip(self, slip, rows):
        inputs = _loads(slip.formula_input_values)
        stamp = slip.formula_content_hash or ''
        out = {
            'no_inputs': not inputs,
            'scheme_changed': bool(stamp) and stamp != self.hash_now,
            'scheme_unknown': not stamp,
            'overlay': rows,
        }
        # -- what the payslip says today (stored lines, per code)
        # WDGAP W2-D2: back pay for EARLIER months that this payslip paid is
        # not part of what its own month's formulas worked out — leave the
        # back-pay lines out, and take the back pay out of its take-home.
        own = slip.line_ids.filtered(lambda l: not l.pb_backpay) \
            if 'pb_backpay' in slip.line_ids._fields else slip.line_ids
        backpay_net = slip.pb_backpay_net if 'pb_backpay_net' in slip._fields else 0.0
        net_code = own.pb_net_line().code if backpay_net else False
        stored = {}
        stored_meta = {}
        for line in own:
            stored[line.code] = stored.get(line.code, 0.0) + (line.total or 0.0)
            stored_meta.setdefault(line.code, line)
        if net_code:
            stored[net_code] = stored.get(net_code, 0.0) - backpay_net
        was_totals = own.pb_pay_totals() if own else dict.fromkeys(TOTAL_KEYS, 0.0)
        if backpay_net and was_totals:
            was_totals = dict(was_totals, net=(was_totals.get('net') or 0.0) - backpay_net)
        for key in TOTAL_KEYS:
            out['was_%s' % key] = self.r(was_totals.get(key))

        # -- the sanity gate: stored inputs, no overlay (R2)
        base = self.evaluate(inputs)
        code, why = self.broken(base)
        if code:
            out.update(status='error', error_item=self.names.get(code, code),
                       error_why=why, lines=[])
            return out
        base_amounts = self.amounts(base)
        drift = []
        for c in sorted(set(stored) | set(base_amounts)):
            a, b = stored.get(c, 0.0), base_amounts.get(c, 0.0)
            if self.r(a) != self.r(b):
                drift.append({'code': c, 'name': self._name_of(c, stored_meta),
                              'stored': self.r(a), 'today': self.r(b)})
        out['drift_json'] = json.dumps(drift, sort_keys=True) if drift else False

        # -- the overlay: only what changed since
        trial = dict(inputs)
        used = []
        whatif_codes = {row['code'] for row in rows if row['kind'] == 'whatif'}
        for row in rows:
            if row['kind'] != 'contract':
                continue
            if row.get('paid_back') or row.get('left_out') or row['code'] in whatif_codes:
                row['applied'] = False
                continue
            trial[row['code']] = _num(trial.get(row['code'], 0.0)) + row['delta']
            row['applied'] = True
            used.append(row)
        for row in rows:
            if row['kind'] == 'whatif':
                row['was_input'] = _num(inputs.get(row['code'], 0.0))
                trial[row['code']] = row['value']
                row['applied'] = True
                used.append(row)
        for row in rows:
            if row['kind'] == 'contract':
                row['was_input'] = _num(inputs.get(row['code'], 0.0))

        if not used:
            out.update(status='drift' if drift else 'same', lines=[])
            for key in TOTAL_KEYS:
                out['diff_%s' % key] = 0.0
            return out

        would = self.evaluate(trial)
        code, why = self.broken(would)
        if code:
            out.update(status='error', error_item=self.names.get(code, code),
                       error_why=why, lines=[])
            return out
        would_amounts = self.amounts(would)
        base_totals = self.engine.totals(base)
        would_totals = self.engine.totals(would)
        for key in TOTAL_KEYS:
            out['diff_%s' % key] = self.r(would_totals.get(key, 0.0)
                                          - base_totals.get(key, 0.0))
        lines = []
        for seq, spec in enumerate(self.engine.specs):
            c = spec['code']
            diff = self.r(would_amounts.get(c, 0.0) - base_amounts.get(c, 0.0))
            if not diff:
                continue
            was = stored.get(c, base_amounts.get(c, 0.0))
            causes = [row for row in used if row['code'] in self.upstream(c)]
            lines.append({
                'sequence': seq, 'code': c, 'name': spec['name'],
                'band': BAND_KIND.get(spec['band'] or '', 'info'),
                'counts': bool(spec['counts']),
                'was': self.r(was), 'baseline': self.r(base_amounts.get(c, 0.0)),
                'would_be': self.r(was + diff), 'diff': diff,
                'cause': json.dumps([self._cause_key(row) for row in causes],
                                    sort_keys=True),
            })
        status = 'drift' if drift else ('changed' if lines else 'same')
        out.update(status=status, lines=lines)
        return out

    def _name_of(self, code, stored_meta):
        if code in self.spec_by_code:
            return self.spec_by_code[code]['name']
        line = stored_meta.get(code)
        return (line.name if line else '') or code

    @staticmethod
    def _cause_key(row):
        if row['kind'] == 'whatif':
            return {'kind': 'whatif', 'id': row.get('whatif_id'), 'code': row['code']}
        return {'kind': 'contract', 'id': row.get('change_id'), 'code': row['code']}
