# -*- coding: utf-8 -*-
"""Integrations Cycle 1 — one connector, many endpoints.

A connector used to be a single `api_endpoint` Char: one base URL, one implied
feed, and every mapping, every pull and every stored row hanging off it with no
way to say WHICH API they came from. Real HRIS integrations are not shaped like
that — the legacy ABM application talks to eight separate Zoho People forms, and
"the employees API is fine, the leave API is failing" is the sentence an operator
needs to be able to say.

So the feed becomes a record:

  `hr.integration.endpoint`           one API this connector actually calls
  `hr.integration.endpoint.template`  the vendor catalogue those are seeded from

Two rules the whole file is built to:

  1. **The catalogue sync is CREATE-ONLY.** It is run on every connector create,
     from the cockpit's "Detect feeds" button and from pb_demo's seeder, so it
     will run many times over a row an operator has renamed or re-pathed. It may
     therefore only ever ADD an endpoint that is missing by `code` — the same
     never-overwrite semantics `action_apply_mapping_template` has for mappings.
  2. **The counts are the BOARD's counts.** `staged_count` is
     `hr.integration.connector._compute_data_store_count`'s domain narrowed by
     data type — `state != 'archived'` — so the sum of a connector's feeds equals
     the number the Integrations board prints on its card. Two screens that
     disagree about how many records are waiting is worse than one screen that
     does not mention it (W62).
"""
import logging

from odoo import api, fields, models
from odoo.tools.sql import table_exists

from .api_data_store import DATA_TYPES

_logger = logging.getLogger(__name__)

# The vendor list an endpoint TEMPLATE may be written for. It is the connector's
# own `connector_type` selection (`integration_connector.py`:33) rather than the
# mapping template's five (`integration_mapping_template.py`:18): a template row
# is only useful if a connector of that type can exist, and `demo` / `excel` are
# the two types this database has most of.
CONNECTOR_TYPES = [
    ('zoho', 'Zoho People'),
    ('excel', 'Excel File Import'),
    ('sap', 'SAP SuccessFactors'),
    ('workday', 'Workday'),
    ('oracle', 'Oracle HCM'),
    ('darwin', 'DarwinHR (Darwinbox)'),
    ('demo', 'Demo / Stub (Testing)'),
]

HTTP_METHODS = [('get', 'GET'), ('post', 'POST')]

# The per-FIELD type vocabulary, declared once (Integrations Cycle 6).
#
# It is `hr.integration.field.mapping.source_data_type`'s own selection, moved
# here so that the catalogue row describing a field and the mapping consuming it
# cannot drift into two vocabularies. `source_data_type` decides whether
# `preview_transform` parses a sample as a float, so a catalogue that could
# invent a type name the mapping has never heard of would produce a preview that
# disagrees with the sync — silently, and only for that one field.
#
# Deliberately NOT the same list as `DATA_TYPES` above: that one says which FEED
# a row came from (employee / attendance / leave …), this one says what a single
# value IS. They were confused once already, in the first draft of this cycle.
SOURCE_DATA_TYPES = [
    ('string', 'Text'),
    ('number', 'Number'),
    ('integer', 'Integer'),
    ('float', 'Decimal'),
    ('date', 'Date'),
    ('datetime', 'Date/Time'),
    ('boolean', 'Yes/No'),
    ('currency', 'Currency'),
]

SYNC_STATUSES = [
    ('success', 'Success'),
    ('partial', 'Partial Success'),
    ('failed', 'Failed'),
]

# The store states that count as "waiting for you" — everything that has not
# been archived. Identical to `_compute_data_store_count`'s domain on purpose;
# see rule 2 in the module docstring.
STAGED_DOMAIN = [('state', '!=', 'archived')]


