# -*- coding: utf-8 -*-
"""FS-9 — the Bank block on the employee side panel (Pay & tax tab).

WHAT WAS TRUE BEFORE. The side panel's "Bank" group
(`pb_employee_vault/models/employee_details.py` `_SPEC`, key ``bank``) read
the old free-text Bank and Account Number boxes on the employee
(`pb_hr_payroll_formula` `bank_name` / `account_number`) plus the Vietnamese
bank file's four fields, in full. Nothing pays from the old boxes; on rize and
sudima nobody had filled them while 194 / 642 people had an approved account,
so the panel said "Bank —" for everybody.

WHAT IS TRUE NOW. That group is replaced (from outside, `_e360_details`
override — no edit of the vault) by one block built from the SAME rules every
other bank reader uses — nothing new is decided here:

* "is there an approved account" = `hr.employee.pb_bank_on_record`, the helper
  Payroll-ready reads (`pb_employee_form_tidy`), and WHICH account =
  `_pb_bank_on_record_facts` beside it (first bank account, else the
  Vietnamese bank file's account) — the account number leaves the server as
  its last four digits only;
* "is a change waiting" = `pb.payment.list._pb_waiting_changes`, the payment
  list's own rule (a bank change in review, one held from an import, or a
  pending Updates / Records proposal that touches bank details);
* "in another person's name" = `hr.employee._pb_other_name_facts`, the BL4
  flag, and "Mark as seen" is BL4's own `pb_other_name_mark_seen` (who and
  when kept, one trail line) — no second seen-mechanism.

WHO. The side panel's own gate (`_vault_is_hr`: HR, the payroll team,
administrators) — the people who saw the panel's bank rows before. The block
is in the panel payload only for them, and `pb_bank_panel` (the refresh
after "Mark as seen") refuses anybody else.
"""

import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

#: the side panel's group key this block replaces
BANK_GROUP = 'bank'
#: what the panel's client draws as the Bank block
KIND = 'pb_bank'
#: a change still open in the bank-document check (draft only when it came
#: from an import — the payment list's rule, `_pb_waiting_changes`)
REQ_OPEN = ('hr_review', 'finance_review')
APPROVAL_OPEN = ('pending', 'blocked')


def _masked(last4):
    return ('•••• ' + last4) if last4 else '••••'


