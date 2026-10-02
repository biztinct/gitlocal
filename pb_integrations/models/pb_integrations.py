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
                rows.append({
                    'feeds': nfeeds, 'feeds_stale': nstale,
                    'id': c.id, 'name': c.name or '—',
                    'type': c.connector_type or '', 'type_label': TYPE_LABEL.get(c.connector_type, c.connector_type or '—'),
                    'icon': TYPE_ICON.get(c.connector_type, 'plug'),
                    'status': status, 'status_label': STATUS_LABEL.get(status, status),
                    'status_cls': STATUS_CLS.get(status, 'muted'),
                    'country': c.country_code or '',
                    'last_sync': str(c.last_sync or ''),
                    'mappings': mc, 'staged': dc, 'synced': sr,
                })
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
    def _ledger_mapping(self, dom):
        M = self.env['hr.integration.field.mapping']
        total = M.search_count(dom)
        recs = M.search(dom, order='connector_id, sequence, source_field', limit=LIMIT)
        # Integrations Cycle 2 — the feed a mapping belongs to, as a column and
        # a facet, so the studio's per-feed counts and this table are answering
        # the same question. Behind Cycle 1's schema probe, not behind
        # `'hr.integration.endpoint' in self.env`: the addons tree is shared and
        # the COLUMN arrives with a database's own upgrade, so on a tenant that
        # has not had one this read would raise UndefinedColumn and leave the
        # whole request's transaction aborted.
        has_feeds = ('hr.integration.endpoint' in self.env
                     and self.env['hr.integration.endpoint']._schema_ready())
        rows = []
        for r in recs:
            state = r.active_state or 'active'
            tone = {'active': 'ok', 'suggested': 'warn', 'ignored': 'muted'}.get(state, 'muted')
            if r.has_transform_error:
                tone = 'err'
            # "Unassigned" and not "—": a mapping drawn before feeds existed is
            # a real, working mapping with no feed named, which is a different
            # thing from a missing value (W79).
            feed = (r.endpoint_id.name or r.endpoint_id.code or 'Unassigned') \
                if has_feeds else ''
            cells = [
                r.source_field_label or r.source_field or '—',
                r.target_rule_id.name or r.target_rule_code or '—',
                _sel(M, 'transformation_type', r.transformation_type),
                r.connector_id.name or '—',
            ]
            facets = {'connector': r.connector_id.name or '', 'state': state}
            if has_feeds:
                cells.append(feed)
                facets['feed'] = feed
            rows.append({
                'id': r.id,
                'cells': cells,
                'badge': {'label': _sel(M, 'active_state', state), 'tone': tone},
                '_f': facets,
                '_s': ' '.join(x for x in [r.source_field or '', r.source_field_label or '',
                                           r.target_rule_code or '',
                                           r.connector_id.name or '', feed] if x),
            })
        columns = [{'label': 'Source field', 'wide': True},
                   {'label': 'Target rule'},
                   {'label': 'Transform'},
                   {'label': 'Connector'}]
        facet_spec = [('connector', 'Connector'), ('state', 'State')]
        if has_feeds:
            columns.append({'label': 'Feed'})
            facet_spec.append(('feed', 'Feed'))
        return {
            'title': 'Field mappings',
            'subtitle': 'Which source field feeds which formula input, and how it is transformed.',
            'search_ph': 'Search source field, target code, connector, feed…',
            'empty': 'No field mappings match these filters.',
            'columns': columns,
            'facets': self._facets(rows, facet_spec),
            'rows': rows, 'total': total, 'shown': len(rows),
        }

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
    def _ledger_store(self, dom):
        S = self.env['hr.api.data.store']
        has_feed = column_exists(self.env.cr, S._table, 'endpoint_id')
        total = S.search_count(dom)
        recs = S.search(dom, order='pull_date desc, id desc', limit=LIMIT)
        rows = []
        for r in recs:
            state = r.state or 'raw'
            tone = {'extracted': 'ok', 'consumed': 'info', 'error': 'err',
                    'archived': 'muted'}.get(state, 'muted')
            feed = (r.endpoint_id.name or r.endpoint_id.code or 'Unassigned') \
                if has_feed else ''
            cells = [
                r.employee_external_id or (r.employee_id.name if r.employee_id else '—'),
                _sel(S, 'data_type', r.data_type),
                r.connector_id.name or '—',
                _s(r.pull_date)[:16],
            ]
            facets = {'connector': r.connector_id.name or '', 'state': state}
            if has_feed:
                cells.insert(2, feed)
                facets['feed'] = feed
            rows.append({
                'id': r.id,
                'cells': cells,
                'badge': {'label': _sel(S, 'state', state), 'tone': tone},
                '_f': facets,
                '_s': ' '.join(x for x in [r.employee_external_id or '',
                                           r.employee_id.name if r.employee_id else '',
                                           r.connector_id.name or '', feed] if x),
            })
        columns = [{'label': 'Key', 'wide': True}, {'label': 'Data type'}]
        facet_spec = [('connector', 'Connector'), ('state', 'State')]
        if has_feed:
            columns.append({'label': 'Feed'})
            facet_spec.append(('feed', 'Feed'))
        columns.extend([{'label': 'Connector'}, {'label': 'Pulled'}])
        return {
            'title': 'API data store',
            'subtitle': 'Everything the connectors have pulled — raw, extracted and versioned.',
            'search_ph': 'Search external id, employee, connector…',
            'empty': 'Nothing has been pulled into the store yet.',
            'columns': columns,
            'facets': self._facets(rows, facet_spec),
            'rows': rows, 'total': total, 'shown': len(rows),
        }

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
        rows = []
        for r in recs:
            error = getattr(r, 'last_error', '') or ''
            # The KIND column prints the rule's own SENTENCE (Cycle 8). "Sum
            # Field Across Records" is a selection label, true of half the
            # table and an answer to nobody's question; "Adds up Actual Pay Hour
            # where OT Type is 150%" is what the reader came to find out. The
            # selection label is the fallback for a row whose summary has not
            # been computed yet — a blank cell would read as a broken rule.
            summary = (getattr(r, 'plain_summary', '') or ''
                       or _sel(R, 'rule_type', r.rule_type))
            rows.append({
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
                'badge': ({'label': 'Error', 'tone': 'err'} if error else
                          {'label': 'Active' if r.active else 'Off',
                           'tone': 'ok' if r.active else 'muted'}),
                '_f': {'connector': r.connector_id.name or '',
                       'state': ('error' if error else
                                 'active' if r.active else 'off')},
                '_s': ' '.join(x for x in [r.name or '', r.output_key or '',
                                           summary, error,
                                           r.connector_id.name or ''] if x),
            })
        return {
            'title': 'Transformation rules',
            'subtitle': 'Values derived from the stored records before mapping runs.',
            'search_ph': 'Search rule name, output key, what it does…',
            'empty': 'No transformation rules on these connectors.',
            'columns': [{'label': 'Rule', 'wide': True},
                        {'label': 'Output key'},
                        {'label': 'What it does', 'wide': True},
                        {'label': 'Feeds'},
                        {'label': 'Connector'}],
            'facets': self._facets(rows, [('connector', 'Connector'), ('state', 'State')]),
            'rows': rows, 'total': total, 'shown': len(rows),
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

    # ------------------------------------------------------------------ facets
    @api.model
    def _facets(self, rows, spec):
        """Facets built from the LOADED rows, so a chip always matches rows.

        Rendered as a dropdown past eight distinct values, and the template
        drops a facet with 0 or 1 value entirely — a filter with one option is a
        control that cannot change anything. Same helper shape as the pay-run
        ledgers', deliberately: two ledgers that behave differently under the
        same-looking chips is a worse cost than one duplicated function.
        """
        out = []
        for key, label in spec:
            vals = sorted({(r['_f'].get(key) or '') for r in rows} - {''})
            out.append({'key': key, 'label': label,
                        'kind': 'chips' if len(vals) <= 8 else 'select',
                        'chips': [{'id': v, 'label': v} for v in vals]})
        return out
