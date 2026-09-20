# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""RPC facade for the Bank Verification cockpit (Phase D §3.3).

An AbstractModel (no table) exposing the queue/KPI data and the per-request
split-view payload to the bespoke OWL screen. All account numbers render MASKED
except in the split verify view for HR/finance (safety rail 2).
"""

import base64
import json

from odoo import api, models, _
from odoo.exceptions import AccessError

_HR_GROUP = 'om_hr_payroll.group_hr_payroll_user'
_FINANCE_GROUPS = ('account.group_account_invoice', 'account.group_account_user',
                   'om_hr_payroll.group_hr_payroll_manager')
_MIME_OK = ('image/png', 'image/jpeg', 'application/pdf')


class PbBankOcr(models.AbstractModel):
    _name = 'pb.bank.ocr'
    _description = 'Bank Verification Cockpit'

    # ------------------------------------------------------------- helpers
    def _is_hr(self):
        return self.env.user.has_group(_HR_GROUP) or self.env.user._is_admin()

    def _is_finance(self):
        for g in _FINANCE_GROUPS:
            try:
                if self.env.user.has_group(g):
                    return True
            except (ValueError, KeyError):
                continue
        return self.env.user._is_admin()

    def _mask(self, number):
        digits = ''.join(ch for ch in (number or '') if ch.isdigit())
        return ('•••• ' + digits[-4:]) if len(digits) >= 4 else (digits or '—')

    def _card(self, req, masked=True):
        emp = req.employee_id
        bank = req.resolved_bank_id.short_name or req.x_bank_name or ''
        return {
            'id': req.id,
            'name': req.name,
            'employee': emp.name,
            'employee_id': emp.id,
            'avatar_url': '/web/image/hr.employee/%s/avatar_128' % emp.id,
            'bank': bank,
            'account': self._mask(req.x_account_number) if masked else (req.x_account_number or ''),
            'state': req.state,
            'doc_kind': req.doc_kind,
            'ocr_state': req.ocr_state,
            'name_score': round(req.name_match_score or 0),
            'name_band': req.name_match_band or '',
            'has_dupes': bool(req.duplicate_ids),
        }

    # --------------------------------------------------------- queue data
    @api.model
    def get_queue_data(self):
        Req = self.env['pb.bank.change.request']
        is_hr, is_fin = self._is_hr(), self._is_finance()
        my_emp = self.env.user.employee_id

        mine = Req.search([('employee_id', '=', my_emp.id)]) if my_emp else Req.browse()
        hr = Req.search([('state', '=', 'hr_review')]) if is_hr else Req.browse()
        fin = Req.search([('state', '=', 'finance_review')]) if is_fin else Req.browse()
        done = Req.search([('state', 'in', ('approved', 'refused'))], limit=50) \
            if (is_hr or is_fin) else mine.filtered(lambda r: r.state in ('approved', 'refused'))

        return {
            'is_hr': is_hr,
            'is_finance': is_fin,
            'queues': {
                'mine': [self._card(r) for r in mine],
                'hr': [self._card(r) for r in hr],
                'finance': [self._card(r) for r in fin],
                'done': [self._card(r) for r in done],
            },
            'kpis': {
                'mine_open': len(mine.filtered(lambda r: r.state not in ('approved', 'refused'))),
                'hr_pending': len(hr),
                'finance_pending': len(fin),
            },
            'provider': self._provider_info(),
        }

    def _provider_info(self):
        cfg = self.env['payroll.ai.config'].get_config_for_purpose('doc_ocr')
        if not cfg:
            return {'configured': False, 'type': _('none'),
                    'note': _('No document-OCR provider configured.')}
        available = False
        try:
            available = cfg.get_provider().is_available()
        except Exception:
            available = False
        return {
            'configured': True,
            'type': cfg.provider_type,
            'model': cfg.model_name or '',
            'available': available,
        }

    @api.model
    def test_provider(self):
        if not (self._is_hr() or self._is_finance()):
            raise AccessError(_("Only HR or Finance can test the OCR provider."))
        cfg = self.env['payroll.ai.config'].get_config_for_purpose('doc_ocr')
        if not cfg:
            return {'success': False, 'message': _('No OCR provider configured.')}
        try:
            return cfg.get_provider().test_connection()
        except Exception as e:
            return {'success': False, 'message': str(e), 'latency_ms': 0}

    # --------------------------------------------------------- request CRUD
    @api.model
    def create_from_upload(self, payload):
        """payload = {name, mime, data (base64), employee_id?}. Creates the
        attachment + a draft request, returns its id."""
        mime = payload.get('mime')
        if mime not in _MIME_OK:
            raise AccessError(_("Only JPG, PNG or PDF documents are accepted."))
        emp_id = payload.get('employee_id') or (self.env.user.employee_id.id if self.env.user.employee_id else False)
        if not emp_id:
            raise AccessError(_("No employee is linked to your user."))
        att = self.env['ir.attachment'].create({
            'name': payload.get('name') or 'bank-document',
            'datas': payload.get('data') or '',
            'mimetype': mime,
        })
        req = self.env['pb.bank.change.request'].create({
            'employee_id': emp_id,
            'attachment_id': att.id,
        })
        att.write({'res_model': req._name, 'res_id': req.id})
        return req.id

    @api.model
    def run_ocr(self, request_id):
        req = self._req(request_id)
        req.action_run_ocr()
        return self.get_request(request_id)

    @api.model
    def save_fields(self, request_id, vals):
        req = self._req(request_id)
        allowed = {'x_bank_name', 'x_bank_branch', 'x_account_name',
                   'x_account_number', 'x_iban', 'x_swift', 'doc_kind'}
        # the duplicate ack is HR/finance testimony, never the requester's
        if self._is_hr() or self._is_finance():
            allowed.add('duplicate_ack')
        req.write({k: v for k, v in (vals or {}).items() if k in allowed})
        return {'ok': True}

    @api.model
    def validate(self, request_id):
        req = self._req(request_id)
        req.action_validate()
        return self.get_request(request_id)

    @api.model
    def do_action(self, request_id, action, note=False):
        req = self._req(request_id)
        method = {
            'submit': 'action_submit',
            'hr_approve': 'action_hr_approve',
            'finance_approve': 'action_finance_approve',
        }.get(action)
        if action == 'refuse':
            req.action_refuse_chain(note=note or False)
        elif method:
            getattr(req, method)()
        else:
            raise AccessError(_("Unknown action."))
        return self.get_request(request_id)

    @api.model
    def get_request(self, request_id):
        req = self._req(request_id)
        # the split verify view is the ONE place the full account shows, and
        # only to HR/finance (or the owner reviewing their own submission)
        owner = req.employee_id.user_id == self.env.user
        unmask = self._is_hr() or self._is_finance() or owner
        conf = {}
        try:
            conf = json.loads(req.confidence_json or '{}')
        except Exception:
            conf = {}
        fields = {}
        for f in ('x_bank_name', 'x_bank_branch', 'x_account_name',
                  'x_account_number', 'x_iban', 'x_swift'):
            fields[f] = {'value': req[f] or '', 'confidence': conf.get(f)}
        diff = []
        for (x, cur, label) in (
            ('x_bank_name', 'cur_bank_name', _('Bank')),
            ('x_bank_branch', 'cur_bank_branch', _('Branch')),
            ('x_account_name', 'cur_account_name', _('Holder')),
            ('x_account_number', 'cur_account_number', _('Account')),
        ):
            cur_v = req[cur] or ''
            new_v = req[x] or ''
            if x == 'x_account_number' and not unmask:
                cur_v, new_v = self._mask(cur_v), self._mask(new_v)
            diff.append({'label': label, 'current': cur_v, 'extracted': new_v,
                         'changed': (req[cur] or '') != (req[x] or '')})
        return {
            'id': req.id,
            'name': req.name,
            'employee': req.employee_id.name,
            'employee_id': req.employee_id.id,
            'avatar_url': '/web/image/hr.employee/%s/avatar_128' % req.employee_id.id,
            'state': req.state,
            'doc_kind': req.doc_kind,
            'ocr_state': req.ocr_state,
            'ocr_provider': req.ocr_provider or '',
            'doc_url': '/web/content/ir.attachment/%s/datas' % req.attachment_id.id if req.attachment_id else '',
            'doc_mime': req.attachment_id.mimetype if req.attachment_id else '',
            'fields': fields,
            'unmask': unmask,
            'diff': diff,
            'validation': {
                'format_ok': req.v_format_ok,
                'format_msg': req.v_format_msg or '',
                'name_score': round(req.name_match_score or 0),
                'name_band': req.name_match_band or '',
            },
            'duplicates': [{'id': e.id, 'name': e.name,
                            'account': self._mask(e.vietnam_bank_account_number)}
                           for e in req.duplicate_ids],
            'duplicate_ack': req.duplicate_ack,
            'can': {
                'submit': req.can_submit,
                'hr_approve': req.can_hr_approve,
                'finance_approve': req.can_finance_approve,
                'refuse': req.can_refuse,
            },
            'stepper': req.approval_widget_json or '{}',
        }

    @api.model
    def get_history(self, employee_id):
        rows = self.env['pb.employee.bank.history'].search(
            [('employee_id', '=', int(employee_id))])
        return [{
            'source': r.change_source,
            'by': r.changed_by.name,
            'at': r.changed_at and r.changed_at.strftime('%Y-%m-%d %H:%M') or '',
            'old_account': self._mask(r.old_account_number),
            'new_account': self._mask(r.new_account_number),
            'old_bank': r.old_bank_name or '',
            'new_bank': r.new_bank_name or '',
        } for r in rows]

    def _req(self, request_id):
        return self.env['pb.bank.change.request'].browse(int(request_id)).exists()
