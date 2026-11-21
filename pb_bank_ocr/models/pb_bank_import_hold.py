# -*- coding: utf-8 -*-
"""WDGAP S6-A follow-up BK2 (owner ruling 2026-11-16 evening): bank details
that arrive by an IMPORT wait for one second person too.

The two older routes:
  * a pay data file (`hr.payroll.import.batch.action_process` — also what a
    connected system's records refresh runs): the bank-account columns
    (`_sync_employee_bank_account`) and any column mapped straight onto the
    four bank fields the bank file reads (`_update_employee_from_raw_data`);
  * the old Vietnam employee import (`vietnam.employee.import.wizard`).

WHAT HAPPENS NOW. While one of those runs, a "hold" is open for its database
cursor. Everything else the import loads is loaded exactly as before. A NEW
or CHANGED bank detail is written to NEITHER bank store: it becomes a waiting
bank change (`pb.bank.change.request`, started from "an import") that travels
the same one-second-person route as My Payobook and the Updates sheet —
never decided by the person who ran the import. Identical details create
nothing; re-importing the same file never makes a second waiting change. The
import's own log says "N bank changes are waiting for approval".

WHY A CURSOR-KEYED HOLD AND NOT A CONTEXT KEY. A context value travels into
everything the import calls (payslip computations, actions, JSON) and can be
sent by a browser; a module-level map keyed on the cursor is neither. Outside
an import nothing is held: direct calls (and every test that drives the
writeback seams one level down) behave as they always did.
"""

import contextlib
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.pb_hr_payroll_formula.models.bank_account_util import (
    acc_numbers_match, sanitize_bank_text,
)

from .pb_employee_bank_history import _BANK_AUDIT_TOKEN

_logger = logging.getLogger(__name__)

FILE_FIELDS = ('vietnam_bank_name', 'vietnam_bank_branch',
               'vietnam_bank_account_name', 'vietnam_bank_account_number')
OPEN_STATES = ('draft', 'hr_review', 'finance_review')
#: FS-16: the key a new hire's bank details travel under — one per person,
#: so a new hire is a single bank change, never a "batch" (batch notice).
NEWHIRE_KEY_PREFIX = 'pb.newhire,'

#: id(cursor) → Hold, while an import runs on that cursor.
_HOLDS = {}


class Hold:
    """One import run: where its waiting bank changes come from."""

    def __init__(self, key, label, proposer):
        self.key = key
        self.label = label
        self.proposer = proposer


@contextlib.contextmanager
def hold_scope(env, key, label, proposer):
    cid = id(env.cr)
    outer = _HOLDS.get(cid)
    _HOLDS[cid] = outer or Hold(key, label, proposer)
    try:
        yield _HOLDS[cid]
    finally:
        if outer is None:
            _HOLDS.pop(cid, None)


def active_hold(env):
    return _HOLDS.get(id(env.cr))


def _digits(text):
    return ''.join(ch for ch in str(text or '') if ch.isalnum()).upper()


