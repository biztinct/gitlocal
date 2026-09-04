# -*- coding: utf-8 -*-
"""The Statutory cockpit's data — the board, and the four ledgers that replaced
its legacy launch tiles.

IA Cycle 4 (the C3 hand-back). This board used to end in five tiles that opened
`ir.actions.act_window` records in `pb_hr_payroll_vietnam` — four of them raw
`list,form` views on VN tables, the fifth a `target: "new"` analytics wizard.
Five clicks, four exits from the Payobook skin into Odoo's own chrome, and no
way back except the browser button.

The four tables are now IN this cockpit: a Data view with a tab strip, a grid,
and a 320px drawer on row click. The analytics WIZARD is not a table and did not
become a ledger — it is a modal that computes a contribution analysis, and it
stays a modal, launched from a labelled button rather than from a tile that
looks like a navigation. Saying which of the five went where is the point; a
report that claimed "five tiles became ledgers" would be describing four.

The legacy actions themselves are untouched and still registered. This cycle
replaces the DOORS, not the models: hidden menus and any other caller keep
working, and nothing here deletes a record type.

Read with the CALLER's own rights throughout — no sudo anywhere in the ledger
code. If the user could open the list, they can open the ledger; if they could
not, the ledger is exactly as empty as the list would have been (W12).

This cycle is READ-PATH ONLY on those four tables: the grid and the drawer, and
no edit UI. Records stay editable through their existing native forms.
"""
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

# Contribution rule codes grouped by insurance type and leg.
CONTRIB_MAP = {
    'SI_EMP': ('SI', 'emp'), 'SI_COMP': ('SI', 'comp'),
    'HI_EMP': ('HI', 'emp'), 'HI_COMP': ('HI', 'comp'),
    'UI_EMP': ('UI', 'emp'), 'UI_COMP': ('UI', 'comp'),
    # Payobook demo formula-config codes (underscore-free per converter contract).
    'SIEMP': ('SI', 'emp'), 'SICOMP': ('SI', 'comp'),
    'HIEMP': ('HI', 'emp'), 'HICOMP': ('HI', 'comp'),
    'UIEMP': ('UI', 'emp'), 'UICOMP': ('UI', 'comp'),
}
INS_LABEL = {'SI': 'Social Insurance (BHXH)', 'HI': 'Health Insurance (BHYT)',
             'UI': 'Unemployment (BHTN)'}

# The one legacy launch that is NOT a table.
#
# `action_vietnam_insurance_analytics` opens `vietnam.insurance.analytics`, a
# TransientModel with `view_mode: form` and `target: new` — a wizard that
# computes a contribution analysis, not a list of records. Turning it into a
# ledger would mean inventing a table it does not have, so it stays what it is
# and is launched from a labelled button in the cockpit header. The other four
# tiles pointed at real `list,form` views and are the ledgers below.
ANALYTICS_ACTION = 'pb_hr_payroll_vietnam.action_vietnam_insurance_analytics'

# The four legacy `list,form` doors, each replaced by an in-cockpit ledger. The
# xmlid is carried so the door test can assert that the cockpit no longer opens
# it and that the ledger stands in its place — and so a reader can see, in one
# table, what became of every tile.
LEDGERS = {
    'policy': {
        'model': 'vietnam.insurance.policy',
        'legacy_action': 'pb_hr_payroll_vietnam.action_vietnam_insurance_policy',
    },
    'tax': {
        'model': 'vietnam.tax.table',
        'legacy_action': 'pb_hr_payroll_vietnam.action_vietnam_tax_table',
    },
    'adjustment': {
        'model': 'vietnam.insurance.adjustment',
        'legacy_action': 'pb_hr_payroll_vietnam.action_vietnam_insurance_adjustment',
    },
    'dependent': {
        'model': 'vietnam.employee.dependent',
        'legacy_action': 'pb_hr_payroll_vietnam.action_vietnam_employee_dependent',
    },
}

# The same row budget the pay-run and integration ledgers use. A statutory
# table is not a report: past a few hundred rows the answer is the search box,
# not a longer scroll.
LIMIT = 400


def _sel(Model, field, value):
    """A Selection value as its LABEL, falling back to the technical value."""
    return dict(Model._fields[field].selection or {}).get(value, value or '')


def _s(v):
    return str(v) if v else ''


