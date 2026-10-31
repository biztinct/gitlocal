# Part of Payobook. See LICENSE file for full copyright and licensing details.

import logging
import time
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class PayrollReport(models.TransientModel):
    """Backend API for the Rippling-style Payroll Report Dashboard."""
    _name = 'hr.payroll.report.api'
    _description = 'Payroll Report API'

    @staticmethod
    def _sum_category(lines, codes):
        """Total the lines in these rule categories, skipping subtotals."""
        return sum(l.total for l in lines
                   if l.category_id and (l.category_id.code or '').upper() in codes
                   and l.pb_counts_in_totals())

    @staticmethod
    def _breakdown(lines, prev_lines, signed=False):
        """One row per component, with the previous period's figure beside it.

        NO EARLIER PAYSLIP IS NOT A CHANGE OF ZERO. Where there is nothing to
        compare against, the difference is left at zero so the screen shows a
        dash — subtracting an absent figure said everybody's pay had just gone
        up by the whole of it.
        """
        rows = []
        for line in lines:
            if not line.total:
                continue
            prev = prev_lines.filtered(
                lambda x: x.salary_rule_id.id == line.salary_rule_id.id)
            prev_val = prev[0].total if prev else 0.0
            current = line.total if signed else abs(line.total)
            previous = prev_val if signed else abs(prev_val)
            rows.append({
                'name': line.name,
                'code': line.code,
                'current': current,
                'previous': previous,
                'diff': (current - previous) if prev_lines else 0.0,
            })
        return rows

    @api.model
    def get_batch_report(self, batch_id):
        """
        Employee-level payroll data for a specific batch run,
        with comparison to the previous batch.
        """
        batch = self.env['hr.payslip.run'].browse(batch_id)
        if not batch.exists():
            return {'error': _('Batch not found')}

        # Find previous batch (same structure/company, earlier date)
        prev_batch = self.env['hr.payslip.run'].search([
            ('id', '!=', batch.id),
            ('date_end', '<', batch.date_start),
            ('state', '!=', 'cancel'),
        ], order='date_end desc', limit=1)

        # Current batch payslips
        current_slips = batch.slip_ids.filtered(lambda s: s.state != 'cancel')
        prev_slips = prev_batch.slip_ids.filtered(lambda s: s.state != 'cancel') if prev_batch else self.env['hr.payslip']

        # Build employee rows
        employees = []
        dept_totals = {}  # dept_name -> {gross, net, deductions, employer_cost, count}

        for slip in current_slips:
            emp = slip.employee_id
            # Get previous slip for comparison
            prev_slip = prev_slips.filtered(lambda s: s.employee_id.id == emp.id)
            row = self._slip_row(slip, prev_slip[:1])
            dept = row['department']
            dept_totals.setdefault(dept, {'gross': 0, 'net': 0, 'deductions': 0, 'count': 0})
            dept_totals[dept]['gross'] += row['gross']
            dept_totals[dept]['net'] += row['net']
            # Already totalled as magnitudes, so no outer abs() here: one at
            # the end cannot put back what opposite signs cancelled on the way.
            dept_totals[dept]['deductions'] += row['deductions']
            dept_totals[dept]['count'] += 1
            employees.append(row)

        # Sort by name
        employees.sort(key=lambda e: e['name'])

        dept_chart = self._dept_chart(dept_totals)
        total_gross = sum(d['gross'] for d in dept_totals.values())
        total_net = sum(d['net'] for d in dept_totals.values())
        total_deductions = sum(d['deductions'] for d in dept_totals.values())

        return {
            'batch': self._batch_payload(batch),
            'prev_batch': {
                'id': prev_batch.id if prev_batch else False,
                'name': prev_batch.name if prev_batch else '',
            },
            'employees': employees,
            'dept_chart': dept_chart,
            'summary': {
                'total_employees': len(employees),
                'total_gross': total_gross,
                'total_net': total_net,
                'total_deductions': total_deductions,
                'changes': sum(1 for e in employees if e['events']),
            },
        }

    @api.model
    def _batch_payload(self, batch):
        return {
            'id': batch.id,
            'name': batch.name,
            'date_start': batch.date_start.isoformat() if batch.date_start else '',
            'date_end': batch.date_end.isoformat() if batch.date_end else '',
            'state': batch.state,
        }

    @api.model
    def _dept_chart(self, dept_totals):
        """Department chart rows from {name: {gross, net, deductions, count}}."""
        dept_chart = []
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22', '#34495e']
        for i, (dept, data) in enumerate(sorted(dept_totals.items())):
            dept_chart.append({
                'name': dept,
                'net': data['net'],
                'gross': data['gross'],
                'deductions': data['deductions'],
                'count': data['count'],
                'color': colors[i % len(colors)],
            })
        return dept_chart

    @api.model
    def _slip_row(self, slip, prev_slip):
        """One person's row: this run's figures beside their previous payslip.

        Shared by :meth:`get_batch_report` (the whole run) and the paged list
        the filter panel shows (FILTER wave 8), so the two can never disagree.
        `prev_slip` is that person's payslip in the previous run, or empty.
        """
        emp = slip.employee_id
        lines = slip.line_ids

        # Which band each line belongs in is the scheme's own answer, read
        # through the shared helper so this screen can never disagree with
        # the pay run it was opened from. Reading the rule category here
        # instead reported ₫0 gross and ₫10,747,123,945 deductions against
        # a run of ₫2,060,124,305 and ₫289,886,044.
        totals = lines.pb_pay_totals()
        gross = totals['gross']
        net = totals['net']
        deductions = totals['deductions']
        # Basic and Allowances are columns of their own, not bands of net
        # pay, so they stay on the rule category — but only over the lines
        # the totals above already count, so a subtotal is never added on
        # top of the components it is a subtotal of.
        basic = self._sum_category(lines, ('BASIC',))
        allowances = self._sum_category(lines, ('ALW', 'ALLOWANCE'))

        prev_gross = prev_net = prev_deductions = prev_basic = 0
        if prev_slip:
            prev_lines = prev_slip[0].line_ids
            prev_totals = prev_lines.pb_pay_totals()
            prev_gross = prev_totals['gross']
            prev_net = prev_totals['net']
            prev_deductions = prev_totals['deductions']
            prev_basic = self._sum_category(prev_lines, ('BASIC',))

        # Detect changes (related events)
        events = []
        if gross != prev_gross and prev_gross:
            diff = gross - prev_gross
            if abs(diff) > 0:
                amount = '{:,.0f}'.format(abs(diff))
                events.append(_("Gross pay increased by %s", amount)
                              if diff > 0 else
                              _("Gross pay decreased by %s", amount))
        if basic != prev_basic and prev_basic:
            diff = basic - prev_basic
            if abs(diff) > 0:
                events.append(_("Basic salary changed by %s",
                                '{:+,.0f}'.format(diff)))

        # Earnings and deductions breakdowns. Both list exactly the lines
        # the figures above are made of — a breakdown that does not add up
        # to the number it sits under is worse than no breakdown.
        prev_line_ids = prev_slip[0].line_ids if prev_slip \
            else self.env['hr.payslip.line']
        earnings = self._breakdown(
            lines.pb_lines_in_band('gross'), prev_line_ids, signed=True)
        deduction_lines = self._breakdown(
            lines.pb_lines_in_band('deductions'), prev_line_ids)

        dept = emp.department_id.name if emp.department_id else _('Unassigned')
        return {
            'id': emp.id,
            'slip_id': slip.id,
            'name': emp.name,
            'job_title': emp.job_title or '',
            'department': dept,
            'avatar_url': f'/web/image/hr.employee/{emp.id}/avatar_128',
            'gross': gross,
            'net': net,
            'deductions': deductions,
            'basic': basic,
            'allowances': allowances,
            'prev_gross': prev_gross,
            'prev_net': prev_net,
            'prev_deductions': prev_deductions,
            # A dash, not a rise, where this person has no earlier payslip
            # to be compared with — see :meth:`_breakdown`.
            'diff_gross': (gross - prev_gross) if prev_slip else 0.0,
            'diff_net': (net - prev_net) if prev_slip else 0.0,
            'events': events,
            'earnings': earnings,
            'deduction_lines': deduction_lines,
        }

    @api.model
    def _prev_batch(self, batch):
        """The run this one is compared with (same rule as get_batch_report:
        the latest run that ended before this one started, whatever its
        scheme — pre-existing, noted as a debt in FILTER wave 8)."""
        return self.env['hr.payslip.run'].search([
            ('id', '!=', batch.id),
            ('date_end', '<', batch.date_start),
            ('state', '!=', 'cancel'),
        ], order='date_end desc', limit=1)

    @api.model
    def get_all_batches(self):
        """Return list of batches for dropdown selection."""
        batches = self.env['hr.payslip.run'].search(
            [('state', '!=', 'cancel')],
            order='date_end desc', limit=24,
        )
        return [{
            'id': b.id,
            'name': b.name,
            'date_start': b.date_start.isoformat() if b.date_start else '',
            'date_end': b.date_end.isoformat() if b.date_end else '',
            'state': b.state,
            'count': len(b.slip_ids),
        } for b in batches]


