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

    # ---------------- Step 2: create + compute ----------------
    @api.model
    def create_and_compute(self, vals):
        Run = self.env['hr.payslip.run']
        Slip = self.env['hr.payslip']
        name = vals.get('name') or 'Payroll run'
        ds = vals.get('date_start')
        de = vals.get('date_end')
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
        run = self.env['hr.payslip.run'].browse(run_id)
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
