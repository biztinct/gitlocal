# -*- coding: utf-8 -*-
"""RPC facade for the bespoke full-screen Pay & Deliver experience.

An AbstractModel (no table) exposing three lanes to the OWL client action:
  * bank file       — prepare, send in, follow, download the approved one,
  * payment release — ask for the money to be sent, follow, see it land,
  * payslips out    — recipient preview + encrypted-PDF batch delivery + log.

Access is enforced HERE (safety rail 3): an ir.actions.client carries no group
field, so every public method guards with `_require_access()` → AccessError.
The resolved PDF password is never returned by any method (rail 4).

WHAT PHASE 5 CHANGED. Every one of the three lanes used to be a button that
did the thing. Each is now a button that ASKS — and the answer, including "no
approval needed" where the business published that, is recorded. The payload
each lane returns therefore carries the same three things: what state it is in,
who it is with, and the door to the request.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .approval_common import PAY_GROUPS as _PAY_GROUPS


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

    # --------------------------------------------------- the approval payload
    def _route_payload(self, record):
        """The same three answers for every lane: state, who, the door.

        `pending` is not enough on its own — an approver's name is what turns
        "waiting" from a dead end into something a person can chase.
        """
        if not record:
            return {'exists': False, 'state': '', 'state_label': '',
                    'request_id': 0, 'with_whom': '', 'block_reason': '',
                    'route': []}
        request = record.approval_request_id
        steps = []
        if request:
            for step in request.step_ids.sorted('sequence'):
                if not step.included or step.kind == 'fast':
                    continue
                steps.append({
                    'title': step.title,
                    'status': step.status,
                    'people': sorted({seat.acting_user_id.name or ''
                                      for seat in step.seat_ids}),
                })
        return {
            'exists': True,
            'id': record.id,
            'state': record.state,
            'state_label': dict(
                record._fields['state'].selection).get(record.state, ''),
            'request_id': request.id if request else 0,
            'with_whom': record._waiting_for(),
            'block_reason': request.block_reason or '' if request else '',
            'route': steps,
        }

    def _fast_lane(self, model, run):
        """Has the business said this one needs no approval?

        Asked of the ENGINE, every read, and never remembered: a route that
        exists exists whether or not anybody ticked a box, and the answer
        decides what the button says.
        """
        Model = self.env[model]
        process = self.env['biz.approval.process']._by_key(
            Model._approval_process_key)
        if not process:
            return False
        company = getattr(run, 'company_id', False) or self.env.company
        keys, _label = self.env['pb.bank.file'].scope_of_run(run)
        resolved = self.env['biz.approval.engine'].sudo().resolve_binding(
            company.id, process.key, keys, 'any')
        if resolved.get('error') or not resolved.get('version_id'):
            return False
        version = self.env['biz.approval.workflow.version'].sudo().browse(
            resolved['version_id'])
        from odoo.addons.biz_approval_workflow.models import definition as D
        steps = [s for s in D.normalise(version.definition)['steps']
                 if s['kind'] not in ('notify',)]
        return (not steps) or any(s['kind'] == 'fast' for s in steps)

    def _bank_file_payload(self, run):
        latest = self.env['pb.bank.file'].search(
            [('run_id', '=', run.id), ('state', '!=', 'superseded')],
            order='id desc', limit=1)
        payload = self._route_payload(latest)
        payload.update({
            'filename': latest.filename or '' if latest else '',
            'row_count': latest.row_count if latest else 0,
            'control_total': latest.control_total if latest else 0.0,
            'excluded_count': latest.excluded_count if latest else 0,
            'byte_size': latest.byte_size if latest else 0,
            'bank_format': latest.bank_format or '' if latest else '',
            'downloadable': bool(latest and latest.state == 'approved'),
            'fast_lane': self._fast_lane('pb.bank.file', run),
        })
        return payload

    def _release_payload(self, run):
        latest = self.env['pb.payment.release'].search(
            [('run_id', '=', run.id)], order='id desc', limit=1)
        payload = self._route_payload(latest)
        payload.update({
            'amount': latest.amount if latest else 0.0,
            'beneficiaries': latest.beneficiaries if latest else 0,
            'bank_reference': latest.bank_reference or '' if latest else '',
            'released_on': fields.Datetime.to_string(latest.released_on) or ''
            if latest else '',
            'fast_lane': self._fast_lane('pb.payment.release', run),
        })
        return payload

    def _delivery_payload(self, batch, run=None):
        base = {'exists': False, 'state': 'draft', 'sent': 0, 'failed': 0,
                'skipped': 0, 'lines': [], 'request_id': 0, 'with_whom': '',
                'state_label': '', 'route': [],
                'fast_lane': self._fast_lane('pb.payslip.delivery.batch', run)
                if run else True}
        if not batch:
            return base
        lines = [{
            'employee': l.employee_id.name or '',
            'email': l.email or '',
            'state': l.state,
            'error': l.error or '',
        } for l in batch.line_ids]
        base.update(self._route_payload(batch))
        base.update({
            'exists': True, 'state': batch.state,
            'sent': batch.sent_count, 'failed': batch.failed_count,
            'skipped': batch.skipped_count, 'lines': lines,
        })
        return base

    # ------------------------------------------------------------- run picker
    @api.model
    def get_recent_runs(self):
        """Recent pay runs (newest first) for the sidebar entry's picker.

        Only runs that actually have something to pay/deliver are offered — i.e.
        an approved run OR one carrying at least one confirmed (done) payslip.
        A draft/empty run has zero deliverable slips (``_done_slips`` filters on
        ``state == 'done'``), so listing it would only dead-end the picker."""
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
                'paid': bool(getattr(run, 'pb_paid', False)),
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
                'state': run.state,
                'approved': (run.state or '') == 'done',
                'paid': bool(getattr(run, 'pb_paid', False)),
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
            'bank_file': self._bank_file_payload(run),
            'release': self._release_payload(run),
            'delivery': self._delivery_payload(self._batch(run), run=run),
            'is_manager': True,
        }

    # ------------------------------------------------------------- money out
    @api.model
    def prepare_bank_file(self, run_id, bank_format, company_account=None):
        """Generate the file, store it, and send it in for approval."""
        self._require_access()
        run = self._run(run_id)
        record = self.env['pb.bank.file'].prepare(
            run, bank_format, company_account or None)
        self.env['biz.approval.engine'].submit(record)
        return self._bank_file_payload(run)

    @api.model
    def download_bank_file(self, run_id):
        """The approved bytes, and nothing else."""
        self._require_access()
        run = self._run(run_id)
        record = self.env['pb.bank.file'].search(
            [('run_id', '=', run.id), ('state', '=', 'approved')],
            order='id desc', limit=1)
        if not record:
            latest = self.env['pb.bank.file'].search(
                [('run_id', '=', run.id), ('state', '!=', 'superseded')],
                order='id desc', limit=1)
            raise AccessError(_(
                "There is no approved bank file for this pay run yet.%s",
                (_(" The one that was prepared is with %s.",
                   latest._waiting_for() or _('its approver'))
                 if latest else '')))
        return record.action_download()

    @api.model
    def request_release(self, run_id, bank_reference=None):
        """Ask for the money behind the approved file to be sent."""
        self._require_access()
        run = self._run(run_id)
        bank_file = self.env['pb.bank.file'].search(
            [('run_id', '=', run.id), ('state', '=', 'approved')],
            order='id desc', limit=1)
        if not bank_file:
            raise AccessError(_(
                "The bank file has to be approved before the money can be "
                "released."))
        release = self.env['pb.payment.release'].prepare(
            bank_file, bank_reference)
        self.env['biz.approval.engine'].submit(release)
        return self._release_payload(run)

    # ------------------------------------------------------------- payslips out
    @api.model
    def send_payslips(self, run_id, force_all=False):
        self._require_access()
        run = self._run(run_id)
        batch = self._batch(run, create=True)
        batch.action_send(force_all=force_all)
        return self._delivery_payload(batch, run=run)

    # ------------------------------------------------------------- the door
    @api.model
    def open_request(self, request_id):
        """Take the person to the request itself, wherever it is."""
        self._require_access()
        return {
            'type': 'ir.actions.client',
            'tag': 'pb_approval_inbox',
            'name': _('Approvals'),
            'params': {'request_id': int(request_id or 0)},
        }
