from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.addons.biz_approval_workflow.models.proposal import BizApprovalProposalMixin
from odoo.addons.pb_pay_builder.models.builder import amount


class ContractPanel(models.AbstractModel):
    _inherit = 'pb.contracts'

    def _pbpb_can_change(self):
        return self._cd_may_write() and self.env['pb.job.change']._may_see_pay()

    def _cd_payload(self, contract):
        data = super()._cd_payload(contract)
        data['may_change_pay'] = self._pbpb_can_change() and contract.state == 'open'
        return data


class ChangePay(models.AbstractModel):
    _inherit = 'pb.pay.builder'

    def _subject(self, home, ref):
        if home != 'change':
            return super()._subject(home, ref)
        panel = self.env['pb.contracts']
        if not panel._pbpb_can_change():
            raise AccessError(_('You can look at this person but not at their pay.'))
        contract = panel._cd_contract(ref.get('contract_id'))
        if not contract or contract.company_id not in self.env.companies:
            raise AccessError(_('This contract is not available.'))
        change = self.env['pb.job.change']
        if contract.state != 'open' or contract != change._running_contract(contract.employee_id):
            raise UserError(_("Open the person's running contract to change their pay."))
        next_month = fields.Date.end_of(change._today_for(contract.company_id), 'month') + timedelta(days=1)
        day = fields.Date.to_date(ref.get('effective_date')) or next_month
        subject = self._contract_subject(contract.sudo(), day)
        return dict(subject, compare=True, can_edit=True, can_open=self._can_open())

    def _answer(self, subject, values, tries=None, open_codes=None):
        answer = super()._answer(subject, values, tries, open_codes)
        if not subject.get('compare') or answer['state'] != 'ok':
            return answer
        old = super()._answer(subject, {}, None, None)
        if old['state'] != 'ok':
            return answer
        before = {line['code']: line for section in old['sections'] for line in section['lines']}
        currency = subject['currency']
        if currency.compare_amounts(answer['head']['value'], old['head']['value']):
            answer['head']['was'] = old['head']['value']
        old_asks = {row['code']: row['value'] for row in old['asks']}
        for row in answer['asks']:
            previous = old_asks[row['code']]
            if row['value'] != previous:
                row['was'] = previous
        for section in answer['sections']:
            for line in section['lines']:
                prev = before.get(line['code'], {}).get('amount')
                if prev is not None and line['amount'] is not None and currency.compare_amounts(line['amount'], prev):
                    line['was'] = prev
        values_before = {}
        deltas = {}
        for key, value in answer['totals'].items():
            previous = old['totals'][key]
            if value is not None and previous is not None and currency.compare_amounts(value, previous):
                change = currency.round(value - previous)
                values_before[key] = previous
                deltas[key] = {'amount': change, 'gain': (change < 0 if key in ('deductions','cost') else change > 0)}
        answer['totals']['was'] = values_before
        answer['deltas'] = deltas
        answer['notes'].insert(0, _('A full month before and after. The month the change starts may mix both.'))
        return answer

    @api.model
    def change_open(self, contract_id):
        subject = self._subject('change', {'contract_id': contract_id})
        contract = subject['contract']
        # Use the approval engine's existing fast/route distinction for the same kind as action_send.
        mode = BizApprovalProposalMixin.route_mode(self.env['pb.job.change'], company=contract.company_id, kind_key='pay')
        return {'person': contract.employee_id.name, 'date': str(subject['day']), 'fast': mode == 'fast', 'values': {},
                'reasons': [{'key': key, 'name': name} for key, name in self._reasons().items()]}

    def _reasons(self):
        return {'review': _('Yearly review'), 'promotion': _('Promotion'), 'correction': _('Correction'), 'other': _('Other')}

    @api.model
    def change_send(self, contract_id, effective_date, reason, values):
        subject = self._subject('change', {'contract_id': contract_id, 'effective_date': effective_date})
        why = self._reasons().get(reason)
        if not why or not effective_date:
            raise UserError(_('Choose the reason and the day the new pay starts.'))
        cfg = subject['config']
        if not cfg:
            raise UserError(_('Choose a pay scheme for this person first.'))
        contract = subject['contract']
        contract.lock_for_update()
        valid = set(cfg._pbpb_person_rules().mapped('code'))
        if not isinstance(values, dict) or any(code not in valid | {'wage'} or amount(v) is None for code, v in values.items()):
            raise UserError(_('Check the amounts and try again.'))
        answer = self._answer(subject, values)
        if answer['state'] != 'ok' or answer.get('has_failed'):
            raise UserError(_('The new pay could not be worked out. Check the amounts.'))
        rows = [{'code': code, 'amount': amount(v)} for code, v in values.items() if code in valid]
        for row in rows:
            template = self.env['hr.contract.advantage.template'].sudo().search([('code', '=', row['code'])], limit=1)
            if template and ((template.lower_bound and row['amount'] < template.lower_bound)
                             or (template.upper_bound and row['amount'] > template.upper_bound)):
                raise UserError(_('Check the permitted amount for %s.', template.name))
        start = self.env['pb.job.change'].pb_start_for_employee(contract.employee_id.id,
            {'wage': answer['head']['monthly'], 'lines': rows, 'effective_date': effective_date,
             'reason_kind': 'pay', 'reason': why})
        board = self.env['pb.job.change.board']
        draft = board._prefill(start['params']['vals'], contract.employee_id)
        return board.send(dict(draft, employee_id=contract.employee_id.id))
