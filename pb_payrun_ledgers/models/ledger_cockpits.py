# -*- coding: utf-8 -*-
"""Data RPCs for the three pay-run ledger cockpits (Full & Final, Proration
Audit, Retro Adjustments). Each returns ONE generic descriptor the shared OWL
component renders — KPI strip, facet chips/selects, and rich rows — cloning the
pb.people roster pattern. Read with the caller's own rights (no sudo): if the
user can open the underlying list, they can open the cockpit."""
import logging

from odoo import _, api, models

_logger = logging.getLogger(__name__)

LIMIT = 400


def _initials(name):
    parts = [p for p in (name or '').replace('-', ' ').split() if p]
    return ((parts[0][0] if parts else '?') + (parts[-1][0] if len(parts) > 1 else '')).upper()


def _emp_avatar(emp):
    return ('/web/image/hr.employee/%s/avatar_128' % emp.id) if emp else ''


def _sel(Model, field):
    """A Selection field's labels in the reader's language (LEARN REFRESH
    step 6): `.selection` is the English source; `_description_selection`
    is what the field's own list and form show."""
    try:
        return dict(Model._fields[field]._description_selection(Model.env))
    except Exception:       # noqa: BLE001 — a label is never worth a screen
        return dict(Model._fields[field].selection or [])


def _sel_facet(Model, key, label, field):
    """Facet from a Selection field — chips keyed by the technical value; matched
    against the row's technical value in `_f[key]`."""
    sel = _sel(Model, field)
    return {'key': key, 'label': label, 'kind': 'chips',
            'chips': [{'id': k, 'label': v} for k, v in sel.items()]}


def _rows_facet(rows, key, label, chip_max=8):
    """Facet built from the loaded rows: distinct `_f[key]` display values. Values
    ARE the labels, so chips always match rows (same-named items — e.g. each
    config's own 'Basic Salary' component — collapse to one chip). Rendered as a
    dropdown once it grows past chip_max; the shared template hides it entirely
    when there is 0/1 distinct value."""
    vals = sorted({(r['_f'].get(key) or '') for r in rows} - {''})
    return {'key': key, 'label': label, 'kind': 'chips' if len(vals) <= chip_max else 'select',
            'chips': [{'id': v, 'label': v} for v in vals]}


def _d(v):
    """A date/datetime as a plain ISO string, or '' — never a Python object."""
    return str(v) if v else ''


def _m2o(rec):
    return rec.display_name if rec else ''


#: Rows per page on the filter panel's list (FILTER W6; the old cap was 400).
PAGE_SIZE = 60
#: Date presets for a date every record has (no "not set" row).
PAST_DATES = ['this_week', 'this_month', 'last_month', 'last_90', 'this_quarter',
              'this_year', 'last_year']


