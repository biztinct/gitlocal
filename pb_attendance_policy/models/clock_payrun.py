"""WFSETUP P10b — the pay run's pre-run check for hours from the clocks.

Proposal WFSETUP_P10A §3.5 / §6. Cloned from the weekly-timesheet seam
(`pb_timesheet_approval/models/payrun_wizard.py`): asked BEFORE the run
exists, for the people the wizard itself is about to pay
(`_eligible_employees`). A run on a clock-sourced scheme for a period on or
after its clock date is refused with ONE grouped list whenever anybody's
hours are missing or doubtful — never zeros. Each payslip checks again
(`hr.formula.config._pb_clock_apply`, defence in depth).

Periods before the clock date, and schemes with no clock date, never reach
any of this (`readiness` answers `active: False` and nothing is refused).
"""
import logging

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PbPayrunWizardClock(models.AbstractModel):
    _inherit = 'pb.payrun.wizard'

    @api.model
    def _pb_clock_panel(self, vals):
        vals = vals or {}
        config = self._scheme_from_vals(vals)
        ds, de = vals.get('date_start'), vals.get('date_end')
        if not config or not ds or not de or 'pb_clock_from' not in config._fields \
                or not config.sudo().pb_clock_from:
            return {'active': False}
        if config.sudo()._pb_clock_mode(ds, de) == 'crossing':
            return {'active': True, 'mode': 'crossing', 'total': 0, 'ready': 0, 'attention': 0,
                    'groups': [], 'clock_from': str(config.sudo().pb_clock_from),
                    'scheme_issues': [_(
                        "This pay period starts before and ends after the clock start date "
                        "(%(day)s). Split it at that date.", day=str(config.sudo().pb_clock_from))]}
        emp_ids = list(vals.get('emp_ids') or [])
        if not emp_ids:
            emp_ids = list(self._eligible_employees(
                statuses=vals.get('statuses'), employee_ids=vals.get('employee_ids'),
                formula_config_id=config.id, date_start=ds, date_end=de) or [])
        employees = self.env['hr.employee'].sudo().browse(emp_ids)
        return self.env['pb.clock.payroll'].readiness(config, employees, ds, de)

    @api.model
    def pb_clock_readiness(self, vals=None):
        self._require_runner()
        try:
            return self._pb_clock_panel(vals)
        except UserError as e:
            return {'active': True, 'error': str(e), 'groups': [], 'total': 0, 'ready': 0, 'attention': 0}
        except Exception:       # noqa: BLE001 — a panel never breaks the screen
            _logger.exception("clock readiness panel failed")
            return {'active': False}

    @api.model
    def _pb_clock_refusal(self, vals):
        panel = self._pb_clock_panel(vals)
        return self.env['pb.clock.payroll'].refusal_text(panel)

    # ------------------------------------------------------------- the seams
    @api.model
    def prepare_run(self, vals):
        self._require_runner()
        text = self._pb_clock_refusal(vals)
        if text:
            return {'needs_confirmation': False, 'blocked': True, 'kind': 'clock', 'message': text}
        return super().prepare_run(vals)

    @api.model
    def create_and_compute(self, vals):
        self._require_runner()
        text = self._pb_clock_refusal(vals)
        if text:
            raise UserError(text)
        return super().create_and_compute(vals)
