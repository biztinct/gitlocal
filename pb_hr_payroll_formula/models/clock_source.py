# -*- coding: utf-8 -*-
"""WFSETUP P10b — "From the clocks": hours that replace the pay data file.

Design of record: `docs/handovers/wfsetup/WFSETUP_P10A_PROPOSAL.md` §2.2, §3,
§4.1, with the owner rulings R8–R16 (`WFSETUP_OWNER_RULINGS.md`) on top.

THE SHAPE (RUNSRC `period_key` precedent, NOT a fourth `source_ids` kind):

* `hr.formula.config.pb_clock_from` — ONE date per scheme. Empty = off. A pay
  period wholly before it is computed exactly as today (the overlay returns at
  its first lines); a period on/after it takes every clock-answered input from
  the clocks; a period that crosses it is refused.
* `hr.formula.rule.pb_clock_key` — which clock fact an INPUT component is
  answered by. Written through `set_source_binding('clock', key)` so every
  board keeps one entry point.
* `_pb_clock_apply` — the overlay. Called by BOTH resolvers (the pay data file
  walk and the file-less payslip resolver) after the pay period fill. It
  OVERRIDES the file's value for a clock-answered input and never falls back
  to the file cell or to the default: any doubt refuses the payslip with the
  reasons named.
* The facts themselves come from `_pb_clock_facts`, a stub here that the
  late-rules module (`pb_attendance_policy`) answers. Without it a clock
  scheme refuses ("Clock hours are not installed").
* A stamp of the source records (`_pb_clock_signature`) is written on the
  payslip when it is computed and checked again when it is approved.

Lateness reaches pay through ONE door only (R10, proposal §5): the paid normal
hours the late rules already cut. Information-only facts (actual hours, late
minutes, …) may never feed a formula (R11, `_pb_check_clock_info`).
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from . import input_provenance

_logger = logging.getLogger(__name__)

#: The clock facts, in the order a screen lists them: key -> (label, use).
#: `pay` facts may feed a formula; `info` facts are shown, never computed
#: with; `empty` is a column that must stay empty in a clock month (Sunday
#: hours: Sunday work arrives as rest-day overtime, a number there would pay
#: it twice). Labels are translated where they are shown (`_pb_clock_label`).
CLOCK_KEYS = (
    ('clock.paid_days', "Paid days (days worked + paid leave + public holidays)", 'pay'),
    ('clock.worked_days', "Days worked", 'info'),
    ('clock.paid_leave_days', "Paid leave days", 'info'),
    ('clock.holiday_days', "Public holiday days", 'info'),
    ('clock.paid_normal_hours', "Paid normal hours", 'info'),
    ('clock.ot_hours', "Overtime hours (within the legal limit)", 'pay'),
    ('clock.ot_premium_hours', "Overtime premium hours", 'pay'),
    ('clock.over_limit_hours', "Overtime above the legal limit", 'info'),
    ('clock.actual_hours', "Actual hours (from punches)", 'info'),
    ('clock.late_minutes', "Late minutes", 'info'),
    ('clock.late_days', "Late working days (for allowance rules)", 'pay'),
    ('clock.deduction_hours', "Hours taken off for lateness", 'info'),
    ('clock.empty', "Left empty (paid through the clocks)", 'empty'),
)
CLOCK_USE = {key: use for key, _label, use in CLOCK_KEYS}
INFO_KEYS = frozenset(k for k, use in CLOCK_USE.items() if use == 'info')
#: Provenance `via` of a value the clocks answered.
CLOCK_VIA = 'clock'

#: Input codes other payroll bridges fill on the file-less path (overtime
#: requests, approved weeks, confirmed late minutes). A clock key on one of
#: them would be added to twice.
BRIDGE_CODES = frozenset({'OTHRS150', 'OTHRS200', 'OTHRS300', 'OTHRSNGT', 'BONHRS',
                          'REGHRS', 'TOTHRS', 'WORKDAYS', 'LATEMIN', 'EARLYMIN'})
#: Late / early minute sources of the weekly Close (`pb_time_pay`). A scheme
#: paid from the clocks takes lateness off through the late rules already.
LATE_CODES = frozenset({'LATEMIN', 'EARLYMIN'})
LATE_SOURCE_KEYS = frozenset({'time.late_minutes', 'time.early_minutes'})

#: Test hook (proposal §3.3): how many times the overlay went past its gate.
BRANCH_COUNTER = {'entered': 0}


def _clock_labels(self):
    """The translated label of every key (literal `_()` calls for gettext).

    Takes a record called `self` so `_()` finds the user's language in this
    frame (odoo.tools.translate._get_lang)."""
    return {
        'clock.paid_days': _("Paid days (days worked + paid leave + public holidays)"),
        'clock.worked_days': _("Days worked"),
        'clock.paid_leave_days': _("Paid leave days"),
        'clock.holiday_days': _("Public holiday days"),
        'clock.paid_normal_hours': _("Paid normal hours"),
        'clock.ot_hours': _("Overtime hours (within the legal limit)"),
        'clock.ot_premium_hours': _("Overtime premium hours"),
        'clock.over_limit_hours': _("Overtime above the legal limit"),
        'clock.actual_hours': _("Actual hours (from punches)"),
        'clock.late_minutes': _("Late minutes"),
        'clock.late_days': _("Late working days (for allowance rules)"),
        'clock.deduction_hours': _("Hours taken off for lateness"),
        'clock.empty': _("Left empty (paid through the clocks)"),
    }


def _is_blank(value):
    if value is None or value is False:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return float(value) == 0.0
    except (TypeError, ValueError):
        return False


class ClockFormulaConfig(models.Model):
    _inherit = 'hr.formula.config'

    pb_clock_from = fields.Date(
        string='Hours from the clocks from', tracking=True,
        help="From this date, the components marked 'From the clocks' take their "
             "value from the clocks and the late and overtime rules instead of "
             "the pay data file. Pay periods before it are paid exactly as "
             "before. Empty = off.")

    # ------------------------------------------------------------ modes
    def _pb_clock_mode(self, date_from, date_to):
        """'off' | 'before' | 'clock' | 'crossing' for one pay period."""
        self.ensure_one()
        start = self.pb_clock_from
        if not start:
            return 'off'
        df = fields.Date.to_date(date_from)
        dt = fields.Date.to_date(date_to) or df
        if not df:
            return 'off'
        if dt < start:
            return 'before'
        if df >= start:
            return 'clock'
        return 'crossing'

    def _pb_clock_rules(self):
        self.ensure_one()
        return self.rule_ids.filtered(lambda r: r.column_type == 'input' and r.pb_clock_key)

    # ------------------------------------------------------------ provider seams
    def _pb_clock_facts(self, employee, date_from, date_to, live=True):
        """{'facts': {key: fact}, 'blockers': [..], 'info': [..]} or {}.

        The late-rules module answers this. `{}` means nothing can answer
        clock facts on this database, and the overlay refuses."""
        return {}

    def _pb_clock_signature(self, employee, date_from, date_to):
        """A stamp of the records the clock facts were made from, or ''."""
        return ''

    def _pb_clock_label(self, key):
        return _clock_labels(self).get(key, key)

    # ------------------------------------------------------------ the overlay
    def _pb_clock_apply(self, employee, date_from, date_to, input_values, prov=None):
        """Replace clock-answered inputs with the clock facts (in place).

        Returns None when the period is not paid from the clocks (nothing is
        touched — the neutrality rail), else True. Raises UserError naming
        every reason a clock value cannot be given. Never falls back.
        """
        if len(self) != 1 or not self.pb_clock_from:
            return None
        if self.env.context.get('pb_application_data_mode'):
            return None
        mode = self._pb_clock_mode(date_from, date_to)
        if mode in ('off', 'before'):
            return None
        rules = self._pb_clock_rules()
        if not rules:
            return None
        BRANCH_COUNTER['entered'] += 1
        who = (employee.display_name if employee else '') or _("this person")
        if mode == 'crossing':
            raise UserError(_(
                "This pay period starts before and ends after the clock start date "
                "(%(day)s). Split it at that date.",
                day=fields.Date.to_string(self.pb_clock_from)))
        if not employee:
            raise UserError(_("Hours from the clocks need the person this row is about."))
        result = self.sudo()._pb_clock_facts(employee, date_from, date_to) or {}
        if not result:
            raise UserError(_("Clock hours are not installed for this scheme. "
                              "Ask an administrator to install the late and overtime rules."))
        facts = result.get('facts') or {}
        reasons = [b.get('text') or b.get('label') or '' for b in result.get('blockers') or []]
        labels = _clock_labels(self)
        for rule in rules:
            key = rule.pb_clock_key
            code = rule.code
            entry = (prov or {}).get(code) or {}
            old = input_values.get(code)
            from_file = (entry.get('src') in ('excel', 'feed')) and not _is_blank(old)
            if key == 'clock.empty':
                if from_file:
                    reasons.append(_(
                        "“%(col)s” must be empty in months paid from the clocks — that work "
                        "is paid as overtime from the clocks (the file says %(value)s).",
                        col=rule.name or code, value=old))
                continue
            fact = facts.get(key)
            if not fact or fact.get('status') != 'resolved':
                reasons.append((fact or {}).get('reason') or _(
                    "%(fact)s could not be worked out.", fact=labels.get(key, key)))
                continue
            value = fact.get('value')
            input_values[code] = value
            if prov is not None:
                ignored = None
                if from_file:
                    try:
                        differs = float(old) != float(value)
                    except (TypeError, ValueError):
                        differs = True
                    if differs:
                        ignored = input_provenance.ignored_side(
                            entry.get('src') or 'excel', entry.get('key'), old)
                prov[code] = input_provenance.entry(
                    'employee_field', key=key, via=CLOCK_VIA, ignored=ignored)
        reasons = [r for r in reasons if r]
        if reasons:
            seen, ordered = set(), []
            for r in reasons:
                if r not in seen:
                    seen.add(r)
                    ordered.append(r)
            raise UserError(_(
                "Hours from the clocks are not ready for %(who)s: %(why)s",
                who=who, why='; '.join(ordered)))
        return True

    # ------------------------------------------------------------ guards (§5)
    @api.constrains('pb_clock_from')
    def _pb_check_clock_scheme(self):
        for config in self.filtered('pb_clock_from'):
            config._pb_clock_refusals(raise_first=True)

    def _pb_clock_refusals(self, raise_first=False):
        """Scheme-level reasons a clock scheme is unsafe, as sentences."""
        self.ensure_one()
        out = []
        for rule in self.rule_ids.filtered(lambda r: r.column_type == 'input'):
            code = (rule.code or '').upper()
            if code in LATE_CODES or (rule.application_source_key or '') in LATE_SOURCE_KEYS:
                out.append(_(
                    "Late minutes are already taken off through the late rules. Remove "
                    "the column “%s” to avoid taking them off twice.", rule.name or rule.code))
        if out and raise_first:
            raise ValidationError(out[0])
        return out

    # ------------------------------------------------------------ the screen twin
    #: Codes a new information column gets — underscore-free and pairwise
    #: non-substring (formula converter contract).
    _PB_CLOCK_NEW_CODES = {
        'clock.paid_days': 'CLKPAIDDAYS', 'clock.worked_days': 'CLKDAYSWORKED',
        'clock.paid_leave_days': 'CLKPAIDLEAVE', 'clock.holiday_days': 'CLKHOLIDAYS',
        'clock.paid_normal_hours': 'CLKPAIDHOURS', 'clock.ot_hours': 'CLKOTHOURS',
        'clock.ot_premium_hours': 'CLKPREMHOURS', 'clock.over_limit_hours': 'CLKOVERLIMIT',
        'clock.actual_hours': 'CLKACTUALHOURS', 'clock.late_minutes': 'CLKMINUTESLATE',
        'clock.deduction_hours': 'CLKLATEHOURS', 'clock.late_days': 'CLKLATEDAYS',
    }

    def pb_clock_meta(self):
        """What the scheme editor's "Hours from the clocks" card shows."""
        self.ensure_one()
        labels = _clock_labels(self)
        inputs = self.rule_ids.filtered(lambda r: r.column_type == 'input').sorted(
            key=lambda r: (r.sequence or 0, r.id))
        mapping = {}
        for rule in inputs.filtered('pb_clock_key'):
            mapping.setdefault(rule.pb_clock_key, rule.id)
        return {
            'available': bool(self.env.get('pb.clock.payroll') is not None),
            'clock_from': fields.Date.to_string(self.pb_clock_from) if self.pb_clock_from else '',
            'keys': [{'key': key, 'label': labels.get(key, label), 'use': use}
                     for key, label, use in CLOCK_KEYS],
            'map': mapping,
            'inputs': [{'id': r.id, 'col': r.column_letter or '', 'code': r.code or '',
                        'name': r.name or '', 'info': r.net_role in (False, 'info') and not r.appears_on_payslip}
                       for r in inputs],
            'issues': self._pb_clock_refusals(),
        }

    def pb_clock_bind(self, key, rule_id):
        """Say which input a clock fact answers: an input id, 'new' (add an
        information-only column for it) or False (nothing answers it)."""
        self.ensure_one()
        self.check_access('write')
        labels = _clock_labels(self)
        if key not in CLOCK_USE:
            raise UserError(_("The clocks do not answer that. Pick one of the hours or days in the list."))
        inputs = self.rule_ids.filtered(lambda r: r.column_type == 'input')
        current = inputs.filtered(lambda r: r.pb_clock_key == key)
        target = self.env['hr.formula.rule']
        if rule_id == 'new':
            if CLOCK_USE[key] != 'info':
                raise UserError(_("Choose the column this is paid in — only information columns are added here."))
            codes = [c for c in self.rule_ids.mapped('code') if c]
            base = self._PB_CLOCK_NEW_CODES.get(key) or 'CLKINFO'
            code, n = base, 1
            while any(code == c or code in c or c in code for c in codes):
                n += 1
                code = '%s%s' % (base, n)
            seq = max(self.rule_ids.mapped('sequence') or [0]) + 10
            vals = {'config_id': self.id, 'name': labels.get(key, key), 'code': code,
                    'column_type': 'input', 'net_role': 'info', 'appears_on_payslip': False,
                    'is_required': False, 'default_value': 0.0, 'sequence': seq, 'data_source': 'none'}
            Rule = self.env['hr.formula.rule']
            for name, value in (('net_role_source', 'user'), ('value_kind', 'quantity'),
                                ('value_kind_source', 'user'), ('number_format', 'number')):
                if name in Rule._fields:
                    vals[name] = value
            target = Rule.create(vals)
        elif rule_id:
            target = inputs.filtered(lambda r: r.id == int(rule_id))
            if not target:
                raise UserError(_("That column is not an input of this scheme."))
        (current - target).clear_source_binding('clock')
        if target:
            target.set_source_binding('clock', key)
        return self.pb_clock_meta()