class LedgerMixin(models.AbstractModel):
    _name = 'pb.ledger.mixin'
    # FILTER W6 (2026-10-31): the three ledgers are on the shared filter
    # panel. They used to load the newest 400 rows and filter those in the
    # browser, with chips counted from the loaded rows. Each data model now
    # declares its sections; the list is paged from the server.
    _inherit = ['pb.filter.mixin']
    _description = 'Pay-run ledger cockpit shared helpers'

    #: saved-views key — one per ledger, so a Full & Final view never shows on Retro
    _ledger_key = None

    @api.model
    def _co_dom(self):
        return [('company_id', 'in', self.env.companies.ids or [self.env.company.id])]

    # ============================================================ filter panel
    def _pbf_model(self):
        return self._detail_model

    def _pbf_screen(self):
        return self._ledger_key or self._name

    def _pbf_base_domain(self):
        return self._co_dom()

    def _pbf_layout_extra(self):
        Model = self.env[self._detail_model]
        return {'currency': self._grid_symbol(Model, self._co_dom())}

    @api.model
    def _sec_department(self, path, pinned=False):
        return {'key': 'department', 'label': _('Department'), 'icon': 'building',
                'group': 'people', 'type': 'many2one', 'path': path, 'pinned': pinned,
                'none_label': _('No department'), 'label_sudo': True}

    @api.model
    def _sec_scheme(self, pinned=False):
        return {'key': 'scheme', 'label': _('Pay scheme'), 'icon': 'sigma',
                'group': 'pay', 'type': 'many2one', 'path': 'formula_config_id',
                'pinned': pinned, 'none_label': _('No pay scheme')}

    @api.model
    def _sec_component(self, pinned=False):
        return {'key': 'component', 'label': _('Component'), 'icon': 'layers',
                'group': 'pay', 'type': 'many2one', 'path': 'component_id',
                'pinned': pinned, 'none_label': _('No component')}

    @api.model
    def _sec_company(self):
        return {'key': 'company', 'label': _('Company'), 'icon': 'landmark',
                'group': 'other', 'type': 'many2one', 'path': 'company_id'}

    @api.model
    def _sec_status(self, options, pinned=True):
        return {'key': 'status', 'label': _('Where it is'), 'icon': 'gitBranch',
                'group': 'other', 'type': 'choice', 'pinned': pinned, 'requires': ['state'],
                'options': [{'value': v, 'label': l, 'tone': t, 'domain': [('state', '=', v)]}
                            for v, l, t in options]}

    def _ledger_head(self, Model, dom):
        """The descriptor without its rows: title, numbers, steps, money sign."""
        raise NotImplementedError

    def _ledger_row_ctx(self, Model):
        """Facts every row of one page shares (labels, which fields exist)."""
        return {}

    def _ledger_row(self, r, ctx):
        raise NotImplementedError

    @api.model
    def get_head(self):
        """The numbers line, the steps and the words — over the whole scope,
        whatever is filtered. The rows come from `get_page`."""
        Model = self.env[self._detail_model]
        dom = self._co_dom()
        head = self._ledger_head(Model, dom)
        head['currency'] = self._grid_symbol(Model, dom)
        head['total'] = Model.search_count(dom)
        return head

    @api.model
    def get_page(self, filters=None, search=None, sort=None, offset=0, limit=PAGE_SIZE):
        """One page of rows for the filter panel's current state."""
        Model = self.env[self._detail_model]
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        domain = self.pbf_domain(filters or {}, search)
        recs = Model.search(domain, order=self.pbf_order(sort) or 'id desc',
                            offset=offset, limit=limit)
        ctx = self._ledger_row_ctx(Model)
        rows = []
        for r in recs:
            try:
                rows.append(self._ledger_row(r, ctx))
            except Exception as e:  # noqa: BLE001 — one bad row never blanks the list
                _logger.debug("Ledger row %s failed: %s", r.id, e)
        return {'rows': rows, 'total': Model.search_count(domain), 'offset': offset}

    @api.model
    def _distinct(self, Model, dom, field):
        try:
            return len(Model.read_group(dom, [field], [field]))
        except Exception:
            return 0

    # ---------------------------------------------------------------- money
    # SCHEMECTX. Every one of these three ledgers is SCHEME-owned — each row
    # carries the scheme that produced it — so an Indian scheme's settlement
    # must not be read out in dong because the company it is filed under keeps
    # its books there. Phase 1 fixed the wizard, the pay run and the fact
    # tables the same way; these cockpits were the last readers left.
    #
    # SC3: the SYMBOL only, never the stored position. `res.currency` records
    # VND as written after the number, and every Payobook screen has always
    # written the sign in front — `ledger.js` still does.
    @api.model
    def _config_symbol(self, config):
        """One scheme's sign, or '' if it cannot answer."""
        if not config:
            return ''
        try:
            if not hasattr(config, 'scheme_currency'):
                return ''
            return config.sudo().scheme_currency().get('symbol') or ''
        except Exception:       # noqa: BLE001 — a sign is never worth a screen
            _logger.debug("Ledger cockpit: scheme currency unavailable",
                          exc_info=True)
            return ''

    @api.model
    def _company_symbol(self):
        return self.env.company.currency_id.symbol or ''

    @api.model
    def _grid_symbol(self, Model, dom):
        """The sign for a whole grid — one list, one sign.

        The scheme's when every row in the list agrees on a scheme; the
        company's when they do not, which is exactly what this screen has
        always shown. Grouping (rather than reading the 400 loaded rows)
        because the KPI strip above the list totals the WHOLE domain, and a
        strip and a list must not disagree about what money they are in.
        """
        try:
            if 'formula_config_id' not in Model._fields:
                return self._company_symbol()
            groups = Model.read_group(dom, ['formula_config_id'],
                                      ['formula_config_id'])
            if len(groups) == 1 and groups[0].get('formula_config_id'):
                config = self.env['hr.formula.config'].sudo().browse(
                    groups[0]['formula_config_id'][0])
                symbol = self._config_symbol(config.exists())
                if symbol:
                    return symbol
        except Exception:       # noqa: BLE001
            _logger.debug("Ledger cockpit: grid currency unavailable",
                          exc_info=True)
        return self._company_symbol()

    # ------------------------------------------------------------------ detail
    # The hub's Adjust/Settle lenses replace the row's NAVIGATION with a drawer,
    # so the drawer has to carry the whole story the native form used to. It is
    # a per-click RPC rather than a payload on every row: `get_data` already
    # ships up to 400 rows, and folding twenty more fields into each of them
    # would multiply a list read by the cost of a detail nobody has asked for
    # yet.
    #
    # Read with the CALLER's own rights, exactly like `get_data` — no sudo. The
    # cockpit is not a wider door than the list it replaces (W12), and a row the
    # user could not read is one `get_data` never handed them in the first
    # place. `_detail_model` names the record's model so a forged id cannot be
    # pointed at another table.
    _detail_model = None

    @api.model
    def get_detail(self, rec_id):
        """One row's full story, as sections of labelled fields.

        Returns `{}` for an id that no longer exists: the drawer is opened from
        a row the user is looking at, so the honest answer to "this was deleted
        while you read the grid" is an empty panel, not a traceback.

        An id the caller may NOT read is a different question and it raises —
        `check_access` is the ORM's own refusal and swallowing it would be W40's
        catch that quietly narrows a feature.
        """
        if not self._detail_model:
            return {}
        rec = self.env[self._detail_model].browse(int(rec_id))
        if not rec.exists():
            return {}
        rec.check_access('read')
        d = self._build_detail(rec)
        # One row, so there is no ambiguity at all: the scheme that produced
        # this settlement says what its money is (SCHEMECTX).
        d['currency'] = (
            self._config_symbol(rec.formula_config_id
                                if 'formula_config_id' in rec._fields
                                else None)
            or self._company_symbol())
        d['id'] = rec.id
        d['res_model'] = self._detail_model
        return d

    def _build_detail(self, rec):
        raise NotImplementedError

    @api.model
    def _section(self, label, fields_):
        """A drawer section; entries whose value is empty are dropped.

        A key with nothing behind it is noise in a 320px panel — and worse, it
        reads as "this record has no batch" when the truth is "this ledger does
        not carry one". Money entries are kept at 0.0 on purpose: a zero
        deduction IS a fact about the settlement.

        The emptiness test is written out by TYPE rather than as
        `value not in ('', None, False)`, because `in` compares with `==` and
        `0.0 == False` — so the tidy one-liner silently dropped every zero
        number as well, which is the opposite of the money rule two lines above.
        """
        keep = []
        for f in fields_:
            v = f.get('value')
            if f.get('money'):
                keep.append(f)
            elif isinstance(v, str) and v.strip():
                keep.append(f)
            elif isinstance(v, (int, float)) and not isinstance(v, bool) and v:
                keep.append(f)
        return {'label': label, 'fields': keep} if keep else None


