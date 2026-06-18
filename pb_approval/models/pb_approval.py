# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

NET_CODES = ('NET', 'NETPAY', 'NETSALARY', 'NET1', 'NET2', 'THNHN', 'THUCNHAN', 'THCNHN', 'THTN')
NET_NAMES = ('thực nhận', 'net pay', 'net salary')

# run.state -> (advance method, stage label, role)
STAGE = {
    'level1': ('action_payslip_run_level1_done', 'HR review', 'HR Manager'),
    'level2': ('action_payslip_run_level2_done', 'GM approval', 'General Manager'),
}


class PbApproval(models.AbstractModel):
    _name = 'pb.approval'
    _description = 'Payobook Approval cockpit data'

    @api.model
    def _net(self, slip):
        try:
            hit = slip.line_ids.filtered(
                lambda l: (l.code or '').upper() in NET_CODES
                or any(n in (l.name or '').lower() for n in NET_NAMES))
            return sum(hit.mapped('total')) if hit else 0.0
        except Exception:
            return 0.0

    @api.model
    def _run_dict(self, run):
        slips = run.slip_ids
        net = sum(self._net(s) for s in slips)
        info = STAGE.get(run.state)
        return {
            'id': run.id, 'name': run.name,
            'period': '%s → %s' % (run.date_start, run.date_end) if run.date_start else '',
            'count': len(slips), 'net': net, 'state': run.state,
            'stage': info[1] if info else ('Done' if run.state == 'done' else run.state),
            'role': info[2] if info else '',
            'pending': bool(info),
        }

    @api.model
    def get_approvals(self):
        Run = self.env['hr.payslip.run']
        pending = Run.search([('state', 'in', ['level1', 'level2'])], order='id desc')
        recent = Run.search([('state', '=', 'done')], order='id desc', limit=6)
        pend = [self._run_dict(r) for r in pending]
        return {
            'pending': pend,
            'recent': [self._run_dict(r) for r in recent],
            'summary': {
                'count': len(pend),
                'net': sum(p['net'] for p in pend),
                'hr': len([p for p in pend if p['state'] == 'level1']),
                'gm': len([p for p in pend if p['state'] == 'level2']),
            },
        }

    @api.model
    def approve_run(self, run_id):
        run = self.env['hr.payslip.run'].browse(run_id)
        info = STAGE.get(run.state)
        if not info:
            return {'ok': False, 'state': run.state, 'msg': 'Nothing to approve'}
        try:
            getattr(run, info[0])()
        except Exception as e:
            _logger.warning("Approval cockpit: approve failed (%s): %s", run.state, e)
            return {'ok': False, 'state': run.state, 'msg': 'Action blocked'}
        return {'ok': True, 'state': run.state}
