# -*- coding: utf-8 -*-
import logging
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import api, models

_logger = logging.getLogger(__name__)


class PbPayrunWizard(models.AbstractModel):
    """Backend orchestration for the guided Run Payroll cockpit.

    Real, but guarded:
      * create_and_compute() creates a *draft* hr.payslip.run and computes its
        payslips for real (fully reversible — the draft run can be deleted).
      * submit_for_approval() advances state only (no irreversible payment).
    Everything is wrapped defensively so one bad employee cannot abort the run.
    """
    _name = 'pb.payrun.wizard'
    _description = 'Payobook Run Payroll wizard orchestration'

    # ---------------- Step 1: defaults ----------------
    @api.model
    def get_defaults(self):
        today = date.today()
        start = today.replace(day=1)
        end = (start + relativedelta(months=1)) - relativedelta(days=1)
        structs = self.env['hr.payroll.structure'].search([], limit=50)
        emp_ids = self._eligible_employees()
        return {
            'name': 'Payroll %s' % start.strftime('%B %Y'),
            'date_start': start.isoformat(),
            'date_end': end.isoformat(),
            'company': self.env.company.name,
            'currency': self.env.company.currency_id.name or 'VND',
            'structures': [{'id': s.id, 'name': s.name} for s in structs],
            'eligible': len(emp_ids),
        }

    def _eligible_employees(self):
        """Employees with a running contract (best-effort)."""
        try:
            contracts = self.env['hr.contract'].search([('state', '=', 'open')])
            emps = contracts.mapped('employee_id')
            if emps:
                return emps.ids
        except Exception:
            pass
        return self.env['hr.employee'].search([]).ids

    # ---------------- Existing-payroll detection + cleanup ----------------
    def _period_runs(self, ds, de):
        """Runs in the active company set overlapping [ds, de] that have payslips."""
        runs = self.env['hr.payslip.run'].search([
            ('date_start', '<=', de), ('date_end', '>=', ds),
            ('company_id', 'in', self.env.companies.ids)
        ]) if 'company_id' in self.env['hr.payslip.run']._fields else \
            self.env['hr.payslip.run'].search([('date_start', '<=', de), ('date_end', '>=', ds)])
        return runs.filtered(lambda r: r.slip_ids)

    def _july_period(self, ds):
        year = (ds or '2026-01-01')[:4]
        return {'name': 'Payroll July %s' % year,
                'date_start': '%s-07-01' % year, 'date_end': '%s-07-31' % year}

    def _clean_period(self, runs):
        """Remove a period's generated artefacts: payslips, journal moves, formula
        computation logs and the runs themselves (fully reversible demo cleanup)."""
        if not runs:
            return 0
        slips = runs.mapped('slip_ids')
        moves = slips.mapped('move_id') if 'move_id' in slips._fields else self.env['account.move']
        for s in slips:
            if s.state not in ('draft', 'cancel'):
                s.state = 'cancel'
        if moves:
            posted = moves.filtered(lambda m: m.state == 'posted')
            if posted:
                posted.button_draft()
            moves.with_context(force_delete=True).unlink()
        fcols = {'formula_computation_log', 'formula_computed_values', 'formula_input_values'}
        common = fcols & set(slips._fields)
        if common and slips:
            slips.write({c: False for c in common})
        n = len(slips)
        slips.unlink()
        runs.write({'state': 'draft'})
        runs.unlink()
        return n

    # ---------------- Step 2: create + compute ----------------
    @api.model
    def create_and_compute(self, vals):
        Run = self.env['hr.payslip.run']
        Slip = self.env['hr.payslip']
        name = vals.get('name') or 'Payroll run'
        ds = vals.get('date_start')
        de = vals.get('date_end')
        force_clean = vals.get('force_clean')

        # Guard: if payroll already exists for this period, ask before overwriting.
        existing = self._period_runs(ds, de)
        if existing and not force_clean:
            locked = any(getattr(r, 'locked', False) for r in existing)
            if locked:
                return {
                    'needs_confirmation': True, 'kind': 'historical',
                    'message': "Historical payroll runs are locked. Would you like to "
                               "clean July’s payroll data and rerun July payroll?",
                    'july': self._july_period(ds),
                }
            return {
                'needs_confirmation': True, 'kind': 'exists',
                'message': "This month’s payroll already exists. Would you like to "
                           "clear existing payroll data and run payroll again?",
            }
        if force_clean and existing:
            self._clean_period(existing)

        run = Run.create({'name': name, 'date_start': ds, 'date_end': de})

        emp_ids = self._eligible_employees()
        exceptions = []
        created = Slip
        for emp in self.env['hr.employee'].browse(emp_ids):
            try:
                oc = Slip.onchange_employee_id(ds, de, emp.id, contract_id=False)
                v = oc.get('value', {})
                if not v.get('contract_id'):
                    exceptions.append({'emp': emp.name, 'why': 'No running contract'})
                    continue
                slip = Slip.create({
                    'employee_id': emp.id,
                    'name': v.get('name') or ('%s - %s' % (emp.name, name)),
                    'struct_id': v.get('struct_id'),
                    'contract_id': v.get('contract_id'),
                    'payslip_run_id': run.id,
                    'input_line_ids': [(0, 0, x) for x in (v.get('input_line_ids') or [])],
                    'worked_days_line_ids': [(0, 0, x) for x in (v.get('worked_days_line_ids') or [])],
                    'date_from': ds,
                    'date_to': de,
                    'company_id': emp.company_id.id,
                })
                created += slip
            except Exception as e:
                _logger.warning("Payrun wizard: skip %s: %s", emp.name, e)
                exceptions.append({'emp': emp.name, 'why': 'Generation error'})

        # compute each slip independently so one failure doesn't roll back all
        computed = 0
        for slip in created:
            try:
                slip.compute_sheet()
                computed += 1
            except Exception as e:
                _logger.warning("Payrun wizard: compute fail %s: %s", slip.employee_id.name, e)
                exceptions.append({'emp': slip.employee_id.name, 'why': 'Compute error'})

        summary = self.get_summary(run.id)
        summary['exceptions'] = exceptions
        summary['computed'] = computed
        return summary

    # ---------------- Step 2 (chunked): prepare + compute in batches ----------------
    # The single create_and_compute() above blocks for the whole run (900 slips),
    # leaving the UI on an indeterminate spinner. prepare_run() + compute_batch()
    # let the OWL wizard drive the work in chunks, showing a determinate progress
    # bar and keeping each RPC bounded (and each batch commits on its own).
    @api.model
    def prepare_run(self, vals):
        """Guard existing payroll, (optionally) clean it, create the draft run and
        return the list of eligible employees for the client to compute in chunks."""
        name = vals.get('name') or 'Payroll run'
        ds = vals.get('date_start')
        de = vals.get('date_end')
        force_clean = vals.get('force_clean')

        existing = self._period_runs(ds, de)
        if existing and not force_clean:
            locked = any(getattr(r, 'locked', False) for r in existing)
            if locked:
                return {
                    'needs_confirmation': True, 'kind': 'historical',
                    'message': "Historical payroll runs are locked. Would you like to "
                               "clean July’s payroll data and rerun July payroll?",
                    'july': self._july_period(ds),
                }
            return {
                'needs_confirmation': True, 'kind': 'exists',
                'message': "This month’s payroll already exists. Would you like to "
                           "clear existing payroll data and run payroll again?",
            }
        # Run the mutations as sudo: on the shared demo the acting user can create
        # and compute payslips but not *unlink* them (record rules), so cleaning a
        # previous run to re-run would raise AccessError. The wizard only ever
        # produces a reversible DRAFT run, and the demo is explicitly shared /
        # overwritable, so elevating these data operations is safe & intended.
        if force_clean and existing:
            self.sudo()._clean_period(existing.sudo())

        run = self.env['hr.payslip.run'].sudo().create({'name': name, 'date_start': ds, 'date_end': de})
        emp_ids = self._eligible_employees()
        return {
            'run_id': run.id, 'name': name,
            'date_start': ds, 'date_end': de,
            'division': vals.get('division'),   # passed back to compute_batch
            'emp_ids': emp_ids, 'total': len(emp_ids),
        }

    @api.model
    def compute_batch(self, payload):
        """Create + compute payslips for one chunk of employees. `payload` carries
        {run_id, name, date_start, date_end, division, emp_ids}. Returns the count
        computed and any exceptions so the client can accumulate progress.
        (pb_demo overrides this to chunk the division-scoped formula compute.)"""
        run_id = payload['run_id']
        name = payload.get('name')
        ds = payload.get('date_start')
        de = payload.get('date_end')
        emp_ids = payload.get('emp_ids') or []
        # sudo: see prepare_run — demo users may lack create/unlink on payslips.
        Slip = self.env['hr.payslip'].sudo()
        exceptions = []
        created = Slip.browse()
        for emp in self.env['hr.employee'].sudo().browse(emp_ids):
            try:
                oc = Slip.onchange_employee_id(ds, de, emp.id, contract_id=False)
                v = oc.get('value', {})
                if not v.get('contract_id'):
                    exceptions.append({'emp': emp.name, 'why': 'No running contract'})
                    continue
                slip = Slip.create({
                    'employee_id': emp.id,
                    'name': v.get('name') or ('%s - %s' % (emp.name, name)),
                    'struct_id': v.get('struct_id'),
                    'contract_id': v.get('contract_id'),
                    'payslip_run_id': run_id,
                    'input_line_ids': [(0, 0, x) for x in (v.get('input_line_ids') or [])],
                    'worked_days_line_ids': [(0, 0, x) for x in (v.get('worked_days_line_ids') or [])],
                    'date_from': ds,
                    'date_to': de,
                    'company_id': emp.company_id.id,
                })
                created += slip
            except Exception as e:
                _logger.warning("Payrun wizard: skip %s: %s", emp.name, e)
                exceptions.append({'emp': emp.name, 'why': 'Generation error'})

        # A shared salary-rule cache across this chunk avoids the per-rule N+1
        # lookup in _create_payslip_lines_from_formulas (see hr_payslip_formula).
        computed = 0
        rule_cache = {}
        for slip in created:
            try:
                slip.with_context(pb_salary_rule_cache=rule_cache).compute_sheet()
                computed += 1
            except Exception as e:
                _logger.warning("Payrun wizard: compute fail %s: %s", slip.employee_id.name, e)
                exceptions.append({'emp': slip.employee_id.name, 'why': 'Compute error'})

        return {'computed': computed, 'exceptions': exceptions}

    # ---------------- Step 3/4: summary + approve ----------------
    @api.model
    def _slip_net(self, slip):
        try:
            lines = slip.line_ids.filtered(lambda l: (l.code or '').upper() == 'NET')
            if lines:
                return sum(lines.mapped('total'))
            # fallback: last line total
            return slip.line_ids and slip.line_ids[-1].total or 0.0
        except Exception:
            return 0.0

    @api.model
    def get_summary(self, run_id):
        # sudo: the run/slips may have been created as sudo (see compute_batch).
        run = self.env['hr.payslip.run'].sudo().browse(run_id)
        slips = run.slip_ids
        rows, total_net = [], 0.0
        for s in slips:
            net = self._slip_net(s)
            total_net += net
            rows.append({
                'id': s.id, 'emp': s.employee_id.name, 'state': s.state,
                'net': net, 'flag': (net <= 0),
            })
        return {
            'run_id': run.id, 'name': run.name, 'state': run.state,
            'count': len(slips), 'total_net': total_net,
            'flagged': len([r for r in rows if r['flag']]),
            'rows': rows,
        }

    @api.model
    def submit_for_approval(self, run_id):
        run = self.env['hr.payslip.run'].browse(run_id)
        ok = False
        try:
            if hasattr(run, 'action_payslip_run_level1_done'):
                run.action_payslip_run_level1_done()
                ok = True
        except Exception as e:
            _logger.warning("Payrun wizard: submit failed: %s", e)
        return {'ok': ok, 'run_id': run.id, 'state': run.state}
