# -*- coding: utf-8 -*-
"""UPDATES P2d — how every kind of pay run reads one-off pay items.

There is no single input resolver (ledger U22/P2d-U4). Two seams cover every
mode, and each override here calls `super()` FIRST and merges after it — so a
one-off is never prorated, and lands after back pay, carry-over and work
segments — through the ONE reader `pb.updates.oneoff._for_slip`:

  1. `hr.payslip._get_formula_input_values` — a run without a pay data file,
     native "Compute Sheet", and the no-file branch of "Recalculate".
  2. `hr.payroll.import.batch._transform_data_to_formula_inputs` — a run
     with a pay data file (create and recalculate) and monthly-template runs
     (whose own override in `pb_payroll_templates` runs inside this one).

Byte-identity rail (test E1): when the payslip's person has no live one-off
for its month that its scheme can read, both seams return exactly what
`super()` returned, called with exactly the caller's own arguments.

Application-data mode (P2d-U5) is NOT covered: its freshness check accepts
only three sources and certifies a frozen snapshot, and a fourth source would
loosen it. That mode reads nothing from Updates (seam 1 returns at once in
its context) and its preparation says so in one line (`_workspace` below).

Paid once: only callers that compute a REAL payslip — the three wrappers
below — pass a `pb_updates_token`; the seams fill it with what they used and the
wrapper reserves it (`_sync_slip`). Review screens call the same resolvers
without it and never reserve, and never meet the D11 stop.
"""
import logging
import uuid

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.pb_updates.models.updates_oneoff import (
    FILE_SOURCES, OneoffClash, _blank, _same_amount, updates_entry)

try:
    from odoo.addons.pb_hr_payroll_formula.models import input_provenance
except Exception:  # pragma: no cover — the engine is a dependency
    input_provenance = None

_logger = logging.getLogger(__name__)


#: Where a computing caller collects what the seams used. The context carries
#: only a token: a context is copied whenever somebody adds a key to it (the
#: monthly-template resolver does), so a dict passed IN it would be filled on
#: a copy and the caller would never see it. The per-cursor cache is the same
#: for every copy of the environment.
USED_KEY = 'pb_updates_oneoff_used'


def used_start(env):
    token = uuid.uuid4().hex
    env.cr.cache.setdefault(USED_KEY, {})[token] = {}
    return token


def used_of(env):
    """The verdicts dict of the computing caller, or None (a review screen)."""
    token = env.context.get('pb_updates_token')
    if not token:
        return None
    return env.cr.cache.setdefault(USED_KEY, {}).setdefault(token, {})


def used_end(env, token):
    return env.cr.cache.get(USED_KEY, {}).pop(token, None) or {}


def _ignored(src, key, value):
    if input_provenance is not None:
        return input_provenance.ignored_side(src, key, value)
    return {'src': src, 'key': key, 'value': value}


