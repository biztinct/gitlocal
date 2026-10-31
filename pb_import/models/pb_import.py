# -*- coding: utf-8 -*-
import logging
from odoo import _, api, models

_logger = logging.getLogger(__name__)

#: Batches per page on the filter panel's list (FILTER W6; the old cap was 20).
PAGE_SIZE = 60
#: A batch somewhere between "file read" and "committed".
IN_PROGRESS = ['loaded', 'matched', 'validated', 'processing']
#: "Needs attention": stopped with an error, or some lines could not be read.
ATTENTION = ['|', ('state', '=', 'error'), ('error_lines', '>', 0)]

# Batch lifecycle — ordered pipeline + terminal/exception states.
STATE_LABEL = {
    'draft': 'Draft', 'loaded': 'Loaded', 'matched': 'Matched',
    'validated': 'Validated', 'processing': 'Processing', 'done': 'Done',
    'error': 'Error', 'cancelled': 'Cancelled',
}
PIPELINE = ['draft', 'loaded', 'matched', 'validated', 'processing', 'done']

SOURCE_LABEL = {
    'excel': 'Excel / CSV',
    'api_data_store': 'API store', 'manual': 'Manual',
}
# IA Cycle 3 — the one-door law. `pb_hr_payroll_formula.action_integration_
# connector` used to be a launch tile here: a raw `list,form` on
# hr.integration.connector, sitting beside two guided wizards and looking like
# one of them. It is gone, along with the Connectors KPI and the Connectors
# panel below. Connectors have exactly ONE home now (Settings · Integrations),
# and Import reaches it through a back-chipped deep link — the same cockpit, and
# for the first time the same way back.
#
# The action itself is untouched and still registered: this cycle replaces the
# DOORS, not the models behind them.
# JOURNEY J2 — every label here says WHAT MOVES and WHEN you use it.
# "Multi-sheet Excel" and "Import Formula Config" set a scheme's columns up
# once; only the hero button loads a period's numbers. Read as a set, the old
# labels made four one-off setup acts look like four ways to do payroll.
#
# The primary tuple is retargeted at `action_payroll_load_pay_data` (the guided
# flow) rather than the raw batch form. Note it is not RENDERED today — the
# cockpit's hero CTA is hard-wired to the wizard and `secondaryLaunches` filters
# `primary` out — so this is correctness for the day something renders it, not
# a live door. Nothing was removed; see MJ8.
LAUNCH_CANDIDATES = [
    ('pb_hr_payroll_formula.action_payroll_load_pay_data',
     'Load Pay Data', 'This period’s numbers — upload, review matches, commit', 'upload', True),
    # RD54 — the same load with no upload. It was always possible and had no
    # door: the reference tenant's only load read the connected system, and
    # nobody ran a second one because every button started on a file.
    ('pb_hr_payroll_formula.action_payroll_load_from_feed',
     'Load From Connected System',
     'This period’s numbers straight from the connected system — no file to upload',
     'cloud-download', False),
    ('pb_import_advanced.action_pb_multisheet_wizard',
     'Set up columns from Excel', 'One-off setup: turn a workbook’s columns into scheme components', 'table', False),
    ('pb_import_advanced.action_pb_employee_wizard',
     'Import Employees', 'Create employee records from a file or a connected system', 'users', False),
    ('pb_import_advanced.action_pb_formula_wizard',
     'Set up a scheme from a file', 'One-off setup: load rules from a salary structure or file', 'function', False),
]


