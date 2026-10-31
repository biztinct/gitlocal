# -*- coding: utf-8 -*-
import logging
import time

from odoo import _, api, models

_logger = logging.getLogger(__name__)

PALETTE = ["#6D28D9", "#0EA5E9", "#059669", "#DB2777", "#F59E0B", "#4F46E5", "#EF4444",
           "#0891B2", "#7C3AED", "#16A34A"]

# A PAYSLIP IN A PAY RUN IS NOT APPROVED ON ITS OWN ANY MORE.
#
# This cockpit used to walk one payslip up a ladder of its own — Submit, HR
# approve, GM approve — beside the run's ladder, and the two had nothing to do
# with each other. The bank export pays every payslip in state `done`, so that
# was a way to get one person's money out of a run nobody had sent in.
#
# The run is the unit of approval. What is left here is reviewing: reading the
# numbers, comparing them, and flagging what looks wrong. The model refuses the
# rest, in its own words, and this map is empty so the screen never offers a
# button the server will not honour.
NEXT = {}

#: Payslips per page on the filter panel's list (FILTER wave 5).
PAGE_SIZE = 60
#: "Needs review" answers kept per worker between the panel's calls.
FLAG_TTL = 120
FLAG_CACHE_MAX = 24
_FLAG_CACHE = {}
#: The three steps a live payslip can be at, and the status option of each.
#: "Waiting for approval" is one step over three stored words: a payslip
#: written before the run's approval replaced the slip ladder still says
#: level1 or level2, and it is waiting for exactly the same thing.
STEP_STATES = (
    ('draft', ('draft',)),
    ('waiting', ('verify', 'level1', 'level2')),
    ('done', ('done',)),
)