class HrPayslipUpdatesOneoff(models.Model):
    _inherit = 'hr.payslip'

    # ------------------------------------------------------------ seam 1
    def _get_formula_input_values(self, config, provenance=None):
        ctx = self.env.context
        if ctx.get('pb_application_data_mode') or not self or len(self) != 1:
            return super()._get_formula_input_values(config, provenance=provenance)
        slip_id = self.id if isinstance(self.id, int) else None
        rows = self.env['pb.updates.oneoff'].sudo()._for_slip(
            self.employee_id, config, self.date_to, slip_id, self.payslip_run_id)
        if not rows:
            return super()._get_formula_input_values(config, provenance=provenance)
        prov = provenance if provenance is not None else {}
        values = super()._get_formula_input_values(config, provenance=prov)
        used = used_of(self.env)
        for code, row in rows.items():
            if row.clash_run_id or row.clash_batch_id:
                # A pay run asked which amount to pay; its answer is read
                # with the pay data file, never without it.
                if used is not None:
                    raise OneoffClash(row, row.clash_file_amount, row.clash_file_key,
                                      'excel', row._clash_sentence())
                continue
            entry = prov.get(code) or {}
            src = entry.get('src') or 'none'
            other = values.get(code)
            if src == 'none' or _blank(other):
                values[code] = row.amount
                prov[code] = updates_entry(row)
                verdict = 'updates'
            elif _same_amount(other, row.amount):
                verdict = 'agreed'
            else:
                # Another source of this run answered with a different amount
                # (a connected system). Never one or the other silently.
                if used is not None:
                    raise UserError(_(
                        "%(item)s for %(name)s: %(updates)s from Updates, %(other)s "
                        "from the connected system. Remove one of them, then "
                        "calculate again.", item=row.label or row.code,
                        name=row.employee_id.name or '', updates=row._amount_label(),
                        other=row._amount_label(other)))
                continue
            if used is not None:
                used[row.id] = verdict
        return values

    # ------------------------------------------- UPDATES P3a — demo shortcut
    def _pb_updates_merge_inputs(self, config, values):
        """A ready-made input dict, with this payslip's one-off pay items
        from Updates merged in: `(values, token)`.

        For callers that compute a payslip WITHOUT either seam — the demo
        generator's own shortcut on payobook (`pb_demo`, P2d deviation 1).
        Same reader (`_for_slip`), same paid-once bookkeeping: hand the token
        back to `_pb_updates_merge_done` once the payslip is computed. With
        no one-off for this person and month the dict comes back unchanged
        and the token is None — byte-identical to before.

        A generated demo figure for the same pay item is not a pay data file
        (there is nobody to ask, D11), so the approved one-off replaces it."""
        self.ensure_one()
        rows = self.env['pb.updates.oneoff'].sudo()._for_slip(
            self.employee_id, config, self.date_to, self.id, self.payslip_run_id)
        if not rows:
            return values, None
        token = used_start(self.env)
        used = self.env.cr.cache[USED_KEY][token]
        values = dict(values)
        for code, row in rows.items():
            if row.clash_run_id or row.clash_batch_id:
                continue
            other = values.get(code)
            used[row.id] = 'agreed' if (not _blank(other) and _same_amount(
                other, row.amount)) else 'updates'
            values[code] = row.amount
        return values, token

    def _pb_updates_merge_done(self, token):
        """Reserve what `_pb_updates_merge_inputs` used for this payslip."""
        self.ensure_one()
        if token:
            self.env['pb.updates.oneoff'].sudo()._sync_slip(
                self, used_end(self.env, token))
        return True

    # ------------------------------------------------------------ wrappers
    def _pb_compute_sheet_with_formulas(self):
        Oneoff = self.env['pb.updates.oneoff'].sudo()
        for slip in self:
            if hasattr(slip, '_application_mode') and slip._application_mode():
                super(HrPayslipUpdatesOneoff, slip)._pb_compute_sheet_with_formulas()
                continue
            token = used_start(self.env)
            try:
                super(HrPayslipUpdatesOneoff, slip.with_context(
                    pb_updates_token=token))._pb_compute_sheet_with_formulas()
            except OneoffClash as clash:
                used_end(self.env, token)
                # A plain UserError for the caller: the compute is refused
                # with the sentence (the pay run lists it as an exception).
                raise UserError(clash.sentence) from None
            Oneoff._sync_slip(slip, used_end(self.env, token))
        return True

    def action_recompute_formula_lines(self):
        Oneoff = self.env['pb.updates.oneoff'].sudo()
        result = None
        stopped = []
        for slip in self:
            if hasattr(slip, '_application_mode') and slip._application_mode():
                result = super(HrPayslipUpdatesOneoff, slip).action_recompute_formula_lines()
                continue
            token = used_start(self.env)
            try:
                result = super(HrPayslipUpdatesOneoff, slip.with_context(
                    pb_updates_token=token, pb_updates_slip_id=slip.id)
                ).action_recompute_formula_lines()
            except OneoffClash as clash:
                used_end(self.env, token)
                line = self.env['hr.payroll.import.line'].sudo().search(
                    [('payslip_id', '=', slip.id)], limit=1)
                Oneoff._open_clash(clash, run=slip.payslip_run_id,
                                   batch=line.batch_id if line else None)
                stopped.append(clash.sentence)
                continue
            Oneoff._sync_slip(slip, used_end(self.env, token))
        if stopped:
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {
                    'title': _('Two amounts for one pay item'),
                    'message': ' '.join(stopped[:3]) + (
                        ' ' + _("%s more are waiting for a choice.") % (len(stopped) - 3)
                        if len(stopped) > 3 else ''),
                    'type': 'warning', 'sticky': True,
                },
            }
        return result


