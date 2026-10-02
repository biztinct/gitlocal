# -*- coding: utf-8 -*-
"""What the four money-out adapters all have to agree about.

THE PAY GATE. Every one of them carries out something that moves money — a
file the bank reads, a release, a journal entry, a payslip nobody has seen yet.
Safety rail 5 says the person who carries it out is the final approver and must
hold the Pay & Deliver role themselves: an approval is permission to make THIS
change, never a way to act through somebody else's rights. So `require_pay()`
is called inside every `_approval_apply`, and the sentence it raises names the
role and the way out.

WHERE A MONEY REQUEST BELONGS. The route is chosen on the pay run's own
(scheme, division) — the same keys Phase 3 gave the run — so a business that
sends Retail's pay runs to one desk sends Retail's bank files to the same desk
without configuring anything twice. Reading those keys means reading the pay
scheme and the employees' divisions, which is a fact about the ROUTE and not a
record the reader is being handed (ledger AM40), so it is read for the engine.

A SEAT IS ALSO A READ (ledger AM60). A bank signatory holds no payroll role at
all — the engine would give them a seat and the ORM would then refuse them the
record the seat is about. Every money-out record therefore carries a technical
`seat_user_ids` and one record-rule clause that reads it.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

#: The role that may move money. Same list the cockpit and the wizard use.
PAY_GROUPS = ('om_hr_payroll.group_hr_payroll_manager',
              'account.group_account_invoice', 'account.group_account_user')

#: Every model in this module whose approvers need a read on the record.
SEATED_MODELS = ('pb.bank.file', 'pb.payment.release', 'pb.payroll.journal',
                 'pb.payslip.delivery.batch')


class PbMoneyApprovalMixin(models.AbstractModel):
    """The half of the adapter contract the four money processes share."""
    _name = 'pb.money.approval.mixin'
    _description = 'Money-out approval helpers'

    # ------------------------------------------------------------- the gate
    @api.model
    def _pay_groups_held(self, user=None):
        user = user or self.env.user
        if user._is_admin():
            return True
        for group in PAY_GROUPS:
            try:
                if user.has_group(group):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    @api.model
    def require_pay(self, what=None):
        """Refuse, by name, anybody who may not move money."""
        if self._pay_groups_held():
            return True
        raise AccessError(_(
            "The final approver needs the Pay & Deliver role to carry this "
            "out%(what)s. Ask someone who has it to decide this step, or ask "
            "for the step to be moved to them.",
            what=(_(" (%s)", what) if what else '')))

    # ------------------------------------------------- where the route lives
    @api.model
    def scope_of_run(self, run):
        """(scope_keys, label) for a pay run — Phase 3's keys, reused.

        Read under sudo for the engine, never for the reader (AM40). A build
        without the pay-run cockpit has no such keys, and the company is then
        the only honest scope.
        """
        company = getattr(run, 'company_id', False) or self.env.company
        if not run or not hasattr(run, '_pb_review_groups'):
            return [''], company.name
        try:
            groups = run.sudo()._pb_review_groups()
        except Exception:       # noqa: BLE001 — a scope must never stop a send
            _logger.warning('pb_pay_delivery: could not read the scope of run '
                            '%s', getattr(run, 'id', 0))
            return [''], company.name
        if not groups:
            return [''], company.name
        group = groups[0]
        keys = run._pb_scope_keys(group['config'], group['division'])
        bits = [b for b in (group['config'].name if group['config'] else '',
                            group['division'].name if group['division'] else '')
                if b]
        label = ' · '.join(bits) or (group['company'] or company).name
        return keys, label

    @api.model
    def run_makers(self, run):
        """Everybody who prepared the money this request is about."""
        if not run:
            return []
        slips = run.sudo().slip_ids.filtered(lambda s: s.state != 'cancel')
        makers = set(slips.mapped('create_uid').ids)
        prepared = getattr(run.sudo(), 'pb_prepared_uid', False)
        if prepared:
            makers.add(prepared.id)
        return sorted(u for u in makers if u)

    @api.model
    def run_is_approved(self, run):
        """Has the pay run itself been signed off? (Phase 3's `done`.)"""
        if not run:
            return False
        return (run.state or '') == 'done'

    # ------------------------------------------------------- whose desk it is
    def _waiting_for(self):
        """Whose desk this record is on right now, in names.

        "Refused" without a name is a dead end; every refusal in this module
        ends with one.
        """
        self.ensure_one()
        request = self.approval_request_id
        if not request:
            return ''
        step = request.step_ids.filtered(
            lambda s: s.key == request.current_step_key)[:1]
        names = sorted({seat.acting_user_id.name or ''
                        for seat in step.seat_ids if seat.status == 'open'})
        return ', '.join(n for n in names if n)

    # --------------------------------------------------------- the audit row
    @api.model
    def audit(self, record, field_name, label, old_value, new_value):
        """One line in the platform-wide trail, for a change no mixin watches.

        `biz.audit.mixin` needs a `biz.audit.rule` row per model and watches
        FIELDS; what happened here — "this run was paid" — is a fact about a
        record the trail has no rule for, so the entry is written directly,
        which the mixin's own docstring allows.

        Never raises: money that really moved must not be un-moved by a trail
        line that could not be written.
        """
        Entry = self.env.get('biz.audit.entry')
        if Entry is None:
            return False
        try:
            company = record.company_id if 'company_id' in record._fields \
                else self.env.company
            Entry.sudo().create({
                'model_name': record._name,
                'res_id': record.id,
                'res_display': record.display_name or '',
                'field_name': field_name,
                'field_label': label,
                'old_value': '' if old_value is None else str(old_value)[:256],
                'new_value': '' if new_value is None else str(new_value)[:256],
                'company_id': (company or self.env.company).id,
            })
        except Exception:       # noqa: BLE001 — a trail must never block money
            _logger.exception('pb_pay_delivery: audit entry failed for %s',
                              record)
        return True


class BizApprovalRequestSeatMoney(models.Model):
    """A seat on a money request is also a permission to READ that record.

    Not a permission to do anything else: `seat_user_ids` feeds one record-rule
    clause and nothing else, and the engine still re-checks the seat, the
    account and the independence rule on every decision. Written on create, so
    a hand-over or a late reassignment — both of which create a NEW seat —
    carry the same read with them (ledger AM60).
    """
    _inherit = 'biz.approval.request.seat'

    @api.model_create_multi
    def create(self, vals_list):
        seats = super().create(vals_list)
        for seat in seats:
            request = seat.step_id.request_id
            model = request.res_model
            if model not in SEATED_MODELS or not request.res_id:
                continue
            record = self.env[model].sudo().browse(request.res_id).exists()
            if not record or 'seat_user_ids' not in record._fields:
                continue
            people = {seat.acting_user_id.id, seat.user_id.id}
            people.discard(False)
            if people:
                record.write({
                    'seat_user_ids': [(4, uid) for uid in sorted(people)]})
        return seats
