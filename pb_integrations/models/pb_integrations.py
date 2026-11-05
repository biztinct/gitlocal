# -*- coding: utf-8 -*-
"""The Integrations cockpit's data — the board, and the three ledgers that
replaced its raw-list satellites.

IA Cycle 3 (the one-door law): this board used to end in three link tiles that
opened `list,form` act_windows on `hr.integration.field.mapping`,
`hr.api.data.store` and `hr.api.transformation.rule`. Three clicks, three exits
from the Payobook skin into Odoo's own chrome, and no way back except the
browser button. They are now IN this cockpit — a Data view with a tab strip, a
grid, and a 320px drawer on row click.

The actions themselves are untouched and still registered. This cycle replaces
the DOORS, not the models: hidden menus and any other caller keep working, and
nothing here deletes a record type.

Read with the CALLER's own rights throughout — no sudo anywhere in this file. If
the user could open the list, they can open the ledger; if they could not, the
ledger is exactly as empty as the list would have been (W12).
"""
import json
import logging

from odoo import _, api, fields, models
from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)

TYPE_LABEL = {
    'zoho': 'Zoho People', 'excel': 'Excel File', 'sap': 'SAP SuccessFactors',
    'workday': 'Workday', 'oracle': 'Oracle HCM', 'darwin': 'DarwinHR', 'demo': 'Demo / Stub',
}
TYPE_ICON = {
    'zoho': 'cloud', 'excel': 'table', 'sap': 'server',
    'workday': 'briefcase', 'oracle': 'database', 'darwin': 'zap', 'demo': 'beaker',
}
STATUS_LABEL = {'disconnected': 'Disconnected', 'connecting': 'Connecting',
                'connected': 'Connected', 'error': 'Error'}
STATUS_CLS = {'connected': 'ok', 'error': 'err', 'connecting': 'warn', 'disconnected': 'muted'}

# The same row budget the pay-run ledgers use. A config table is not a report:
# past a few hundred rows the answer is the search box, not a longer scroll.
LIMIT = 400
#: Rows per page on the filter panel's lists (FILTER W6).
PAGE_SIZE = 60

# The three ledgers, each naming its model and the legacy act_window it
# REPLACED AS A DOOR. The xmlid is carried so the one-door test can assert that
# the cockpit no longer opens it and the ledger stands in its place.
LEDGERS = {
    'mapping': {
        'model': 'hr.integration.field.mapping',
        'legacy_action': 'pb_hr_payroll_formula.action_field_mapping',
    },
    'store': {
        'model': 'hr.api.data.store',
        'legacy_action': 'pb_hr_payroll_formula.action_api_data_store',
    },
    'rule': {
        'model': 'hr.api.transformation.rule',
        'legacy_action': 'pb_hr_payroll_formula.action_api_transformation_rule',
    },
}


def _sel(Model, field, value):
    """A Selection value as its LABEL, falling back to the technical value."""
    return dict(Model._fields[field].selection or {}).get(value, value or '')


def _s(v):
    return str(v) if v else ''


def _payload_preview(value, cap=12):
    """A JSON column as `[(key, short value)]`, bounded.

    A raw API payload is the one field on these tables that can be megabytes,
    and a drawer is 320px wide. Sending the whole thing so the client can show
    twelve lines of it would put an unbounded blob on every drawer open — so the
    trimming happens HERE, where the size is known, and the drawer says how many
    keys it did not show rather than pretending twelve was all of them (W45).
    """
    if not isinstance(value, dict):
        return [], 0
    keys = sorted(value.keys())
    out = []
    for k in keys[:cap]:
        v = value[k]
        if isinstance(v, (dict, list)):
            try:
                v = json.dumps(v)
            except (TypeError, ValueError):
                v = str(v)
        v = str(v)
        out.append((k, v if len(v) <= 120 else v[:117] + '…'))
    return out, max(0, len(keys) - cap)