class PbBankChangeRequestImport(models.Model):
    _inherit = 'pb.bank.change.request'

    pb_origin = fields.Selection(selection_add=[('import', 'An import')],
                                 ondelete={'import': 'set default'})
    pb_import_key = fields.Char(string='Import', readonly=True, copy=False,
                                index=True)
    pb_import_label = fields.Char(string='From the import', readonly=True,
                                  copy=False)

    @api.constrains('attachment_id', 'pb_origin')
    def _pb_check_document(self):
        for rec in self:
            if rec.pb_origin != 'import' and not rec.attachment_id:
                raise UserError(_("Upload the bank document first."))

    # ------------------------------------------------------- the hold itself
    @api.model
    def _pb_hold_from_import(self, employee, vals, hold):
        """Turn one person's incoming bank details into a waiting change.

        `vals` holds the x_* values the import wanted to write (blank = keep
        what is on record). Returns 'same' (nothing changes), 'waiting' (a
        change already waits with these details, or one was made now)."""
        employee = employee.sudo()
        cur = {
            'x_bank_name': employee.vietnam_bank_name or '',
            'x_bank_branch': employee.vietnam_bank_branch or '',
            'x_account_name': employee.vietnam_bank_account_name or '',
            'x_account_number': employee.vietnam_bank_account_number or '',
        }
        new = dict(cur)
        for key, value in vals.items():
            value = sanitize_bank_text(value) or ''
            if value:
                new[key] = value
        if not new['x_account_number']:
            return 'same'
        same_number = _digits(new['x_account_number']) == _digits(cur['x_account_number'])
        if same_number and all((new[k] or '').strip().lower() == (cur[k] or '').strip().lower()
                               for k in ('x_bank_name', 'x_bank_branch', 'x_account_name')):
            return 'same'
        Req = self.sudo()
        for open_req in Req.search([('employee_id', '=', employee.id),
                                    ('state', 'in', OPEN_STATES)]):
            if (_digits(open_req.x_account_number) == _digits(new['x_account_number'])
                    and (open_req.x_bank_name or '').strip().lower()
                    == (new['x_bank_name'] or '').strip().lower()
                    and (open_req.x_account_name or '').strip().lower()
                    == (new['x_account_name'] or '').strip().lower()):
                return 'waiting'           # never a second waiting change
        req = Req.create({
            'employee_id': employee.id,
            'company_id': employee.company_id.id,
            'pb_origin': 'import',
            'proposed_by_id': hold.proposer.id or self.env.uid,
            'pb_import_key': hold.key,
            'pb_import_label': hold.label,
            'ocr_state': 'done',
            'doc_kind': 'other',
            'x_bank_name': new['x_bank_name'] or False,
            'x_bank_branch': new['x_bank_branch'] or False,
            'x_account_name': new['x_account_name'] or False,
            'x_account_number': new['x_account_number'],
        })
        req.action_validate()
        try:
            with self.env.cr.savepoint():
                req.with_user(hold.proposer.id or self.env.uid).sudo().action_submit()
        except UserError as exc:
            # e.g. the number is somebody else's: it waits as a draft with the
            # reason, for HR to look at on the bank screen.
            req._sys_write({'pb_decision_note': exc.args[0] if exc.args else ''})
        return 'waiting'

    # ------------------------------------------------- FS-16: the new hire
    @api.model
    def _pb_hold_new_hire(self, employee, vals, proposer):
        """The bank details typed on People › Add employee, for the person
        just created: the same door as an import (a waiting change on the
        one-second-person route, never written straight), proposed by the
        person who typed them. `vals` holds x_* values. Returns the change
        (sudo) — waiting, or a draft with the reason when the route refused
        it (the number is somebody else's) — or an empty recordset when
        there was nothing to send."""
        employee = employee.sudo()
        key = '%s%s' % (NEWHIRE_KEY_PREFIX, employee.id)
        hold = Hold(key, _("New hire: %s", employee.name or ''), proposer)
        # made AS the proposer: the approval engine counts the record's
        # creator as one of the people who prepared it, and that must be the
        # person who typed the details — not whoever approved the hire.
        Req = self.with_user(proposer.id) if proposer else self
        Req._pb_hold_from_import(employee, vals, hold)
        return self.sudo().search([('pb_import_key', '=', key)],
                                  order='id desc', limit=1)

    @api.model
    def _pb_import_counts(self, key):
        Req = self.sudo()
        return {
            'waiting': Req.search_count([('pb_import_key', '=', key),
                                         ('state', 'in', ('hr_review', 'finance_review'))]),
            'check': Req.search_count([('pb_import_key', '=', key),
                                       ('state', '=', 'draft')]),
        }

    @api.model
    def _pb_import_sentence(self, key):
        counts = self._pb_import_counts(key)
        parts = []
        if counts['waiting']:
            parts.append(_("%s bank changes are waiting for approval. Nothing "
                           "changes where these people are paid until a second "
                           "person approves.", counts['waiting']))
        if counts['check']:
            parts.append(_("%s bank changes need HR to look at them first on the "
                           "bank screen.", counts['check']))
        return ' '.join(parts)

    # -------------------------------------------- approve all in this file
    @api.model
    def pb_approve_import(self, key):
        """The approver's one action for every waiting change from ONE import:
        each is approved as this user where they hold an open seat, and
        refused (left waiting) where they ran the import or are not asked."""
        Req = self.sudo()
        engine = self.env['biz.approval.engine']
        user = self.env.user
        done = mine = other = failed = 0
        for req in Req.search([('pb_import_key', '=', key),
                               ('state', 'in', ('hr_review', 'finance_review'))],
                              order='id'):
            if user in req._pb_never_decide():
                mine += 1
                continue
            request = req._chain_open_request()
            step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
            seat = step.seat_ids.filtered(
                lambda s: s.status == 'open' and s.acting_user_id == user)[:1]
            if not seat:
                other += 1
                continue
            try:
                with self.env.cr.savepoint():
                    engine.decide(request.id, step.key, 'approve')
                done += 1
            except Exception:              # noqa: BLE001 — counted, said in words
                _logger.info('pb_bank_ocr: approve-all could not approve %s',
                             req.name, exc_info=True)
                failed += 1
        parts = [_("%s approved.", done)]
        if mine:
            parts.append(_("%s left waiting: you ran this import, so somebody "
                           "else approves them.", mine))
        if other:
            parts.append(_("%s left waiting for somebody else.", other))
        if failed:
            parts.append(_("%s could not be approved; open them one by one.",
                           failed))
        return {'approved': done, 'yours': mine, 'others': other,
                'failed': failed, 'sentence': ' '.join(parts)}

    @api.model
    def _pb_import_groups(self):
        """Waiting changes from imports where this user holds an open seat,
        one row per import, for the bank screen's "Approve all" panel."""
        user = self.env.user
        groups = {}
        for req in self.sudo().search([('pb_origin', '=', 'import'),
                                       ('state', 'in', ('hr_review', 'finance_review'))]):
            request = req._chain_open_request()
            seats = request.step_ids.filtered(
                lambda s: s.status == 'active').seat_ids.filtered(
                lambda s: s.status == 'open' and s.acting_user_id == user)
            if not seats:
                continue
            row = groups.setdefault(req.pb_import_key, {
                'key': req.pb_import_key, 'label': req.pb_import_label or '',
                'count': 0})
            row['count'] += 1
        return sorted(groups.values(), key=lambda r: r['label'])


