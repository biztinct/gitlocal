# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

PALETTE = ["#6D28D9", "#0EA5E9", "#059669", "#DB2777", "#F59E0B", "#4F46E5", "#EF4444",
           "#0891B2", "#7C3AED", "#16A34A"]

# state -> (advance method, label of the action that moves it forward)
NEXT = {
    'draft':  ('action_payslip_done', 'Submit for HR review'),
    'level1': ('action_payslip_level1_done', 'HR approve → GM'),
    'level2': ('action_payslip_level2_done', 'GM approve → Done'),
}


class PbPayslipReview(models.AbstractModel):
    _name = 'pb.payslip.review'
    _description = 'Payobook Payslip Review cockpit data'

    NET_CODES = ('NET', 'NETPAY', 'NETSALARY', 'NETWAGE', 'NET1', 'NET2', 'THNHN',
                 'THUCNHAN', 'THCNHN', 'THTN')
    GROSS_CODES = ('GROSS', 'GROSSSALARY', 'TONGTHUNHAP', 'TNGTHUNHP', 'TONG', 'TOTAL')

    @api.model
    def _match(self, slip, codes, names):
        """Sum line totals whose code or name matches; None if nothing matched."""
        try:
            hit = slip.line_ids.filtered(lambda l: (l.code or '').upper() in codes
                                         or any(n in (l.name or '').lower() for n in names))
            return sum(hit.mapped('total')) if hit else None
        except Exception:
            return None

    @api.model
    def _net(self, slip):
        return self._match(slip, self.NET_CODES, ('thực nhận', 'net pay', 'net salary'))

    @api.model
    def _gross(self, slip):
        return self._match(slip, self.GROSS_CODES, ('tổng thu nhập', 'gross'))

    @api.model
    def _active_company_ids(self):
        return self.env.companies.ids or [self.env.company.id]

    @api.model
    def _company_run_ids(self):
        """Run ids that have at least one payslip in the ACTIVE companies — so the
        cockpit never opens a run from a company the user isn't currently in
        (hr.payslip.run has no company_id; we scope through the payslips)."""
        self.env.cr.execute("""
            SELECT DISTINCT payslip_run_id FROM hr_payslip
            WHERE company_id IN %s AND payslip_run_id IS NOT NULL
        """, (tuple(self._active_company_ids()),))
        return [r[0] for r in self.env.cr.fetchall()]

    @api.model
    def get_runs(self):
        runs = self.env['hr.payslip.run'].search(
            [('id', 'in', self._company_run_ids())], order='id desc', limit=20)
        return [{'id': r.id, 'name': r.name} for r in runs]

    @api.model
    def _slip_totals(self, slip_ids):
        """{slip_id: {'net': x|None, 'gross': y|None}} via SQL — avoids loading
        every slip's lines into Python (tens of thousands of rows per run)."""
        res = {sid: {'net': None, 'gross': None} for sid in slip_ids}
        if not slip_ids:
            return res
        self.env.cr.execute("""
            SELECT pl.slip_id, c.code, COALESCE(SUM(pl.total), 0)
            FROM hr_payslip_line pl
            JOIN hr_salary_rule_category c ON c.id = pl.category_id
            WHERE pl.slip_id IN %s AND c.code IN ('NET', 'GROSS')
            GROUP BY pl.slip_id, c.code
        """, (tuple(slip_ids),))
        for sid, code, total in self.env.cr.fetchall():
            res[sid]['net' if code == 'NET' else 'gross'] = total or 0.0
        return res

    @api.model
    def _default_run(self):
        """Most recent ACTIVE-company run with positive take-home — uses the stored,
        indexed pb_total_net, scoped to runs that have payslips in active companies."""
        Run = self.env['hr.payslip.run']
        run_ids = self._company_run_ids()
        if not run_ids:
            return Run.browse()
        run = Run.search([('id', 'in', run_ids), ('pb_total_net', '>', 0)],
                         order='id desc', limit=1)
        return run or Run.search([('id', 'in', run_ids)], order='id desc', limit=1)

    @api.model
    def get_review_data(self, run_id=None):
        Run = self.env['hr.payslip.run']
        run = Run.browse(run_id) if run_id else self._default_run()
        if not run:
            return {'run': None, 'runs': self.get_runs(), 'slips': [], 'totals': {}}

        # Only payslips in the active companies — never touch a record the user's
        # current company context can't read (avoids multi-company access errors).
        cids = self._active_company_ids()
        slip_recs = run.slip_ids.filtered(lambda s: s.company_id.id in cids)
        totals = self._slip_totals(slip_recs.ids)
        slips, t_net, t_gross, n_net, n_gross = [], 0.0, 0.0, 0, 0
        for i, s in enumerate(slip_recs):
            tt = totals.get(s.id, {})
            net, gross = tt.get('net'), tt.get('gross')
            if net is not None:
                t_net += net
                n_net += 1
            if gross is not None:
                t_gross += gross
                n_gross += 1
            slips.append({
                'id': s.id, 'emp': s.employee_id.name or '—',
                'title': s.contract_id.job_id.name if s.contract_id and s.contract_id.job_id else (s.struct_id.name or ''),
                'net': net, 'gross': gross, 'state': s.state,
                'flag': (net is not None and net <= 0), 'color': PALETTE[i % len(PALETTE)],
            })
        return {
            'run': {'id': run.id, 'name': run.name, 'state': run.state,
                    'period': '%s → %s' % (run.date_start, run.date_end) if run.date_start else ''},
            'runs': self.get_runs(),
            'slips': slips,
            'totals': {'count': len(slips),
                       'net': t_net if n_net else None,
                       'gross': t_gross if n_gross else None,
                       'done': len([x for x in slips if x['state'] == 'done']),
                       'flagged': len([x for x in slips if x['flag']])},
        }

    @api.model
    def get_slip_detail(self, slip_id):
        s = self.env['hr.payslip'].browse(slip_id)
        lines = []
        for l in s.line_ids:
            # Multilingual: prefer the translatable salary-rule label (resolves to the
            # reader's language) over the frozen line snapshot.
            label = (l.salary_rule_id.name if l.salary_rule_id else False) or l.name or l.code
            lines.append({'name': label, 'code': l.code or '',
                          'total': l.total or 0.0})
        return {
            'id': s.id, 'emp': s.employee_id.name, 'state': s.state,
            'structure': s.struct_id.name or '', 'period': '%s → %s' % (s.date_from, s.date_to),
            'net': self._net(s), 'gross': self._gross(s),
            'lines': lines,
            'color': PALETTE[(slip_id or 0) % len(PALETTE)],
        }

    @api.model
    def advance_state(self, slip_id):
        s = self.env['hr.payslip'].browse(slip_id)
        st = s.state
        info = NEXT.get(st)
        if info:
            method, _label = info
            try:
                getattr(s, method)()
            except Exception as e:
                _logger.warning("Payslip review advance failed (%s): %s", st, e)
                return {'ok': False, 'state': s.state, 'msg': 'Action blocked'}
        return {'ok': True, 'state': s.state}