class PbImport(models.AbstractModel):
    _name = 'pb.import'
    _inherit = ['pb.filter.mixin']
    _description = 'Payobook Import cockpit data'

    # ============================================================ filter panel
    # FILTER W6 (2026-10-31): the batch list moved onto the shared filter
    # panel. It used to load the newest 20 batches and filter those in the
    # browser while the numbers above counted every batch ("Errors 3" over a
    # list that held one). Now everything is counted and paged on the server.
    # `get_import_data` still returns its 20 rows: the Learn facade
    # (import_learn.py) reads them (ruling R4).

    def _pbf_model(self):
        return 'hr.payroll.import.batch'

    def _pbf_screen(self):
        return 'import'

    def _pbf_base_domain(self):
        co_ids = self.env.companies.ids or [self.env.company.id]
        return [('company_id', 'in', co_ids)]

    def _pbf_search_fields(self):
        return ['name', 'import_filename', 'formula_config_id.name', 'connector_id.name']

    def _pbf_sorts(self):
        return [
            {'key': 'newest', 'label': _('Newest first'), 'order': 'create_date desc, id desc'},
            {'key': 'oldest', 'label': _('Oldest first'), 'order': 'create_date asc, id asc'},
            {'key': 'period', 'label': _('Latest pay period first'),
             'order': 'date_from desc nulls last, id desc'},
            {'key': 'errors', 'label': _('Most problem lines first'),
             'order': 'error_lines desc, create_date desc, id desc'},
            {'key': 'name', 'label': _('Name, A to Z'), 'order': 'name asc, id asc'},
        ]

    def _pbf_spec(self):
        st = lambda key, label, tone: {  # noqa: E731 — one option per pipeline state
            'value': key, 'label': label, 'tone': tone, 'domain': [('state', '=', key)]}
        return [
            # ---- pinned: where is it, where did it come from, which period
            {'key': 'state', 'label': _('Where it is'), 'icon': 'gitBranch',
             'group': 'other', 'type': 'choice', 'pinned': True, 'requires': ['state'],
             # the same six words as the steps above, then the two dead ends
             'options': [
                 st('draft', _('Draft'), 'slate'),
                 st('loaded', _('Loaded'), 'blue'),
                 st('matched', _('Matched'), 'blue'),
                 st('validated', _('Validated'), 'blue'),
                 st('processing', _('Processing'), 'blue'),
                 st('done', _('Done'), 'green'),
                 st('error', _('Stopped with an error'), 'rose'),
                 st('cancelled', _('Cancelled'), 'slate'),
             ]},
            {'key': 'source', 'label': _('Where the data came from'), 'icon': 'upload',
             'group': 'other', 'type': 'choice', 'pinned': True, 'requires': ['source_type'],
             'options': [
                 {'value': 'excel', 'label': _('A file (Excel or CSV)'), 'tone': 'blue',
                  'domain': [('source_type', '=', 'excel')]},
                 {'value': 'api', 'label': _('The connected system'), 'tone': 'blue',
                  'domain': [('source_type', '=', 'api_data_store')]},
                 {'value': 'manual', 'label': _('Typed in'), 'tone': 'slate',
                  'domain': [('source_type', '=', 'manual')]},
             ]},
            {'key': 'period', 'label': _('Pay period starts'), 'icon': 'calendar',
             'group': 'dates', 'type': 'date', 'path': 'date_from', 'pinned': True,
             'presets': 'past', 'none_label': _('No period set')},
            # ---- more filters
            {'key': 'errors', 'label': _('Problems'), 'icon': 'triangleAlert',
             'group': 'other', 'type': 'choice', 'requires': ['state', 'error_lines'],
             'help': _('Needs attention means it stopped with an error, or some lines could not be read.'),
             'options': [
                 {'value': 'attention', 'label': _('Needs attention'), 'tone': 'rose',
                  'domain': ATTENTION},
                 {'value': 'clean', 'label': _('No problems'), 'tone': 'green',
                  'domain': [('state', '!=', 'error'), ('error_lines', '=', 0)]},
             ]},
            {'key': 'scheme', 'label': _('Pay scheme'), 'icon': 'sigma',
             'group': 'pay', 'type': 'many2one', 'path': 'formula_config_id',
             'none_label': _('No pay scheme')},
            {'key': 'connector', 'label': _('Connected system'), 'icon': 'plug',
             'group': 'other', 'type': 'many2one', 'path': 'connector_id',
             'none_label': _('None (a file or typed in)')},
            {'key': 'run', 'label': _('Pay run'), 'icon': 'play',
             'group': 'pay', 'type': 'choice', 'requires': ['payslip_run_id'],
             'options': [
                 {'value': 'yes', 'label': _('Pay run made'), 'tone': 'green',
                  'domain': [('payslip_run_id', '!=', False)]},
                 {'value': 'no', 'label': _('No pay run yet'), 'tone': 'slate',
                  'domain': [('payslip_run_id', '=', False)]},
             ]},
            {'key': 'one_time', 'label': _('Use once'), 'icon': 'repeat',
             'group': 'pay', 'type': 'choice', 'requires': ['one_time'],
             'help': _('A file used once feeds that pay run only; nothing is saved to the employee records.'),
             'options': [
                 {'value': 'yes', 'label': _('Used once, nothing saved'), 'tone': 'amber',
                  'domain': [('one_time', '=', True)]},
                 {'value': 'no', 'label': _('Saved to the records'), 'tone': 'slate',
                  'domain': [('one_time', '=', False)]},
             ]},
            {'key': 'company', 'label': _('Company'), 'icon': 'landmark',
             'group': 'other', 'type': 'many2one', 'path': 'company_id'},
            {'key': 'country', 'label': _('Country'), 'icon': 'globe',
             'group': 'other', 'type': 'selection', 'path': 'country_code',
             'none_label': _('Not set')},
            {'key': 'created', 'label': _('Started'), 'icon': 'clock',
             'group': 'dates', 'type': 'date', 'path': 'create_date', 'presets': 'past'},
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All batches'), 'icon': 'layoutList', 'filters': {}},
            {'key': 'attention', 'label': _('Needs attention'), 'filters': {'errors': ['attention']}},
            {'key': 'progress', 'label': _('In progress'), 'filters': {'state': list(IN_PROGRESS)}},
            {'key': 'done_month', 'label': _('Done this month'),
             'filters': {'state': ['done'], 'created': {'preset': 'this_month'}}},
            {'key': 'drafts', 'label': _('Drafts'), 'filters': {'state': ['draft']}},
        ]

    @api.model
    def _batch_row(self, b):
        st = b.state
        return {
            'id': b.id,
            'name': b.name or '—',
            'state': st,
            'state_label': STATE_LABEL.get(st, st or '—'),
            'step': (PIPELINE.index(st) + 1) if st in PIPELINE else 0,
            'source': SOURCE_LABEL.get(b.source_type, b.source_type or '—'),
            'total_lines': b.total_lines or 0,
            'matched': b.matched_employees or 0,
            'new': b.new_employees or 0,
            'errors': b.error_lines or 0,
            'date': str(b.create_date or '')[:10],
        }

    @api.model
    def get_batch_page(self, filters=None, search=None, sort=None, offset=0, limit=PAGE_SIZE):
        """One page of batches for the filter panel's current state."""
        if 'hr.payroll.import.batch' not in self.env:
            return {'rows': [], 'total': 0, 'offset': 0}
        Batch = self.env['hr.payroll.import.batch']
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        domain = self.pbf_domain(filters or {}, search)
        recs = Batch.search(domain, order=self.pbf_order(sort) or 'create_date desc, id desc',
                            offset=offset, limit=limit)
        rows = []
        for b in recs:
            try:
                rows.append(self._batch_row(b))
            except Exception as e:  # noqa: BLE001 — one bad row never blanks the list
                _logger.debug("Import batch row failed: %s", e)
        return {'rows': rows, 'total': Batch.search_count(domain), 'offset': offset}

    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug("Import metric failed: %s", e)
            return default

    @api.model
    def _sc4_lane_availability(self):
        """`{'excel': bool, 'api': bool}` — does ANY active scheme still allow
        the lane? Defaults to True on databases that predate the setting."""
        out = {'excel': True, 'api': True}
        try:
            Config = self.env.get('hr.formula.config')
            if Config is None or 'source_excel_enabled' not in Config._fields:
                return out
            configs = Config.sudo().search([('state', '!=', 'archived')])
            if not configs:
                return out
            out['excel'] = any(c.source_excel_enabled for c in configs)
            out['api'] = any(c.source_api_enabled for c in configs)
        except Exception as e:      # noqa: BLE001 — doors, never the cockpit
            _logger.debug("SC-4 lane availability failed: %s", e)
        return out

    @api.model
    def get_import_data(self):
        company = self.env.company
        co_ids = self.env.companies.ids or [company.id]
        DOM = [('company_id', 'in', co_ids)]

        # ---------- batches ----------
        batches = []
        state_counts = {k: 0 for k in STATE_LABEL}
        total_batches = 0
        if 'hr.payroll.import.batch' in self.env:
            Batch = self.env['hr.payroll.import.batch']
            total_batches = self._safe(lambda: Batch.search_count(DOM))
            try:
                for g in Batch.read_group(DOM, ['state'], ['state']):
                    st = g.get('state')
                    if st in state_counts:
                        state_counts[st] = g.get('state_count') or g.get('__count') or 0
            except Exception:
                pass
            try:
                recs = Batch.search_read(
                    DOM,
                    ['name', 'state', 'source_type', 'date_from', 'date_to',
                     'total_lines', 'matched_employees', 'new_employees',
                     'error_lines', 'create_date'],
                    order='create_date desc, id desc', limit=20)
                for r in recs:
                    st = r.get('state')
                    batches.append({
                        'id': r['id'],
                        'name': r.get('name') or '—',
                        'state': st,
                        'state_label': STATE_LABEL.get(st, st or '—'),
                        'step': (PIPELINE.index(st) + 1) if st in PIPELINE else 0,
                        'source': SOURCE_LABEL.get(r.get('source_type'), r.get('source_type') or '—'),
                        'total_lines': r.get('total_lines') or 0,
                        'matched': r.get('matched_employees') or 0,
                        'new': r.get('new_employees') or 0,
                        'errors': r.get('error_lines') or 0,
                        'date': str(r.get('create_date') or '')[:10],
                    })
            except Exception as e:
                _logger.debug("Import batch list failed: %s", e)

        done = state_counts.get('done', 0)
        errors = state_counts.get('error', 0)
        in_progress = sum(state_counts.get(s, 0)
                          for s in ('draft', 'loaded', 'matched', 'validated', 'processing'))

        # ---------- connectors ----------
        # NOT a list any more — a COUNT, and only so the deep link can say how
        # many are over there ("Manage connectors · 31"). Reading 24 connector
        # rows to render a panel this cockpit no longer owns would be work done
        # for a surface that is gone. `has_connectors` is separate from the
        # number because a database with the model but no rows is a real state
        # and "0" is a fact, not a missing key (W45).
        connectors = 0
        has_model = 'hr.integration.connector' in self.env
        if has_model:
            connectors = self._safe(
                lambda: self.env['hr.integration.connector'].search_count([]))

        # ---------- launch buttons ----------
        # SC-4 — a door is offered only when SOME active scheme still allows
        # its lane. The pay-data upload hides when every scheme has switched
        # spreadsheets off; the connected-system load hides when every scheme
        # has switched the connected system off. Setup wizards (columns from
        # Excel, scheme from a file) stay: they build schemes, they are not a
        # pay-run source.
        lane_doors = {
            'pb_hr_payroll_formula.action_payroll_load_pay_data': 'excel',
            'pb_hr_payroll_formula.action_payroll_load_from_feed': 'api',
        }
        allowed = self._sc4_lane_availability()
        launches = []
        for xmlid, label, desc, icon, primary in LAUNCH_CANDIDATES:
            lane = lane_doors.get(xmlid)
            if lane and not allowed.get(lane, True):
                continue
            try:
                if self.env.ref(xmlid, raise_if_not_found=False):
                    launches.append({'xmlid': xmlid, 'label': label, 'desc': desc,
                                     'icon': icon, 'primary': primary})
            except Exception:
                continue

        return {
            'company': company.name,
            'kpis': {
                'total_batches': total_batches, 'done': done,
                'in_progress': in_progress, 'errors': errors,
            },
            'pipeline': [{'key': s, 'label': STATE_LABEL[s],
                          'count': state_counts.get(s, 0)} for s in PIPELINE],
            'batches': batches,
            'connectors': connectors,
            'has_connectors': has_model,
            'launches': launches,
        }