class PayrollImportBatchUpdatesOneoff(models.Model):
    _inherit = 'hr.payroll.import.batch'

    # ------------------------------------------------------------ seam 2
    def _template_entered_zero(self, employee, rule):
        """A monthly-template file writes 0 in every adjustment cell nobody
        filled in. Such a 0 is a blank, not an amount (P2d-U2); a 0 somebody
        entered for the month is an amount."""
        period = self._template_period() if hasattr(self, '_template_period') else None
        if not period:
            return True
        row = self.env['pb.payroll.month.inputs'].sudo().search([
            ('config_id', '=', self.formula_config_id.id),
            ('company_id', '=', self.company_id.id),
            ('employee_id', '=', employee.id), ('period', '=', period)], limit=1)
        return bool(row) and ('rule:%s' % rule.id) in (row.payload or {})

    def _file_cell_is_amount(self, key, raw_data, topup_data):
        """Did the pay data file really carry an AMOUNT for this item?

        The resolver can also bind a component by spreadsheet column letter,
        so a file without the item's column can still hand it a name or a
        code (normalised to 0). Only a cell that reads as a number is the
        file "carrying a value" (D11); anything else is a blank."""
        found = False
        value = None
        for blob in (raw_data or {}, topup_data or {}):
            if key in blob:
                found, value = True, blob.get(key)
                break
        if not found:
            return True
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, float)):
            return True
        text = str(value or '').strip()
        if not text:
            return False
        try:
            return self._coerce_numeric_string(text) is not None
        except Exception:  # noqa: BLE001
            return False

    def _transform_data_to_formula_inputs(self, raw_data, contract=None, employee=None,
                                          provenance=None, topup_data=None):
        person = employee or (contract.employee_id if contract else None)
        config = self.formula_config_id
        ctx = self.env.context
        rows = {}
        if person and config and len(self) == 1 and self.date_to:
            rows = self.env['pb.updates.oneoff'].sudo()._for_slip(
                person, config, self.date_to, ctx.get('pb_updates_slip_id') or None,
                self.payslip_run_id, batch=self)
        if not rows:
            return super()._transform_data_to_formula_inputs(
                raw_data, contract=contract, employee=employee,
                provenance=provenance, topup_data=topup_data)
        prov = provenance if provenance is not None else {}
        values = super()._transform_data_to_formula_inputs(
            raw_data, contract=contract, employee=employee, provenance=prov,
            topup_data=topup_data)
        used = used_of(self.env)
        items = None
        for code, row in rows.items():
            entry = prov.get(code) or {}
            src = entry.get('src') or 'none'
            other = values.get(code)
            carried = src in FILE_SOURCES and not _blank(other) and \
                self._file_cell_is_amount(entry.get('key'), raw_data, topup_data)
            if carried and _same_amount(other, 0.0) and self._template_period():
                items = items or self.env['pb.updates.oneoff'].sudo()._items_of(config)
                rule = (items.get(code) or {}).get('rule')
                if rule and not self._template_entered_zero(person, rule):
                    carried = False
            bound = (row.clash_run_id and row.clash_run_id == self.payslip_run_id) or \
                    (row.clash_batch_id and row.clash_batch_id == self)
            choice = row.clash_choice if bound else False
            if not carried:
                values[code] = row.amount
                prov[code] = updates_entry(row)
                verdict = 'updates'
            elif _same_amount(other, row.amount):
                verdict = 'agreed'
            elif choice == 'updates':
                values[code] = row.amount
                prov[code] = updates_entry(row, ignored=_ignored(
                    src, entry.get('key'), other))
                verdict = 'updates'
            elif choice == 'file':
                entry = dict(entry)
                entry['ignored'] = _ignored('employee_field', 'updates:%s' % row.id,
                                            row.amount)
                prov[code] = entry
                verdict = 'file'
            else:
                # D11 — stop and ask. Only a caller computing a real payslip
                # asked for this; a review screen just sees the file's value.
                if used is not None:
                    raise OneoffClash(row, other, entry.get('key'), src,
                                      row._clash_sentence(file_amount=other))
                continue
            if used is not None:
                used[row.id] = verdict
        return values

    # ------------------------------------------------------------ wrapper
    def _create_payslip(self, employee, contract, line):
        Oneoff = self.env['pb.updates.oneoff'].sudo()
        token = used_start(self.env)
        try:
            payslip = super(PayrollImportBatchUpdatesOneoff, self.with_context(
                pb_updates_token=token, pb_updates_slip_id=False)
            )._create_payslip(employee, contract, line)
        except OneoffClash as clash:
            used_end(self.env, token)
            Oneoff._open_clash(clash, run=self.payslip_run_id, batch=self)
            self._log(clash.sentence)
            # No payslip from the file for this person until somebody
            # chooses; the pay run lists the question (D11).
            return self.env['hr.payslip']
        used = used_end(self.env, token)
        if payslip:
            payslip = payslip.with_env(self.env)
            Oneoff._sync_slip(payslip, used)
        return payslip


