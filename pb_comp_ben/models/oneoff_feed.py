# -*- coding: utf-8 -*-
"""`pb.oneoff.feed` — how an approved award becomes a line on a payslip.

=====================================================================
THE LANE, AND WHY IT IS THIS ONE. Read this before changing anything.
=====================================================================

The handover said: build a "This run only" import batch with one row per award
and process it. Reading the machinery first (as it instructed) turned up one
fact that changes the shape:

  **`payroll_import_batch._create_payslip` ALWAYS CREATES.** There is no
  "find the slip this run already has for this person and update it" path
  (`payroll_import_batch.py:3512`). So processing an award batch against a run
  that has already been computed puts a SECOND payslip on one person for one
  month — the exact duplicate this system refuses everywhere else, and the very
  thing `pb_payrun_wizard._adopt_loose_slips` was written to prevent.

  And the run "Queue this month" is aimed at is by definition a run that HAS
  been computed: it is this month's draft, sitting in front of the officer.

So the lane is the one-time batch for everything the one-time batch is good at,
and a targeted recompute for the one thing it cannot do:

  1. **A real `hr.payroll.import.batch`, `one_time=True`,
     `auto_create_employees=False`, `auto_create_contracts=False`,
     `create_payslips=False`.** It is the AUDIT RECORD — who was fed what, into
     which run, on which date, under which pay component. `one_time` is what
     guarantees the safety rail the owner cares about: no employee record, no
     contract, no bank account and no contract component is written, ever
     (`payroll_import_batch.py:1524-1540`).

  2. **Its lines are created DIRECTLY, not through a generated spreadsheet.**
     `action_load_file` exists to turn a file into `raw_data_json`; we already
     have the dict. Generating an XLSX in memory only to parse it back would add
     `xlsxwriter` to the path, a temp file's worth of failure modes, and a
     header-matching round trip — for a blob we can write exactly.

  3. **Delivery is a recompute of the run's EXISTING payslip.** The award value
     is merged into that payslip's stored `formula_input_values` under the pay
     component's code, and the payslip's lines are rebuilt by the batch's own
     `_compute_and_create_payslip_lines` — the identical function the
     "Recalculate" button uses (`hr_payslip_formula.py:913`). Nothing new is
     created; the slip that was there is the slip that stays.

  4. **The value is also written into that payslip's own pay-data row**, when it
     has one. `action_recompute_formula_lines` RE-READS the sources (RD45), so a
     value injected only into the stored blob would vanish the next time anybody
     pressed Recalculate. Writing it into the run's own import line — a
     this-run-only record by definition — is what makes the award survive.

  5. **A person with no payslip in the run is REPORTED, never created.** That is
     the one_time doctrine (`ONE_TIME_NO_EMPLOYEE`) expressed for this lane.

=====================================================================
THE COMPONENT CODE IS A REQUIREMENT, NOT A PREFERENCE.
=====================================================================
A payslip's inputs are `config.rule_ids` where `column_type == 'input'`
(`hr_payslip_formula.py:492`). A number under a code the scheme has never heard
of is read by nothing and lands nowhere — no error, no line, no total. So the
preview REFUSES when the target run's scheme has no component with the
configured code, and says in plain words what to add and where. Nothing here
edits a formula scheme: an automatic column in somebody's pay scheme is a
change to how everyone is paid.

=====================================================================
THE PUBLIC API (P8 — the recognition programme calls this)
=====================================================================
    pb.oneoff.feed.preview_for_run(run_id, incentive_ids=None, month=None)
    pb.oneoff.feed.queue_for_run(incentive_ids, run_id, source=None)
    pb.oneoff.feed.feed_period(month, company_id=False, run_id=False)
    pb.oneoff.feed.mark_paid_for_run(run_id)

`source` is carried on `pb.incentive.source` ('manual' | 'rnr'); P8 creates its
awards with `source='rnr'` and hands their ids to `queue_for_run`. The feed does
not care which they are — it is the ledger that records where they came from.
"""

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .comp_common import (
    FEEDABLE_RUN_STATES, P_INCENTIVE_CODE, counted, param,
)

_logger = logging.getLogger(__name__)

#: Payslip states an award may still be added to. A 'done' slip is a paid slip.
FEEDABLE_SLIP_STATES = ('draft', 'verify', 'level1', 'level2')


