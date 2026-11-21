# -*- coding: utf-8 -*-
"""WDGAP W2-F (F-1) — an Extra run never takes the mid-month advance twice.

Owner ruling (2026-11-15): "An Extra run ignores the advance from the file
when the month's regular run already took it, and says so on screen."

WHAT "THE ADVANCE" IS. Only what the scheme already types as the advance: the
end-of-month components that receive a mid-month amount through the scheme's
carry-over setting (`hr.payroll.cycle.component.mapping`, active, this scheme
as the end side) — the same rows `_apply_mid_cycle_carryover` reads. Never a
code written here. A scheme with no such row has no advance, and nothing on
this page touches it.

THE RULE, per person picked for an Extra run that loads a pay data file:

  * TAKEN — another payslip of the same scheme family (the scheme and its
    branches) for the same pay month, already worked out (any state but
    draft-without-lines and cancelled), not in this run, carries a non-zero
    advance. The Extra run feeds 0 for the advance input(s) and the payslip
    records which payslip took it (`pb_advance_taken_in_id`).
  * UNDECIDED — nothing carries it, but a REGULAR payslip of that month exists
    that has not been worked out yet: whether it will take the advance cannot
    be told. Unchanged behaviour (the Extra run takes it) and the review says
    why.
  * FREE — nothing carries it and no regular payslip is waiting: unchanged
    behaviour, the Extra run may be the one that takes it.

"Another payslip ... carries it" reads both halves of the handover's wording
("a regular payslip, or one that consumed the carry-over"): any worked-out
payslip whose advance is not zero — a regular one, or an earlier Extra run
that was itself the one to take it. An earlier Extra run that was kept out
carries 0 and never counts.

Regular and top-up runs never ask: the read is reached only through a batch
whose run is an Extra run (`pb_run_kind`, read by name — the engine does not
depend on pb_payruns, W2-A precedent), so their payslips are byte-identical.
"""
import json
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)

TAKEN = 'taken'
UNDECIDED = 'undecided'
FREE = 'free'


def _advance_value(slip, codes):
    """The advance a payslip carries: its fed inputs first (that is where the
    carry-over writes), then its worked-out values. 0.0 when unreadable."""
    for blob in (slip.formula_input_values, slip.formula_computed_values):
        try:
            values = json.loads(blob or '{}')
        except (TypeError, ValueError):
            continue
        if not isinstance(values, dict):
            continue
        total = 0.0
        found = False
        for code in codes:
            if code in values:
                found = True
                try:
                    total += abs(float(values.get(code) or 0.0))
                except (TypeError, ValueError):
                    continue
        if found:
            return total
    return 0.0