class PbPayslipReview(models.AbstractModel):
    _name = 'pb.payslip.review'
    _inherit = ['pb.filter.mixin']
    _description = 'Payobook Payslip Review cockpit data'

    # ============================================================ filter panel
    # FILTER wave 5. The list is ONE pay run's payslips: the run picker above
    # the panel stays the screen's scope control and rides on every kit call
    # as `pbf_ctx.run_id`. The filters do not carry the run, so a saved view
    # ("Need review in Sales") works on every run — one screen key for all.

    def _pbf_model(self):
        return 'hr.payslip'

    def _pbf_screen(self):
        return 'payslips'

    @api.model
    def _pbf_run(self):
        """The run the panel is scoped to: the picker's, else the default."""
        Run = self.env['hr.payslip.run']
        rid = self._pbf_ctx().get('run_id')
        try:
            rid = int(rid) if rid else 0
        except (TypeError, ValueError):
            rid = 0
        run = Run.browse(rid).exists() if rid else Run.browse()
        return run or self._default_run()

    def _pbf_base_domain(self):
        run = self._pbf_run()
        if not run:
            return [('id', '=', 0)]
        # Only payslips in the active companies — the same rule as before.
        return [('payslip_run_id', '=', run.id),
                ('company_id', 'in', self._active_company_ids())]

    def _pbf_search_fields(self):
        return ['employee_id.name', 'number', 'employee_id.barcode']

    def _pbf_layout_extra(self):
        run = self._pbf_run()
        return {'run_id': run.id if run else False}

    def _pbf_sorts(self):
        return [
            {'key': 'name', 'label': _('Name, A to Z'), 'order': 'employee_id asc, id asc'},
            {'key': 'name_desc', 'label': _('Name, Z to A'), 'order': 'employee_id desc, id desc'},
            {'key': 'number', 'label': _('Payslip number'), 'order': 'number asc, id asc'},
            {'key': 'newest', 'label': _('Newest payslips first'), 'order': 'id desc'},
        ]

    def _pbf_spec(self):
        Slip = self.env['hr.payslip']
        spec = [
            # ---- pinned: the three questions asked of every run
            {'key': 'status', 'label': _('Where it is'), 'icon': 'activity', 'group': 'pay',
             'type': 'choice', 'pinned': True,
             'options': [
                 {'value': 'draft', 'label': _('Draft'), 'tone': 'slate',
                  'domain': [('state', '=', 'draft')]},
                 {'value': 'waiting', 'label': _('Waiting for approval'), 'tone': 'amber',
                  'domain': [('state', 'in', ('verify', 'level1', 'level2'))]},
                 {'value': 'done', 'label': _('Done'), 'tone': 'green',
                  'domain': [('state', '=', 'done')]},
                 {'value': 'cancel', 'label': _('Rejected'), 'tone': 'rose',
                  'domain': [('state', '=', 'cancel')]},
             ]},
            {'key': 'review', 'label': _('Review'), 'icon': 'alert', 'group': 'pay',
             'type': 'choice', 'pinned': True,
             'help': _('Needs review: take-home pay at zero or below, or a big change '
                       'on the same person\'s previous payslip.'),
             'options': [
                 {'value': 'flag', 'label': _('Needs review'), 'tone': 'amber',
                  'domain_method': '_pbf_flagged_domain'},
                 {'value': 'ok', 'label': _('Looks fine'), 'tone': 'green',
                  'domain_method': '_pbf_unflagged_domain'},
             ]},
            {'key': 'department', 'label': _('Department'), 'icon': 'building', 'group': 'people',
             'type': 'many2one', 'path': 'employee_id.department_id', 'pinned': True,
             'none_label': _('No department')},
            # ---- more filters
            {'key': 'job', 'label': _('Job position'), 'icon': 'briefcase', 'group': 'people',
             'type': 'many2one', 'path': 'contract_id.job_id', 'none_label': _('No job position')},
            {'key': 'structure', 'label': _('Pay structure'), 'icon': 'sigma', 'group': 'pay',
             'type': 'many2one', 'path': 'struct_id', 'none_label': _('No pay structure')},
            {'key': 'scheme', 'label': _('Payroll scheme'), 'icon': 'layers', 'group': 'pay',
             'type': 'many2one', 'path': 'formula_config_id', 'label_sudo': True,
             'none_label': _('No scheme')},
            {'key': 'company', 'label': _('Company'), 'icon': 'landmark', 'group': 'work',
             'type': 'many2one', 'path': 'company_id'},
            {'key': 'refund', 'label': _('Refunds'), 'icon': 'undo', 'group': 'pay',
             'type': 'choice', 'requires': ['credit_note'],
             'options': [
                 {'value': 'yes', 'label': _('Refunds'), 'tone': 'rose',
                  'domain': [('credit_note', '=', True)]},
                 {'value': 'no', 'label': _('Regular payslips'), 'tone': 'slate',
                  'domain': [('credit_note', '=', False)]},
             ]},
            {'key': 'period', 'label': _('Period ends'), 'icon': 'calendar', 'group': 'dates',
             'type': 'date', 'path': 'date_to', 'presets': 'past'},
        ]
        # "Paid" is the bank's answer (pb_pay_delivery stamps the payslip when
        # its money left), not the payroll state; absent without that module.
        if 'pb_paid' in Slip._fields:
            spec.insert(-1, {
                'key': 'paid', 'label': _('Paid'), 'icon': 'banknote', 'group': 'pay',
                'type': 'choice', 'requires': ['pb_paid'],
                'options': [
                    {'value': 'yes', 'label': _('Paid'), 'tone': 'green',
                     'domain': [('pb_paid', '=', True)]},
                    {'value': 'no', 'label': _('Not paid yet'), 'tone': 'slate',
                     'domain': [('pb_paid', '=', False)]},
                ]})
        return spec

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All in this run'), 'icon': 'receipt', 'filters': {}},
            {'key': 'review', 'label': _('Need review'), 'filters': {'review': ['flag']}},
            {'key': 'waiting', 'label': _('Waiting for approval'), 'filters': {'status': ['waiting']}},
            {'key': 'done', 'label': _('Done'), 'filters': {'status': ['done']}},
            {'key': 'refunds', 'label': _('Refunds'), 'filters': {'refund': ['yes']}},
        ]

    # ---- "Needs review": a Python fact (review_flags.py), one query per run.
    # The kit asks for it once per count and once per view (F18/F25), so it is
    # worked out ONCE per request and kept on the cursor.
    @api.model
    def _pbf_run_flags(self, run=None):
        """{slip_id: flag dict} for the scoped run's active-company payslips."""
        run = run or self._pbf_run()
        if not run:
            return {}
        cids = tuple(sorted(self._active_company_ids()))
        key = ('pb_payslip_review.flags', run.id, self.env.uid, cids)
        cache = self.env.cr.cache
        if key not in cache:
            slip_ids = self.env['hr.payslip'].search(
                [('payslip_run_id', '=', run.id), ('company_id', 'in', list(cids))]).ids
            cache[key] = self._pbf_flags_across_requests(run, slip_ids) if slip_ids else {}
        return cache[key]

    @api.model
    def _pbf_flags_across_requests(self, run, slip_ids):
        """`pb_review_flags` is one query, but on a 1,000-payslip run it takes
        ~2.5 s, and the panel asks three times per filter change (layout,
        counts, page). Kept in this worker for FLAG_TTL seconds, keyed by the
        run's payslips as they are now (how many, last written) and the
        threshold, so a recompute or a new threshold is seen at once; the TTL
        bounds what the key cannot see (the previous month's payslips)."""
        Slip = self.env['hr.payslip']
        Slip.flush_model(['payslip_run_id', 'write_date'])
        self.env.cr.execute(
            "SELECT COUNT(*), MAX(write_date) FROM hr_payslip WHERE id IN %s",
            (tuple(slip_ids),))
        n, last = self.env.cr.fetchone()
        threshold = run.pb_review_change_pct()
        key = (self.env.cr.dbname, run.id, self.env.lang or '', n, str(last), threshold,
               tuple(sorted(slip_ids))[:1], tuple(sorted(slip_ids))[-1:])
        now = time.time()
        hit = _FLAG_CACHE.get(key)
        if hit and now - hit[0] < FLAG_TTL:
            return hit[1]
        flags = run.sudo().pb_review_flags(slip_ids)
        if len(_FLAG_CACHE) >= FLAG_CACHE_MAX:
            for k in sorted(_FLAG_CACHE, key=lambda k: _FLAG_CACHE[k][0])[:FLAG_CACHE_MAX // 2]:
                _FLAG_CACHE.pop(k, None)
        _FLAG_CACHE[key] = (now, flags)
        return flags

    @api.model
    def _pbf_flagged_ids(self):
        return [sid for sid, fl in self._pbf_run_flags().items() if (fl or {}).get('flag')]

    @api.model
    def _pbf_flagged_domain(self):
        return [('id', 'in', self._pbf_flagged_ids() or [0])]

    @api.model
    def _pbf_unflagged_domain(self):
        ids = self._pbf_flagged_ids()
        return [('id', 'not in', ids)] if ids else []

    # ---- the screen's own calls
    @api.model
    def get_review_head(self, run_id=None):
        """The run, the picker and the numbers line — over the whole run,
        whatever is filtered (the panel loads the list itself)."""
        Run = self.env['hr.payslip.run']
        run = Run.browse(int(run_id)).exists() if run_id else self._default_run()
        if not run:
            return {'run': None, 'runs': self.get_runs(), 'totals': {}}
        cids = self._active_company_ids()
        slips = self.env['hr.payslip'].search(
            [('payslip_run_id', '=', run.id), ('company_id', 'in', cids)])
        flags = self._pbf_run_flags(run)
        totals = self._slip_totals(slips.ids)
        t_net = t_gross = 0.0
        n_net = n_gross = 0
        for s in slips:
            net = (flags.get(s.id) or {}).get('net')
            gross = totals.get(s.id, {}).get('gross')
            if net is not None:
                t_net += net
                n_net += 1
            if gross is not None:
                t_gross += gross
                n_gross += 1
        return {
            'run': {'id': run.id, 'name': run.name, 'state': run.state,
                    'period': '%s → %s' % (run.date_start, run.date_end) if run.date_start else ''},
            'runs': self.get_runs(),
            'totals': {'count': len(slips),
                       'net': t_net if n_net else None,
                       'gross': t_gross if n_gross else None,
                       'done': len(slips.filtered(lambda x: x.state == 'done')),
                       'flagged': len([1 for fl in flags.values() if (fl or {}).get('flag')])},
        }

    @api.model
    def get_slip_page(self, filters=None, search=None, sort=None, offset=0, limit=PAGE_SIZE):
        """One page of the run's payslips for the panel's current state, plus
        the step strip's counts: each step counted against every OTHER filter
        (the panel's own rule, ruling R1), with how many there need review."""
        Slip = self.env['hr.payslip']
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        filters = filters if isinstance(filters, dict) else {}
        domain = self.pbf_domain(filters, search)
        recs = Slip.search(domain, order=self.pbf_order(sort) or 'id desc',
                           offset=offset, limit=limit)
        flags = self._pbf_run_flags()
        totals = self._slip_totals(recs.ids)
        rows = []
        for i, s in enumerate(recs):
            try:
                fl = flags.get(s.id) or {}
                rows.append({
                    'id': s.id, 'emp': s.employee_id.name or '—',
                    'title': s.contract_id.job_id.name if s.contract_id and s.contract_id.job_id
                    else (s.struct_id.name or ''),
                    'net': fl.get('net'), 'gross': totals.get(s.id, {}).get('gross'),
                    'state': s.state,
                    'flag': bool(fl.get('flag')), 'why': fl.get('reason') or '',
                    'color': PALETTE[(offset + i) % len(PALETTE)],
                })
            except Exception as ex:  # noqa: BLE001 — one bad row never blanks the list
                _logger.debug("Payslip review row failed: %s", ex)
        # the steps: one read of (id, state) for the list minus the status filter
        steps = {key: {'n': 0, 'flagged': 0} for key, _states in STEP_STATES}
        of_state = {st: key for key, states in STEP_STATES for st in states}
        for row in Slip.search_read(self.pbf_domain(filters, search, skip='status'), ['state']):
            key = of_state.get(row['state'])
            if key:
                steps[key]['n'] += 1
                if (flags.get(row['id']) or {}).get('flag'):
                    steps[key]['flagged'] += 1
        return {'rows': rows, 'total': Slip.search_count(domain), 'offset': offset,
                'steps': steps}

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
        # LEARN REFRESH step 6 — take-home pay and "Need review" come from the
        # run's one shared answer (review_flags.py), the same the Run lens
        # counts, so the two "Need review" numbers can never disagree. It also
        # reads the scheme's own net line rather than summing the NET category,
        # which counted FULLPAY and NET together on the demo world.
        flags = run.sudo().pb_review_flags(slip_recs.ids)
        slips, t_net, t_gross, n_net, n_gross = [], 0.0, 0.0, 0, 0
        for i, s in enumerate(slip_recs):
            tt = totals.get(s.id, {})
            fl = flags.get(s.id) or {}
            net, gross = fl.get('net'), tt.get('gross')
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
                'flag': bool(fl.get('flag')), 'why': fl.get('reason') or '',
                'color': PALETTE[i % len(PALETTE)],
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
        """Kept so an old client cannot silently do nothing, and says why.

        The RPC name survives because a browser that has not reloaded still
        knows it; what it does now is explain, once, where the decision moved
        to.
        """
        s = self.env['hr.payslip'].browse(slip_id)
        if s.exists() and s.payslip_run_id:
            return {'ok': False, 'state': s.state, 'msg': _(
                "Payslips are approved together, as a pay run. Send the pay "
                "run in for approval instead.")}
        return {'ok': False, 'state': s.state if s.exists() else False,
                'msg': _("This payslip is not part of a pay run, so there is "
                         "nothing to approve here.")}