class PbOneoffFeed(models.AbstractModel):
    _name = 'pb.oneoff.feed'
    _description = 'One-off pay feed'

    # ------------------------------------------------------------- resolving
    @api.model
    def _run(self, run_id):
        """R43 — a record argument arrives as an integer over the wire."""
        rid = run_id.id if hasattr(run_id, 'id') else int(run_id or 0)
        return self.env['hr.payslip.run'].sudo().browse(rid).exists()

    @api.model
    def _config_for_run(self, run):
        """The pay scheme this run was computed with.

        Taken from the run's own payslips, because that is what actually decided
        the numbers — not from a default, which could be a different scheme
        entirely on a database with several.
        """
        if not run:
            return self.env['hr.formula.config'].browse()
        for slip in run.slip_ids:
            config = getattr(slip, 'formula_config_id', False)
            if config:
                return config.sudo()
        batch = self.env['hr.payroll.import.batch'].sudo().search(
            [('payslip_run_id', '=', run.id)], order='id desc', limit=1)
        return batch.formula_config_id.sudo() if batch else \
            self.env['hr.formula.config'].browse()

    @api.model
    def _incentive_code(self):
        return (param(self.env, P_INCENTIVE_CODE) or 'INCENTV').strip().upper()

    @api.model
    def _code_rule(self, config, code):
        """The scheme's input component with this code, if it has one."""
        if not config:
            return None
        wanted = (code or '').strip().upper()
        for rule in config.rule_ids:
            if (rule.code or '').strip().upper() == wanted and \
                    rule.column_type == 'input':
                return rule
        return None

    # -------------------------------------------------------------- preview
    @api.model
    def preview_for_run(self, run_id, incentive_ids=None, month=None):
        """What WOULD happen. Nothing is written.

        The dialog behind "Queue this month" shows this and nothing else, so the
        person pressing the button has already read the answer.
        """
        run = self._run(run_id)
        out = {
            'ok': False, 'problem': '', 'run': '', 'run_state': '',
            'code': self._incentive_code(), 'code_ok': False,
            'scheme': '', 'rows': [], 'total': 0.0, 'currency': '',
            'payable': 0, 'unmatched': 0,
        }
        if not run:
            out['problem'] = _("That pay run no longer exists.")
            return out
        out['run'] = run.name or ''
        out['run_state'] = run.state or 'draft'
        if (run.state or 'draft') not in FEEDABLE_RUN_STATES:
            out['problem'] = _(
                "“%(name)s” has already been sent for approval, so nothing can "
                "be added to it. Awards can only be put into a run that is "
                "still being prepared.", name=run.name or '')
            return out

        config = self._config_for_run(run)
        out['scheme'] = config.display_name if config else ''
        if not config:
            out['problem'] = _(
                "This pay run has no pay scheme behind it yet, so there is "
                "nowhere for an award to go. Compute the run first.")
            return out
        rule = self._code_rule(config, out['code'])
        out['code_ok'] = bool(rule)
        if not rule:
            out['problem'] = _(
                "The pay scheme “%(scheme)s” has no pay item called "
                "%(code)s, so an award put into this run would not appear on "
                "anybody's payslip. Open Mapping for this scheme, add an input "
                "item with the code %(code)s, and include it in the net pay "
                "formula. Then come back here.",
                scheme=config.display_name or '', code=out['code'])
            return out

        incentives = self._pick(run, incentive_ids, month)
        if not incentives:
            out['problem'] = _(
                "There are no approved awards waiting for this month.")
            return out

        slips = self._slips_by_employee(run)
        total, payable, unmatched = 0.0, 0, 0
        rows = []
        for inc in incentives:
            emp = inc._person()
            slip = slips.get(emp.id)
            why = ''
            if not slip:
                why = _("not in this pay run")
                unmatched += 1
            elif slip.state not in FEEDABLE_SLIP_STATES:
                why = _("this payslip is already finished")
                unmatched += 1
            else:
                payable += 1
                total += inc.amount or 0.0
            rows.append({
                'id': inc.id,
                'employee': emp.name or '',
                'employee_id': emp.id,
                'kind': inc.kind,
                'amount': inc.amount or 0.0,
                'month': fields.Date.to_string(inc.period_month) or '',
                'ok': not why,
                'why': why,
            })
        out.update({
            'ok': payable > 0, 'rows': rows, 'total': total,
            'payable': payable, 'unmatched': unmatched,
            'currency': (run.slip_ids[:1].company_id.currency_id.symbol
                         if run.slip_ids else self.env.company.currency_id.symbol) or '',
        })
        if not payable:
            out['problem'] = _(
                "None of the approved awards belong to somebody in this pay "
                "run, so there is nothing to add.")
        return out

    @api.model
    def _pick(self, run, incentive_ids=None, month=None):
        """Which awards this pass is about."""
        Incentive = self.env['pb.incentive']
        if incentive_ids:
            recs = Incentive.browse([int(i) for i in incentive_ids]).exists()
            return recs.filtered(
                lambda i: i.state == 'approved'
                and i.fulfilment in (False, 'pending', 'letter'))
        day = month or run.date_end or fields.Date.context_today(self)
        company = getattr(run, 'company_id', False)
        return Incentive.approved_for_month(
            day, company_id=company.id if company else False)

    @api.model
    def _slips_by_employee(self, run):
        out = {}
        for slip in run.slip_ids:
            out.setdefault(slip.employee_id.id, slip)
        return out

    # ---------------------------------------------------------- the queueing
    @api.model
    def queue_for_run(self, incentive_ids, run_id, source=None):
        """Put approved awards into a run that is still being prepared.

        Returns `{ok, msg, queued, skipped, batch, rows}`.

        IDEMPOTENT BY CONSTRUCTION. The component's value is SET to the total of
        every award queued into this run for that person — not added to — so
        running it twice is running it once, and an award that is already
        `queued` is never picked again.
        """
        run = self._run(run_id)
        preview = self.preview_for_run(run_id, incentive_ids=incentive_ids)
        if not preview['ok']:
            raise UserError(preview['problem'] or _(
                "There is nothing to put into this pay run."))
        code = preview['code']
        config = self._config_for_run(run)
        incentives = self._pick(run, incentive_ids, None)
        slips = self._slips_by_employee(run)

        payable = incentives.filtered(
            lambda i: slips.get(i.employee_id.id)
            and slips[i.employee_id.id].state in FEEDABLE_SLIP_STATES)
        skipped = incentives - payable
        if not payable:
            raise UserError(_(
                "None of these awards belong to somebody in this pay run."))

        batch = self._build_batch(run, config, payable, code)
        rows, done = [], self.env['pb.incentive']
        for inc in payable:
            slip = slips[inc.employee_id.id]
            try:
                total = self._employee_total(run, inc, payable)
                self._apply_to_payslip(batch, slip, code, total)
            except Exception:               # noqa: BLE001 — one row, not all
                _logger.exception(
                    'pb_comp_ben: award %s could not be put into payslip %s',
                    inc.id, slip.id)
                rows.append({'employee': inc._person().name or '',
                             'ok': False,
                             'why': _("the payslip could not be recalculated")})
                continue
            inc.write({
                'fulfilment': 'queued',
                'run_id': run.id,
                'feed_batch_ref': batch.name,
            })
            inc.message_post(body=_(
                "Put into pay run “%(run)s” as %(code)s.",
                run=run.name or '', code=code))
            done |= inc
            rows.append({'employee': inc._person().name or '', 'ok': True,
                         'why': ''})
        for inc in skipped:
            rows.append({'employee': inc._person().name or '', 'ok': False,
                         'why': _("not in this pay run")})
        # `hr.payslip.run` HAS NO CHATTER on this build (no `mail.thread`), so
        # there is nowhere on the run to post this. It is logged, and every
        # award carries the same sentence in its OWN chatter, which is where
        # somebody would look for it anyway.
        _logger.info(
            'pb_comp_ben: %s award(s) fed into run %s as %s, this run only.',
            len(done), run.id, code)
        return {
            'ok': bool(done),
            'queued': len(done),
            'skipped': len(rows) - len(done),
            'batch': batch.name,
            'code': code,
            'rows': rows,
            # R46 — bracketed plurals are how a screen announces it was written
            # by a programme rather than by a person.
            'msg': _("%(n)s went into “%(run)s”.",
                     n=counted(len(done), _('award'), _('awards')),
                     run=run.name or ''),
        }

    @api.model
    def feed_period(self, month, company_id=False, run_id=False):
        """Every approved award for a month, into that month's open run."""
        run = self._run(run_id) if run_id else self._run_for_month(
            month, company_id)
        if not run:
            raise UserError(_(
                "There is no pay run still being prepared for that month, so "
                "there is nowhere to put the awards yet."))
        return self.queue_for_run(None, run.id)

    @api.model
    def _run_for_month(self, month, company_id=False):
        day = fields.Date.to_date(month) if month else fields.Date.context_today(self)
        first = day.replace(day=1)
        return self.env['hr.payslip.run'].sudo().search([
            ('state', 'in', list(FEEDABLE_RUN_STATES)),
            ('date_end', '>=', first),
            ('date_start', '<=', day.replace(day=28)),
        ], order='date_start desc, id desc', limit=1)

    # ------------------------------------------------------------ the batch
    def _build_batch(self, run, config, incentives, code):
        """The one-time batch — the audit record, and the safety rail.

        `create_payslips=False` because delivery is a recompute of the slip the
        run already has (see this module's header). Everything else is exactly
        what the wizard's "This run only" toggle sets, because it must be: a
        batch that says "save nothing" must not also be carrying a standing
        instruction to create people.
        """
        Batch = self.env['hr.payroll.import.batch'].sudo()
        batch = Batch.create({
            'name': _("%s — awards") % (run.name or _('Pay run')),
            'source_type': 'excel',
            'formula_config_id': config.id,
            'payslip_run_id': run.id,
            'payroll_period': 'custom',
            'date_from': run.date_start,
            'date_to': run.date_end,
            'one_time': True,
            'auto_create_employees': False,
            'auto_create_contracts': False,
            'create_payslips': False,
        })
        Line = self.env['hr.payroll.import.line'].sudo()
        vals = []
        for idx, inc in enumerate(incentives, start=1):
            emp = inc._person()
            vals.append({
                'batch_id': batch.id,
                'sequence': idx,
                # The employee is ALREADY known — the awards name them — so the
                # line is born matched and no identity ladder is walked. The
                # three text columns are filled anyway, because this row is read
                # by a person later.
                'employee_id': emp.id,
                'employee_code': emp.barcode or emp.identification_id or '',
                'employee_name': emp.name or '',
                'employee_email': emp.work_email or '',
                'is_new_employee': False,
                'raw_data_json': json.dumps({
                    'Employee Code': emp.barcode or emp.identification_id or '',
                    'Employee Name': emp.name or '',
                    code: inc.amount or 0.0,
                }),
                'state': 'matched',
            })
        Line.create(vals)
        # 'matched' is where `action_load_file` + `action_match_employees` would
        # have left it; both were skipped because their two jobs (parse a file,
        # find the person) are already done.
        batch.write({'state': 'matched'})
        batch.action_validate()
        batch.action_process()
        return batch

    def _employee_total(self, run, incentive, batchmates):
        """Every award this person has in this run, added up.

        The component's value is SET to this, never incremented, which is what
        makes a second press of the button a no-op rather than a doubling.
        """
        emp_id = incentive.employee_id.id
        already = self.env['pb.incentive'].sudo().search([
            ('run_id', '=', run.id),
            ('employee_id', '=', emp_id),
            ('fulfilment', 'in', ('queued', 'paid')),
        ])
        total = sum(already.mapped('amount'))
        total += sum(i.amount or 0.0 for i in batchmates
                     if i.employee_id.id == emp_id)
        return total

    def _apply_to_payslip(self, batch, slip, code, amount):
        """Put the amount on the slip the run already has — and make it stick.

        TWO WRITES, and both are needed:

          * the payslip's stored `formula_input_values`, which is what the
            engine computes from right now;
          * the run's own pay-data row for that person, when there is one,
            because "Recalculate" RE-READS the sources (RD45) and would drop a
            value that only ever lived in the stored blob.

        Both are scoped to THIS RUN. Nothing touches the employee record, the
        contract, or any component the contract carries.
        """
        slip = slip.sudo()
        try:
            values = json.loads(slip.formula_input_values or '{}') or {}
        except Exception:                   # noqa: BLE001
            values = {}
        values[code] = amount
        slip.write({'formula_input_values': json.dumps(values)})

        # The run's own pay-data row, so a later recalculation keeps the award.
        line = self.env['hr.payroll.import.line'].sudo().search([
            ('payslip_id', '=', slip.id),
        ], order='id', limit=1)
        if line:
            try:
                raw = json.loads(line.raw_data_json or '{}') or {}
            except Exception:               # noqa: BLE001
                raw = {}
            raw[code] = amount
            line.write({'raw_data_json': json.dumps(raw)})

        slip.line_ids.unlink()
        batch._compute_and_create_payslip_lines(slip, values)
        return True

    # ------------------------------------------------------------- the payout
    @api.model
    def mark_paid_for_run(self, run_id):
        """Everything queued into this run is now paid. Called on final approval."""
        run = self._run(run_id)
        if not run:
            return 0
        queued = self.env['pb.incentive'].sudo().search([
            ('run_id', '=', run.id), ('fulfilment', '=', 'queued')])
        if not queued:
            return 0
        queued.write({'fulfilment': 'paid'})
        for inc in queued:
            try:
                inc.message_post(body=_(
                    "Paid with pay run “%s”.", run.name or ''))
            except Exception:               # noqa: BLE001
                _logger.debug('pb_comp_ben: could not note payment on award %s',
                              inc.id)
        _logger.info('pb_comp_ben: %s award(s) marked paid with run %s',
                     len(queued), run.id)
        return len(queued)
