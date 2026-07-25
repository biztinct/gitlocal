# -*- coding: utf-8 -*-
"""Approvals cockpit — RPC facade over the hr.payslip.run approval chain.

Read-and-act facade (C18.55a): it never writes a state field itself. Every
decision rides hr.payslip.run's OWN gated action as the real clicking user, so
the model-side tier gate (``_pb_require_tier``, pb_payruns) is the single
authority — this facade's ``_require_access`` is defence in depth, not the
guard.

Phase L: the chain is 3-tier — level0 (Payroll Officer) → level1 (HR Manager) →
level2 (Finance / GM) → done. State KEYS are frozen downstream contracts
('done' is the approved signal for pay delivery and analytics); only the cockpit
LABELS changed.
"""
import logging

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

NET_CODES = ('NET', 'NETPAY', 'NETSALARY', 'NET1', 'NET2', 'THNHN', 'THUCNHAN', 'THCNHN', 'THTN')
NET_NAMES = ('thực nhận', 'net pay', 'net salary')

# run.state -> advance method. Ordered: the index doubles as the chain stepper
# position on the cockpit cards.
STAGE = {
    'level0': 'action_payslip_run_level0_done',
    'level1': 'action_payslip_run_level1_done',
    'level2': 'action_payslip_run_level2_done',
}
STAGE_ORDER = ('level0', 'level1', 'level2')

# Any of these may OPEN the cockpit; what each may DO is decided per tier by the
# model (C18.17 — one permission world, the facade gate is only the front door).
_APPROVAL_GROUPS = (
    'pb_hr_payroll_base.group_payroll_base_officer',
    'pb_hr_payroll_base.group_payroll_base_manager',
    'pb_hr_payroll_base.group_payroll_final_approver',
    'pb_hr_payroll_base.group_payroll_super_admin',
    'pb_demo.group_payobook_demo',
)


class PbApproval(models.AbstractModel):
    _name = 'pb.approval'
    _description = 'Payobook Approval cockpit data'

    # ------------------------------------------------------------- access
    @api.model
    def _require_access(self):
        """First line of every public method (the cockpit is not group-gatable
        on the client action itself — C18.9)."""
        user = self.env.user
        if user._is_admin():
            return
        for g in _APPROVAL_GROUPS:
            try:
                if user.has_group(g):
                    return
            except (ValueError, KeyError):
                continue
        raise AccessError(_(
            "You are not allowed to open Approvals. This requires a Payroll "
            "Officer, Payroll Manager or Final Approver role."))

    # ------------------------------------------------------------- labels
    @api.model
    def _stage_labels(self):
        """state -> (lane/stage label, role name). Built per call so the
        translation of the ACTIVE user's language is used."""
        return {
            'level0': (_('Officer review'), _('Payroll Officer')),
            'level1': (_('HR review'), _('HR Manager')),
            'level2': (_('Finance approval'), _('Finance / GM')),
        }

    # ------------------------------------------------------------- payload
    @api.model
    def _run_dict(self, run, labels=None):
        # Reads the STORED totals on hr.payslip.run (instant) — no line aggregation.
        labels = labels if labels is not None else self._stage_labels()
        info = labels.get(run.state)
        idx = STAGE_ORDER.index(run.state) if run.state in STAGE_ORDER else -1
        return {
            'id': run.id, 'name': run.name,
            'period': '%s → %s' % (run.date_start, run.date_end) if run.date_start else '',
            'count': run.pb_employee_count if 'pb_employee_count' in run._fields else 0,
            'net': run.pb_total_net if 'pb_total_net' in run._fields else 0.0,
            'state': run.state,
            'stage': info[0] if info else (
                _('Rejected') if run.state == 'cancel'
                else _('Done') if run.state == 'done' else run.state),
            'role': info[1] if info else '',
            'pending': bool(info),
            # chain stepper: how many of the 3 tiers this run has cleared
            'step': idx if idx >= 0 else (len(STAGE_ORDER) if run.state == 'done' else 0),
            # actionable BY ME? drives the card's Approve/Reject vs "waits on…"
            'mine': bool(info) and run._pb_tier_ok(run.state),
            'reject_note': run.pb_reject_note or '',
            'reject_by': run.pb_reject_uid.name or '',
        }

    @api.model
    def get_approvals(self):
        self._require_access()
        Run = self.env['hr.payslip.run']
        labels = self._stage_labels()
        # hr.payslip.run has no company_id (C18.43) — never filter by company.
        pending = Run.search([('state', 'in', list(STAGE_ORDER))], order='id desc')
        recent = Run.search([('state', 'in', ['done', 'cancel'])], order='id desc', limit=6)
        pend = [self._run_dict(r, labels) for r in pending]
        lanes = [{'key': s, 'label': labels[s][0], 'role': labels[s][1],
                  'runs': [p for p in pend if p['state'] == s]}
                 for s in STAGE_ORDER]
        return {
            'lanes': lanes,
            'pending': pend,
            'recent': [self._run_dict(r, labels) for r in recent],
            'summary': {
                'count': len(pend),
                'net': sum(p['net'] for p in pend),
                'mine': len([p for p in pend if p['mine']]),
                'officer': len([p for p in pend if p['state'] == 'level0']),
                'hr': len([p for p in pend if p['state'] == 'level1']),
                'fin': len([p for p in pend if p['state'] == 'level2']),
            },
        }

    # ------------------------------------------------------------- actions
    @api.model
    def _decide(self, run_id, method, ctx=None):
        """Run one gated model action on one run and translate the outcome.

        The savepoint matters: the legacy level1 advance writes the state and
        THEN builds the GM notification, which can raise (missing analytics /
        no approver email). Without it, a caught failure would leave the state
        change committed while we reported ok=False.
        """
        run = self.env['hr.payslip.run'].browse(int(run_id))
        if not run.exists():
            return {'ok': False, 'state': False, 'msg': _('This pay run no longer exists.')}
        try:
            with self.env.cr.savepoint():
                getattr(run.with_context(**(ctx or {})), method)()
        except (AccessError, UserError) as e:
            # the model's OWN words — never a generic "Action blocked"
            self.env.invalidate_all()
            return {'ok': False, 'state': run.state, 'msg': str(e)}
        except Exception as e:
            _logger.warning("Approval cockpit: %s failed on run %s: %s", method, run_id, e)
            self.env.invalidate_all()
            return {'ok': False, 'state': run.state, 'msg': str(e) or _('Action failed.')}
        return {'ok': True, 'state': run.state}

    @api.model
    def approve_run(self, run_id):
        self._require_access()
        run = self.env['hr.payslip.run'].browse(int(run_id))
        if not run.exists():
            return {'ok': False, 'state': False, 'msg': _('This pay run no longer exists.')}
        method = STAGE.get(run.state)
        if not method:
            return {'ok': False, 'state': run.state,
                    'msg': _('This pay run is not awaiting approval.')}
        return self._decide(run_id, method)

    @api.model
    def reject_run(self, run_id, note):
        self._require_access()
        note = (note or '').strip()
        if not note:
            return {'ok': False, 'state': False,
                    'msg': _('Please give a reason for rejecting this pay run.')}
        return self._decide(run_id, 'action_payslip_run_cancel',
                            ctx={'pb_reject_note': note})
