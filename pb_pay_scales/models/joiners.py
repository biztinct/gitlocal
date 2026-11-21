# -*- coding: utf-8 -*-
"""New joiners start on the scale (owner ruling J4), on every joiner path,
by inheritance only (FACTS §3.2):

1. People › Add a contract  (`pb.people.contract.wizard`): the wage box opens
   already filled from the scale (``get_defaults``), with the sentence that
   produced it; an EMPTY box sent to ``create_contract`` is filled the same
   way; a typed wage that is a step of the grade is "On scale", any other
   typed wage wins and is "Pinned" with the reason picked on the screen.
2. People › Add employee (`pb.people.onboard.wizard`): the screen asks
   ``joiner_suggest`` when the job or the start date changes (patch in
   ``joiner_hint.js``); the contract goes through path 1.
3. Updates › joiners sheet: a row with a job and a start date and NO wage
   gets the scale's amount, shown in the review grid before anything is sent.
4. Hiring › joined: the agreed offer's monthly pay wins; only an offer with no
   monthly pay at all takes the scale's amount, and the offer's trail says so.

Nothing here touches an existing contract.
"""
import logging

from odoo import _, api, models

_logger = logging.getLogger(__name__)

#: The pin reasons a hire screen may send (anything else reads "other").
SCREEN_REASONS = ('offer', 'offer_match', 'retention', 'above_top', 'legacy',
                  'typed', 'other')


def _reason(value):
    value = (value or '').strip() if isinstance(value, str) else ''
    return value if value in SCREEN_REASONS else ''


class PbContractWizardScales(models.AbstractModel):
    _inherit = 'pb.people.contract.wizard'

    @api.model
    def get_defaults(self, employee_id=False, renew_from=False):
        out = super().get_defaults(employee_id, renew_from)
        if renew_from or not employee_id:
            return out
        try:
            hint = self.env['pb.pay.scales'].joiner_suggest(employee_id=employee_id)
        except Exception:       # noqa: BLE001 — a hint never breaks the dialog
            _logger.debug("pb_pay_scales: hint failed", exc_info=True)
            return out
        out['scale_hint'] = hint
        if hint.get('found') and not (out.get('prefill') or {}).get('wage'):
            prefill = dict(out.get('prefill') or {})
            prefill['wage'] = hint['amount']
            out['prefill'] = prefill
        return out

    @api.model
    def create_contract(self, vals):
        vals = dict(vals or {})
        reason = _reason(vals.get('pb_scale_pin_reason')) \
            or _reason(self.env.context.get('pb_scale_pin_reason'))
        note = vals.get('pb_scale_pin_note') or False
        try:
            wage = float(vals.get('wage') or 0.0)
        except (TypeError, ValueError):
            wage = 0.0
        if wage <= 0 and vals.get('employee_id'):
            employee = self.env['hr.employee'].sudo().browse(
                int(vals['employee_id'])).exists()
            if employee:
                answer = self.env['pb.pay.scales'].resolve(
                    employee.job_id, employee.company_id,
                    vals.get('date_start'), employee)
                if answer['found']:
                    vals['wage'] = answer['amount']
        result = super().create_contract(vals)
        if isinstance(result, dict) and result.get('applied') and result.get('contract_id'):
            contract = self.env['hr.contract'].sudo().browse(
                int(result['contract_id'])).exists()
            if contract:
                self.env['pb.pay.scales'].place_new_contract(
                    contract, reason=reason or None, source='hire', note=note)
        return result


class PbOnboardWizardScales(models.AbstractModel):
    _inherit = 'pb.people.onboard.wizard'

    @api.model
    def create_employee(self, vals):
        # The reason picked on the screen travels in the form values (and so
        # in a new-hire proposal's payload when it waits for approval); the
        # contract call inside does not pass it on, so the context does.
        reason = _reason((vals or {}).get('pb_scale_pin_reason'))
        if reason:
            return super(PbOnboardWizardScales, self.with_context(
                pb_scale_pin_reason=reason)).create_employee(vals)
        return super().create_employee(vals)


class PbUpdatesJoinersScales(models.AbstractModel):
    _inherit = 'pb.updates.desk'

    @api.model
    def _judge_row(self, j, schemes, items, index, seen, today, default_start):
        try:
            self._pbs_fill_wage(j)
        except Exception:       # noqa: BLE001 — the sheet never breaks on a scale
            _logger.debug("pb_pay_scales: joiner sheet fill failed", exc_info=True)
        return super()._judge_row(j, schemes, items, index, seen, today, default_start)

    @api.model
    def _pbs_fill_wage(self, j):
        from odoo.addons.pb_updates.models.updates_joiners import WAGE
        if j.get('quick') or 'wage' in (j.get('vals') or {}):
            return
        job_id = (j.get('vals') or {}).get('job_id')
        if not job_id:
            return
        job = self.env['hr.job'].sudo().browse(int(job_id)).exists()
        if not job:
            return
        answer = self.env['pb.pay.scales'].resolve(
            job, self.env.company, (j.get('vals') or {}).get('date_start'))
        if not answer['found']:
            return
        amount = answer['amount']
        j['vals']['wage'] = amount
        label = answer['sentence']
        j['cells'][WAGE] = {
            'status': 'ok', 'old': '', 'new': label, 'why': '',
            'value': amount, 'consumed': True,
            'label': _("Monthly wage"), 'note': _("From the pay scale"),
        }


class PbHiringOfferScales(models.Model):
    _inherit = 'pb.hiring.offer'

    def _ensure_contract(self):
        had = self.contract_id
        contract = super()._ensure_contract()
        if had or not contract:
            return contract
        try:
            self._pbs_after_contract(contract)
        except Exception:       # noqa: BLE001 — joining never fails on a scale
            _logger.warning("pb_pay_scales: offer %s scale step failed", self.id,
                            exc_info=True)
        return contract

    def _pbs_after_contract(self, contract):
        Scales = self.env['pb.pay.scales']
        contract = contract.sudo()
        if (contract.wage or 0.0) <= 0:
            answer = Scales.resolve(contract.job_id or contract.employee_id.job_id,
                                    contract.company_id, contract.date_start,
                                    contract.employee_id)
            if not answer['found']:
                return
            contract.write({'wage': answer['amount']})
            self.sudo().message_post(body=_(
                "The offer had no monthly pay, so the contract wage came from "
                "the pay scale: %(line)s.", line=answer['sentence']))
        Scales.place_new_contract(contract, reason='offer', source='hire')