class PbIntegrations(models.AbstractModel):
    _name = 'pb.integrations'
    # FILTER W6: the connector cards and the three Data tables are on the
    # shared filter panel (see "filter panel" below).
    _inherit = ['pb.filter.mixin']
    _description = 'Payobook integrations cockpit'

    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug("Integrations metric failed: %s", e)
            return default

    # ==================================================================== board
    @api.model
    def get_board(self):
        if 'hr.integration.connector' not in self.env:
            return {'kpis': {}, 'connectors': [], 'total': 0, 'shown': 0}
        C = self.env['hr.integration.connector']
        cons = self._safe(lambda: C.search([], order='name'), default=C.browse())
        # NOT `'hr.integration.endpoint' in self.env`: the model class is
        # registered from the python, which every database on this shared box
        # loads, while the TABLE is created by that database's own upgrade.
        # The registry probe is True in the gap between the two and the board
        # then swallows an UndefinedTable per connector — and leaves the
        # transaction aborted (found live on three tenants).
        has_feeds = ('hr.integration.endpoint' in self.env
                     and self.env['hr.integration.endpoint']._schema_ready())
        now = fields.Datetime.now()

        rows = []
        connected = errored = 0
        synced = mappings = staged = 0
        feeds = feeds_stale = 0
        for c in cons:
            try:
                status = c.connection_status or 'disconnected'
                if status == 'connected':
                    connected += 1
                if status == 'error':
                    errored += 1
                mc = getattr(c, 'mapping_count', 0) or len(c.field_mapping_ids)
                dc = getattr(c, 'data_store_count', 0) or len(c.data_store_ids)
                sr = getattr(c, 'total_synced_records', 0) or 0
                synced += sr
                mappings += mc
                staged += dc
                nfeeds, nstale = self._feed_summary(c, now) if has_feeds else (0, 0)
                feeds += nfeeds
                feeds_stale += nstale
                rows.append(self._connector_row(c, now, has_feeds, (nfeeds, nstale)))
            except Exception as ex:
                _logger.debug("Connector row failed: %s", ex)
                continue

        types = {}
        for r in rows:
            types[r['type']] = types.get(r['type'], 0) + 1

        return {
            'kpis': {
                'connectors': len(rows), 'connected': connected, 'errors': errored,
                'synced': synced, 'mappings': mappings, 'staged': staged,
                'feeds': feeds, 'feeds_stale': feeds_stale,
            },
            'types': [{'name': TYPE_LABEL.get(k, k), 'type': k, 'count': v}
                      for k, v in sorted(types.items(), key=lambda x: -x[1])],
            'connectors': rows,
            # SOURCING S5 — four things worth telling somebody about, counted once
            # for the whole board. Each is a COUNT plus the drill-down that finds
            # the rows, so a hint is actionable rather than an anxiety.
            'hints': self._sourcing_hints(),
            'total': len(rows), 'shown': len(rows),
            # Did anybody actually COUNT the feeds? `has_feeds` above is False
            # on a database whose upgrade has not run here yet, and every feed
            # number in this payload is then 0 — not because there are none, but
            # because nothing could look. The board used to print that 0 as a
            # fact ("0 feeds", KPI "Feeds 0"), which is W79's failure exactly:
            # a database that never got its upgrade rendered identically to one
            # with an empty catalogue. The client hides the phrase rather than
            # printing a number it was never given.
            'feeds_known': has_feeds,
            # CLOCK-3 §4.3: the attendance machines are a source too. pb_clock
            # is not a dependency: absent → no row.
            'time_clocks': self._time_clocks_card(),
        }

    @api.model
    def _time_clocks_card(self):
        """The "Time clocks" row, when the time-clock module is installed and
        the reader is an attendance officer; None otherwise."""
        if 'pb.clock.alert' not in self.env:
            return None
        return self._safe(lambda: self.env['pb.clock.alert']._integrations_card(), None)

    @api.model
    def _connector_row(self, c, now, has_feeds, feed_summary=None):
        """One connector card (the board's list and the filter panel's page)."""
        status = c.connection_status or 'disconnected'
        mc = getattr(c, 'mapping_count', 0) or len(c.field_mapping_ids)
        dc = getattr(c, 'data_store_count', 0) or len(c.data_store_ids)
        sr = getattr(c, 'total_synced_records', 0) or 0
        if feed_summary is None:
            feed_summary = self._feed_summary(c, now) if has_feeds else (0, 0)
        nfeeds, nstale = feed_summary
        return {
            'feeds': nfeeds, 'feeds_stale': nstale,
            'id': c.id, 'name': c.name or '—',
            'type': c.connector_type or '', 'type_label': TYPE_LABEL.get(c.connector_type, c.connector_type or '—'),
            'icon': TYPE_ICON.get(c.connector_type, 'plug'),
            'status': status, 'status_label': STATUS_LABEL.get(status, status),
            'status_cls': STATUS_CLS.get(status, 'muted'),
            'country': c.country_code or '',
            'last_sync': str(c.last_sync or ''),
            'mappings': mc, 'staged': dc, 'synced': sr,
            # the filter panel lists archived connectors too (FILTER W6)
            'archived': not c.active,
        }

    @api.model
    def _feed_summary(self, c, now):
        """How many feeds this connector has, and how many are overdue.

        "Overdue" is measured against the connector's OWN `sync_interval`, in
        minutes, because that is the promise the connector makes. Two rules make
        the number honest rather than alarming:

          * a feed that has NEVER run is stale whatever the interval says — the
            promise has not been kept once;
          * `sync_interval = 0` means "manual only" on this model, so a feed
            that HAS run is never aged out by it. Ageing a manual feed would
            paint half the board red for doing exactly what it was configured to
            do, and a warning everybody learns to ignore is not a warning (W64's
            instinct: an instrument or an ignored instrument).
        """
        eps = c.endpoint_ids
        if not eps:
            return 0, 0
        interval = c.sync_interval or 0
        stale = 0
        for e in eps:
            if not e.last_sync:
                stale += 1
                continue
            if interval > 0 and (now - e.last_sync).total_seconds() > interval * 60:
                stale += 1
        return len(eps), stale

    # ================================================================= ledgers
    @api.model
    def _readable_connectors(self):
        """The connectors this caller may READ — the ledgers' real scope.

        Found live: `hr.integration.connector` carries a multi-company record
        rule, all three satellite tables reach their connector by many2one, and
        NONE of them carries a company of its own. So an unscoped ledger read
        rows belonging to a connector the caller cannot see, dereferenced
        `connector_id.name` to render the column, and the whole table came back
        as "This table could not be loaded" — one unreadable row out of two
        hundred took the other one hundred and ninety-nine with it.

        `search([])` applies the record rules, so scoping to its result is both
        the fix and the correct answer: you see the data of the connectors you
        can see. It is not a permission decision — the rule already made that —
        it is refusing to ask a question whose answer would raise.
        """
        return self.env['hr.integration.connector'].search([]).ids

    # ============================================================ filter panel
    # FILTER W6 (2026-10-31). The connector cards and the three Data tables
    # are on the shared filter panel, one record type per call
    # (`pbf_ctx.kind`: connectors / mapping / store / rule; screens
    # `connectors` and `integrations:<kind>`). They used to be filtered in the
    # browser — the cards over every connector, the tables over their newest
    # 400 rows with chips counted from those rows (the count lie People
    # fixed). Read with the caller's own rights, as everything in this file.

    @api.model
    def _pbf_kind(self):
        kind = self._pbf_ctx().get('kind')
        if kind in LEDGERS and LEDGERS[kind]['model'] in self.env:
            return kind
        return 'connectors'

    @api.model
    def _has_feeds(self):
        """Is the feed table really there on THIS database (see get_board)?"""
        return ('hr.integration.endpoint' in self.env
                and self.env['hr.integration.endpoint']._schema_ready())

    def _pbf_model(self):
        kind = self._pbf_kind()
        return 'hr.integration.connector' if kind == 'connectors' else LEDGERS[kind]['model']

    def _pbf_screen(self):
        kind = self._pbf_kind()
        return 'connectors' if kind == 'connectors' else 'integrations:%s' % kind

    def _pbf_records(self):
        Rec = self.env[self._pbf_model()]
        # archived connectors and switched-off rules are listed too: a rule
        # that is off is exactly the thing somebody comes looking for
        if self._pbf_kind() in ('connectors', 'rule'):
            return Rec.with_context(active_test=False)
        return Rec

    def _pbf_base_domain(self):
        if self._pbf_kind() == 'connectors':
            return []
        # The satellites reach a connector the caller may not read (see
        # `_readable_connectors`); a subquery with the record rules applied.
        return [('connector_id', 'in', self.env['hr.integration.connector']._search([]))]

    def _pbf_search_fields(self):
        kind = self._pbf_kind()
        if kind == 'connectors':
            return ['name', 'description']
        if kind == 'mapping':
            out = ['source_field', 'source_field_label', 'target_rule_code', 'connector_id.name']
            return out + (['endpoint_id.name'] if self._has_feeds() else [])
        if kind == 'store':
            return ['employee_external_id', 'employee_id.name', 'connector_id.name']
        return ['name', 'output_key', 'plain_summary', 'last_error', 'connector_id.name']

    def _pbf_sorts(self):
        kind = self._pbf_kind()
        if kind == 'connectors':
            return [
                {'key': 'name', 'label': _('Name, A to Z'), 'order': 'name asc, id asc'},
                {'key': 'recent', 'label': _('Synced most recently'), 'order': 'last_sync desc nulls last, name'},
                {'key': 'stale', 'label': _('Longest since a sync'), 'order': 'last_sync asc nulls first, name'},
                {'key': 'records', 'label': _('Most records pulled'),
                 'order': 'total_synced_records desc nulls last, name'},
            ]
        if kind == 'mapping':
            return [
                {'key': 'connector', 'label': _('By connector'),
                 'order': 'connector_id, sequence, source_field'},
                {'key': 'field', 'label': _('Source field, A to Z'), 'order': 'source_field asc, id asc'},
            ]
        if kind == 'store':
            return [
                {'key': 'newest', 'label': _('Newest pull first'), 'order': 'pull_date desc, id desc'},
                {'key': 'oldest', 'label': _('Oldest pull first'), 'order': 'pull_date asc, id asc'},
            ]
        return [
            {'key': 'connector', 'label': _('By connector'), 'order': 'connector_id, sequence, id'},
            {'key': 'name', 'label': _('Name, A to Z'), 'order': 'name asc, id asc'},
            {'key': 'failed', 'label': _('Failed most recently'),
             'order': 'last_error_at desc nulls last, id desc'},
        ]

    @api.model
    def _pbf_sec_connector(self):
        return {'key': 'connector', 'label': _('Connector'), 'icon': 'plug',
                'group': 'other', 'type': 'many2one', 'path': 'connector_id', 'pinned': True}

    def _pbf_spec(self):
        kind = self._pbf_kind()
        company = {'key': 'company', 'label': _('Company'), 'icon': 'landmark',
                   'group': 'other', 'type': 'many2one', 'path': 'company_id',
                   'none_label': _('Every company')}
        if kind == 'connectors':
            spec = [
                {'key': 'status', 'label': _('Connection'), 'icon': 'plug',
                 'group': 'other', 'type': 'selection', 'path': 'connection_status', 'pinned': True},
                {'key': 'type', 'label': _('System'), 'icon': 'server',
                 'group': 'other', 'type': 'selection', 'path': 'connector_type', 'pinned': True},
                {'key': 'synced', 'label': _('Last synced'), 'icon': 'refresh',
                 'group': 'dates', 'type': 'date', 'path': 'last_sync', 'pinned': True,
                 'presets': ['today', 'this_week', 'this_month', 'last_month', 'last_90',
                             'this_year', 'none'],
                 'none_label': _('Never synced')},
                {'key': 'sync_result', 'label': _('Last sync result'), 'icon': 'activity',
                 'group': 'other', 'type': 'selection', 'path': 'last_sync_status',
                 'none_label': _('No sync yet')},
                {'key': 'records', 'label': _('Records pulled'), 'icon': 'database',
                 'group': 'other', 'type': 'number', 'path': 'total_synced_records'},
                {'key': 'auth', 'label': _('Sign-in method'), 'icon': 'key',
                 'group': 'other', 'type': 'selection', 'path': 'auth_type'},
                {'key': 'country', 'label': _('Country'), 'icon': 'globe',
                 'group': 'other', 'type': 'selection', 'path': 'country_code',
                 'none_label': _('Every country')},
                company,
                {'key': 'active', 'label': _('In use or archived'), 'icon': 'archive',
                 'group': 'other', 'type': 'choice', 'requires': ['active'],
                 'options': [
                     {'value': 'yes', 'label': _('In use'), 'tone': 'green', 'domain': [('active', '=', True)]},
                     {'value': 'no', 'label': _('Archived'), 'tone': 'slate', 'domain': [('active', '=', False)]},
                 ]},
            ]
            if self._has_feeds():
                spec.insert(4, {
                    'key': 'feeds', 'label': _('Feeds'), 'icon': 'layers',
                    'group': 'other', 'type': 'choice',
                    'options': [
                        {'value': 'yes', 'label': _('Has feeds'), 'tone': 'green',
                         'domain': [('endpoint_ids', '!=', False)]},
                        {'value': 'no', 'label': _('No feeds yet'), 'tone': 'slate',
                         'domain': [('endpoint_ids', '=', False)]},
                    ]})
            return spec
        if kind == 'mapping':
            spec = [
                self._pbf_sec_connector(),
                {'key': 'state', 'label': _('Mapping state'), 'icon': 'gitBranch',
                 'group': 'other', 'type': 'selection', 'path': 'active_state', 'pinned': True},
                {'key': 'health', 'label': _('Health'), 'icon': 'shieldCheck',
                 'group': 'other', 'type': 'choice', 'requires': ['has_transform_error', 'is_severed'],
                 'options': [
                     {'value': 'error', 'label': _('Transform error'), 'tone': 'rose',
                      'domain': [('has_transform_error', '=', True)]},
                     {'value': 'severed', 'label': _('Severed'), 'tone': 'amber',
                      'domain': [('is_severed', '=', True)]},
                     {'value': 'ok', 'label': _('Healthy'), 'tone': 'green',
                      'domain': [('has_transform_error', '=', False), ('is_severed', '=', False)]},
                 ]},
                {'key': 'target', 'label': _('Target rule'), 'icon': 'sigma',
                 'group': 'pay', 'type': 'many2one', 'path': 'target_rule_id',
                 'none_label': _('No target')},
                {'key': 'transform', 'label': _('Transform'), 'icon': 'wrench',
                 'group': 'other', 'type': 'selection', 'path': 'transformation_type'},
                {'key': 'source_type', 'label': _('Source data type'), 'icon': 'hash',
                 'group': 'other', 'type': 'selection', 'path': 'source_data_type'},
                {'key': 'required', 'label': _('Required'), 'icon': 'flag',
                 'group': 'other', 'type': 'choice', 'requires': ['is_required'],
                 'options': [
                     {'value': 'yes', 'label': _('Required'), 'tone': 'amber', 'domain': [('is_required', '=', True)]},
                     {'value': 'no', 'label': _('Optional'), 'tone': 'slate', 'domain': [('is_required', '=', False)]},
                 ]},
            ]
            if self._has_feeds():
                spec.insert(2, {'key': 'feed', 'label': _('Feed'), 'icon': 'layers',
                                'group': 'other', 'type': 'many2one', 'path': 'endpoint_id',
                                'pinned': True, 'none_label': _('Unassigned')})
            return spec
        if kind == 'store':
            spec = [
                self._pbf_sec_connector(),
                {'key': 'state', 'label': _('Status'), 'icon': 'gitBranch',
                 'group': 'other', 'type': 'selection', 'path': 'state', 'pinned': True},
                {'key': 'data_type', 'label': _('Data type'), 'icon': 'table',
                 'group': 'other', 'type': 'selection', 'path': 'data_type', 'pinned': True},
                {'key': 'employee', 'label': _('Matched employee'), 'icon': 'user',
                 'group': 'people', 'type': 'many2one', 'path': 'employee_id',
                 'none_label': _('Not matched to anyone')},
                {'key': 'pulled', 'label': _('Pulled'), 'icon': 'download',
                 'group': 'dates', 'type': 'date', 'path': 'pull_date',
                 'presets': ['today', 'this_week', 'this_month', 'last_month', 'last_90', 'this_year']},
                {'key': 'period', 'label': _('Period from'), 'icon': 'calendar',
                 'group': 'dates', 'type': 'date', 'path': 'period_from', 'presets': 'past',
                 'none_label': _('No period')},
                {'key': 'trigger', 'label': _('Pulled by'), 'icon': 'play',
                 'group': 'other', 'type': 'selection', 'path': 'pull_triggered_by'},
                {'key': 'changes', 'label': _('Changed since last pull'), 'icon': 'history',
                 'group': 'other', 'type': 'choice', 'requires': ['has_changes'],
                 'options': [
                     {'value': 'yes', 'label': _('Changed'), 'tone': 'amber', 'domain': [('has_changes', '=', True)]},
                     {'value': 'no', 'label': _('Unchanged'), 'tone': 'slate', 'domain': [('has_changes', '=', False)]},
                 ]},
                {'key': 'batch', 'label': _('Used in batch'), 'icon': 'database',
                 'group': 'pay', 'type': 'many2one', 'path': 'import_batch_id',
                 'none_label': _('Not used yet')},
                company,
            ]
            S = self.env['hr.api.data.store']
            if self._has_feeds() and column_exists(self.env.cr, S._table, 'endpoint_id'):
                spec.insert(3, {'key': 'feed', 'label': _('Feed'), 'icon': 'layers',
                                'group': 'other', 'type': 'many2one', 'path': 'endpoint_id',
                                'none_label': _('Unassigned')})
            return spec
        return [
            self._pbf_sec_connector(),
            {'key': 'active', 'label': _('On or off'), 'icon': 'powerOff',
             'group': 'other', 'type': 'choice', 'pinned': True, 'requires': ['active'],
             'options': [
                 {'value': 'on', 'label': _('On'), 'tone': 'green', 'domain': [('active', '=', True)]},
                 {'value': 'off', 'label': _('Off'), 'tone': 'slate', 'domain': [('active', '=', False)]},
             ]},
            {'key': 'failing', 'label': _('Errors'), 'icon': 'triangleAlert',
             'group': 'other', 'type': 'choice', 'pinned': True, 'requires': ['last_error'],
             'options': [
                 {'value': 'yes', 'label': _('Failing'), 'tone': 'rose', 'domain': [('last_error', '!=', False)]},
                 {'value': 'no', 'label': _('No error'), 'tone': 'green', 'domain': [('last_error', '=', False)]},
             ]},
            {'key': 'rule_type', 'label': _('Kind of rule'), 'icon': 'sigma',
             'group': 'other', 'type': 'selection', 'path': 'rule_type'},
            {'key': 'source_type', 'label': _('Reads'), 'icon': 'table',
             'group': 'other', 'type': 'selection', 'path': 'source_data_type'},
            {'key': 'builder', 'label': _('Built with'), 'icon': 'wrench',
             'group': 'other', 'type': 'selection', 'path': 'builder_mode'},
            {'key': 'records', 'label': _('Source records'), 'icon': 'layers',
             'group': 'other', 'type': 'selection', 'path': 'record_source'},
            {'key': 'failed_at', 'label': _('Last failed'), 'icon': 'calendarClock',
             'group': 'dates', 'type': 'date', 'path': 'last_error_at', 'presets': 'past',
             'none_label': _('Never failed')},
        ]

    def _pbf_builtin_views(self):
        kind = self._pbf_kind()
        if kind == 'connectors':
            return [
                {'key': 'all', 'label': _('All connectors'), 'icon': 'layoutList', 'filters': {}},
                {'key': 'attention', 'label': _('Needs attention'), 'filters': {'status': ['error']}},
                {'key': 'never', 'label': _('Never synced'), 'filters': {'synced': {'preset': 'none'}}},
                {'key': 'today', 'label': _('Synced today'), 'filters': {'synced': {'preset': 'today'}}},
                {'key': 'excel', 'label': _('Spreadsheet feeds'), 'filters': {'type': ['excel']}},
            ]
        if kind == 'mapping':
            return [
                {'key': 'all', 'label': _('All mappings'), 'icon': 'layoutList', 'filters': {}},
                {'key': 'active', 'label': _('Active'), 'filters': {'state': ['active']}},
                {'key': 'severed', 'label': _('Severed'), 'filters': {'health': ['severed']}},
                {'key': 'error', 'label': _('With a transform error'), 'filters': {'health': ['error']}},
            ]
        if kind == 'store':
            return [
                {'key': 'all', 'label': _('Everything'), 'icon': 'layoutList', 'filters': {}},
                {'key': 'today', 'label': _('Pulled today'), 'filters': {'pulled': {'preset': 'today'}}},
                {'key': 'failed', 'label': _('Failed pulls'), 'filters': {'state': ['error']}},
                {'key': 'unmatched', 'label': _('Not matched to anyone'), 'filters': {'employee': [False]}},
                {'key': 'changed', 'label': _('Changed since last pull'), 'filters': {'changes': ['yes']}},
            ]
        return [
            {'key': 'all', 'label': _('All rules'), 'icon': 'layoutList', 'filters': {}},
            {'key': 'active', 'label': _('Active'), 'filters': {'active': ['on']}},
            {'key': 'failing', 'label': _('Failing'), 'filters': {'failing': ['yes']}},
        ]

    @api.model
    def _page_args(self, offset, limit):
        try:
            return max(0, int(offset or 0)), max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            return 0, PAGE_SIZE

    @api.model
    def get_connector_page(self, filters=None, search=None, sort=None, offset=0, limit=PAGE_SIZE):
        """One page of connector cards for the filter panel's state."""
        if 'hr.integration.connector' not in self.env:
            return {'rows': [], 'total': 0, 'offset': 0}
        M = self.with_context(pbf_ctx={'kind': 'connectors'})
        Rec = M._pbf_records()
        offset, limit = self._page_args(offset, limit)
        domain = M.pbf_domain(filters or {}, search)
        has_feeds = self._has_feeds()
        now = fields.Datetime.now()
        rows = []
        for c in Rec.search(domain, order=M.pbf_order(sort) or 'name', offset=offset, limit=limit):
            try:
                rows.append(self._connector_row(c, now, has_feeds))
            except Exception as ex:  # noqa: BLE001 — one bad card never blanks the list
                _logger.debug("Connector row failed: %s", ex)
        return {'rows': rows, 'total': Rec.search_count(domain), 'offset': offset}

    @api.model
    def get_ledger_head(self, kind):
        """A Data table's words and columns, without its rows."""
        spec = LEDGERS.get(kind)
        if not spec or spec['model'] not in self.env:
            return {'columns': [], 'total': 0, 'empty': _('This table does not exist on this database.')}
        head = getattr(self, '_words_%s' % kind)()
        M = self.with_context(pbf_ctx={'kind': kind})
        head['total'] = M._pbf_records().search_count(M._pbf_base_domain())
        return head

    @api.model
    def get_ledger_page(self, kind, filters=None, search=None, sort=None, offset=0, limit=PAGE_SIZE):
        """One page of a Data table for the filter panel's state. The
        connector / feed / data-type deep links arrive as filters on the
        panel (droppable chips), inside the same readable-connector scope —
        a deep link can never widen it."""
        spec = LEDGERS.get(kind)
        if not spec or spec['model'] not in self.env:
            return {'rows': [], 'total': 0, 'offset': 0}
        M = self.with_context(pbf_ctx={'kind': kind})
        Rec = M._pbf_records()
        offset, limit = self._page_args(offset, limit)
        domain = M.pbf_domain(filters or {}, search)
        recs = Rec.search(domain, order=M.pbf_order(sort) or 'id desc', offset=offset, limit=limit)
        ctx = getattr(self, '_row_ctx_%s' % kind)()
        build = getattr(self, '_row_%s' % kind)
        return {'rows': [build(r, ctx) for r in recs], 'total': Rec.search_count(domain), 'offset': offset}

    @api.model
    def get_ledger(self, kind, connector_id=None, data_type=None,
                   endpoint_id=None):
        """One satellite table as a grid descriptor.

        `kind` is looked up in LEDGERS rather than used to index `self.env`: a
        forged kind must not be able to point this method at another table.

        `endpoint_id` is the exact feed scope the connector cockpit's "View
        data" button arrives with; `data_type` remains as backward-compatible
        context for older callers. Both are validated, and neither may widen
        the connector scope. On the other ledgers they are ignored so the tab
        strip stays usable.
        """
        spec = LEDGERS.get(kind)
        if not spec or spec['model'] not in self.env:
            return {'columns': [], 'rows': [], 'total': 0, 'shown': 0,
                    'empty': 'This table does not exist on this database.'}
        scope = self._readable_connectors()
        if connector_id:
            # An INTERSECTION, never a replacement: a deep link may not widen
            # the scope past what the record rules allow.
            cid = int(connector_id)
            scope = [cid] if cid in scope else []
        dom = [('connector_id', 'in', scope)]
        if kind == 'store' and data_type:
            known = dict(
                self.env['hr.api.data.store']._fields['data_type'].selection)
            if data_type in known:
                dom = dom + [('data_type', '=', data_type)]
        if kind == 'store' and endpoint_id:
            Endpoint = self.env.get('hr.integration.endpoint') \
                if 'hr.integration.endpoint' in self.env else None
            endpoint = Endpoint.browse(int(endpoint_id)).exists() \
                if Endpoint is not None and Endpoint._schema_ready() else Endpoint
            allowed = bool(
                endpoint and endpoint.connector_id.id in scope and
                (not connector_id or endpoint.connector_id.id == int(connector_id)))
            # A forged/stale endpoint id must narrow to nothing, never fall back
            # to the broader data-type view the caller did not ask for.
            dom = dom + ([('endpoint_id', '=', endpoint.id)] if allowed
                         else [('id', '=', 0)])
        builder = getattr(self, '_ledger_%s' % kind)
        return builder(dom)

    @api.model
    def get_ledger_detail(self, kind, rec_id):
        """One row's whole story, as sections of labelled fields.

        Returns `{}` for an id that no longer exists — the drawer is opened from
        a row the user is looking at, so the honest answer to "this was deleted
        while you read the grid" is an empty panel, not a traceback.

        An id the caller may not READ is a different question and it raises:
        `check_access` is the ORM's own refusal and swallowing it would be a
        catch that quietly narrows a feature (W40). Same shape as the pay-run
        ledgers' `get_detail`, deliberately.
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

        A key with no value is noise in a 320px panel, and worse, it reads as
        "this record has no target rule" when the truth is "this ledger does not
        carry one". Written out by TYPE rather than as `v not in ('', None,
        False)`, because `in` compares with `==` and `0 == False` — the tidy
        one-liner silently drops every zero as well (the pay-run ledgers' bug,
        avoided here by copying the fix rather than the bug).
        """
        keep = []
        for f in fields_:
            v = f.get('value')
            # Booleans FIRST and by identity. `isinstance(True, bool)` is true
            # and `isinstance(True, int)` is also true, so any ordering that
            # tests numbers first turns Yes into a 1 and any ordering that
            # tests `bool` without splitting the two renders True as "No".
            if v is True or v is False:
                if v:
                    keep.append(dict(f, value='Yes'))
                elif f.get('keep_false'):
                    keep.append(dict(f, value='No'))
                continue
            if isinstance(v, str) and v.strip():
                keep.append(f)
            elif isinstance(v, (int, float)) and v:
                keep.append(dict(f, value=str(v)))
        return {'label': label, 'fields': keep} if keep else None

    # ------------------------------------------------------- field mappings
    @api.model
    def _row_ctx_mapping(self):
        # Integrations Cycle 2 — the feed a mapping belongs to, as a column, so
        # the studio's per-feed counts and this table are answering the same
        # question. Behind Cycle 1's schema probe, not behind
        # `'hr.integration.endpoint' in self.env`: the addons tree is shared and
        # the COLUMN arrives with a database's own upgrade, so on a tenant that
        # has not had one this read would raise UndefinedColumn and leave the
        # whole request's transaction aborted.
        return {'has_feeds': self._has_feeds()}

    @api.model
    def _row_mapping(self, r, ctx):
        M = self.env['hr.integration.field.mapping']
        has_feeds = ctx['has_feeds']
        state = r.active_state or 'active'
        tone = {'active': 'ok', 'suggested': 'warn', 'ignored': 'muted'}.get(state, 'muted')
        if r.has_transform_error:
            tone = 'err'
        # "Unassigned" and not "—": a mapping drawn before feeds existed is
        # a real, working mapping with no feed named, which is a different
        # thing from a missing value (W79).
        feed = (r.endpoint_id.name or r.endpoint_id.code or _('Unassigned')) \
            if has_feeds else ''
        cells = [
            r.source_field_label or r.source_field or '—',
            r.target_rule_id.name or r.target_rule_code or '—',
            _sel(M, 'transformation_type', r.transformation_type),
            r.connector_id.name or '—',
        ]
        if has_feeds:
            cells.append(feed)
        return {
            'id': r.id,
            'cells': cells,
            'badge': {'label': _sel(M, 'active_state', state), 'tone': tone},
            '_s': ' '.join(x for x in [r.source_field or '', r.source_field_label or '',
                                       r.target_rule_code or '',
                                       r.connector_id.name or '', feed] if x),
        }

    @api.model
    def _words_mapping(self):
        columns = [{'label': _('Source field'), 'wide': True},
                   {'label': _('Target rule')},
                   {'label': _('Transform')},
                   {'label': _('Connector')}]
        if self._has_feeds():
            columns.append({'label': _('Feed')})
        return {
            'title': _('Field mappings'),
            'subtitle': _('Which source field feeds which formula input, and how it is transformed.'),
            'search_ph': _('Search source field, target code, connector, feed…'),
            'empty': _('No field mappings on these connectors yet.'),
            'columns': columns,
        }

    @api.model
    def _ledger_mapping(self, dom):
        """The old one-shot grid (newest 400); the screen reads
        get_ledger_head + get_ledger_page now (kept for its tests, R4)."""
        M = self.env['hr.integration.field.mapping']
        total = M.search_count(dom)
        recs = M.search(dom, order='connector_id, sequence, source_field', limit=LIMIT)
        ctx = self._row_ctx_mapping()
        rows = [self._row_mapping(r, ctx) for r in recs]
        return dict(self._words_mapping(), rows=rows, total=total, shown=len(rows))

    @api.model
    def _detail_feed_name(self, r):
        """The feed a mapping names, or '' when this database has no feeds."""
        if 'hr.integration.endpoint' not in self.env:
            return ''
        if not self.env['hr.integration.endpoint']._schema_ready():
            return ''
        return r.endpoint_id.name or r.endpoint_id.code or ''

    @api.model
    def _detail_mapping(self, r):
        M = self.env['hr.integration.field.mapping']
        return {
            'title': r.source_field_label or r.source_field or '—',
            'subtitle': r.connector_id.name or '',
            'sections': [s for s in [
                self._section('Source', [
                    {'label': 'Field path', 'value': r.source_field or ''},
                    {'label': 'Label', 'value': r.source_field_label or ''},
                    # The feed, when this database has feeds at all. `_section`
                    # drops an empty entry, so an un-upgraded tenant simply does
                    # not show the row rather than showing a blank one.
                    {'label': 'Feed', 'value': self._detail_feed_name(r)},
                    {'label': 'Data type', 'value': _sel(M, 'source_data_type', r.source_data_type)},
                    {'label': 'Sample value', 'value': r.source_sample_value or ''},
                ]),
                # SOURCING S5 — "Produced by". When the source key is one this
                # connector COMPUTES rather than one the vendor sends, say which
                # rule makes it; the field path alone gives no hint.
                self._section('Produced by', [
                    {'label': 'Rule', 'value': (self._mapping_producer(r).name
                                                if self._mapping_producer(r) else '')},
                ]),
                self._section('Target', [
                    {'label': 'Formula rule', 'value': r.target_rule_id.name or ''},
                    {'label': 'Code', 'value': r.target_rule_code or ''},
                    {'label': 'Column', 'value': r.target_column_letter or ''},
                    # SOURCING S2 — a mapping that remembers a component it no
                    # longer points at used to look identical to one that never
                    # had one. `_section` drops the row when it is False.
                    {'label': 'Lost its component',
                     'value': (_("Yes — remembers “%s”") % (r.target_rule_code or '')
                               if r.is_severed else '')},
                ]),
                self._section('Transform', [
                    {'label': 'Type', 'value': _sel(M, 'transformation_type', r.transformation_type)},
                    {'label': 'Factor / value', 'value': r.transformation_value},
                    {'label': 'Decimals', 'value': r.transformation_decimals},
                    {'label': 'Expression', 'value': r.transformation_code or '', 'wrap': True},
                    {'label': 'Default if empty', 'value': r.default_value},
                ]),
                self._section('Status', [
                    {'label': 'Mapping state', 'value': _sel(M, 'active_state', r.active_state)},
                    {'label': 'Active', 'value': bool(r.active), 'keep_false': True},
                    {'label': 'Required', 'value': bool(r.is_required), 'keep_false': True},
                    # Surfaced on purpose: a python transform that raised falls
                    # back to the default value, and the failure must stay
                    # visible rather than silently becoming a number.
                    {'label': 'Transform error', 'value': r.transform_error_msg or '',
                     'tone': 'err', 'wrap': True},
                    {'label': 'Notes', 'value': r.notes or '', 'wrap': True},
                ]),
            ] if s],
        }

    # ---------------------------------------------------------- api data store
    @api.model
    def _row_ctx_store(self):
        S = self.env['hr.api.data.store']
        return {'has_feed': column_exists(self.env.cr, S._table, 'endpoint_id')}

    @api.model
    def _row_store(self, r, ctx):
        S = self.env['hr.api.data.store']
        has_feed = ctx['has_feed']
        state = r.state or 'raw'
        tone = {'extracted': 'ok', 'consumed': 'info', 'error': 'err',
                'archived': 'muted'}.get(state, 'muted')
        feed = (r.endpoint_id.name or r.endpoint_id.code or _('Unassigned')) \
            if has_feed else ''
        cells = [
            r.employee_external_id or (r.employee_id.name if r.employee_id else '—'),
            _sel(S, 'data_type', r.data_type),
            r.connector_id.name or '—',
            _s(r.pull_date)[:16],
        ]
        if has_feed:
            cells.insert(2, feed)
        return {
            'id': r.id,
            'cells': cells,
            'badge': {'label': _sel(S, 'state', state), 'tone': tone},
            '_s': ' '.join(x for x in [r.employee_external_id or '',
                                       r.employee_id.name if r.employee_id else '',
                                       r.connector_id.name or '', feed] if x),
        }

    @api.model
    def _words_store(self):
        columns = [{'label': _('Key'), 'wide': True}, {'label': _('Data type')}]
        if self._row_ctx_store()['has_feed']:
            columns.append({'label': _('Feed')})
        columns.extend([{'label': _('Connector')}, {'label': _('Pulled')}])
        return {
            'title': _('API data store'),
            'subtitle': _('Everything the connectors have pulled — raw, extracted and versioned.'),
            'search_ph': _('Search external id, employee, connector…'),
            'empty': _('Nothing has been pulled into the store yet.'),
            'columns': columns,
        }

    @api.model
    def _ledger_store(self, dom):
        """The old one-shot grid (newest 400; kept for its tests, R4)."""
        S = self.env['hr.api.data.store']
        total = S.search_count(dom)
        recs = S.search(dom, order='pull_date desc, id desc', limit=LIMIT)
        ctx = self._row_ctx_store()
        rows = [self._row_store(r, ctx) for r in recs]
        return dict(self._words_store(), rows=rows, total=total, shown=len(rows))

    @api.model
    def _detail_store(self, r):
        S = self.env['hr.api.data.store']
        has_feed = column_exists(self.env.cr, S._table, 'endpoint_id')
        raw, raw_more = _payload_preview(r.raw_payload)
        ext, ext_more = _payload_preview(r.extracted_data)
        com, com_more = _payload_preview(r.computed_data)
        sections = [
            self._section('Identity', [
                {'label': 'External employee id', 'value': r.employee_external_id or ''},
                {'label': 'Matched employee', 'value': r.employee_id.name if r.employee_id else ''},
                {'label': 'Data type', 'value': _sel(S, 'data_type', r.data_type)},
                {'label': 'Source feed', 'value': (
                    r.endpoint_id.name or r.endpoint_id.code or 'Unassigned')
                    if has_feed else ''},
                {'label': 'Connector', 'value': r.connector_id.name or ''},
            ]),
            self._section('Period', [
                {'label': 'Period', 'value': r.period_label or ''},
                {'label': 'From', 'value': _s(r.period_from)},
                {'label': 'To', 'value': _s(r.period_to)},
            ]),
            self._section('Pull', [
                {'label': 'Pulled at', 'value': _s(r.pull_date)},
                {'label': 'Duration (ms)', 'value': r.pull_duration_ms},
                {'label': 'Triggered by', 'value': _sel(S, 'pull_triggered_by', r.pull_triggered_by)},
                {'label': 'Status', 'value': _sel(S, 'state', r.state)},
                {'label': 'Used in batch', 'value': r.import_batch_id.name if r.import_batch_id else ''},
                {'label': 'Error', 'value': r.error_message or '', 'tone': 'err', 'wrap': True},
            ]),
            self._section('Versioning', [
                {'label': 'Version', 'value': r.version},
                {'label': 'Changed since last pull', 'value': bool(r.has_changes), 'keep_false': True},
            ]),
        ]
        for label, pairs, more in (('Extracted data', ext, ext_more),
                                   ('Computed data', com, com_more),
                                   ('Raw payload', raw, raw_more)):
            fields_ = [{'label': k, 'value': v, 'wrap': True} for k, v in pairs]
            if more:
                fields_.append({'label': '…and more', 'value': '%s further keys' % more})
            sec = self._section(label, fields_)
            if sec:
                sections.append(sec)
        return {
            'title': r.employee_external_id or (r.employee_id.name if r.employee_id else '—'),
            'subtitle': _sel(S, 'data_type', r.data_type),
            'sections': [s for s in sections if s],
        }

    # ----------------------------------------------------- transformation rules
    @api.model
    def _ledger_rule(self, dom):
        R = self.env['hr.api.transformation.rule']
        # `active` is a real field here, so the ledger shows the archived rows
        # too — a rule that is off is exactly the thing somebody comes looking
        # for, and a filter that hides it makes the table lie by omission.
        recs = R.with_context(active_test=False).search(
            dom, order='connector_id, sequence, id', limit=LIMIT)
        total = R.with_context(active_test=False).search_count(dom)
        ctx = self._row_ctx_rule()
        rows = [self._row_rule(r, ctx) for r in recs]
        return dict(self._words_rule(), rows=rows, total=total, shown=len(rows))

    @api.model
    def _row_ctx_rule(self):
        return {}

    @api.model
    def _row_rule(self, r, ctx):
        R = self.env['hr.api.transformation.rule']
        error = getattr(r, 'last_error', '') or ''
        # The KIND column prints the rule's own SENTENCE (Cycle 8). "Sum
        # Field Across Records" is a selection label, true of half the
        # table and an answer to nobody's question; "Adds up Actual Pay Hour
        # where OT Type is 150%" is what the reader came to find out. The
        # selection label is the fallback for a row whose summary has not
        # been computed yet — a blank cell would read as a broken rule.
        summary = (getattr(r, 'plain_summary', '') or ''
                   or _sel(R, 'rule_type', r.rule_type))
        return {
            'id': r.id,
            # The composer opens on a CONNECTOR, and the row is the only
            # thing the client has when it is clicked.
            'connector_id': r.connector_id.id,
            'cells': [
                r.name or '—',
                r.output_key or '—',
                summary,
                # SOURCING S5 — a rule that feeds nothing is now visible in
                # the LIST, without opening a single row.
                str(len(self._rule_consumers(r))),
                r.connector_id.name or '—',
            ],
            # An error outranks "off": a rule that is on and failing is the
            # row somebody is looking for, and "Active" beside a silent
            # failure is the badge telling the lie (W149's shape).
            'badge': ({'label': _('Error'), 'tone': 'err'} if error else
                      {'label': _('Active') if r.active else _('Off'),
                       'tone': 'ok' if r.active else 'muted'}),
            '_s': ' '.join(x for x in [r.name or '', r.output_key or '',
                                       summary, error,
                                       r.connector_id.name or ''] if x),
        }

    @api.model
    def _words_rule(self):
        return {
            'title': _('Transformation rules'),
            'subtitle': _('Values derived from the stored records before mapping runs.'),
            'search_ph': _('Search rule name, output key, what it does…'),
            'empty': _('No transformation rules on these connectors.'),
            'columns': [{'label': _('Rule'), 'wide': True},
                        {'label': _('Output key')},
                        {'label': _('What it does'), 'wide': True},
                        {'label': _('Feeds')},
                        {'label': _('Connector')}],
        }

    # ==================================================================
    # SOURCING S5 — the cockpit closes the loop.
    #
    # A rule that computes a key nobody reads is invisible until something says
    # so, and a mapping that lost its component looks identical to one that never
    # had one. These three helpers are what let a list answer "is this wired to
    # anything?" without opening every row.
    # ==================================================================
    # ==================================================================
    # SOURCING S5 — health hints.
    #
    # Four questions the product could not answer before this programme:
    # does anything read what this rule computes; did a mapping quietly lose the
    # component it fed; is there an input with no source at all; and did a source
    # somebody deliberately chose produce nothing on the last run.
    #
    # Each returns a count and a `kind` the cockpit can drill into. Silence is the
    # normal state: a hint with a zero count is dropped rather than rendered as a
    # reassuring green nothing.
    # ==================================================================
    @api.model
    def _sourcing_hints(self):
        hints = []

        def add(kind, count, label, detail):
            if count:
                hints.append({'kind': kind, 'count': count,
                              'label': label, 'detail': detail})

        # 1 — a rule computes a key and nothing reads it.
        Rule = self.env.get('hr.api.transformation.rule')
        if Rule is not None:
            orphans = [r for r in self._safe(
                lambda: Rule.sudo().with_context(active_test=False).search([]),
                default=[]) if r.output_key and not self._rule_consumers(r)]
            add('rule_unconsumed', len(orphans),
                _("Rule outputs nothing reads"),
                _("These rules compute a value that no pay component takes: %s")
                % ', '.join(r.output_key for r in orphans[:12]))

        # 2 — a mapping that remembers a component it no longer points at.
        Mapping = self.env.get('hr.integration.field.mapping')
        if Mapping is not None and 'is_severed' in Mapping._fields:
            n = self._safe(lambda: Mapping.sudo().search_count(
                [('is_severed', '=', True)]), default=0)
            add('mapping_severed', n,
                _("Mappings that lost their component"),
                _("Each remembers the component it used to feed. Reconnect puts "
                  "them back."))

        # 3 — an input with no source at all.
        FRule = self.env.get('hr.formula.rule')
        if FRule is not None and 'source_binding' in FRule._fields:
            n = self._safe(lambda: FRule.sudo().search_count([
                ('column_type', '=', 'input'),
                ('source_binding', '=', False),
                ('data_source_field', '=', False),
                ('is_contract_component', '=', False),
            ]), default=0)
            add('input_unsourced', n,
                _("Inputs with no source chosen"),
                _("These components are matched by name when a run imports them, "
                  "which works until a column is renamed."))

        # 4 — a source somebody CHOSE that produced nothing on the last run.
        Payslip = self.env.get('hr.payslip')
        if Payslip is not None and FRule is not None \
                and 'formula_input_sources' in Payslip._fields:
            n = self._safe(self._sourcing_empty_bound_count, default=0)
            add('bound_empty', n,
                _("Chosen sources that produced nothing"),
                _("The last run found nothing under the key these components are "
                  "set to read, so they fell back or used their default."))
        return hints

    @api.model
    def _sourcing_empty_bound_count(self):
        """Components whose bound source was empty on the most recent run.

        Reads ONE payslip per configuration — the newest carrying a provenance
        blob — rather than scanning a payslip table that is 28,000 rows deep on a
        live tenant. `via` is what S3 wrote for exactly this question.
        """
        import json as _json
        Payslip = self.env['hr.payslip'].sudo()
        seen = set()
        total = 0
        for slip in Payslip.search([('formula_input_sources', '!=', False)],
                                   order='date_to desc, id desc', limit=400):
            cfg = slip.formula_config_id.id
            if not cfg or cfg in seen:
                continue
            seen.add(cfg)
            try:
                blob = _json.loads(slip.formula_input_sources or '{}')
            except (TypeError, ValueError):
                continue
            if not isinstance(blob, dict):
                continue
            total += sum(1 for e in blob.values()
                         if isinstance(e, dict)
                         and e.get('via') in ('fallback', 'binding_empty'))
        return total

    @api.model
    def _rule_consumers(self, rule):
        """Components that read this rule's output — mappings and S3 bindings."""
        if not rule.output_key:
            return []
        out = []
        Mapping = self.env['hr.integration.field.mapping'].sudo()
        for m in Mapping.search([('connector_id', '=', rule.connector_id.id),
                                 ('source_field', '=', rule.output_key)]):
            if m.target_rule_id:
                out.append('%s (%s)' % (m.target_rule_id.name or '',
                                        m.target_rule_id.code or ''))
        Rule = self.env.get('hr.formula.rule')
        if Rule is not None and 'source_binding' in Rule._fields:
            for r in Rule.sudo().search([('source_binding', '=', 'rule'),
                                         ('source_binding_key', '=', rule.output_key)]):
                label = '%s (%s)' % (r.name or '', r.code or '')
                if label not in out:
                    out.append(label)
        return out

    @api.model
    def _mapping_producer(self, mapping):
        """The transformation rule that produces this mapping's source key, if any."""
        Rule = self.env.get('hr.api.transformation.rule')
        if Rule is None or not mapping.source_field:
            return None
        found = Rule.sudo().search([('connector_id', '=', mapping.connector_id.id),
                                    ('output_key', '=', mapping.source_field)], limit=1)
        return found or None

    @api.model
    def _detail_rule(self, r):
        R = self.env['hr.api.transformation.rule']
        return {
            'title': r.name or '—',
            'subtitle': r.output_key or '',
            'sections': [s for s in [
                self._section('Rule', [
                    {'label': 'Name', 'value': r.name or ''},
                    {'label': 'Output key', 'value': r.output_key or ''},
                    {'label': 'Kind', 'value': _sel(R, 'rule_type', r.rule_type)},
                    {'label': 'Reads', 'value': _sel(R, 'source_data_type', r.source_data_type)},
                    {'label': 'Description', 'value': r.description or '', 'wrap': True},
                ]),
                # SOURCING S5 — the reverse link. A rule that feeds nothing said
                # nothing about it before; now it says so in as many words.
                self._section('Feeds these components', [
                    {'label': 'Components',
                     'value': ', '.join(self._rule_consumers(r))
                              or _("Nothing reads this rule's output."),
                     'wrap': True},
                ]),
                self._section('Aggregate', [
                    {'label': 'Field', 'value': r.aggregate_field or ''},
                    {'label': 'Filter', 'value': r.filter_expression or '', 'wrap': True},
                ]),
                self._section('Dates', [
                    {'label': 'Source field', 'value': r.date_source_field or ''},
                    {'label': 'Compare to', 'value': _sel(R, 'date_compare_to', r.date_compare_to)},
                    {'label': 'Fixed date', 'value': _s(r.date_fixed_value)},
                    {'label': 'Unit', 'value': _sel(R, 'date_unit', r.date_unit)},
                    # Declared on the model since the beginning and never
                    # rendered here — so a `date_check` rule showed its source
                    # field and its unit and silently withheld the actual TEST,
                    # which is the only part of it a reader wants. Fixed in
                    # passing (Cycle 8).
                    {'label': 'Test', 'value': _sel(R, 'date_check_operator',
                                                    r.date_check_operator)},
                    {'label': 'Test value', 'value': r.date_check_value},
                ]),
                self._section('Expression', [
                    {'label': 'Python', 'value': r.python_code or '', 'wrap': True},
                ]),
                self._section('Status', [
                    {'label': 'Active', 'value': bool(r.active), 'keep_false': True},
                    {'label': 'Sequence', 'value': r.sequence},
                    {'label': 'Default', 'value': r.default_value},
                    {'label': 'Connector', 'value': r.connector_id.name or ''},
                    # A rule that fails answers with its default and says
                    # nothing — which is the gap Cycle 8 closed on the model.
                    # Surfacing it here is the other half: an error nobody can
                    # read is an error nobody will fix.
                    {'label': 'Last error',
                     'value': getattr(r, 'last_error', '') or '',
                     'tone': 'err', 'wrap': True},
                    {'label': 'Failed at', 'value': _s(getattr(r, 'last_error_at', ''))},
                ]),
            ] if s],
        }

    # The `_facets` helper that lived here (chips counted from the loaded
    # rows) is gone: the filter panel counts every section over the whole
    # table on the server (FILTER W6).
