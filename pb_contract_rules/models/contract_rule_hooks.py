# -*- coding: utf-8 -*-
"""Where the fixed-term rule speaks — all by inheritance (S8 lane rule).

  * `pb.contract.review.decision_preview('extend')` carries a `limit` answer
    the board draws as a red warning with "Make it permanent" beside it.
  * `action_request_extension` keeps the reason as the reason for going past
    the rule and writes that down; it never refuses for the rule (ruling J3).
  * `_build_new_contract` notes on the new contract that it went past the rule.
  * The extension's sign-off route gains a fact, "Goes past the fixed-term
    rule", that a business may add a step on; its detail says so.
  * The decision drawer shows "Fixed-term contract 2 in a row".
  * Updates can fill the earlier-contract numbers (`_master_fields`, the
    S8 shared seam: call super, add only these two fields).
"""
from odoo import _, api, models


class PbContractReviewRules(models.Model):
    _inherit = 'pb.contract.review'

    def decision_preview(self, decision, months=None):
        answer = super().decision_preview(decision, months=months)
        if decision != 'extend':
            return answer
        try:
            span = int(months) if months else None
        except (TypeError, ValueError):
            span = None
        if span is None:
            from odoo.addons.pb_contract_lifecycle.models.contract_common import (
                P_EXTENSION_MONTHS, number)
            span = int(number(self.env, P_EXTENSION_MONTHS, 12))
        check = self.env['pb.contract.rule'].check_extension(
            self.contract_id, span)
        if check.get('over'):
            answer = dict(answer)
            answer['limit'] = check
        return answer

    def action_request_extension(self, reason=None, months=None):
        self.ensure_one()
        span = months
        if not span:
            from odoo.addons.pb_contract_lifecycle.models.contract_common import (
                P_EXTENSION_MONTHS, number)
            span = int(number(self.env, P_EXTENSION_MONTHS, 12))
        check = self.env['pb.contract.rule'].check_extension(
            self.contract_id, span)
        result = super().action_request_extension(reason=reason, months=months)
        if check.get('over'):
            text = ' '.join(check.get('lines') or [])
            self.message_post(body=_(
                "Asked to extend past the fixed-term rule (%(rule)s). %(why)s "
                "Reason given: %(reason)s",
                rule=check.get('rule') or '', why=text,
                reason=(reason or '').strip()))
            extension = self.env['pb.contract.extension'].sudo().browse(
                int((result or {}).get('extension_id') or 0)).exists()
            if extension:
                extension.message_post(body=_(
                    "This goes past the fixed-term rule (%(rule)s). %(why)s",
                    rule=check.get('rule') or '', why=text))
        return result

    def _build_new_contract(self, start, new_end, contract_type=None):
        # WDGAP S8-D: "Make it permanent" calls this with `contract_type`; the
        # S8-B signature dropped it and the conversion raised a TypeError.
        # Passed through unchanged; the fixed-term note is for an extension
        # (a contract WITH an end date) only.
        contract = super()._build_new_contract(start, new_end,
                                               contract_type=contract_type)
        if contract and self.contract_id and new_end:
            months = max(1, round((new_end - start).days / 30.4375)) \
                if (new_end and start) else 12
            check = self.env['pb.contract.rule'].check_extension(
                self.contract_id, months)
            if check.get('over'):
                try:
                    contract.sudo().message_post(body=_(
                        "This contract goes past the fixed-term rule "
                        "(%(rule)s): %(why)s",
                        rule=check.get('rule') or '',
                        why=' '.join(check.get('lines') or [])))
                except Exception:   # noqa: BLE001 — a note never undoes a contract
                    pass
        return contract


class PbContractExtensionRules(models.Model):
    _inherit = 'pb.contract.extension'

    def _pb_rule_check(self):
        self.ensure_one()
        contract = self.review_id.contract_id if self.review_id else False
        if not contract:
            return {'over': False}
        return self.env['pb.contract.rule'].check_extension(
            contract, self.months or 1)

    def _chain_facts(self):
        facts = super()._chain_facts()
        facts['past_fixed_term_rule'] = {
            'value': bool(self._pb_rule_check().get('over')), 'unit': ''}
        return facts

    @api.model
    def _chain_fact_specs(self):
        specs = super()._chain_fact_specs()
        specs['past_fixed_term_rule'] = {
            'type': 'bool', 'label': _('Goes past the fixed-term rule')}
        return specs

    def _approval_detail(self, request):
        detail = super()._approval_detail(request)
        check = self._pb_rule_check()
        if detail is not None and check.get('over'):
            detail = dict(detail)
            detail['chips'] = list(detail.get('chips') or []) + [
                {'label': _('Fixed-term rule'), 'value': _('Goes past it')}]
            note = detail.get('note') or ''
            detail['note'] = (' '.join(check.get('lines') or []) +
                              ('\n' + note if note else ''))[:480]
        return detail


class PbContractLifeRules(models.AbstractModel):
    _inherit = 'pb.contractlife'

    @api.model
    def get_contract(self, contract_id):
        answer = super().get_contract(contract_id)
        contract = self.env['hr.contract'].browse(int(contract_id)).exists()
        answer = dict(answer)
        answer['fixed_term'] = self._safe(
            lambda: self.env['pb.contract.rule'].summary(contract),
            default={}) if contract else {}
        answer['fixed_term_rules'] = bool(
            self.env.user.has_group('hr.group_hr_user'))
        return answer

    @api.model
    def open_fixed_term_rules(self):
        return self.env['ir.actions.act_window']._for_xml_id(
            'pb_contract_rules.action_pb_contract_rule')


class PbRecordsDeskFixedTerm(models.AbstractModel):
    _inherit = 'pb.records.desk'

    @api.model
    def _master_fields(self):
        fields_by_model = dict(super()._master_fields())
        employee = tuple(fields_by_model.get('hr.employee') or ())
        extra = tuple(f for f in ('pb_fixed_term_before',
                                  'pb_fixed_term_months_before')
                      if f not in employee)
        fields_by_model['hr.employee'] = employee + extra
        return fields_by_model