class PayslipRunOneoffSummary(models.AbstractModel):
    """What the Run Payroll screen shows about one-offs from Updates: one
    line on its first step, and the D11 questions on its review step."""
    _inherit = 'pb.payrun.wizard'

    @api.model
    def _updates_oneoff_line(self, config_id, date_start, date_end, emp_ids=None):
        """`{count, people, total, line, kind}` for the people of a run."""
        Oneoff = self.env['pb.updates.oneoff'].sudo()
        config = self.env['hr.formula.config'].sudo().browse(int(config_id or 0)).exists()
        day = fields.Date.to_date(date_end) if date_end else None
        if not config or not day:
            return {}
        items = Oneoff._items_of(config)
        if not items:
            return {}
        domain = [('period_month', '=', Oneoff._month_of(day)), ('state', '=', 'approved'),
                  ('action', '=', 'set'), ('code', 'in', list(items)),
                  ('company_id', '=', config.company_id.id or self.env.company.id)]
        if emp_ids is not None:
            domain.append(('employee_id', 'in', list(emp_ids)))
        rows = Oneoff.search(domain)
        if config.cycle_type == 'mid_cycle':
            rows = rows.filtered(lambda r: r.config_id == config)
        if not rows:
            return {}
        app = bool(getattr(config, 'application_data_enabled', False))
        earn = sum(r.amount for r in rows if r.net_role == 'earning')
        take = sum(r.amount for r in rows if r.net_role == 'deduction')
        currency = config.currency_id or config.company_id.currency_id
        money = lambda v: Oneoff.browse()._money(v, currency)  # noqa: E731
        bits = []
        if earn:
            bits.append(_("%s added to pay") % money(earn))
        if take:
            bits.append(_("%s taken from pay") % money(take))
        n, people = len(rows), len(rows.mapped('employee_id'))
        if app:
            line = _("%(n)s one-off pay items from Updates are not included in a pay "
                     "run from application data. A run with a pay data file, or "
                     "without one, includes them.", n=n) if n != 1 else _(
                "1 one-off pay item from Updates is not included in a pay run from "
                "application data. A run with a pay data file, or without one, "
                "includes it.")
        else:
            line = (_("1 one-off pay item from Updates will be included (%s).")
                    % ', '.join(bits)) if n == 1 else (
                _("%(n)s one-off pay items from Updates will be included for "
                  "%(people)s people (%(total)s).", n=n, people=people,
                  total=', '.join(bits)))
        return {'count': n, 'people': people, 'earn': earn, 'take': take,
                'line': line, 'kind': 'application' if app else 'included'}

    @api.model
    def scheme_preview(self, vals=None):
        answer = super().scheme_preview(vals)
        try:
            vals = vals or {}
            if isinstance(answer, dict):
                answer['updates_oneoffs'] = self._updates_oneoff_line(
                    vals.get('formula_config_id'), vals.get('date_start'),
                    vals.get('date_end'))
        except Exception:  # noqa: BLE001 — a notice must never break the screen
            _logger.exception('pb_updates: the one-off line failed')
        return answer

    @api.model
    def get_summary(self, run_id):
        answer = super().get_summary(run_id)
        try:
            run = self.env['hr.payslip.run'].sudo().browse(int(run_id or 0)).exists()
            if run and isinstance(answer, dict):
                rows = self.env['pb.updates.oneoff'].sudo()._clash_rows(run=run)
                answer['oneoff_clashes'] = rows._clash_payload()
                answer['oneoff_can_choose'] = self.env['pb.updates.oneoff']._may_choose()
        except Exception:  # noqa: BLE001
            _logger.exception('pb_updates: the one-off questions failed')
        return answer


class PayrollPreparationOneoff(models.Model):
    """Application-data mode: its preparation says, once, that one-offs from
    Updates are not included in this kind of pay run (handover §3)."""
    _inherit = 'hr.payroll.preparation'

    def _workspace(self):
        answer = super()._workspace()
        try:
            note = ''
            config = getattr(self, 'config_id', False)
            if config and self.date_to:
                Oneoff = self.env['pb.updates.oneoff'].sudo()
                items = Oneoff._items_of(config)
                rows = Oneoff.search([
                    ('period_month', '=', Oneoff._month_of(self.date_to)),
                    ('state', '=', 'approved'), ('action', '=', 'set'),
                    ('code', 'in', list(items) or ['-']),
                    ('employee_id', 'in', self.employee_ids.ids)]) if items else Oneoff
                if rows:
                    note = _("%s one-off pay items from Updates are not included in "
                             "this kind of pay run. Run it with a pay data file, or "
                             "without one, to include them.") % len(rows) \
                        if len(rows) != 1 else _(
                            "1 one-off pay item from Updates is not included in this "
                            "kind of pay run. Run it with a pay data file, or without "
                            "one, to include it.")
            answer['updates_oneoffs_note'] = note
        except Exception:  # noqa: BLE001
            _logger.exception('pb_updates: one-off note failed on preparation %s', self.id)
            answer['updates_oneoffs_note'] = ''
        return answer