class PbStatutory(models.AbstractModel):
    _name = 'pb.statutory'
    _description = 'Payobook Statutory cockpit data'

    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug("Statutory metric failed: %s", e)
            return default

    @api.model
    def get_statutory_data(self):
        company = self.env.company
        cur = company.currency_id
        co_ids = self.env.companies.ids or [company.id]

        # ---------- insurance policy ----------
        policy = None
        if 'vietnam.insurance.policy' in self.env:
            Pol = self.env['vietnam.insurance.policy']
            rec = self._safe(
                lambda: Pol.search([('company_id', 'in', co_ids), ('active', '=', True)],
                                   order='effective_date desc', limit=1),
                default=Pol.browse())
            if rec:
                policy = {
                    'name': rec.name, 'code': rec.code or '',
                    'effective': str(rec.effective_date or ''),
                    'rows': [
                        {'key': 'SI', 'label': INS_LABEL['SI'],
                         'employee': rec.si_employee_rate, 'employer': rec.si_employer_rate,
                         'ceiling': rec.si_max_salary_ceiling},
                        {'key': 'HI', 'label': INS_LABEL['HI'],
                         'employee': rec.hi_employee_rate, 'employer': rec.hi_employer_rate,
                         'ceiling': rec.hi_max_salary_ceiling},
                        {'key': 'UI', 'label': INS_LABEL['UI'],
                         'employee': rec.ui_employee_rate, 'employer': rec.ui_employer_rate,
                         'ceiling': rec.ui_max_salary_ceiling},
                    ],
                }
                te = sum(r['employee'] for r in policy['rows'])
                tr = sum(r['employer'] for r in policy['rows'])
                policy['total_employee'] = round(te, 2)
                policy['total_employer'] = round(tr, 2)
                policy['total_combined'] = round(te + tr, 2)

        # ---------- tax table ----------
        tax = None
        if 'vietnam.tax.table' in self.env:
            Tax = self.env['vietnam.tax.table']
            rec = self._safe(
                lambda: Tax.search([('company_id', 'in', co_ids), ('active', '=', True)],
                                   order='tax_year desc', limit=1),
                default=Tax.browse())
            if rec:
                slabs = []
                try:
                    for s in rec.slab_ids.sorted(lambda x: (x.sequence, x.income_from)):
                        slabs.append({
                            'from': s.income_from, 'to': s.income_to,
                            'rate': s.tax_rate, 'fixed': s.fixed_amount,
                        })
                except Exception:
                    slabs = []
                tax = {
                    'name': rec.name, 'year': rec.tax_year,
                    'personal_deduction': rec.personal_deduction,
                    'dependent_deduction': rec.dependent_deduction,
                    'slabs': slabs,
                }

        # ---------- contribution actuals (latest run) ----------
        actuals = None
        Run = self.env['hr.payslip.run']
        # hr.payslip.run has no company_id column in this build — only scope by it
        # when the field actually exists (else the latest run overall).
        run_dom = [('company_id', 'in', co_ids)] if 'company_id' in Run._fields else []
        latest = self._safe(
            lambda: Run.search(run_dom, order='date_end desc, id desc', limit=1),
            default=Run.browse())
        if latest:
            buckets = {k: {'emp': 0.0, 'comp': 0.0} for k in ('SI', 'HI', 'UI')}
            try:
                g = self.env['hr.payslip.line'].read_group(
                    [('slip_id.payslip_run_id', '=', latest.id),
                     ('code', 'in', list(CONTRIB_MAP.keys()))],
                    ['total:sum'], ['code'])
                for row in g:
                    code = row.get('code')
                    amt = abs(row.get('total') or 0.0)
                    if code in CONTRIB_MAP:
                        ins, leg = CONTRIB_MAP[code]
                        buckets[ins][leg] += amt
            except Exception:
                pass
            emp_total = sum(b['emp'] for b in buckets.values())
            comp_total = sum(b['comp'] for b in buckets.values())
            covered = self._safe(
                lambda: self.env['hr.payslip'].search_count(
                    [('payslip_run_id', '=', latest.id)]))
            actuals = {
                'run_name': latest.name or '',
                'rows': [{'key': k, 'label': INS_LABEL[k],
                          'emp': buckets[k]['emp'], 'comp': buckets[k]['comp'],
                          'total': buckets[k]['emp'] + buckets[k]['comp']}
                         for k in ('SI', 'HI', 'UI')],
                'emp_total': emp_total, 'comp_total': comp_total,
                'grand_total': emp_total + comp_total, 'covered': covered,
            }

        # ---------- policies + tax tables rosters (config — list all) ----------
        policies = []
        if 'vietnam.insurance.policy' in self.env:
            for p in self._safe(lambda: self.env['vietnam.insurance.policy'].search(
                    [], order='effective_date desc, id desc', limit=120), default=[]):
                policies.append({
                    'id': p.id, 'name': p.name or '—', 'code': p.code or '',
                    'effective': str(p.effective_date or ''), 'end': str(p.end_date or ''),
                    'total_employer': round(getattr(p, 'total_employer_rate', 0) or 0, 2),
                    'total_employee': round(getattr(p, 'total_employee_rate', 0) or 0, 2),
                    'active': bool(p.active),
                })
        tax_tables = []
        if 'vietnam.tax.table' in self.env:
            for t in self._safe(lambda: self.env['vietnam.tax.table'].search(
                    [], order='tax_year desc, id desc', limit=120), default=[]):
                tax_tables.append({
                    'id': t.id, 'name': t.name or '—', 'code': t.code or '',
                    'year': t.tax_year, 'slabs': getattr(t, 'slab_count', 0) or len(t.slab_ids),
                    'personal': t.personal_deduction, 'dependent': t.dependent_deduction,
                    'active': bool(t.active),
                })
        dependents = self._safe(
            lambda: self.env['vietnam.employee.dependent'].search_count([])
            if 'vietnam.employee.dependent' in self.env else 0)

        # ---------- the one surviving launch ----------
        # A wizard, not a table (see ANALYTICS_ACTION). Offered only when it is
        # really on this database: a tile pointing at a deleted action renders
        # normally and answers a click with nothing (W79).
        analytics_action = ''
        if self.env.ref(ANALYTICS_ACTION, raise_if_not_found=False):
            analytics_action = ANALYTICS_ACTION

        return {
            'currency': cur.symbol or '',
            'company': company.name,
            'kpis': {
                'contributions': (actuals or {}).get('grand_total', 0),
                'emp_leg': (actuals or {}).get('emp_total', 0),
                'comp_leg': (actuals or {}).get('comp_total', 0),
                'policies': len(policies), 'tax_tables': len(tax_tables),
                'dependents': dependents,
            },
            'policy': policy,
            'tax': tax,
            'actuals': actuals,
            'policies': policies,
            'tax_tables': tax_tables,
            'analytics_action': analytics_action,
            'ledgers': [k for k, spec in LEDGERS.items()
                        if spec['model'] in self.env],
        }

    # ================================================================= ledgers
    @api.model
    def _employee_scope(self):
        """A domain fragment limiting a table to employees the caller may READ.

        Found live, and it is W97 word for word: a satellite table whose own
        record rule is WIDER than its many2one's takes the whole grid down on
        the first unreadable row. `vietnam.insurance.adjustment` is scoped by
        its own `company_id`; `hr.employee` is scoped more tightly on this
        database; so an unscoped read reached one employee (id 28) the caller
        may not see, dereferenced `employee_id.name` to render a column, and the
        client showed "This table could not be loaded" — every readable row lost
        to one refusal, with the message naming neither the row nor the reason.

        `Emp._search([])` is a SUBQUERY with the record rules already applied, so
        this is not a permission decision (the rule made that) — it is refusing
        to ask a question whose answer would raise. A subquery rather than a
        list of ids because this tenant has 4 500 employees and a domain is not
        a place to put them.

        Rows with no employee at all stay in: they are not about a person, so no
        rule hides them.
        """
        Emp = self.env['hr.employee']
        return ['|', ('employee_id', '=', False),
                ('employee_id', 'in', Emp._search([]))]

    @api.model
    def get_ledger(self, kind):
        """One VN statutory table as a grid descriptor.

        `kind` is looked up in LEDGERS rather than used to index `self.env`: a
        forged kind must not be able to point this method at another table (the
        same reasoning as `pb.integrations.get_ledger`).

        Company scoping is the record rules' own answer — `search([])` applies
        them. The one thing this cockpit must add is `_employee_scope()`, for
        the two tables that reach a person; see that method.
        """
        spec = LEDGERS.get(kind)
        if not spec or spec['model'] not in self.env:
            return {'columns': [], 'rows': [], 'total': 0, 'shown': 0,
                    'empty': 'This table does not exist on this database.'}
        return getattr(self, '_ledger_%s' % kind)()

    @api.model
    def get_ledger_detail(self, kind, rec_id):
        """One row's whole story, as sections of labelled fields.

        Returns `{}` for an id that no longer exists — the drawer is opened from
        a row the user is looking at, so the honest answer to "this was deleted
        while you read the grid" is an empty panel, not a traceback.

        An id the caller may not READ is a different question and it RAISES:
        `check_access` is the ORM's own refusal and swallowing it would be a
        catch that quietly narrows a feature (W40).
        """
        spec = LEDGERS.get(kind)
        if not spec or spec['model'] not in self.env:
            return {}
        rec = self.env[spec['model']].browse(int(rec_id))
        if not rec.exists():
            return {}
        rec.check_access('read')
        d = getattr(self, '_detail_%s' % kind)(rec)
        d['id'] = rec.id
        d['res_model'] = spec['model']
        return d

    @api.model
    def _section(self, label, fields_):
        """A drawer section; entries with nothing behind them are dropped.

        Written out by TYPE rather than as `v not in ('', None, False)`, because
        `in` compares with `==` and `0 == False` — the tidy one-liner silently
        drops every zero as well, and on a table of RATES a zero is a fact (a
        scheme the employer does not contribute to). Copied from the C3 ledger's
        fix rather than from the bug it replaced.
        """
        keep = []
        for f in fields_:
            v = f.get('value')
            # Booleans FIRST and by identity: `isinstance(True, int)` is also
            # true, so any ordering that tests numbers first turns Yes into a 1.
            if v is True or v is False:
                if v:
                    keep.append(dict(f, value='Yes'))
                elif f.get('keep_false'):
                    keep.append(dict(f, value='No'))
                continue
            if isinstance(v, str) and v.strip():
                keep.append(f)
            elif isinstance(v, (int, float)):
                if v or f.get('keep_zero'):
                    keep.append(dict(f, value=str(v)))
        return {'label': label, 'fields': keep} if keep else None

    @api.model
    def _facets(self, rows, spec):
        """Facets built from the LOADED rows, so a chip always matches rows."""
        out = []
        for key, label in spec:
            vals = sorted({(r['_f'].get(key) or '') for r in rows} - {''})
            out.append({'key': key, 'label': label,
                        'kind': 'chips' if len(vals) <= 8 else 'select',
                        'chips': [{'id': v, 'label': v} for v in vals]})
        return out

    # ------------------------------------------------------ insurance policies
    @api.model
    def _ledger_policy(self):
        P = self.env['vietnam.insurance.policy']
        # `active` is a real field here, so the ledger shows the archived rows
        # too — a superseded policy is exactly the thing somebody comes looking
        # for, and a filter that hides it makes the table lie by omission.
        recs = P.with_context(active_test=False).search(
            [], order='effective_date desc, id desc', limit=LIMIT)
        total = P.with_context(active_test=False).search_count([])
        rows = []
        for r in recs:
            rows.append({
                'id': r.id,
                'cells': [
                    r.name or '—',
                    r.code or '—',
                    _s(r.effective_date) or '—',
                    '%s%% / %s%%' % (round(r.total_employee_rate or 0, 2),
                                     round(r.total_employer_rate or 0, 2)),
                ],
                'badge': {'label': 'Active' if r.active else 'Archived',
                          'tone': 'ok' if r.active else 'muted'},
                '_f': {'state': 'active' if r.active else 'archived',
                       'company': r.company_id.name or ''},
                '_s': ' '.join(x for x in [r.name or '', r.code or ''] if x),
            })
        return {
            'title': 'Insurance policies',
            'subtitle': 'Contribution rates, ceilings and the dates they apply from.',
            'search_ph': 'Search policy name or code…',
            'empty': 'No insurance policies match these filters.',
            'columns': [{'label': 'Policy', 'wide': True}, {'label': 'Code'},
                        {'label': 'Effective'}, {'label': 'EE / ER total'}],
            'facets': self._facets(rows, [('state', 'State'), ('company', 'Company')]),
            'rows': rows, 'total': total, 'shown': len(rows),
        }

    @api.model
    def _detail_policy(self, r):
        return {
            'title': r.name or '—',
            'subtitle': r.code or '',
            'sections': [s for s in [
                self._section('Identity', [
                    {'label': 'Name', 'value': r.name or ''},
                    {'label': 'Code', 'value': r.code or ''},
                    {'label': 'Company', 'value': r.company_id.name or ''},
                    {'label': 'Effective from', 'value': _s(r.effective_date)},
                    {'label': 'Effective to', 'value': _s(r.end_date)},
                    {'label': 'Active', 'value': bool(r.active), 'keep_false': True},
                ]),
                self._section('Social insurance (BHXH)', [
                    {'label': 'Employee rate', 'value': r.si_employee_rate, 'keep_zero': True},
                    {'label': 'Employer rate', 'value': r.si_employer_rate, 'keep_zero': True},
                    {'label': 'Salary ceiling', 'value': r.si_max_salary_ceiling},
                ]),
                self._section('Health insurance (BHYT)', [
                    {'label': 'Employee rate', 'value': r.hi_employee_rate, 'keep_zero': True},
                    {'label': 'Employer rate', 'value': r.hi_employer_rate, 'keep_zero': True},
                    {'label': 'Salary ceiling', 'value': r.hi_max_salary_ceiling},
                ]),
                self._section('Unemployment (BHTN)', [
                    {'label': 'Employee rate', 'value': r.ui_employee_rate, 'keep_zero': True},
                    {'label': 'Employer rate', 'value': r.ui_employer_rate, 'keep_zero': True},
                    {'label': 'Salary ceiling', 'value': r.ui_max_salary_ceiling},
                ]),
                self._section('Occupational', [
                    {'label': 'Accident rate (employer)', 'value': r.oa_employer_rate},
                    {'label': 'Disease rate (employer)', 'value': r.od_employer_rate},
                    {'label': 'Accident waiver', 'value': bool(r.oa_waiver_enabled),
                     'keep_false': True},
                    {'label': 'Waiver months', 'value': r.oa_waiver_max_months},
                ]),
                self._section('Waivers', [
                    {'label': 'Waive UI for foreign staff',
                     'value': bool(r.waive_ui_foreign), 'keep_false': True},
                    {'label': 'Waive HI for foreign staff',
                     'value': bool(r.waive_hi_foreign), 'keep_false': True},
                    {'label': 'Waive UI in no-fund areas',
                     'value': bool(r.waive_ui_no_fund_areas), 'keep_false': True},
                ]),
                self._section('Totals', [
                    {'label': 'Employee total', 'value': r.total_employee_rate},
                    {'label': 'Employer total', 'value': r.total_employer_rate},
                ]),
            ] if s],
        }

    # ------------------------------------------------------------- tax tables
    @api.model
    def _ledger_tax(self):
        T = self.env['vietnam.tax.table']
        recs = T.with_context(active_test=False).search(
            [], order='tax_year desc, id desc', limit=LIMIT)
        total = T.with_context(active_test=False).search_count([])
        rows = []
        for r in recs:
            rows.append({
                'id': r.id,
                'cells': [r.name or '—', r.code or '—', str(r.tax_year or ''),
                          str(len(r.slab_ids))],
                'badge': {'label': 'Active' if r.active else 'Archived',
                          'tone': 'ok' if r.active else 'muted'},
                '_f': {'state': 'active' if r.active else 'archived',
                       'year': str(r.tax_year or '')},
                '_s': ' '.join(x for x in [r.name or '', r.code or ''] if x),
            })
        return {
            'title': 'Tax tables',
            'subtitle': 'Progressive brackets, personal relief and dependent relief.',
            'search_ph': 'Search table name or code…',
            'empty': 'No tax tables match these filters.',
            'columns': [{'label': 'Table', 'wide': True}, {'label': 'Code'},
                        {'label': 'Year'}, {'label': 'Brackets'}],
            'facets': self._facets(rows, [('state', 'State'), ('year', 'Year')]),
            'rows': rows, 'total': total, 'shown': len(rows),
        }

    @api.model
    def _detail_tax(self, r):
        sections = [
            self._section('Identity', [
                {'label': 'Name', 'value': r.name or ''},
                {'label': 'Code', 'value': r.code or ''},
                {'label': 'Tax year', 'value': r.tax_year},
                {'label': 'Company', 'value': r.company_id.name or ''},
                {'label': 'Active', 'value': bool(r.active), 'keep_false': True},
            ]),
            self._section('Reliefs', [
                {'label': 'Personal deduction', 'value': r.personal_deduction},
                {'label': 'Dependent deduction', 'value': r.dependent_deduction},
                {'label': 'Insurance exempt', 'value': bool(r.insurance_exemption),
                 'keep_false': True},
            ]),
        ]
        # The brackets themselves, in the drawer, because a tax table with its
        # bracket count and no brackets is a row that answers the wrong
        # question. Bounded: a table with two hundred slabs is a data problem,
        # and a 320px panel is not where it gets diagnosed.
        slabs = []
        for s in r.slab_ids.sorted(lambda x: (x.sequence, x.income_from))[:40]:
            slabs.append({
                'label': '%s → %s' % (int(s.income_from or 0),
                                      int(s.income_to) if s.income_to else '∞'),
                'value': '%s%%' % (s.tax_rate or 0),
            })
        sections.append(self._section('Brackets', slabs))
        if len(r.slab_ids) > 40:
            sections.append(self._section('Brackets (continued)', [
                {'label': '…and more',
                 'value': '%s further brackets' % (len(r.slab_ids) - 40)}]))
        return {
            'title': r.name or '—',
            'subtitle': str(r.tax_year or ''),
            'sections': [s for s in sections if s],
        }

    # ------------------------------------------------------ insurance adjustments
    @api.model
    def _ledger_adjustment(self):
        A = self.env['vietnam.insurance.adjustment']
        dom = self._employee_scope()
        recs = A.search(dom, order='adjustment_date desc, id desc', limit=LIMIT)
        total = A.search_count(dom)
        rows = []
        for r in recs:
            state = r.state or 'draft'
            tone = {'applied': 'ok', 'confirmed': 'info', 'cancelled': 'muted',
                    'draft': 'warn'}.get(state, 'muted')
            rows.append({
                'id': r.id,
                'cells': [
                    r.employee_id.name or '—',
                    _sel(A, 'insurance_type', r.insurance_type),
                    _sel(A, 'adjustment_type', r.adjustment_type),
                    _s(r.adjustment_date) or '—',
                ],
                'badge': {'label': _sel(A, 'state', state), 'tone': tone},
                '_f': {'state': state,
                       'insurance': _sel(A, 'insurance_type', r.insurance_type)},
                '_s': ' '.join(x for x in [r.name or '',
                                           r.employee_id.name or ''] if x),
            })
        return {
            'title': 'Insurance adjustments',
            'subtitle': 'Backdated corrections, refunds and additional collections.',
            'search_ph': 'Search reference or employee…',
            'empty': 'No insurance adjustments on this database.',
            'columns': [{'label': 'Employee', 'wide': True},
                        {'label': 'Scheme'}, {'label': 'Kind'}, {'label': 'Date'}],
            'facets': self._facets(rows, [('state', 'State'),
                                          ('insurance', 'Scheme')]),
            'rows': rows, 'total': total, 'shown': len(rows),
        }

    @api.model
    def _detail_adjustment(self, r):
        A = self.env['vietnam.insurance.adjustment']
        return {
            'title': r.employee_id.name or r.name or '—',
            'subtitle': r.name or '',
            'sections': [s for s in [
                self._section('Adjustment', [
                    {'label': 'Reference', 'value': r.name or ''},
                    {'label': 'Employee', 'value': r.employee_id.name or ''},
                    {'label': 'Company', 'value': r.company_id.name or ''},
                    {'label': 'Scheme', 'value': _sel(A, 'insurance_type', r.insurance_type)},
                    {'label': 'Kind', 'value': _sel(A, 'adjustment_type', r.adjustment_type)},
                    {'label': 'Reason', 'value': _sel(A, 'reason', r.reason)},
                    {'label': 'Status', 'value': _sel(A, 'state', r.state)},
                ]),
                self._section('Period', [
                    {'label': 'Adjusted on', 'value': _s(r.adjustment_date)},
                    {'label': 'Covers from', 'value': _s(r.period_from)},
                    {'label': 'Covers to', 'value': _s(r.period_to)},
                ]),
                self._section('Money', [
                    {'label': 'Old contribution', 'value': r.old_contribution, 'keep_zero': True},
                    {'label': 'New contribution', 'value': r.new_contribution, 'keep_zero': True},
                    {'label': 'Difference', 'value': r.difference, 'keep_zero': True},
                    {'label': 'Employer share', 'value': r.employer_amount},
                    {'label': 'Employee share', 'value': r.employee_amount},
                    # A THIRD model, with rules of its own. The row is already
                    # scoped by its employee; the payslip is not, so the same
                    # one-unreadable-record trap applies to this single field
                    # and it degrades to blank rather than taking the drawer
                    # down (W97, bounded to the dereference that can raise).
                    {'label': 'Applied on payslip',
                     'value': self._safe(
                         lambda: (r.applied_payslip_id.number
                                  or r.applied_payslip_id.name or ''), default='')
                     if r.applied_payslip_id else ''},
                ]),
                self._section('Notes', [
                    {'label': 'Notes', 'value': r.notes or '', 'wrap': True},
                ]),
            ] if s],
        }

    # --------------------------------------------------------------- dependents
    @api.model
    def _ledger_dependent(self):
        D = self.env['vietnam.employee.dependent']
        # Same scope as the adjustments: this table reaches a person too, and it
        # rendered only because its newest 400 rows happened not to include the
        # one employee the caller cannot read. A correct count and a poisoned
        # row look identical (W97).
        dom = self._employee_scope()
        recs = D.search(dom, order='employee_id, id desc', limit=LIMIT)
        total = D.search_count(dom)
        rows = []
        for r in recs:
            status = r.status or 'draft'
            tone = {'approved': 'ok', 'pending': 'warn', 'expired': 'muted',
                    'rejected': 'err'}.get(status, 'muted')
            rows.append({
                'id': r.id,
                'cells': [
                    r.name or '—',
                    r.employee_id.name or '—',
                    _sel(D, 'relationship', r.relationship),
                    _s(r.effective_from) or '—',
                ],
                'badge': {'label': _sel(D, 'status', status), 'tone': tone},
                '_f': {'status': _sel(D, 'status', status),
                       'relationship': _sel(D, 'relationship', r.relationship)},
                '_s': ' '.join(x for x in [r.name or '', r.employee_id.name or '',
                                           r.identification_number or ''] if x),
            })
        return {
            'title': 'Dependents',
            'subtitle': 'Registered dependents and the personal relief they carry.',
            'search_ph': 'Search dependent, employee or ID number…',
            'empty': 'No dependents registered on this database.',
            'columns': [{'label': 'Dependent', 'wide': True},
                        {'label': 'Employee'}, {'label': 'Relationship'},
                        {'label': 'From'}],
            'facets': self._facets(rows, [('status', 'Status'),
                                          ('relationship', 'Relationship')]),
            'rows': rows, 'total': total, 'shown': len(rows),
        }

    @api.model
    def _detail_dependent(self, r):
        D = self.env['vietnam.employee.dependent']
        return {
            'title': r.name or '—',
            'subtitle': r.employee_id.name or '',
            'sections': [s for s in [
                self._section('Dependent', [
                    {'label': 'Name', 'value': r.name or ''},
                    {'label': 'Employee', 'value': r.employee_id.name or ''},
                    {'label': 'Relationship', 'value': _sel(D, 'relationship', r.relationship)},
                    {'label': 'Date of birth', 'value': _s(r.date_of_birth)},
                ]),
                self._section('Registration', [
                    {'label': 'ID number', 'value': r.identification_number or ''},
                    {'label': 'Tax code', 'value': r.tax_registration_number or ''},
                    {'label': 'Registered on', 'value': _s(r.registration_date)},
                    {'label': 'Status', 'value': _sel(D, 'status', r.status)},
                ]),
                self._section('Relief', [
                    {'label': 'Effective from', 'value': _s(r.effective_from)},
                    {'label': 'Effective to', 'value': _s(r.effective_to)},
                    {'label': 'Monthly allowance', 'value': r.tax_allowance},
                    {'label': 'Currently eligible', 'value': bool(r.is_currently_eligible),
                     'keep_false': True},
                ]),
                self._section('Notes', [
                    {'label': 'Notes', 'value': r.notes or '', 'wrap': True},
                ]),
            ] if s],
        }

    # ------------------------------------------------------------------ details
    @api.model
    def get_policy_detail(self, policy_id):
        p = self.env['vietnam.insurance.policy'].browse(int(policy_id))
        if not p.exists():
            return {'error': 'Policy not found'}
        rows = [
            {'key': 'SI', 'label': INS_LABEL['SI'], 'employee': p.si_employee_rate,
             'employer': p.si_employer_rate, 'ceiling': p.si_max_salary_ceiling},
            {'key': 'HI', 'label': INS_LABEL['HI'], 'employee': p.hi_employee_rate,
             'employer': p.hi_employer_rate, 'ceiling': p.hi_max_salary_ceiling},
            {'key': 'UI', 'label': INS_LABEL['UI'], 'employee': p.ui_employee_rate,
             'employer': p.ui_employer_rate, 'ceiling': p.ui_max_salary_ceiling},
        ]
        waivers = []
        for f, lbl in [('waive_ui_foreign', 'Waive UI for foreign staff'),
                       ('waive_hi_foreign', 'Waive HI for foreign staff'),
                       ('waive_ui_no_fund_areas', 'Waive UI in no-fund areas'),
                       ('oa_waiver_enabled', 'Occupational-accident waiver')]:
            if getattr(p, f, False):
                waivers.append(lbl)
        return {
            'id': p.id, 'name': p.name or '—', 'code': p.code or '',
            'effective': str(p.effective_date or ''), 'end': str(p.end_date or ''),
            'active': bool(p.active),
            'currency': self.env.company.currency_id.symbol or '',
            'rows': rows,
            'total_employee': round(getattr(p, 'total_employee_rate', 0) or 0, 2),
            'total_employer': round(getattr(p, 'total_employer_rate', 0) or 0, 2),
            'waivers': waivers,
            'error': None,
        }

    @api.model
    def get_tax_detail(self, tax_id):
        t = self.env['vietnam.tax.table'].browse(int(tax_id))
        if not t.exists():
            return {'error': 'Tax table not found'}
        slabs = []
        for s in t.slab_ids.sorted(lambda x: (x.sequence, x.income_from)):
            slabs.append({'from': s.income_from, 'to': s.income_to,
                          'rate': s.tax_rate, 'fixed': s.fixed_amount})
        return {
            'id': t.id, 'name': t.name or '—', 'code': t.code or '', 'year': t.tax_year,
            'active': bool(t.active),
            'currency': self.env.company.currency_id.symbol or '',
            'personal': t.personal_deduction, 'dependent': t.dependent_deduction,
            'slabs': slabs, 'slab_count': len(slabs),
            'error': None,
        }