class PbPeopleBankPanel(models.AbstractModel):
    _inherit = 'pb.people'

    # ------------------------------------------------------------ the tab
    @api.model
    def _e360_details(self, emp, unmask, vietnam=None):
        tabs = super()._e360_details(emp, unmask, vietnam=vietnam)
        pay = list(tabs.get('pay') or [])
        at = next((i for i, g in enumerate(pay) if g.get('key') == BANK_GROUP), None)
        # The old group goes whatever happens next: it read the old box.
        pay = [g for g in pay if g.get('key') != BANK_GROUP]
        group = None
        if self._vault_is_hr():
            try:
                group = self._pb_bank_group(self._pb_bank_block(emp))
            except Exception:                           # noqa: BLE001
                # a bank block must never cost anybody the side panel
                _logger.warning('Side panel: the bank block could not be built for '
                                'employee %s', emp.id, exc_info=True)
        if group:
            if at is None:
                at = next((i + 1 for i, g in enumerate(pay) if g.get('key') == 'setup'), 0)
            pay.insert(min(at, len(pay)), group)
        tabs['pay'] = pay
        return tabs

    @api.model
    def _pb_bank_group(self, block):
        """The block as a panel group. `rows` are what the panel's generic
        renderer would draw (and what the Form builder's screen rule walks);
        the client draws `pb_bank` instead."""
        _ = self.env._
        rows = [
            {'key': 'pb_bank_status', 'label': _('Status'), 'value': block['status_label'],
             'empty': False},
            {'key': 'pb_bank_name', 'label': _('Bank'), 'value': block['bank'] or None,
             'empty': not block['bank']},
            {'key': 'pb_bank_holder', 'label': _('Account holder'),
             'value': block['holder'] or None, 'empty': not block['holder']},
            {'key': 'pb_bank_number', 'label': _('Account number'),
             'value': block['masked'] or None, 'empty': not block['masked']},
        ]
        return {
            'key': BANK_GROUP, 'kind': KIND, 'title': _('Bank'), 'icon': 'creditCard',
            'rows': rows, 'filled': sum(1 for r in rows if not r['empty']),
            'pb_bank': block,
        }

    # ------------------------------------------------------------ the block
    @api.model
    def _pb_bank_block(self, emp):
        """Everything the Bank block shows for one person. Never the whole
        account number (last four digits only)."""
        _ = self.env._
        emp.ensure_one()
        facts = emp._pb_bank_on_record_facts()
        waiting = self._pb_bank_waiting(emp)
        if facts['on_record']:
            status, label = 'approved', _('Approved')
        elif waiting:
            status, label = 'waiting', _('Waiting for approval')
        else:
            status, label = 'none', _('None')
        return {
            'status': status,
            'status_label': label,
            'store': facts['store'],
            'bank': facts['bank'] if facts['on_record'] else '',
            'holder': facts['holder'] if facts['on_record'] else '',
            'last4': facts['last4'] if facts['on_record'] else '',
            'masked': _masked(facts['last4']) if facts['on_record'] else '',
            'vn_file_masked': _masked(facts['vn_file_last4']) if facts['vn_file_last4'] else '',
            'waiting': waiting,
            'other_name': self._pb_bank_other_name(emp) if facts['store'] == 'account' else None,
            'can_add': self._pb_bank_checks_open(),
        }

    @api.model
    def _pb_bank_waiting(self, emp):
        """None, or the change still waiting for approval: how many, the new
        account's last four digits when the change names one, and where to
        open it (for this reader)."""
        found = (self.env['pb.payment.list']._pb_waiting_changes(emp) or {}).get(emp.id) or []
        if not found:
            return None
        new_last4 = ''
        for item in found:
            digits = (item or {}).get('number') or ''
            if len(digits) > 4:
                new_last4 = digits[-4:]
                break
        return {
            'count': len(found),
            'new_masked': _masked(new_last4) if new_last4 else '',
            'link': self._pb_bank_waiting_link(emp),
        }

    @api.model
    def _pb_bank_waiting_targets(self, emp):
        """(model, id) of the records behind the waiting change, newest first
        — only to find a door to them; whether a change IS waiting is the
        payment list's rule above."""
        out = []
        Req = self.env.get('pb.bank.change.request')
        if Req is not None:
            Req = Req.sudo().with_context(active_test=False)
            domain = [('employee_id', '=', emp.id)]
            if 'pb_origin' in Req._fields:
                domain += ['|', ('state', 'in', REQ_OPEN),
                           '&', ('state', '=', 'draft'), ('pb_origin', '=', 'import')]
            else:
                domain += [('state', 'in', REQ_OPEN)]
            out += [(Req._name, r.id) for r in Req.search(domain, order='id desc')]
        Apply = self.env.get('pb.records.apply')
        if Apply is not None and 'touches_bank' in Apply._fields:
            for proposal in Apply.sudo().search([('state', '=', 'pending'),
                                                 ('touches_bank', '=', True)],
                                                order='id desc'):
                try:
                    rows = json.loads(proposal.plan_json or '[]')
                except (TypeError, ValueError):
                    continue
                if any(isinstance(r, dict) and r.get('emp_id') == emp.id
                       and str(r.get('field_id') or '')[:2] == 'b:'
                       for r in (rows if isinstance(rows, list) else [])):
                    out.append((Apply._name, proposal.id))
        return out

    @api.model
    def _pb_bank_waiting_link(self, emp):
        """The Approvals inbox on the request (when this reader may read it),
        else the bank checks screen for a bank-document change (when this
        reader works there), else nothing."""
        targets = self._pb_bank_waiting_targets(emp)
        AR = self.env.get('biz.approval.request')
        if AR is not None:
            for model, rid in targets:
                ar = AR.sudo().search([('res_model', '=', model), ('res_id', '=', rid),
                                       ('state', 'in', APPROVAL_OPEN)],
                                      order='id desc', limit=1)
                if ar and ar.with_user(self.env.user).has_access('read'):
                    return {'kind': 'inbox', 'focus': 'request:%d' % ar.id}
        if any(m == 'pb.bank.change.request' for m, _i in targets) \
                and self._pb_bank_checks_open():
            return {'kind': 'bank_checks'}
        return None

    @api.model
    def _pb_bank_checks_open(self):
        """The bank checks screen (bank change requests) shows the HR queue to
        the payroll team (`pb.bank.ocr._is_hr`)."""
        Cockpit = self.env.get('pb.bank.ocr')
        if Cockpit is None or not self.env.ref('pb_bank_ocr.action_pb_bank_ocr',
                                               raise_if_not_found=False):
            return False
        try:
            return bool(Cockpit._is_hr())
        except Exception:                               # noqa: BLE001
            return False

    @api.model
    def _pb_bank_other_name(self, emp):
        """BL4's flag on the approved account, as the block shows it."""
        Emp = self.env['hr.employee']
        if not hasattr(Emp, '_pb_other_name_facts'):
            return None
        show, holder, _key = emp._pb_other_name_facts()
        if not holder:
            return None
        sudo = emp.sudo()
        try:
            Emp._pb_other_name_gate()
            can_mark = True
        except Exception:                               # noqa: BLE001
            can_mark = False
        return {
            'show': bool(show),
            'holder': holder,
            'seen_by': '' if show else (sudo.pb_other_name_seen_by.name or ''),
            'seen_on': '' if show else (fields.Date.to_string(
                fields.Datetime.context_timestamp(self, sudo.pb_other_name_seen_on))
                if sudo.pb_other_name_seen_on else ''),
            'can_mark': can_mark and bool(show),
        }

    # ------------------------------------------------------------ the call
    @api.model
    def pb_bank_panel(self, employee_id):
        """The Bank block alone — the side panel re-reads it after "Mark as
        seen". Same gate as the panel."""
        self._require_hr()
        emp = self._emp(employee_id or 0)
        if not emp:
            return {'error': self.env._("Employee not found.")}
        emp.check_access('read')
        return self._pb_bank_block(emp)