class HrEmployeeImportHold(models.Model):
    """Bank fields written by an import while a hold is open wait instead."""
    _inherit = 'hr.employee'

    def _pb_split_bank(self, vals):
        bank = {f: vals[f] for f in FILE_FIELDS if f in vals}
        rest = {k: v for k, v in vals.items() if k not in FILE_FIELDS}
        return bank, rest

    @staticmethod
    def _pb_x(bank):
        return {
            'x_bank_name': bank.get('vietnam_bank_name') or '',
            'x_bank_branch': bank.get('vietnam_bank_branch') or '',
            'x_account_name': bank.get('vietnam_bank_account_name') or '',
            'x_account_number': bank.get('vietnam_bank_account_number') or '',
        }

    def _pb_hold_applies(self):
        return (active_hold(self.env) is not None
                and self.env.context.get('from_bank_request') is not _BANK_AUDIT_TOKEN)

    def write(self, vals):
        if not self._pb_hold_applies() or not set(FILE_FIELDS).intersection(vals):
            return super().write(vals)
        hold = active_hold(self.env)
        bank, rest = self._pb_split_bank(vals)
        Req = self.env['pb.bank.change.request']
        for rec in self:
            changed = {f: v for f, v in bank.items()
                       if (rec.sudo()[f] or '') != (v or '')}
            if changed:
                Req._pb_hold_from_import(rec, self._pb_x(changed), hold)
        # Unchanged bank values stay in the write exactly as the import sent
        # them (a no-op), so an import with no bank change writes what it
        # always wrote.
        keep = {f: v for f, v in bank.items()
                if all((rec.sudo()[f] or '') == (v or '') for rec in self)}
        return super().write(dict(rest, **keep))

    @api.model_create_multi
    def create(self, vals_list):
        if not self._pb_hold_applies():
            return super().create(vals_list)
        hold = active_hold(self.env)
        held = []
        clean = []
        for vals in vals_list:
            bank, rest = self._pb_split_bank(vals)
            held.append({f: v for f, v in bank.items() if v})
            clean.append(rest)
        records = super().create(clean)
        Req = self.env['pb.bank.change.request']
        for rec, bank in zip(records, held):
            if bank:
                Req._pb_hold_from_import(rec, self._pb_x(bank), hold)
        return records