class HrIntegrationEndpoint(models.Model):
    """One API a connector calls — the feed behind a data type."""

    _name = 'hr.integration.endpoint'
    _description = 'HR Integration Endpoint'
    _order = 'sequence, name, id'

    connector_id = fields.Many2one(
        'hr.integration.connector', string='Connector',
        required=True, ondelete='cascade', index=True)
    connector_type = fields.Selection(
        related='connector_id.connector_type', store=True)

    name = fields.Char(string='Feed', required=True)
    code = fields.Char(
        string='Code', required=True,
        help="Stable slug for this feed, e.g. zoho_employees. Unique per "
             "connector — the catalogue sync matches on it.")
    data_type = fields.Selection(
        DATA_TYPES, string='Data Type', required=True, index=True,
        help="What kind of record this feed produces. Shared with the API data "
             "store, so a feed's rows can always be found.")

    http_method = fields.Selection(HTTP_METHODS, string='Method', default='get')
    path = fields.Char(
        string='Path',
        help="Relative path appended to the connector's API endpoint, or an "
             "absolute URL when this feed lives somewhere else.")
    params_note = fields.Char(
        string='Parameters',
        help="Human note about the query this feed needs, e.g. "
             "\"sIndex, limit=200, dateFormat\".")
    description = fields.Text(string='Description')

    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    is_legacy_abm = fields.Boolean(
        string='Legacy ABM',
        help="Used by the legacy ABM application.")

    last_sync = fields.Datetime(string='Last Sync')
    last_sync_status = fields.Selection(SYNC_STATUSES, string='Last Sync Status')
    last_error = fields.Char(string='Last Error')

    synced_count = fields.Integer(
        string='Records Pulled', compute='_compute_counts')
    staged_count = fields.Integer(
        string='Staged Records', compute='_compute_counts')
    mapping_count = fields.Integer(
        string='Field Mappings', compute='_compute_counts')

    # W33: `_sql_constraints = [...]` is no longer supported on Odoo 19 — the
    # registry logs one WARNING and then ignores the list, so the constraint
    # silently does not exist in PostgreSQL. `models.Constraint` is the
    # supported form (precedent: pb_schedule/models/schedule_budget.py:73).
    _connector_code_uniq = models.Constraint(
        'unique(connector_id, code)',
        'This connector already has a feed with that code.',
    )

    # ------------------------------------------------------------- deployed?
    @api.model
    def _schema_ready(self):
        """Does THIS database actually have the feeds table?

        The addons tree is SHARED by every database on this box, but a schema is
        created by an UPGRADE, per database. So between the rsync of a module
        that adds a model and the `-u` of database N, database N loads code
        describing a table it has not got — and `'hr.integration.endpoint' in
        self.env` is True the whole time, because the model class is registered
        from the python, not from the schema. That probe therefore answers the
        wrong question, and the right one is asked of PostgreSQL.

        Measured on this box before it was guarded: the Integrations board's
        per-connector `try/except` swallowed the `UndefinedTable`, printed a
        board with zero connectors, and left the request's transaction ABORTED
        so that everything after it failed too — a whole cockpit gone, quietly,
        on three tenant databases (W116's family: a shared tree makes any schema
        change a deploy step on every database).

        A silent fallback would make a database that never got its upgrade
        indistinguishable from one that has no feeds (W79), so this says so in
        the log, once per registry, naming the database.
        """
        if table_exists(self.env.cr, self._table):
            return True
        if not self.env.registry.__dict__.get('_pb_feeds_schema_warned'):
            self.env.registry.__dict__['_pb_feeds_schema_warned'] = True
            _logger.warning(
                "Database %s loads the connector-feeds code but has no %s "
                "table: this database has not been upgraded since the model "
                "was added. Feeds are hidden until `-u pb_hr_payroll_formula` "
                "runs here. Every other Integrations surface is unaffected.",
                self.env.cr.dbname, self._table)
        return False

    # ------------------------------------------------------------------ counts
    def _compute_counts(self):
        """Store-row and mapping arithmetic, batched.

        `staged_count` is the connector board's own definition narrowed by data
        type; `synced_count` counts EVERY row this feed has ever put in the
        store, archived ones included — a row that was archived was still
        pulled. The two therefore nest (`staged <= synced`) and neither can
        contradict the number on the board.
        """
        Store = self.env['hr.api.data.store']
        Map = self.env['hr.integration.field.mapping']
        if not self:
            return
        keys = [(e.connector_id.id, e.data_type) for e in self
                if e.connector_id and e.data_type]
        conn_ids = sorted({k[0] for k in keys})
        types = sorted({k[1] for k in keys})

        # `_read_group` (not `read_group`): Odoo 19's own aggregation door,
        # returning tuples with the many2one already browsed.
        synced, staged = {}, {}
        if conn_ids and types:
            base = [('connector_id', 'in', conn_ids), ('data_type', 'in', types)]
            synced = {
                (conn.id, dt): n for conn, dt, n in Store._read_group(
                    base, ['connector_id', 'data_type'], ['__count'])
            }
            staged = {
                (conn.id, dt): n for conn, dt, n in Store._read_group(
                    base + STAGED_DOMAIN, ['connector_id', 'data_type'],
                    ['__count'])
            }

        maps = {}
        ids = [e.id for e in self if e.id]
        if ids:
            maps = {
                ep.id: n for ep, n in Map._read_group(
                    [('endpoint_id', 'in', ids)], ['endpoint_id'], ['__count'])
                if ep
            }

        for e in self:
            key = (e.connector_id.id, e.data_type)
            e.synced_count = synced.get(key, 0)
            e.staged_count = staged.get(key, 0)
            e.mapping_count = maps.get(e.id, 0)


class HrIntegrationEndpointTemplate(models.Model):
    """The vendor catalogue a connector's feeds are instantiated from.

    Data-XML seedable and empty until Cycle 3 ships the Zoho People rows the
    legacy ABM inventory describes. It is deliberately NOT a per-connector
    record: a template belongs to a VENDOR, and every connector of that vendor
    gets the same starting set.
    """

    _name = 'hr.integration.endpoint.template'
    _description = 'HR Integration Endpoint Template'
    _order = 'connector_type, sequence, id'

    connector_type = fields.Selection(CONNECTOR_TYPES, required=True, index=True)
    code = fields.Char(required=True)
    name = fields.Char(required=True)
    data_type = fields.Selection(DATA_TYPES, required=True)
    http_method = fields.Selection(HTTP_METHODS, default='get')
    path = fields.Char()
    params_note = fields.Char()
    description = fields.Text()
    sequence = fields.Integer(default=10)
    is_legacy_abm = fields.Boolean(
        help="Used by the legacy ABM application.")
    active = fields.Boolean(default=True)

    _type_code_uniq = models.Constraint(
        'unique(connector_type, code)',
        'That vendor already has an endpoint template with this code.',
    )
