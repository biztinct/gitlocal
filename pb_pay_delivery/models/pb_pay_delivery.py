# -*- coding: utf-8 -*-
"""RPC facade for the bespoke full-screen Pay & Deliver experience (Phase F §4).

An AbstractModel (no table) exposing two lanes to the OWL client action:
  * money out  — validation preview + real bank-file generation (delegates to
    the data-driven vietnam.bank.export.wizard),
  * payslips out — recipient preview + encrypted-PDF batch delivery + per-slip
    log (delegates to pb.payslip.delivery.batch).

Access is enforced HERE (safety rail 3 / C18.9): an ir.actions.client carries no
group field, so every public method guards with _require_access() → AccessError.
The resolved PDF password is never returned by any method (rail 4).
"""

from odoo import _, api, models
from odoo.exceptions import AccessError

_PAY_GROUPS = ('om_hr_payroll.group_hr_payroll_manager',
               'account.group_account_invoice', 'account.group_account_user')


class PbPayDelivery(models.AbstractModel):
    _name = 'pb.pay.delivery'
    _description = 'Pay & Deliver Cockpit'

    # ------------------------------------------------------------- access
    @api.model
    def _require_access(self):
        user = self.env.user
        if user._is_admin():
            return
        for g in _PAY_GROUPS:
            try:
                if user.has_group(g):
                    return
            except (ValueError, KeyError):
                continue
        raise AccessError(_(
            "You are not allowed to open Pay & Deliver. This requires the "
            "Payroll Manager or a Finance role."))

    # ------------------------------------------------------------- helpers
    def _run(self, run_id):
        return self.env['hr.payslip.run'].browse(int(run_id))

    def _done_slips(self, run):
        return run.slip_ids.filtered(lambda s: s.state == 'done')

    def _wizard(self, run):
        return self.env['vietnam.bank.export.wizard'].create({
            'payslip_run_id': run.id})

    def _validation_preview(self, run):
        """Format-independent row validation (account/holder/bank/net)."""
        wiz = self._wizard(run)
        registry = self.env['pb.bank.registry']
        eligible, excluded, total_net = 0, [], 0.0
        for slip in self._done_slips(run).sorted(key=lambda s: s.employee_id.name or ''):
            sources, reasons, net = wiz._row_sources(slip, eligible + 1, registry)
            if reasons:
                excluded.append({
                    'employee': slip.employee_id.name or '',
                    'employee_id': slip.employee_id.id,
                    'reasons': reasons,
                })
            else:
                eligible += 1
                total_net += net
        return eligible, excluded, total_net

    def _batch(self, run, create=False):
        batch = self.env['pb.payslip.delivery.batch'].search(
            [('run_id', '=', run.id)], order='create_date desc', limit=1)
        if not batch and create:
            batch = self.env['pb.payslip.delivery.batch'].create({
                'run_id': run.id, 'name': _('Delivery — %s', run.name)})
        return batch

    def _delivery_payload(self, batch):
        if not batch:
            return {'exists': False, 'state': 'draft', 'sent': 0, 'failed': 0,
                    'skipped': 0, 'lines': []}
        lines = [{
            'employee': l.employee_id.name or '',
            'email': l.email or '',
            'state': l.state,
            'error': l.error or '',
        } for l in batch.line_ids]
        return {
            'exists': True, 'state': batch.state,
            'sent': batch.sent_count, 'failed': batch.failed_count,
            'skipped': batch.skipped_count, 'lines': lines,
        }

    # ------------------------------------------------------------- run picker
    @api.model
    def get_recent_runs(self):
        """Recent pay runs (newest first) for the sidebar entry's picker.

        Only runs that actually have something to pay/deliver are offered — i.e.
        an approved run OR one carrying at least one confirmed (done) payslip.
        A draft/empty run has zero deliverable slips (``_done_slips`` filters on
        ``state == 'done'``), so listing it would only dead-end the picker
        (Phase-F review debt)."""
        self._require_access()
        runs = self.env['hr.payslip.run'].search(
            ['|', ('state', '=', 'done'), ('slip_ids.state', '=', 'done')],
            order='date_end desc, id desc', limit=24)
        out = []
        for run in runs:
            done = self._done_slips(run)
            out.append({
                'id': run.id, 'name': run.name, 'state': run.state,
                'period': "%s → %s" % (run.date_start, run.date_end)
                if run.date_start and run.date_end else '',
                'headcount': len(done),
            })
        return out

    # ------------------------------------------------------------- load
    @api.model
    def get_delivery_data(self, run_id):
        self._require_access()
        run = self._run(run_id)
        done = self._done_slips(run)

        eligible, excluded, total_net = self._validation_preview(run)

        # Recipient preview (payslips-out lane).
        recips, no_email = [], []
        for slip in done.sorted(key=lambda s: s.employee_id.name or ''):
            emp = slip.employee_id
            entry = {'employee': emp.name or '',
                     'avatar_url': '/web/image/hr.employee/%s/avatar_128' % emp.id,
                     'email': emp.work_email or ''}
            (recips if emp.work_email else no_email).append(entry)

        banks = [{'key': l.bank_format, 'name': l.name}
                 for l in self.env['pb.bank.file.layout'].search(
                     [], order='name')]

        currency = (self.env.company.currency_id.symbol or '₫')
        pattern = self.env['ir.config_parameter'].sudo().get_param(
            'pb_pay_delivery.pdf_password_pattern') or '{account_last4}{birth_year}'

        return {
            'run': {
                'id': run.id, 'name': run.name,
                'period': "%s → %s" % (run.date_start, run.date_end)
                if run.date_start and run.date_end else '',
                'headcount': len(done),
                'total_net': total_net,
            },
            'currency': currency,
            'banks': banks,
            'validation': {
                'eligible': eligible,
                'excluded_count': len(excluded),
                'excluded': excluded,
            },
            'recipients': {
                'count': len(recips),
                'no_email_count': len(no_email),
                'avatars': [r['avatar_url'] for r in recips[:14]],
                'no_email': no_email,
            },
            'password_pattern': pattern,
            'delivery': self._delivery_payload(self._batch(run)),
            'is_manager': True,
        }

    # ------------------------------------------------------------- money out
    @api.model
    def generate_bank_file(self, run_id, bank_format, company_account=None):
        self._require_access()
        run = self._run(run_id)
        wiz = self._wizard(run)
        wiz.bank_format = bank_format
        if company_account:
            wiz.company_account_number = company_account
        return wiz._generate()

    # ------------------------------------------------------------- payslips out
    @api.model
    def send_payslips(self, run_id, force_all=False):
        self._require_access()
        run = self._run(run_id)
        batch = self._batch(run, create=True)
        batch.action_send(force_all=force_all)
        return self._delivery_payload(batch)