class HrPayrollImportBatchHold(models.Model):
    _inherit = 'hr.payroll.import.batch'

    pb_bank_waiting_note = fields.Char(
        string='Bank changes', compute='_compute_pb_bank_waiting_note')

    def _pb_hold_key(self):
        self.ensure_one()
        return 'hr.payroll.import.batch,%s' % self.id

    def _compute_pb_bank_waiting_note(self):
        Req = self.env['pb.bank.change.request']
        for rec in self:
            rec.pb_bank_waiting_note = Req._pb_import_sentence(
                rec._pb_hold_key()) if rec.id else ''

    def action_process(self):
        self.ensure_one()
        label = _("Pay data file %s", self.name or '')
        with hold_scope(self.env, self._pb_hold_key(), label,
                        self.create_uid or self.env.user):
            res = super().action_process()
        sentence = self.env['pb.bank.change.request']._pb_import_sentence(
            self._pb_hold_key())
        if sentence:
            self._log(sentence)
        return res

    def _sync_employee_bank_account(self, employee, raw_data, line=None):
        hold = active_hold(self.env)
        if hold is None or not employee:
            return super()._sync_employee_bank_account(employee, raw_data, line=line)
        bank_mappings = self._get_bank_mappings()
        if not bank_mappings:
            return super()._sync_employee_bank_account(employee, raw_data, line=line)
        # The same reading the original does (role by role, the declared
        # source order, no column letters), so what is compared is what would
        # have been written.
        values = {}
        for role, mapping in bank_mappings.items():
            raw, has_value = self._writeback_raw_value(
                raw_data, mapping.component_id, mapping=mapping, line=line,
                employee=employee, allow_column_letter=False)
            if has_value:
                values[role] = raw
        acc_number = self._sanitize_acc_number(values.get('acc_number'), line=line)
        if not acc_number:
            return super()._sync_employee_bank_account(employee, raw_data, line=line)
        bank_name = sanitize_bank_text(values.get('bank_name')) or ''
        holder = sanitize_bank_text(values.get('acc_holder_name')) or ''
        emp = employee.sudo()
        # Already on record — in the file store, or as one of the person's
        # accounts with the same bank and holder: nothing changes where pay
        # goes, so the import does exactly what it always did.
        if acc_numbers_match(emp.vietnam_bank_account_number or '', acc_number):
            known = True
        else:
            known = False
            for account in emp.bank_account_ids:
                if acc_numbers_match(account.acc_number, acc_number):
                    known = ((not bank_name or (account.bank_id.name or '').lower()
                              == bank_name.lower())
                             and (not holder or (account.acc_holder_name or '').lower()
                                  == holder.lower()))
                    break
        if known:
            return super()._sync_employee_bank_account(employee, raw_data, line=line)
        self.env['pb.bank.change.request']._pb_hold_from_import(employee, {
            'x_account_number': acc_number,
            'x_bank_name': bank_name,
            'x_account_name': holder,
        }, hold)
        return self.env['res.partner.bank']


class VietnamEmployeeImportHold(models.TransientModel):
    _inherit = 'vietnam.employee.import.wizard'

    def action_import_employees(self):
        self.ensure_one()
        key = 'vietnam.employee.import.wizard,%s' % self.id
        label = _("Employee import of %s", fields.Date.to_string(
            fields.Date.context_today(self)))
        with hold_scope(self.env, key, label, self.env.user):
            res = super().action_import_employees()
        sentence = self.env['pb.bank.change.request']._pb_import_sentence(key)
        if sentence:
            self.import_summary = '%s\n%s' % (self.import_summary or '', sentence)
        return res