class PbFullFinal(models.AbstractModel):
    _name = 'pb.fullfinal'
    _inherit = 'pb.ledger.mixin'
    _description = 'Full & Final cockpit data'
    _detail_model = 'hr.full.final.settlement'

    def _build_detail(self, r):
        src = _sel(self.env[self._detail_model], 'source')
        e = r.employee_id
        return {
            'title': (e.name if e else r.name) or '—',
            'subtitle': r.name or '',
            'sections': [s for s in [
                self._section(_('Who'), [
                    {'label': _('Employee'), 'value': e.name if e else ''},
                    {'label': _('Employee ID'), 'value': r.employee_code or ''},
                    {'label': _('Department'), 'value': _m2o(r.department_id)},
                    {'label': _('Job position'), 'value': _m2o(r.job_id)},
                    {'label': _('Contract'), 'value': _m2o(r.contract_id)},
                ]),
                self._section(_('Settlement'), [
                    {'label': _('Settlement date'), 'value': _d(r.settlement_date)},
                    {'label': _('Month'), 'value': r.settlement_month or ''},
                    {'label': _('Period'), 'value': ' → '.join(
                        [x for x in [_d(r.date_from), _d(r.date_to)] if x])},
                    {'label': _('Source'), 'value': src.get(r.source, r.source or '')},
                ]),
                self._section(_('Money'), [
                    {'label': _('Earnings'), 'value': r.total_earnings, 'money': True},
                    {'label': _('Deductions'), 'value': r.total_deductions, 'money': True},
                    {'label': _('Net payable'), 'value': r.net_payable, 'money': True,
                     'strong': True, 'tone': 'ok'},
                ]),
                self._section(_('Breakdown'), [
                    {'label': _('Basic salary'), 'value': r.c_basic, 'money': True},
                    {'label': _('Allowances'), 'value': r.c_allow, 'money': True},
                    {'label': _('Overtime'), 'value': r.c_ot, 'money': True},
                    {'label': _('Bonus'), 'value': r.c_bonus, 'money': True},
                    {'label': _('Unused leave'), 'value': r.c_leave, 'money': True},
                    {'label': _('Other earnings'), 'value': r.c_other_earn, 'money': True},
                    {'label': _('Personal income tax'), 'value': r.c_pit, 'money': True},
                    {'label': _('Social insurance'), 'value': r.c_si, 'money': True},
                    {'label': _('Health insurance'), 'value': r.c_hi, 'money': True},
                    {'label': _('Unemployment insurance'), 'value': r.c_ui, 'money': True},
                    {'label': _('Loan / advance'), 'value': r.c_loan, 'money': True},
                    {'label': _('Other deductions'), 'value': r.c_other_ded, 'money': True},
                ]),
                self._section(_('Why it could not be worked out'), [
                    {'label': _('Reason'), 'value': r.pb_compute_issue or ''
                     if 'pb_compute_issue' in r._fields else ''},
                ]),
                self._section(_('Trace'), [
                    {'label': _('Salary structure'), 'value': _m2o(r.formula_config_id)},
                    {'label': _('Payroll batch'), 'value': _m2o(r.import_batch_id)},
                    {'label': _('Company'), 'value': _m2o(r.company_id)},
                ]),
            ] if s],
        }

    _ledger_key = 'fullfinal'

    # ------------------------------------------------------------ filter panel
    def _pbf_search_fields(self):
        return ['employee_id.name', 'employee_code', 'department_id.name', 'name']

    def _pbf_sorts(self):
        return [
            {'key': 'newest', 'label': _('Newest settlement first'),
             'order': 'settlement_date desc, id desc'},
            {'key': 'oldest', 'label': _('Oldest settlement first'),
             'order': 'settlement_date asc, id asc'},
            {'key': 'net', 'label': _('Biggest net payable first'),
             'order': 'net_payable desc, id desc'},
            {'key': 'name', 'label': _('Name, A to Z'), 'order': 'name asc, id asc'},
        ]

    def _pbf_spec(self):
        uid = self.env.uid
        return [
            # ---- pinned: where it is, where it came from, whose team
            self._sec_status([
                ('draft', _('Being prepared'), 'slate'),
                ('returned', _('Sent back to be fixed'), 'amber'),
                ('pending', _('Waiting for approval'), 'blue'),
                ('approved', _('Approved'), 'green'),
                ('rejected', _('Turned down'), 'rose'),
            ]),
            {'key': 'source', 'label': _('Source'), 'icon': 'upload',
             'group': 'other', 'type': 'selection', 'path': 'source', 'pinned': True},
            self._sec_department('department_id', pinned=True),
            # ---- more filters
            {'key': 'check', 'label': _('Checks'), 'icon': 'checkCheck',
             'group': 'pay', 'type': 'choice', 'requires': ['pb_to_check', 'pb_compute_issue'],
             'options': [
                 {'value': 'yes', 'label': _('Ready to check'), 'tone': 'amber',
                  'domain': [('pb_to_check', '=', True)]},
                 {'value': 'issue', 'label': _('Could not be worked out'), 'tone': 'rose',
                  'domain': [('pb_compute_issue', '!=', False),
                             ('state', 'in', ('draft', 'returned'))]},
                 {'value': 'no', 'label': _('Nothing to check'), 'tone': 'slate',
                  'domain': [('pb_to_check', '=', False), '|',
                             ('pb_compute_issue', '=', False),
                             ('state', 'not in', ('draft', 'returned'))]},
             ]},
            # "Mine" is the reader's own seat on the approval (a stored
            # many2many, so a literal domain does it — no Python fact)
            {'key': 'mine', 'label': _('Waiting on me'), 'icon': 'userCheck',
             'group': 'people', 'type': 'choice', 'requires': ['seat_user_ids', 'state'],
             'options': [
                 {'value': 'mine', 'label': _('Waiting on me'), 'tone': 'amber',
                  'domain': [('state', '=', 'pending'), ('seat_user_ids', 'in', [uid])]},
                 {'value': 'others', 'label': _('Waiting on someone else'), 'tone': 'slate',
                  'domain': [('state', '=', 'pending'), ('seat_user_ids', 'not in', [uid])]},
             ]},
            self._sec_scheme(),
            {'key': 'job', 'label': _('Job position'), 'icon': 'briefcase',
             'group': 'people', 'type': 'many2one', 'path': 'job_id',
             'none_label': _('No job position'), 'label_sudo': True},
            {'key': 'batch', 'label': _('Batch'), 'icon': 'database',
             'group': 'pay', 'type': 'many2one', 'path': 'import_batch_id',
             'none_label': _('Not from a batch')},
            {'key': 'money', 'label': _('Net payable'), 'icon': 'banknote',
             'group': 'pay', 'type': 'number', 'path': 'net_payable', 'unit': 'money'},
            {'key': 'when', 'label': _('Settled on'), 'icon': 'calendar',
             'group': 'dates', 'type': 'date', 'path': 'settlement_date', 'presets': PAST_DATES},
            {'key': 'approved_on', 'label': _('Approved on'), 'icon': 'calendarClock',
             'group': 'dates', 'type': 'date', 'path': 'approved_at', 'presets': 'past',
             'none_label': _('Not approved yet')},
            self._sec_company(),
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All settlements'), 'icon': 'layoutList', 'filters': {}},
            {'key': 'check', 'label': _('Ready to check'), 'filters': {'check': ['yes']}},
            {'key': 'mine', 'label': _('Waiting on me'), 'filters': {'mine': ['mine']}},
            {'key': 'approved_month', 'label': _('Approved this month'),
             'filters': {'approved_on': {'preset': 'this_month'}}},
            {'key': 'manual', 'label': _('Manual'), 'filters': {'source': ['manual']}},
        ]

    def _ledger_kpis(self, FF, dom):
        agg = FF.read_group(dom, ['net_payable:sum', 'total_earnings:sum', 'total_deductions:sum'], [])
        a = agg[0] if agg else {}
        total = FF.search_count(dom)
        kpis = [
            {'icon': 'fileText', 'value': total, 'label': _('Settlements')},
            {'icon': 'receipt', 'ic_tone': 'green', 'money': True, 'value': a.get('net_payable') or 0.0, 'label': _('Net payable')},
            {'icon': 'sigma', 'ic_tone': 'blue', 'money': True, 'value': a.get('total_earnings') or 0.0, 'label': _('Earnings')},
            {'icon': 'sigma', 'ic_tone': 'amber', 'money': True, 'value': a.get('total_deductions') or 0.0, 'label': _('Deductions')},
            # `facet`: pressing this figure narrows the rows the same way the
            # Source chip does (quiet board — a figure that can filter, does).
            {'icon': 'user', 'value': FF.search_count(dom + [('source', '=', 'manual')]), 'label': _('Manual'),
             'facet': ['source', 'manual']},
        ]
        # LEARN REFRESH step 6 — settlements the monthly load made are worked
        # out but not sent in: somebody looks first. This is that pile, and
        # pressing it narrows the rows to it (each offers Send for approval).
        has_check = 'pb_to_check' in FF._fields
        if has_check:
            kpis.insert(1, {'icon': 'checkCheck', 'value': FF.search_count(
                dom + [('pb_to_check', '=', True)]),
                'label': _('Ready to check'), 'tone': 'warn',
                'facet': ['check', 'yes']})
            issues = FF.search_count(dom + [('pb_compute_issue', '!=', False),
                                            ('state', 'in', ('draft', 'returned'))])
            if issues:
                kpis.insert(2, {'icon': 'alert', 'value': issues,
                                'label': _('Could not be worked out'),
                                'tone': 'err', 'facet': ['check', 'issue']})
        return kpis

    def _ledger_head(self, FF, dom):
        return {
            'title': _('Full & Final'),
            'subtitle': _('Every settlement, its components and net payable at a glance.'),
            'search_ph': _('Search employee, ID, department…'),
            'kpis': self._ledger_kpis(FF, dom),
            'steps': self._fnf_step_defs(FF),
            'list_action': 'pb_hr_fullandfinal.action_full_and_final_employees',
        }

    def _ledger_row_ctx(self, FF):
        return {'has_check': 'pb_to_check' in FF._fields, 'src_lbl': _sel(FF, 'source')}

    def _ledger_row(self, r, ctx):
        has_check, src_lbl = ctx['has_check'], ctx['src_lbl']
        e = r.employee_id
        sub = ' · '.join([x for x in [r.department_id.name if r.department_id else '',
                                      r.job_id.name if r.job_id else ''] if x]) or '—'
        issue = r.pb_compute_issue if has_check else ''
        check = ('issue' if issue and r.state in ('draft', 'returned')
                 else 'yes' if has_check and r.pb_to_check else 'no')
        badges = [{'label': src_lbl.get(r.source, r.source or '—'),
                   'tone': 'info' if r.source == 'auto' else 'muted'}]
        # What the row can do is what its state allows: a settlement is
        # printed once approved, sent in once checked, and one that could
        # not be worked out says so instead of offering a door that refuses.
        if check == 'issue':
            badges.append({'label': _('Could not be worked out'), 'tone': 'err'})
            action = False
        elif check == 'yes':
            badges.append({'label': _('Ready to check'), 'tone': 'warn'})
            action = {'label': _('Send for approval'), 'icon': 'send',
                      'method': 'action_pb_send_for_approval',
                      'done': _('Sent for approval')}
        elif r.state == 'approved' or 'state' not in r._fields:
            action = {'label': _('Download'), 'icon': 'download',
                      'method': 'action_download_full_and_final'}
        else:
            action = False
        return {
            'id': r.id, 'res_model': 'hr.full.final.settlement',
            'avatar': _emp_avatar(e), 'initials': _initials(e.name if e else r.name),
            'title': (e.name if e else r.name) or '—', 'subtitle': sub,
            'badges': badges,
            'note': issue or '',
            'metrics': [{'label': _('Net payable'), 'value': r.net_payable, 'money': True, 'strong': True, 'tone': 'ok'}],
            'action': action,
            '_f': {'source': r.source or '',
                   'check': check,
                   'state': r.state or '',
                   'dept': r.department_id.name if r.department_id else '',
                   'config': r.formula_config_id.name if r.formula_config_id else ''},
            '_s': ' '.join([x for x in [e.name if e else '', r.employee_code or '',
                                        r.department_id.name if r.department_id else ''] if x]),
            '_d': str(r.settlement_date) if r.settlement_date else '',
        }

    @api.model
    def get_data(self):
        """The old one-shot descriptor (newest 400 rows, facets from them).
        The screen reads `get_head` + `get_page` now; this stays for the
        callers that still read it (tests, ruling R4)."""
        FF = self.env['hr.full.final.settlement']
        dom = self._co_dom()
        cur = self._grid_symbol(FF, dom)
        total = FF.search_count(dom)
        recs = FF.search(dom, order='settlement_date desc, id desc', limit=LIMIT)
        kpis = self._ledger_kpis(FF, dom)
        steps = self._fnf_steps(FF, dom)
        ctx = self._ledger_row_ctx(FF)
        rows = [self._ledger_row(r, ctx) for r in recs]
        facets = [
            _sel_facet(FF, 'source', _('Source'), 'source'),
            _rows_facet(rows, 'dept', _('Department')),
            _rows_facet(rows, 'config', _('Salary structure')),
        ]
        return {
            'title': _('Full & Final'), 'subtitle': _('Every settlement, its components and net payable at a glance.'),
            'search_ph': _('Search employee, ID, department…'), 'empty': _('No settlements match these filters.'),
            'currency': cur, 'date': True, 'kpis': kpis, 'facets': facets,
            'steps': steps,
            'rows': rows, 'total': total,
            'list_action': 'pb_hr_fullandfinal.action_full_and_final_employees',
        }

    # A settlement travels one route: prepared, sent in, approved. Each state
    # belongs to EXACTLY one step, so the counts add up; "Sent back" is back
    # with the people preparing it, and "Turned down" is an outcome at no
    # step. Counted over the whole scope, not only the rows loaded.
    FNF_STEPS = (
        ('prepare', ('draft', 'returned')),
        ('pending', ('pending',)),
        ('approved', ('approved',)),
    )

    @api.model
    def _fnf_step_defs(self, FF):
        """The three steps without counts: the filter panel counts them for
        whatever else is filtered (ruling R1), from its "Where it is" section."""
        if 'state' not in FF._fields:
            return {}
        titles = {'prepare': _('Being prepared'),
                  'pending': _('Waiting for approval'),
                  'approved': _('Approved')}
        return {'unit': 'settlement',
                'items': [{'key': key, 'title': titles[key], 'states': list(states)}
                          for key, states in self.FNF_STEPS]}

    @api.model
    def _fnf_steps(self, FF, dom):
        if 'state' not in FF._fields:
            return {}
        try:
            counts = {}
            for state, n in FF._read_group(dom, ['state'], ['__count']):
                counts[state] = n
            uid = self.env.uid
            mine = 0
            if 'seat_user_ids' in FF._fields:
                mine = FF.search_count(dom + [('state', '=', 'pending'),
                                              ('seat_user_ids', 'in', [uid])])
            # Our own words, not the state field's labels: the step titles
            # are this screen's, and the words are the same in English
            # (LEARN REFRESH step 6 — they now reach Vietnamese).
            titles = {'prepare': _('Being prepared'),
                      'pending': _('Waiting for approval'),
                      'approved': _('Approved')}
            ready = (FF.search_count(dom + [('pb_to_check', '=', True)])
                     if 'pb_to_check' in FF._fields else 0)
            items = []
            for key, states in self.FNF_STEPS:
                n = sum(counts.get(st, 0) for st in states)
                items.append({
                    'key': key, 'title': titles[key], 'states': list(states),
                    'count': n,
                    'waiting': n if key == 'pending' else 0,
                    'mine': mine if key == 'pending' else 0,
                    'returned': counts.get('returned', 0) if key == 'prepare' else 0,
                    'ready': ready if key == 'prepare' else 0,
                })
            return {'unit': 'settlement', 'items': items}
        except Exception as e:
            _logger.debug("Full & Final steps failed: %s", e)
            return {}