class ClockFormulaRule(models.Model):
    _inherit = 'hr.formula.rule'

    pb_clock_key = fields.Selection(
        selection='_pb_clock_key_selection', string='Answered by the clocks',
        help="From the scheme's clock start date, this component takes its value from "
             "the clocks and the late and overtime rules instead of the pay data file.")

    @api.model
    def _pb_clock_key_selection(self):
        labels = _clock_labels(self)
        return [(key, labels.get(key, label)) for key, label, _use in CLOCK_KEYS]

    @api.constrains('pb_clock_key', 'column_type', 'code', 'net_role',
                    'appears_on_payslip', 'excel_formula')
    def _pb_check_clock_info(self):
        """R11 / proposal §3.4 — information stays information."""
        configs = self.mapped('config_id')
        for rule in self.filtered('pb_clock_key'):
            if rule.column_type != 'input':
                raise ValidationError(_("“%s” is calculated — only an input can come from the clocks.")
                                      % (rule.name or rule.code))
            if (rule.code or '').upper() in BRIDGE_CODES:
                raise ValidationError(_(
                    "“%s” is already filled from overtime requests or approved weeks. "
                    "Use another component for hours from the clocks.") % (rule.name or rule.code))
            if rule.pb_clock_key in INFO_KEYS and (
                    rule.net_role not in (False, 'info') or rule.appears_on_payslip):
                raise ValidationError(_(
                    "“%s” is shown for information and cannot be paid. Set its pay role "
                    "to “Information only” and keep it off the payslip lines.")
                    % (rule.name or rule.code))
        for config in configs:
            info = config.rule_ids.filtered(
                lambda r: r.column_type == 'input' and r.pb_clock_key in INFO_KEYS)
            if not info:
                continue
            refs = {}
            for r in info:
                for token in {(r.code or '').upper(), (r.column_letter or '').upper()}:
                    if token:
                        refs[token] = r
            for formula in config.rule_ids.filtered(lambda r: r.column_type == 'formula'):
                deps = {d.strip().upper() for d in (formula.formula_dependencies or '').split(',') if d.strip()}
                deps |= {d.rstrip('0123456789') for d in deps}
                hit = next((refs[t] for t in deps if t in refs), None)
                if hit:
                    raise ValidationError(_(
                        "“%s” is shown for information and cannot be used in a formula. "
                        "Pay is worked out from paid hours.") % (hit.name or hit.code))
        for config in configs.filtered('pb_clock_from'):
            config._pb_clock_refusals(raise_first=True)


