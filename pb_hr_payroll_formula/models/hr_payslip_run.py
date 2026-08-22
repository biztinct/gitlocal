# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import UserError


class HrPayslipRun(models.Model):
    _inherit = ['hr.payslip.run']

    def action_recompute_formula_lines_batch(self):
        total = 0
        for run in self:
            slips = run.slip_ids.filtered(lambda s: s.calculation_method == 'formula')
            if slips:
                slips.action_recompute_formula_lines()
                total += len(slips)
        if not total:
            raise UserError(_("No formula-based payslips found to recompute."))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Recomputed'),
                'message': _("Recomputed %s payslip(s).") % total,
                'type': 'success',
            }
        }

    # ------------------------------------------------------------------
    # COLROLES P4 — role-driven leading columns in the payroll workbook
    # ------------------------------------------------------------------
    def _export_base_columns(self, config):
        """Let a structure's own Identity / Employee Profile columns open the sheet.

        The export has always started with a fixed five (MSNV, Full name, Unit,
        contract type, overtime subject) chosen for one Vietnamese workbook. Once a
        structure has roles, it already knows which of ITS columns identify a person
        — so when the structure opts in, those lead instead, in their own order.

        Strictly opt-in: `export_identity_columns` is False by default and, while it
        is, this returns `super()` untouched and the workbook is byte-for-byte what
        it was. Contract, bank and reference columns are deliberately NOT promoted —
        they are people data, not the "who is this row" heading a payroll reviewer
        reads across.

        Lives here rather than in `om_hr_payroll` because the field and the roles
        belong to the formula engine (ledger CR1: never widen om's upgrade surface).
        """
        base = super()._export_base_columns(config)
        if not config or not getattr(config, 'export_identity_columns', False):
            return base

        rules = config.rule_ids.filtered(
            lambda r: (r.column_role or 'payroll') in ('identity', 'profile')
        ).sorted(key=lambda r: (r.sequence, r.id))
        if not rules:
            # Opted in but nothing is marked — falling back to the fixed set beats
            # handing back a workbook with no employee columns at all.
            return base

        columns = []
        for rule in rules:
            code = (rule.code or '').strip().upper()
            name = (rule.name or '').strip().upper()
            keys = []
            if code:
                keys.append(('code', code))
            if name and name != code:
                keys.append(('name', name))
            if not keys:
                continue
            lookup = [k for k in (rule.code, rule.name, rule.column_letter) if k]
            columns.append({
                'header': rule.name or rule.code,
                'keys': keys,
                'lookup': lookup,
                'use_string_payload': True,
            })
        return columns or base