class PbProration(models.AbstractModel):
    _name = 'pb.proration'
    _inherit = 'pb.ledger.mixin'
    _description = 'Proration Audit cockpit data'
    _detail_model = 'hr.payroll.proration.line'

    def _build_detail(self, r):
        PLM = self.env[self._detail_model]
        basis = _sel(PLM, 'proration_basis')
        state = _sel(PLM, 'state')
        e = r.employee_id
        return {
            'title': e.name if e else '—',
            'subtitle': r.component_id.name if r.component_id else '',
            'sections': [s for s in [
                self._section(_('Who'), [
                    {'label': _('Employee'), 'value': e.name if e else ''},
                    {'label': _('Contract'), 'value': _m2o(r.contract_id)},
                    {'label': _('Status'), 'value': state.get(r.state, r.state or '')},
                ]),
                self._section(_('Component'), [
                    {'label': _('Component'), 'value': _m2o(r.component_id)},
                    {'label': _('Code'), 'value': r.component_code or ''},
                    {'label': _('Configuration'), 'value': _m2o(r.formula_config_id)},
                ]),
                self._section(_('Period'), [
                    {'label': _('Effective date'), 'value': _d(r.effective_date)},
                    {'label': _('Period'), 'value': ' → '.join(
                        [x for x in [_d(r.date_from), _d(r.date_to)] if x])},
                    {'label': _('Basis'), 'value': basis.get(r.proration_basis,
                                                          r.proration_basis or '')},
                    {'label': _('Period days'), 'value': r.period_days},
                    {'label': _('Old days'), 'value': r.old_days},
                    {'label': _('New days'), 'value': r.new_days},
                ]),
                self._section(_('Money'), [
                    {'label': _('Old amount'), 'value': r.old_amount, 'money': True},
                    {'label': _('New amount'), 'value': r.new_amount, 'money': True},
                    {'label': _('Prorated'), 'value': r.prorated_amount, 'money': True,
                     'strong': True, 'tone': 'ok'},
                ]),
                self._section(_('Trace'), [
                    {'label': _('Import batch'), 'value': _m2o(r.import_batch_id)},
                    {'label': _('Change reference'), 'value': _m2o(r.advantage_change_id)},
                    {'label': _('Segments'), 'value': r.segment_summary or '', 'wrap': True},
                ]),
            ] if s],
        }

    _ledger_key = 'proration'

    # ------------------------------------------------------------ filter panel
    def _pbf_search_fields(self):
        return ['employee_id.name', 'component_id.name', 'component_code']

    def _pbf_sorts(self):
        return [
            {'key': 'newest', 'label': _('Latest period first'), 'order': 'date_from desc, id desc'},
            {'key': 'oldest', 'label': _('Earliest period first'), 'order': 'date_from asc, id asc'},
            {'key': 'amount', 'label': _('Biggest prorated amount first'),
             'order': 'prorated_amount desc, id desc'},
        ]

    def _pbf_spec(self):
        return [
            # ---- pinned: the questions "answer one person" asks (Learn)
            self._sec_component(pinned=True),
            {'key': 'batch', 'label': _('Batch'), 'icon': 'database',
             'group': 'pay', 'type': 'many2one', 'path': 'import_batch_id', 'pinned': True,
             'none_label': _('Not from a batch')},
            self._sec_status([('draft', _('Still draft'), 'slate'),
                              ('posted', _('Posted'), 'green')]),
            # ---- more filters
            self._sec_department('employee_id.department_id'),
            self._sec_scheme(),
            {'key': 'basis', 'label': _('Counted by'), 'icon': 'calculator',
             'group': 'pay', 'type': 'selection', 'path': 'proration_basis'},
            {'key': 'money', 'label': _('Prorated amount'), 'icon': 'banknote',
             'group': 'pay', 'type': 'number', 'path': 'prorated_amount', 'unit': 'money'},
            {'key': 'when', 'label': _('Effective'), 'icon': 'calendar',
             'group': 'dates', 'type': 'date', 'path': 'effective_date', 'presets': 'past',
             'none_label': _('No date')},
            self._sec_company(),
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All lines'), 'icon': 'layoutList', 'filters': {}},
            {'key': 'posted_month', 'label': _('Posted this month'),
             'filters': {'status': ['posted'], 'when': {'preset': 'this_month'}}},
            {'key': 'draft', 'label': _('Still draft'), 'filters': {'status': ['draft']}},
        ]

    def _ledger_kpis(self, PL, dom):
        total = PL.search_count(dom)
        agg = PL.read_group(dom, ['prorated_amount:sum'], [])
        pro = (agg[0].get('prorated_amount') if agg else 0.0) or 0.0
        return [
            {'icon': 'sigma', 'value': total, 'label': _('Proration lines')},
            {'icon': 'users', 'ic_tone': 'blue', 'value': self._distinct(PL, dom, 'employee_id'), 'label': _('Employees')},
            {'icon': 'receipt', 'ic_tone': 'green', 'money': True, 'value': pro, 'label': _('Total prorated')},
            {'icon': 'layers', 'ic_tone': 'amber', 'value': self._distinct(PL, dom, 'import_batch_id'), 'label': _('Batches')},
        ]

    def _ledger_head(self, PL, dom):
        return {
            'title': _('Proration Audit'),
            'subtitle': _('Every prorated component, old → new → prorated, per employee.'),
            'search_ph': _('Search employee or component…'),
            'kpis': self._ledger_kpis(PL, dom),
            'list_action': 'pb_hr_payroll_formula.action_payroll_proration_line',
        }

    def _ledger_row_ctx(self, PL):
        return {'st_lbl': _sel(PL, 'state')}

    def _ledger_row(self, r, ctx):
        st_lbl = ctx['st_lbl']
        e = r.employee_id
        return {
            'id': r.id, 'res_model': 'hr.payroll.proration.line',
            'avatar': _emp_avatar(e), 'initials': _initials(e.name if e else ''),
            'title': e.name if e else '—',
            'subtitle': r.component_id.name if r.component_id else '—',
            'code': r.component_code or (r.component_id.code if r.component_id else ''),
            'badges': [{'label': st_lbl.get(r.state) or (r.state or '').title(), 'tone': 'ok' if r.state == 'posted' else 'muted'}],
            'metrics': [
                {'label': _('Old'), 'value': r.old_amount, 'money': True},
                {'label': _('New'), 'value': r.new_amount, 'money': True},
                {'label': _('Prorated'), 'value': r.prorated_amount, 'money': True, 'strong': True, 'tone': 'ok'},
            ],
            '_f': {'state': r.state or '',
                   'component': r.component_id.name if r.component_id else '',
                   'config': r.formula_config_id.name if r.formula_config_id else '',
                   'batch': r.import_batch_id.name if r.import_batch_id else ''},
            '_s': ' '.join([x for x in [e.name if e else '', r.component_id.name if r.component_id else '',
                                        r.component_code or ''] if x]),
            '_d': str(r.effective_date) if r.effective_date else '',
        }

    @api.model
    def get_data(self):
        """The old one-shot descriptor; the screen reads get_head + get_page (R4)."""
        PL = self.env['hr.payroll.proration.line']
        dom = self._co_dom()
        cur = self._grid_symbol(PL, dom)
        total = PL.search_count(dom)
        recs = PL.search(dom, order='date_from desc, id desc', limit=LIMIT)
        kpis = self._ledger_kpis(PL, dom)
        ctx = self._ledger_row_ctx(PL)
        rows = [self._ledger_row(r, ctx) for r in recs]
        facets = [
            _sel_facet(PL, 'state', _('Status'), 'state'),
            _rows_facet(rows, 'component', _('Component')),
            _rows_facet(rows, 'config', _('Configuration')),
            _rows_facet(rows, 'batch', _('Batch')),
        ]
        return {
            'title': _('Proration Audit'), 'subtitle': _('Every prorated component, old → new → prorated, per employee.'),
            'search_ph': _('Search employee or component…'), 'empty': _('No proration lines match these filters.'),
            'currency': cur, 'date': True, 'kpis': kpis, 'facets': facets,
            'rows': rows, 'total': total,
            'list_action': 'pb_hr_payroll_formula.action_payroll_proration_line',
        }