#: Rows per page of the filtered list (FILTER wave 8). A 4,500-slip run used
#: to load whole; each row reads two payslips' lines, so the page stays short.
REPORT_PAGE = 60


class PbPayrollReport(models.AbstractModel):
    """The Payroll Report's list on the shared filter panel (FILTER wave 8).

    One run at a time: the browser passes the run as `pbf_ctx.run_id` and
    reconfigures the panel when another run is picked. The list is the run's
    payslips, paged; the totals and the department summary are worked out on
    the server over the WHOLE filtered set (never added up from a page).

    "Pay changed" is the same comparison the rows have always shown (gross or
    basic moved against the person's payslip in the previous run), worked out
    once per request for the whole run in SQL — the same bands as the pay
    run's own totals — and kept on the cursor for the rest of the request
    (F18/F25): the panel counts every option and every view.
    """
    _name = 'pb.payroll.report'
    _description = 'Payroll Report list'
    _inherit = ['pb.filter.mixin']

    # ------------------------------------------------------------ the run
    @api.model
    def _run(self):
        try:
            rid = int(self._pbf_ctx().get('run_id') or 0)
        except (TypeError, ValueError):
            rid = 0
        Run = self.env['hr.payslip.run']
        return Run.browse(rid).exists() if rid else Run

    def _pbf_model(self):
        return 'hr.payslip'

    def _pbf_screen(self):
        # one key for every run: a view saved on May opens on June too
        return 'payreport'

    def _pbf_base_domain(self):
        run = self._run()
        if not run:
            return [('id', '=', 0)]
        return [('payslip_run_id', '=', run.id), ('state', '!=', 'cancel')]

    def _pbf_search_fields(self):
        # what the old search box looked in: name, job title, department
        return ['employee_id.name', 'employee_id.job_title',
                'employee_id.department_id.name', 'number']

    def _pbf_sorts(self):
        return [
            {'key': 'name', 'label': _('Name, A to Z'), 'order': 'employee_id, id'},
            {'key': 'name_desc', 'label': _('Name, Z to A'), 'order': 'employee_id desc, id desc'},
            {'key': 'number', 'label': _('Payslip number'), 'order': 'number, id'},
        ]

    def _pbf_spec(self):
        run = self._run()
        start = fields.Date.to_string(run.date_start) if run and run.date_start else False
        spec = [
            {'key': 'department', 'label': _('Department'), 'icon': 'building',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id.department_id',
             'pinned': True, 'none_label': _('No department')},
            {'key': 'changed', 'label': _('Against the last run'), 'icon': 'trendingUp',
             'group': 'pay', 'type': 'choice', 'pinned': True,
             'help': _('Pay changed: gross pay or basic salary moved against the '
                       'same person in the previous run.'),
             'options': [
                 {'value': 'changed', 'label': _('Pay changed'), 'tone': 'amber',
                  'domain_method': '_pbf_dm_changed'},
                 {'value': 'same', 'label': _('Same as last run'), 'tone': 'slate',
                  'domain_method': '_pbf_dm_same'},
                 {'value': 'first', 'label': _('Nothing to compare with'), 'tone': 'blue',
                  'domain_method': '_pbf_dm_first'},
             ]},
            {'key': 'job', 'label': _('Job position'), 'icon': 'briefcase',
             'group': 'work', 'type': 'many2one', 'path': 'contract_id.job_id',
             'pinned': True, 'none_label': _('No job position')},
            {'key': 'structure', 'label': _('Pay structure'), 'icon': 'sigma',
             'group': 'pay', 'type': 'many2one', 'path': 'struct_id',
             'none_label': _('No pay structure')},
            {'key': 'status', 'label': _('Payslip status'), 'icon': 'fileText',
             'group': 'pay', 'type': 'selection', 'path': 'state'},
            {'key': 'manager', 'label': _('Manager'), 'icon': 'userCheck',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id.parent_id',
             'none_label': _('No manager')},
            {'key': 'company', 'label': _('Company'), 'icon': 'landmark',
             'group': 'work', 'type': 'many2one', 'path': 'company_id'},
        ]
        if start:
            spec.append(
                {'key': 'newjoiner', 'label': _('Joined'), 'icon': 'userPlus',
                 'group': 'dates', 'type': 'choice',
                 'requires': ['employee_id.first_contract_date'],
                 'options': [
                     {'value': 'new', 'label': _('Joined in this run'), 'tone': 'green',
                      'domain': [('employee_id.first_contract_date', '>=', start)]},
                     {'value': 'before', 'label': _('Joined before this run'), 'tone': 'slate',
                      'domain': ['|', ('employee_id.first_contract_date', '<', start),
                                 ('employee_id.first_contract_date', '=', False)]},
                 ]})
        return spec

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('Everyone in this run'), 'icon': 'users', 'filters': {}},
            {'key': 'changed', 'label': _('Pay changed'), 'filters': {'changed': ['changed']}},
            {'key': 'new', 'label': _('New joiners this run'), 'filters': {'newjoiner': ['new']}},
        ]

    # ---------------------------------------------------- the money facts
    @api.model
    def _slip_money(self, slip_ids):
        """{slip id: {'gross', 'net', 'deductions', 'basic'}} for these payslips.

        The pay run's own rule (`hr.payslip.run._compute_pb_totals`, kept in
        step with `hr.payslip.line.pb_pay_totals` by pb_payruns' tests), per
        payslip, in one query; basic is `_sum_category(…, BASIC)` over the
        same counted lines. Without pb_payruns there is no SQL twin of the
        bands, so the ORM helper is used per payslip instead.
        """
        out = {}
        if not slip_ids:
            return out
        Run = self.env['hr.payslip.run']
        Line = self.env['hr.payslip.line']
        api_ = self.env['hr.payroll.report.api']
        if not hasattr(Run, '_pb_bucket_sql'):
            for slip in self.env['hr.payslip'].browse(slip_ids):
                totals = slip.line_ids.pb_pay_totals()
                out[slip.id] = {'gross': totals['gross'], 'net': totals['net'],
                                'deductions': totals['deductions'],
                                'basic': api_._sum_category(slip.line_ids, ('BASIC',))}
            return out
        from odoo.addons.pb_payruns.models.payslip_money import uses_signed_deductions
        role_aware = 'pay_role' in Line._fields
        detail_aware = 'component_detail' in Line._fields
        columns = ['slip_id', 'category_id', 'total']
        if role_aware:
            columns.append('pay_role')
        if detail_aware:
            columns.append('component_detail')
        Line.flush_model(columns)
        self.env['hr.salary.rule.category'].flush_model(['code'])
        bucket = Run._pb_bucket_sql(role_aware)
        net_clause = ("pl.pay_role = 'net' OR c.code = 'NET'"
                      if role_aware else "c.code = 'NET'")
        detail_clause = ("AND ((" + net_clause + ") OR pl.component_detail IS NOT TRUE)"
                         if detail_aware else "")
        explicit = "COALESCE(pl.pay_role = 'deduction', FALSE)" if role_aware else 'FALSE'
        self.env.cr.execute("""
            SELECT pl.slip_id, """ + bucket + """ AS bucket,
                   COALESCE(SUM(CASE WHEN """ + bucket + """ IN ('DED', 'DEDUCTION', 'COMP', 'ERCOST')
                                     THEN ABS(pl.total) ELSE pl.total END), 0),
                   COALESCE(SUM(pl.total), 0),
                   BOOL_AND(""" + explicit + """),
                   COALESCE(SUM(CASE WHEN UPPER(c.code) = 'BASIC' THEN pl.total ELSE 0 END), 0)
            FROM hr_payslip_line pl
            LEFT JOIN hr_salary_rule_category c ON c.id = pl.category_id
            WHERE pl.slip_id IN %s
              AND """ + bucket + """ IS NOT NULL
              """ + detail_clause + """
            GROUP BY pl.slip_id, 2
        """, (tuple(slip_ids),))
        per_slip = {}
        for sid, code, magnitude, signed, expl, basic in self.env.cr.fetchall():
            per_slip.setdefault(sid, {})[code] = (float(magnitude or 0.0), float(signed or 0.0),
                                                  expl, float(basic or 0.0))
        for sid in slip_ids:
            bands = per_slip.get(sid, {})
            mag = lambda b: bands[b][0] if b in bands else 0.0  # noqa: E731
            gross = mag('GROSS') or (mag('BASIC') + mag('ALW'))
            net = mag('NET')
            ded = [bands[b] for b in ('DED', 'DEDUCTION', 'COMP') if b in bands]
            apply_signed = uses_signed_deductions(
                gross, net, sum(b[1] for b in ded), sum(b[0] for b in ded),
                bool(ded) and all(b[2] for b in ded),
                any(b in bands for b in ('GROSS', 'BASIC', 'ALW')), 'NET' in bands)
            deductions = sum((b[1] if apply_signed else b[0]) for b in ded)
            out[sid] = {'gross': gross, 'net': net, 'deductions': deductions,
                        'basic': sum(v[3] for v in bands.values())}
        return out

    @api.model
    def _facts(self):
        """Everything about the picked run the panel asks more than once,
        worked out once per request: each payslip's money, its match in the
        previous run, and which ones changed."""
        run = self._run()
        key = ('pb.payroll.report:facts', run.id, self.env.uid,
               tuple(self.env.companies.ids))
        cache = self.env.cr.cache
        if key in cache:
            return cache[key]
        started = time.time()
        Slip = self.env['hr.payslip']
        facts = {'money': {}, 'prev_of': {}, 'changed': set(), 'same': set(),
                 'first': set(), 'prev_run': False, 'ms': 0}
        if run:
            cur = Slip.search([('payslip_run_id', '=', run.id), ('state', '!=', 'cancel')])
            prev_run = self.env['hr.payroll.report.api']._prev_batch(run)
            prev = Slip.search([('payslip_run_id', '=', prev_run.id),
                                ('state', '!=', 'cancel')]) if prev_run else Slip
            # the first of a person's payslips in the previous run, in the
            # model's own order — exactly what `filtered(...)[0]` picked
            prev_by_emp = {}
            for row in prev.read(['employee_id'], load=False) if prev else []:
                prev_by_emp.setdefault(row['employee_id'], row['id'])
            money = self._slip_money(cur.ids + prev.ids)
            for row in cur.read(['employee_id'], load=False):
                sid = row['id']
                pid = prev_by_emp.get(row['employee_id'])
                if not pid:
                    facts['first'].add(sid)
                    continue
                facts['prev_of'][sid] = pid
                c, p = money.get(sid, {}), money.get(pid, {})
                # the rows' own rule (`_slip_row` events), to the cent
                moved = any(
                    p.get(k) and round((c.get(k) or 0.0) - p[k], 2) != 0
                    for k in ('gross', 'basic'))
                facts['changed' if moved else 'same'].add(sid)
            facts.update(money=money, prev_run=prev_run.id if prev_run else False)
        facts['ms'] = int((time.time() - started) * 1000)
        _logger.info("Payroll Report: pay-change facts for run %s in %s ms",
                     run.id if run else '-', facts['ms'])
        cache[key] = facts
        return facts

    def _pbf_dm_changed(self):
        return [('id', 'in', sorted(self._facts()['changed']) or [0])]

    def _pbf_dm_same(self):
        return [('id', 'in', sorted(self._facts()['same']) or [0])]

    def _pbf_dm_first(self):
        return [('id', 'in', sorted(self._facts()['first']) or [0])]

    # ------------------------------------------------------------ the page
    @api.model
    def get_report_page(self, filters=None, search=None, sort=None, offset=0,
                        limit=REPORT_PAGE, with_summary=True):
        """One page of the run's payslips for the panel's state, plus — on the
        first page — the totals and the department summary of EVERY payslip
        the filters match."""
        started = time.time()
        run = self._run()
        api_ = self.env['hr.payroll.report.api']
        empty_summary = {'total_employees': 0, 'total_gross': 0.0, 'total_net': 0.0,
                         'total_deductions': 0.0, 'changes': 0}
        if not run:
            return {'rows': [], 'total': 0, 'offset': 0, 'summary': empty_summary,
                    'dept_chart': [], 'batch': {}, 'prev_batch': {}}
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or REPORT_PAGE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, REPORT_PAGE
        Slip = self.env['hr.payslip']
        domain = self.pbf_domain(filters or {}, search)
        slips = Slip.search(domain, order=self.pbf_order(sort) or 'employee_id, id',
                            offset=offset, limit=limit)
        facts = self._facts()
        prev_ids = [facts['prev_of'].get(s.id) for s in slips]
        prevs = Slip.browse([p for p in prev_ids if p])
        prev_map = {p.id: p for p in prevs}
        # read every line of the page's payslips (and their matches) at once
        (slips | prevs).mapped('line_ids').mapped('category_id')
        rows = []
        for slip, pid in zip(slips, prev_ids):
            row = api_._slip_row(slip, prev_map.get(pid, Slip))
            row['changed'] = slip.id in facts['changed']
            rows.append(row)
        out = {'rows': rows, 'offset': offset,
               'total': Slip.search_count(domain)}
        if with_summary and not offset:
            out.update(self._summary(domain, facts))
            prev_run = self.env['hr.payslip.run'].browse(facts['prev_run']) \
                if facts['prev_run'] else self.env['hr.payslip.run']
            out['batch'] = api_._batch_payload(run)
            out['prev_batch'] = {'id': prev_run.id if prev_run else False,
                                 'name': prev_run.name if prev_run else ''}
        out['ms'] = int((time.time() - started) * 1000)
        out['facts_ms'] = facts['ms']
        return out

    @api.model
    def _summary(self, domain, facts):
        """Totals and the department summary over every matching payslip."""
        Slip = self.env['hr.payslip']
        api_ = self.env['hr.payroll.report.api']
        money = facts['money']
        dept_totals = {}
        n = changes = 0
        gross = net = deductions = 0.0
        zero = {'gross': 0.0, 'net': 0.0, 'deductions': 0.0}
        # one grouped query: the matching payslips' ids per department (the
        # person's department, as the rows show it); the money comes from the
        # facts already worked out for this request
        for dept_rec, ids in Slip._read_group(domain, ['employee_id.department_id'], ['id:array_agg']):
            dept = dept_rec.name if dept_rec else _('Unassigned')
            d = dept_totals.setdefault(dept, {'gross': 0, 'net': 0, 'deductions': 0, 'count': 0})
            for sid in ids:
                m = money.get(sid) or zero
                d['gross'] += m['gross']
                d['net'] += m['net']
                d['deductions'] += m['deductions']
                d['count'] += 1
                gross += m['gross']
                net += m['net']
                deductions += m['deductions']
                n += 1
                if sid in facts['changed']:
                    changes += 1
        return {
            'summary': {'total_employees': n, 'total_gross': gross, 'total_net': net,
                        'total_deductions': deductions, 'changes': changes},
            'dept_chart': api_._dept_chart(dept_totals),
        }


class HrPayslipRunPayrollReport(models.Model):
    """Extend payslip run to add Payroll Report button."""
    _inherit = 'hr.payslip.run'

    def action_open_payroll_report(self):
        """Open the Rippling-style Payroll Report for this batch."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'payroll_report_dashboard',
            'name': f'Payroll Report — {self.name}',
            'context': {'batch_id': self.id},
        }