# ==== end of the ledger region ====
# The marker is load-bearing: `test_the_ledger_is_read_only_this_cycle` reads
# the region between it and the ledger header, and the CONFIG WIZARDS below do
# legitimately create records. A region gate needs explicit delimiters or it
# swallows the next class and fails on code that was never in scope (W64).


class PbStatutoryWizard(models.AbstractModel):
    _name = 'pb.statutory.wizard'
    _description = 'Payobook statutory config wizards'

    @api.model
    def get_defaults(self):
        from datetime import date
        return {
            'today': date.today().isoformat(),
            'year': date.today().year,
            'currency': self.env.company.currency_id.symbol or '',
            # Vietnam 2024 defaults
            'policy': {'si_employer': 17.5, 'si_employee': 8.0, 'si_ceiling': 46800000,
                       'hi_employer': 3.0, 'hi_employee': 1.5, 'hi_ceiling': 46800000,
                       'ui_employer': 1.0, 'ui_employee': 1.0, 'ui_ceiling': 93600000},
            'tax': {'personal': 11000000, 'dependent': 4400000},
        }

    @api.model
    def create_policy(self, vals):
        if 'vietnam.insurance.policy' not in self.env:
            return {'error': 'Insurance policy model not installed.'}
        if not (vals.get('name') or '').strip() or not (vals.get('code') or '').strip():
            return {'error': 'Name and code are required.'}
        cvals = {'name': vals['name'].strip(), 'code': vals['code'].strip()}
        if vals.get('effective_date'):
            cvals['effective_date'] = vals['effective_date']
        for k in ('si_employer_rate', 'si_employee_rate', 'si_max_salary_ceiling',
                  'hi_employer_rate', 'hi_employee_rate', 'hi_max_salary_ceiling',
                  'ui_employer_rate', 'ui_employee_rate', 'ui_max_salary_ceiling'):
            if vals.get(k) not in (None, ''):
                cvals[k] = float(vals[k])
        try:
            p = self.env['vietnam.insurance.policy'].create(cvals)
        except Exception as e:
            return {'error': str(getattr(e, 'name', None) or e) or 'Could not create policy.'}
        return {'policy_id': p.id, 'name': p.name, 'error': None}

    @api.model
    def create_tax_table(self, vals):
        if 'vietnam.tax.table' not in self.env:
            return {'error': 'Tax table model not installed.'}
        if not (vals.get('name') or '').strip() or not (vals.get('code') or '').strip():
            return {'error': 'Name and code are required.'}
        cvals = {'name': vals['name'].strip(), 'code': vals['code'].strip(),
                 'tax_year': int(vals.get('tax_year') or 0)}
        if vals.get('personal_deduction') not in (None, ''):
            cvals['personal_deduction'] = float(vals['personal_deduction'])
        if vals.get('dependent_deduction') not in (None, ''):
            cvals['dependent_deduction'] = float(vals['dependent_deduction'])
        try:
            t = self.env['vietnam.tax.table'].create(cvals)
            if vals.get('gen_slabs') and hasattr(t, 'action_create_default_slabs'):
                t.action_create_default_slabs()
        except Exception as e:
            return {'error': str(getattr(e, 'name', None) or e) or 'Could not create tax table.'}
        return {'tax_id': t.id, 'name': t.name, 'slabs': len(t.slab_ids), 'error': None}