class PbRetro(models.AbstractModel):
    _name = 'pb.retro'
    _inherit = 'pb.ledger.mixin'
    _description = 'Retro Adjustments cockpit data'
    _detail_model = 'hr.payroll.retro.adjustment'

    def _build_detail(self, r):
        state = _sel(self.env[self._detail_model], 'state')
        e = r.employee_id
        delta = r.delta_amount or 0.0
        return {
            'title': e.name if e else '—',
            'subtitle': r.component_id.name if r.component_id else '',
            'sections': [s for s in [
                self._section(_('Who'), [
                    {'label': _('Employee'), 'value': e.name if e else ''},
                    {'label': _('Contract'), 'value': _m2o(r.contract_id)},
                    {'label': _('Status'), 'value': state.get(r.state, r.state or '')},
                ]),
                self._section(_('Component'), [
                    {'label': _('Component'), 'value': _m2o(r.component_id)},
                    {'label': _('Code'), 'value': r.component_code or ''},
                    {'label': _('Configuration'), 'value': _m2o(r.formula_config_id)},
                ]),
                self._section(_('Period'), [
                    {'label': _('Retro period'), 'value': ' → '.join(
                        [x for x in [_d(r.period_from), _d(r.period_to)] if x])},
                    {'label': _('Change effective'), 'value': _d(r.change_effective_date)},
                ]),
                self._section(_('Money'), [
                    {'label': _('Old amount'), 'value': r.old_amount, 'money': True},
                    {'label': _('New amount'), 'value': r.new_amount, 'money': True},
                    {'label': _('Delta'), 'value': delta, 'money': True, 'strong': True,
                     'tone': 'ok' if delta >= 0 else 'warn'},
                ]),
                self._section(_('Trace'), [
                    {'label': _('Applied in batch'), 'value': _m2o(r.applied_in_batch_id)},
                    {'label': _('Applied in payslip'), 'value': _m2o(r.applied_in_payslip_id)},
                    {'label': _('Original payslip'), 'value': _m2o(r.original_payslip_id)},
                    {'label': _('Change reference'), 'value': _m2o(r.advantage_change_id)},
                ]),
            ] if s],
        }

    _ledger_key = 'retro'

    # ------------------------------------------------------------ filter panel
    def _pbf_search_fields(self):
        return ['employee_id.name', 'component_id.name', 'component_code']

    def _pbf_sorts(self):
        return [
            {'key': 'newest', 'label': _('Latest period first'), 'order': 'period_from desc, id desc'},
            {'key': 'oldest', 'label': _('Earliest period first'), 'order': 'period_from asc, id asc'},
            {'key': 'delta', 'label': _('Biggest change first'), 'order': 'delta_amount desc, id desc'},
            {'key': 'delta_low', 'label': _('Biggest cut first'), 'order': 'delta_amount asc, id desc'},
        ]

    def _pbf_spec(self):
        return [
            # ---- pinned: the same three questions as the Proration Audit
            self._sec_component(pinned=True),
            {'key': 'batch', 'label': _('Applied in batch'), 'icon': 'database',
             'group': 'pay', 'type': 'many2one', 'path': 'applied_in_batch_id', 'pinned': True,
             'none_label': _('Not applied yet')},
            self._sec_status([('draft', _('Still draft'), 'slate'),
                              ('posted', _('Posted'), 'green'),
                              ('cancelled', _('Cancelled'), 'rose')]),
            # ---- more filters
            self._sec_department('employee_id.department_id'),
            self._sec_scheme(),
            {'key': 'direction', 'label': _('Up or down'), 'icon': 'arrowUpDown',
             'group': 'pay', 'type': 'choice', 'requires': ['delta_amount'],
             'options': [
                 {'value': 'up', 'label': _('Pay goes up'), 'tone': 'green',
                  'domain': [('delta_amount', '>', 0)]},
                 {'value': 'down', 'label': _('Pay goes down'), 'tone': 'amber',
                  'domain': [('delta_amount', '<', 0)]},
                 {'value': 'zero', 'label': _('No change'), 'tone': 'slate',
                  'domain': [('delta_amount', '=', 0)]},
             ]},
            {'key': 'money', 'label': _('Delta'), 'icon': 'banknote',
             'group': 'pay', 'type': 'number', 'path': 'delta_amount', 'unit': 'money'},
            {'key': 'when', 'label': _('Period start'), 'icon': 'calendar',
             'group': 'dates', 'type': 'date', 'path': 'period_from', 'presets': PAST_DATES},
            self._sec_company(),
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All adjustments'), 'icon': 'layoutList', 'filters': {}},
            {'key': 'posted_month', 'label': _('Posted this month'),
             'filters': {'status': ['posted'], 'when': {'preset': 'this_month'}}},
            {'key': 'draft', 'label': _('Still draft'), 'filters': {'status': ['draft']}},
            {'key': 'cancelled', 'label': _('Cancelled'), 'filters': {'status': ['cancelled']}},
        ]

    def _ledger_kpis(self, RA, dom):
        total = RA.search_count(dom)
        agg = RA.read_group(dom, ['delta_amount:sum'], [])
        delta = (agg[0].get('delta_amount') if agg else 0.0) or 0.0
        return [
            {'icon': 'sigma', 'value': total, 'label': _('Retro lines')},
            {'icon': 'users', 'ic_tone': 'blue', 'value': self._distinct(RA, dom, 'employee_id'), 'label': _('Employees')},
            {'icon': 'receipt', 'ic_tone': 'green' if delta >= 0 else 'amber', 'money': True, 'value': delta, 'label': _('Total delta')},
            {'icon': 'layers', 'ic_tone': 'amber', 'value': self._distinct(RA, dom, 'applied_in_batch_id'), 'label': _('Batches')},
        ]

    def _ledger_head(self, RA, dom):
        return {
            'title': _('Retro Adjustments'),
            'subtitle': _('Retroactive deltas, old → new → delta, per employee.'),
            'search_ph': _('Search employee or component…'),
            'kpis': self._ledger_kpis(RA, dom),
            'list_action': 'pb_hr_payroll_formula.action_payroll_retro_adjustment',
        }

    def _ledger_row_ctx(self, RA):
        return {'st_lbl': _sel(RA, 'state')}

    def _ledger_row(self, r, ctx):
        st_lbl = ctx['st_lbl']
        e = r.employee_id
        return {
            'id': r.id, 'res_model': 'hr.payroll.retro.adjustment',
            'avatar': _emp_avatar(e), 'initials': _initials(e.name if e else ''),
            'title': e.name if e else '—',
            'subtitle': r.component_id.name if r.component_id else '—',
            'code': r.component_code or (r.component_id.code if r.component_id else ''),
            'badges': [{'label': st_lbl.get(r.state) or (r.state or '').title(),
                        'tone': 'ok' if r.state == 'posted' else ('warn' if r.state == 'cancelled' else 'muted')}],
            'metrics': [
                {'label': _('Old'), 'value': r.old_amount, 'money': True},
                {'label': _('New'), 'value': r.new_amount, 'money': True},
                {'label': _('Delta'), 'value': r.delta_amount, 'money': True, 'strong': True,
                 'tone': 'ok' if (r.delta_amount or 0) >= 0 else 'warn'},
            ],
            '_f': {'state': r.state or '',
                   'component': r.component_id.name if r.component_id else '',
                   'config': r.formula_config_id.name if r.formula_config_id else '',
                   'batch': r.applied_in_batch_id.name if r.applied_in_batch_id else ''},
            '_s': ' '.join([x for x in [e.name if e else '', r.component_id.name if r.component_id else '',
                                        r.component_code or ''] if x]),
            '_d': str(r.period_from) if r.period_from else '',
        }

    @api.model
    def get_data(self):
        """The old one-shot descriptor; the screen reads get_head + get_page (R4)."""
        RA = self.env['hr.payroll.retro.adjustment']
        dom = self._co_dom()
        cur = self._grid_symbol(RA, dom)
        total = RA.search_count(dom)
        recs = RA.search(dom, order='period_from desc, id desc', limit=LIMIT)
        kpis = self._ledger_kpis(RA, dom)
        ctx = self._ledger_row_ctx(RA)
        rows = [self._ledger_row(r, ctx) for r in recs]
        facets = [
            _sel_facet(RA, 'state', _('Status'), 'state'),
            _rows_facet(rows, 'component', _('Component')),
            _rows_facet(rows, 'config', _('Configuration')),
            _rows_facet(rows, 'batch', _('Applied batch')),
        ]
        return {
            'title': _('Retro Adjustments'), 'subtitle': _('Retroactive deltas, old → new → delta, per employee.'),
            'search_ph': _('Search employee or component…'), 'empty': _('No retro adjustments match these filters.'),
            'currency': cur, 'date': True, 'kpis': kpis, 'facets': facets,
            'rows': rows, 'total': total,
            'list_action': 'pb_hr_payroll_formula.action_payroll_retro_adjustment',
        }
