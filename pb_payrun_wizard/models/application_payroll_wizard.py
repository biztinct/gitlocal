"""Application-record payroll is an explicit, scoped route through the wizard."""
import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ApplicationPayrunWizard(models.AbstractModel):
    _inherit = 'pb.payrun.wizard'

    def _application_scope(self, vals):
        self._require_runner()
        self._check_period(vals.get('date_start'), vals.get('date_end'))
        config = self._require_scheme(vals)
        if config:
            config = config.sudo(False)
        if not config or not getattr(config, 'application_data_enabled', False):
            raise UserError(_('Enable application payroll in this scheme’s source settings first.'))
        employee_ids = self._eligible_employees(
            statuses=vals.get('statuses'), employee_ids=vals.get('employee_ids'),
            formula_config_id=config.id, date_start=vals['date_start'], date_end=vals['date_end'])
        if not employee_ids:
            raise UserError(_('No eligible employees match this scheme and period.'))
        return config, sorted(set(employee_ids))

    def _application_certification_payload(self, vals, employee_ids):
        cert = vals.get('application_certifications') or {}
        if not isinstance(cert, dict):
            raise UserError(_('Review the application data coverage.'))
        return {'channels': cert.get('channels') or {},
                'zero_keys': cert.get('zero_keys') or [], 'employee_ids': employee_ids}

    @api.model
    def spreadsheet_gate(self, vals=None):
        self._require_runner()
        answer = super().spreadsheet_gate(vals)
        config_id = int((vals or {}).get('formula_config_id') or answer.get('config_id') or 0)
        if config_id and 'hr.formula.config' in self.env:
            config = self.env['hr.formula.config'].browse(config_id).exists()
            if config and hasattr(config, '_application_require_access'):
                config._application_require_access()
                can_certify = True
                try:
                    config._application_require_access(certify=True)
                except AccessError:
                    can_certify = False
                answer['application'] = {
                    'enabled': config.application_data_enabled,
                    'basis': config.payroll_basis, 'standard_day_basis': config.standard_day_basis,
                    'fixed_standard_days': config.fixed_standard_days,
                    'effective_from': str(config.application_effective_from or ''),
                    'can_certify': can_certify,
                    'settings_stamp': config._application_settings_stamp(),
                }
                if config.application_data_enabled or answer.get('wanted'):
                    answer['config_name'] = config.name
                    answer['config_id'] = config.id
        return answer

    @api.model
    def open_payroll_review(self, vals):
        config, employee_ids = self._application_scope(vals)
        prep = self.env['hr.payroll.preparation']._open(config, employee_ids, vals['date_start'], vals['date_end'])
        return prep.workspace()

    def _reviewed_preparation(self, vals, config, employee_ids):
        prep = self.env['hr.payroll.preparation'].browse(int(vals.get('preparation_id') or 0)).exists()
        if not prep:
            raise UserError(_('Open Review pay data and complete the worksheet review first.'))
        prep._assert_scope(config, employee_ids, vals['date_start'], vals['date_end'])
        return prep

    @api.model
    def application_data_preview(self, vals):
        config, employee_ids = self._application_scope(vals)
        if vals.get('preparation_id'):
            return self._reviewed_preparation(vals, config, employee_ids)._resolved(True)
        cert = self._application_certification_payload(vals, employee_ids)
        if any(cert['channels'].values()) or cert['zero_keys']:
            config._application_require_access(certify=True)
            if not (vals.get('application_certification_reason') or '').strip():
                raise UserError(_('Add the review reference or reason before certifying period coverage.'))
        answer = config.application_preflight(employee_ids, vals['date_start'], vals['date_end'], cert)
        # Only offer missing/explicit-zero monthly items. Existing approved
        # amounts stay authoritative; conflicts are never waived by zero.
        missing = {}
        for person in answer['employees']:
            for item in person['inputs']:
                if item.get('key', '').startswith('period.input.') and item['status'] in ('missing', 'zero_confirmed'):
                    missing[item['key']] = missing.get(item['key'], 0) + 1
        answer['zero_options'] = [dict(v, key=k, owner='Monthly adjustments', missing_count=missing[k])
            for k, v in config._application_source_catalogue().items()
            if v.get('certification_zero_allowed') and k in missing]
        return answer

    @api.model
    def application_issue_action(self, vals, kind, code='', employee_id=False):
        config, employee_ids = self._application_scope(vals)
        return config.application_issue_action(employee_ids, vals['date_start'], vals['date_end'], kind, code, employee_id)

    @api.model
    def sync_plan(self, vals=None):
        if (vals or {}).get('spreadsheet_skipped'):
            self._require_runner()
            config = self._require_scheme(vals)
            if config and getattr(config, 'application_data_enabled', False):
                return {'steps': [], 'unroutable': []}
        return super().sync_plan(vals)

    @api.model
    def prepare_run(self, vals):
        self._require_runner()
        config = self._require_scheme(vals)
        application = vals.get('spreadsheet_skipped') and config and getattr(config, 'application_data_enabled', False)
        if not application:
            return super().prepare_run(vals)
        config, employee_ids = self._application_scope(vals)
        config._application_require_access(certify=True)
        prep = self._reviewed_preparation(vals, config, employee_ids) if vals.get('preparation_id') else False
        if prep:
            review = json.loads(prep.review_json)
            vals = dict(vals, application_certifications=review['certification'], application_certification_reason=review['reason'])
        if not (vals.get('application_certification_reason') or '').strip():
            raise UserError(_('Record your period review before running payroll from application data.'))
        preview = prep._resolved(True) if prep else self.application_data_preview(vals)
        if not preview['ok']:
            return {'blocked': True, 'message': _('Resolve the application data blockers before creating payroll.'),
                    'application_preflight': preview}
        # The legacy wizard adopts loose payslips. Historical spreadsheet slips
        # cannot become certified application payroll simply by joining a run.
        loose = self.env['hr.payslip'].sudo().search_count([
            ('employee_id', 'in', employee_ids), ('payslip_run_id', '=', False),
            ('date_from', '=', vals['date_start']), ('date_to', '=', vals['date_end'])])
        if loose:
            raise UserError(_('Review the existing unassigned payslips for this period before starting an application-data run.'))
        answer = super().prepare_run(vals)
        if answer.get('run_id'):
            run = self.env['hr.payslip.run'].browse(answer['run_id'])
            run.write({'application_data_mode': True})
            run.action_certify_application_data(
                self._application_certification_payload(vals, employee_ids),
                vals['application_certification_reason'])
            if prep:
                prep._attach(run)
            answer['application_data_mode'] = True
        return answer

    @api.model
    def compute_batch(self, payload):
        self._require_runner()
        run = self.env['hr.payslip.run'].browse(int(payload.get('run_id') or 0)).exists()
        if run and getattr(run, 'application_data_mode', False):
            config = run._application_config()
            config._application_require_access()
            if run.state != 'draft':
                raise UserError(_('Only a draft payroll run can be computed.'))
            cert = run._application_certification()
            if (fields.Date.to_date(payload.get('date_start')) != run.date_start or
                    fields.Date.to_date(payload.get('date_end')) != run.date_end or
                    int(payload.get('formula_config_id') or 0) != config.id or
                    not set(payload.get('emp_ids') or []).issubset(set(cert.get('employee_ids') or []))):
                raise AccessError(_('The computation must match the certified scheme, employees and period.'))
        return super().compute_batch(payload)

    @api.model
    def attach_spreadsheet(self, run_id, config_id, file_b64, filename,
                           date_start, date_end, one_time=False):
        self._require_runner()
        run = self.env['hr.payslip.run'].browse(int(run_id or 0)).exists()
        if run and getattr(run, 'application_data_mode', False):
            return {'ok': False, 'msg': _('This run uses certified application records. Start a separate spreadsheet run to import a file.')}
        return super().attach_spreadsheet(run_id, config_id, file_b64, filename,
                                           date_start, date_end, one_time=one_time)
