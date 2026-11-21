# -*- coding: utf-8 -*-
"""INBOX-BULK-BANK — "N of them are in another person's name" on the extra
check in front of Approve selected.

The approvals inbox (`pb.approval.inbox._bulk_confirm_notes`) does not know
bank accounts, so it leaves this count empty; this bridge fills it with the
ONE name test the payment list and the side panel's notice use
(`pb.payment.list._pb_name_band` → 'other', ruling BL4), applied to the
account each waiting change PROPOSES:

* a bank change (`pb.bank.change.request`: the Updates sheet, an import, My
  Payobook, the staff bank screen) — its proposed holder name against the
  employee's name;
* a Records desk change (`pb.records.apply`) — every proposed "account
  holder" value against the name of the person it is for.

A READ: counts only (never a name or a number leaves this method), nothing
is written, and a change that cannot be read is simply not counted.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class PbApprovalInboxOtherName(models.AbstractModel):
    _inherit = 'pb.approval.inbox'

    @api.model
    def _bulk_confirm_notes(self, requests):
        notes = super()._bulk_confirm_notes(requests)
        if 'pb.payment.list' not in self.env:
            return notes
        count = 0
        for request in requests:
            record = self._record_of(request)
            if record is None:
                continue
            try:
                if self._pb_proposes_other_name(record):
                    count += 1
            except Exception as exc:  # noqa: BLE001 — a count, never a blocker
                _logger.debug('Other-name count: request %s skipped: %s',
                              request.id, exc)
        notes['other_name'] = count
        return notes

    @api.model
    def _pb_proposes_other_name(self, record):
        band = self.env['pb.payment.list']._pb_name_band
        record = record.sudo()
        if record._name == 'pb.bank.change.request':
            employee = record.employee_id
            holder = (record.x_account_name or '').strip() or str(
                getattr(employee, 'vietnam_bank_account_name', '') or ''
            ).strip()
            if not employee or not holder:
                return False
            return band(holder, employee.name or '') == 'other'
        if record._name == 'pb.records.apply' and hasattr(record, 'plan'):
            for row in record.plan() or []:
                if not isinstance(row, dict) \
                        or row.get('field_id') != 'b:acc_holder_name':
                    continue
                holder = str(row.get('new_label') or '').strip()
                name = str(row.get('emp_name') or '').strip()
                if holder and name and band(holder, name) == 'other':
                    return True
        return False
