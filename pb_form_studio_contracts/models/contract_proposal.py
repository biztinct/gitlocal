# -*- coding: utf-8 -*-
"""What the approver reads when a custom contract field waits (R9).

The stock rows name a held term by `_TERM_WORDS` and fall back to the raw
key — an approver would read "x_pbfs_uniform_size · opt_1 · opt_2". Here a
custom field reads as its own label in the approver's language, with the old
and the new value in words. A field the approver may not see shows as a
hidden field, label and values withheld (handover ADDENDUM 1).

The re-read at approval time (`_live_snapshot`) uses the SAME shape the
snapshot was taken in (`snap_value`), so a link, a date or a file does not
look "changed by somebody else" when nobody touched it.
"""
from odoo import models, tools

from .hr_contract import is_custom, snap_value


class PbContractProposal(models.Model):
    _inherit = 'pb.contract.proposal'

    def _live_snapshot(self):
        snap = super()._live_snapshot()
        contract = self._contract()
        if contract is None:
            return snap
        for key in list(snap):
            if is_custom(key):
                snap[key] = snap_value(contract, key)
        return snap

    def _fs3_words(self, contract, field, value, proposed=False):
        _ = self.env._
        t = field.type
        if t == 'boolean':
            if isinstance(value, str):
                value = value.strip().lower() in ('1', 'true', 'yes', 'y')
            return _('Yes') if value else _('No')
        if value in (None, False, ''):
            return ''
        if t == 'binary':
            return _('A new file') if proposed else _('A file')
        if t == 'selection':
            return dict(field._description_selection(self.env)).get(value, str(value))
        if t == 'many2one':
            try:
                return self._row_label(field.comodel_name, int(value), '')
            except (TypeError, ValueError):
                return str(value)
        if t == 'date':
            try:
                return tools.format_date(self.env, value)
            except Exception:                           # noqa: BLE001
                return str(value)
        if t == 'monetary':
            try:
                return tools.format_amount(self.env, float(str(value).replace(',', '')),
                                           contract.currency_id or self.env.company.currency_id)
            except Exception:                           # noqa: BLE001
                return str(value)
        if t in ('integer', 'float'):
            try:
                number = float(str(value).replace(',', ''))
            except ValueError:
                return str(value)
            return '{:,}'.format(int(number)) if number == int(number) else '{:,}'.format(number)
        return str(value)

    def _proposal_rows(self):
        rows = super()._proposal_rows()
        contract = self._contract()
        if contract is None:
            return rows
        terms = (self.payload() or {}).get('terms') or {}
        if not any(is_custom(k) for k in terms):
            return rows
        snapshot = self.snapshot() or {}
        Contract = self.env['hr.contract']
        out = []
        for row in rows:
            label = row[0] if row else ''
            if not is_custom(label) or label not in terms:
                out.append(row)
                continue
            field = Contract._fields.get(label)
            if field is None:
                out.append((self.env._('A field that has since been deleted'), '', ''))
                continue
            if not Contract._has_field_access(field, 'read'):
                out.append((self.env._('A field you cannot see'), '', ''))
                continue
            words = field.get_description(self.env, ['string']).get('string') or label
            out.append((words,
                        self._fs3_words(contract, field, snapshot.get(label)),
                        self._fs3_words(contract, field, terms.get(label), proposed=True)))
        return out