class HrFormulaConfigAdvanceOnce(models.Model):
    _inherit = 'hr.formula.config'

    # ------------------------------------------------------------ typing
    def _pb_advance_mappings(self):
        """Active carry-over rows that name this scheme, on either side."""
        self.ensure_one()
        return self.env['hr.payroll.cycle.component.mapping'].sudo().search([
            '|', ('end_cycle_config_id', '=', self.id),
            ('mid_cycle_config_id', '=', self.id),
            ('active', '=', True)])

    def _pb_advance_rules(self):
        """This scheme's components the carry-over setting types as the
        advance: the end-side receivers and the mid-side sources."""
        self.ensure_one()
        Rule = self.env['hr.formula.rule'].sudo()
        out = Rule.browse()
        for mapping in self._pb_advance_mappings():
            if mapping.end_cycle_config_id == self:
                out |= mapping.end_component_id
            if mapping.mid_cycle_config_id == self:
                out |= mapping.mid_component_id
        return out

    def _pb_advance_input_codes(self):
        """The input codes an end-of-month scheme receives the advance in —
        spelt exactly as `_apply_mid_cycle_carryover` writes them."""
        self.ensure_one()
        codes = []
        for mapping in self._pb_advance_mappings():
            if mapping.end_cycle_config_id != self:
                continue
            rule = mapping.end_component_id
            code = rule.code or rule.column_letter
            if code and code not in codes:
                codes.append(code)
        return codes

    def _pb_scheme_family(self):
        """The scheme and its branches (a branch is a copy of the scheme made
        for editing, `parent_branch_id`)."""
        self.ensure_one()
        Config = self.sudo().with_context(active_test=False)
        root = Config.browse(self.id)
        seen = set()
        while root.parent_branch_id and root.parent_branch_id.id not in seen:
            seen.add(root.id)
            root = root.parent_branch_id
        family = root
        todo = root
        while todo:
            children = todo.mapped('child_branch_ids') - family
            family |= children
            todo = children
        return family

    # ------------------------------------------------------------ the rule
    def _pb_advance_verdicts(self, employees, date_from, date_to, exclude_run=None):
        """{employee_id: {'verdict': TAKEN | UNDECIDED | FREE, 'slip': payslip,
        'where': run or payslip name}} for an Extra run of this scheme over
        [date_from, date_to]. {} when the scheme types no advance."""
        self.ensure_one()
        codes = self._pb_advance_input_codes()
        if not codes or not employees or not date_from or not date_to:
            return {}
        Slip = self.env['hr.payslip'].sudo()
        domain = [
            ('employee_id', 'in', employees.ids),
            ('formula_config_id', 'in', self._pb_scheme_family().ids),
            ('state', '!=', 'cancel'),
            ('date_from', '<=', date_to),
            ('date_to', '>=', date_from),
        ]
        if 'credit_note' in Slip._fields:
            domain.append(('credit_note', '=', False))
        if exclude_run:
            domain += ['|', ('payslip_run_id', '=', False),
                       ('payslip_run_id', '!=', exclude_run.id)]
        slips = Slip.search(domain, order='date_from, id')
        has_kind = 'pb_run_kind' in self.env['hr.payslip.run']._fields

        def kind_of(slip):
            if not has_kind or not slip.payslip_run_id:
                return 'regular'
            return slip.payslip_run_id.pb_run_kind or 'regular'

        def worked_out(slip):
            return slip.state != 'draft' or bool(slip.line_ids)

        out = {}
        for employee in employees:
            mine = slips.filtered(lambda s, e=employee: s.employee_id == e)
            carriers = [s for s in mine if worked_out(s) and _advance_value(s, codes)]
            # a regular payslip is the one named when several carry it
            regular = [s for s in carriers if kind_of(s) == 'regular']
            taken = (regular or carriers or [Slip.browse()])[0]
            pending = next((s for s in mine if not worked_out(s)
                            and kind_of(s) == 'regular'), Slip.browse())
            if taken:
                out[employee.id] = {'verdict': TAKEN, 'slip': taken,
                                    'where': taken.payslip_run_id.name or taken.name or ''}
            elif pending:
                out[employee.id] = {'verdict': UNDECIDED, 'slip': pending,
                                    'where': pending.payslip_run_id.name or pending.name or ''}
            else:
                out[employee.id] = {'verdict': FREE, 'slip': Slip.browse(), 'where': ''}
        return out


class HrPayslipAdvanceOnce(models.Model):
    _inherit = 'hr.payslip'

    pb_advance_taken_in_id = fields.Many2one(
        'hr.payslip', string='Mid-month advance already taken in',
        readonly=True, copy=False, ondelete='set null', index='btree_not_null',
        help="This extra payslip did not take the mid-month advance, because "
             "this payslip of the same month already had.")


class HrPayrollImportBatchAdvanceOnce(models.Model):
    _inherit = 'hr.payroll.import.batch'

    def _pb_advance_kept_out(self, employee):
        """The payslip that already took this month's advance, when this
        batch feeds an Extra run and the rule says TAKEN; else empty."""
        Slip = self.env['hr.payslip'].sudo()
        run = self.payslip_run_id
        if not employee or not run or not self.formula_config_id \
                or 'pb_run_kind' not in run._fields \
                or (run.pb_run_kind or 'regular') != 'extra' \
                or self.formula_config_id.cycle_type != 'end_cycle':
            return Slip.browse()
        verdict = self.formula_config_id._pb_advance_verdicts(
            employee, self.date_from, self.date_to, exclude_run=run).get(employee.id)
        if verdict and verdict['verdict'] == TAKEN:
            return verdict['slip']
        return Slip.browse()

    def _pb_feed_no_advance(self, input_values, employee, slip):
        """Feed 0 for every input the scheme receives the advance in, and say
        so in the log (the payslip records it on its own field)."""
        for code in self.formula_config_id._pb_advance_input_codes():
            input_values[code] = 0.0
        _logger.info(
            "Advance once: extra run batch %s, employee %s — the mid-month "
            "advance was already taken in payslip %s; 0 fed.",
            self.id, employee.id, slip.id)