class ClockPayslip(models.Model):
    _inherit = 'hr.payslip'

    pb_clock_stamp = fields.Char(
        string='Clock hours stamp', readonly=True, copy=False,
        help="A fingerprint of the shifts, overtime and time off the clock hours of this "
             "payslip were worked out from. Approval is refused if they changed since.")

    def _pb_clock_used(self, sources_json):
        try:
            import json
            data = json.loads(sources_json or '{}')
        except Exception:       # noqa: BLE001
            return False
        return isinstance(data, dict) and any(
            isinstance(v, dict) and v.get('via') == CLOCK_VIA for v in data.values())

    def _pb_clock_current_stamp(self):
        self.ensure_one()
        config = self.formula_config_id
        if not config or not self.employee_id:
            return ''
        return config.sudo()._pb_clock_signature(self.employee_id, self.date_from, self.date_to) or ''

    def _pb_clock_restamp(self):
        for slip in self:
            used = slip._pb_clock_used(slip.formula_input_sources)
            stamp = slip._pb_clock_current_stamp() if used else False
            if (slip.pb_clock_stamp or False) != (stamp or False):
                super(ClockPayslip, slip).write({'pb_clock_stamp': stamp or False})

    @api.model_create_multi
    def create(self, vals_list):
        slips = super().create(vals_list)
        todo = slips.filtered(lambda s: s.formula_input_sources and s._pb_clock_used(s.formula_input_sources))
        if todo:
            todo._pb_clock_restamp()
        return slips

    def write(self, vals):
        if vals.get('state') in ('verify', 'level1', 'level2', 'done'):
            self.filtered(lambda s: s.pb_clock_stamp and s.state != vals['state'])._pb_clock_assert_current()
        result = super().write(vals)
        if 'formula_input_sources' in vals:
            self._pb_clock_restamp()
        return result

    def _pb_clock_assert_current(self):
        for slip in self:
            if slip._pb_clock_current_stamp() != slip.pb_clock_stamp:
                raise UserError(_(
                    "Clock hours changed after these payslips were computed (%s). "
                    "Recompute before approving.") % (slip.employee_id.display_name or slip.name))
