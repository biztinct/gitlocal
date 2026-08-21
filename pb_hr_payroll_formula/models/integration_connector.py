# -*- coding: utf-8 -*-

import time
import logging
from datetime import date, datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .integration_endpoint import SOURCE_DATA_TYPES

_logger = logging.getLogger(__name__)


class HrIntegrationConnector(models.Model):
    """
    HR Integration Connector - Manages connections to external HR systems
    like Zoho People, SAP SuccessFactors, Workday, Oracle HCM, or Excel files.
    """
    _name = 'hr.integration.connector'
    _description = 'HR System Integration Connector'
    _inherit = ['mail.thread']
    _order = 'sequence, name'
    _rec_name = 'name'

    # ==========================================
    # BASIC FIELDS
    # ==========================================
    name = fields.Char(
        string='Connector Name',
        required=True,
        tracking=True
    )

    connector_type = fields.Selection([
        ('zoho', 'Zoho People'),
        ('excel', 'Excel File Import'),
        ('sap', 'SAP SuccessFactors'),
        ('workday', 'Workday'),
        ('oracle', 'Oracle HCM'),
        ('darwin', 'DarwinHR (Darwinbox)'),
        ('demo', 'Demo / Stub (Testing)')
    ], string='Connector Type', required=True, tracking=True)

    description = fields.Text(
        string='Description'
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    # ==========================================
    # CONNECTION SETTINGS
    # ==========================================
    api_endpoint = fields.Char(
        string='API Endpoint',
        help="Base URL for API calls"
    )

    api_version = fields.Char(
        string='API Version',
        default='v1'
    )

    auth_type = fields.Selection([
        ('oauth2', 'OAuth 2.0'),
        ('api_key', 'API Key'),
        ('basic', 'Basic Authentication'),
        ('bearer', 'Bearer Token')
    ], string='Authentication Type', default='oauth2')

    # ==========================================
    # CREDENTIALS (Sensitive - System Only)
    # ==========================================
    client_id = fields.Char(
        string='Client ID',
        groups="base.group_system"
    )

    client_secret = fields.Char(
        string='Client Secret',
        groups="base.group_system"
    )

    api_key = fields.Char(
        string='API Key',
        groups="base.group_system"
    )

    username = fields.Char(
        string='Username',
        groups="base.group_system"
    )

    password = fields.Char(
        string='Password',
        groups="base.group_system"
    )

    access_token = fields.Text(
        string='Access Token',
        groups="base.group_system"
    )

    refresh_token = fields.Text(
        string='Refresh Token',
        groups="base.group_system"
    )

    token_expiry = fields.Datetime(
        string='Token Expiry',
        groups="base.group_system"
    )

    # ==========================================
    # OAUTH SETTINGS
    # ==========================================
    oauth_authorize_url = fields.Char(
        string='Authorization URL'
    )

    oauth_token_url = fields.Char(
        string='Token URL'
    )

    oauth_scope = fields.Char(
        string='OAuth Scope'
    )

    # ==========================================
    # FIELD MAPPINGS
    # ==========================================
    field_mapping_ids = fields.One2many(
        'hr.integration.field.mapping',
        'connector_id',
        string='Field Mappings'
    )

    mapping_count = fields.Integer(
        string='Mappings',
        compute='_compute_mapping_count'
    )

    # ==========================================
    # ENDPOINTS — one connector, many feeds
    # ==========================================
    endpoint_ids = fields.One2many(
        'hr.integration.endpoint',
        'connector_id',
        string='Endpoints',
    )

    endpoint_count = fields.Integer(
        string='Endpoints',
        compute='_compute_endpoint_count',
    )

    # ==========================================
    # API DATA STORE & TRANSFORMATION RULES
    # ==========================================
    data_store_ids = fields.One2many(
        'hr.api.data.store',
        'connector_id',
        string='Stored Data',
    )
    data_store_count = fields.Integer(
        string='Stored Records',
        compute='_compute_data_store_count',
    )
    transformation_rule_ids = fields.One2many(
        'hr.api.transformation.rule',
        'connector_id',
        string='Transformation Rules',
    )

    # ==========================================
    # CONNECTION STATUS
    # ==========================================
    connection_status = fields.Selection([
        ('disconnected', 'Disconnected'),
        ('connecting', 'Connecting...'),
        ('connected', 'Connected'),
        ('error', 'Error')
    ], string='Status', default='disconnected', tracking=True)

    last_sync = fields.Datetime(
        string='Last Sync',
        help="When this connector last PULLED data. Not written by a "
             "connection test — see last_connection_test.",
    )

    # Integrations Cycle 7, WP-5. `base_connector.update_connector_status()`
    # stamped `last_sync` on every CONNECTION-STATUS change, so a successful
    # "Test connection" wrote the clock that the cockpit header prints as
    # "Last sync". On abm that produced two truths on one screen: the header
    # read `Connected · Last sync 2026-08-20 23:25` above seven feeds all
    # reading `Never synced · 0 staged · 0 pulled`. The row proves it —
    # last_sync_status NULL, total_synced_records NULL, zero store rows, and
    # last_sync_message the literal string "Connection successful".
    # A test is a fact about the CONNECTION and now has its own field.
    last_connection_test = fields.Datetime(
        string='Last Connection Test', readonly=True, copy=False,
        help="When the connection to this system was last tested. A test "
             "proves the credentials work; it moves no data.",
    )

    last_sync_status = fields.Selection([
        ('success', 'Success'),
        ('partial', 'Partial Success'),
        ('failed', 'Failed')
    ], string='Last Sync Status')

    last_sync_message = fields.Text(
        string='Last Sync Message'
    )

    last_error = fields.Text(
        string='Last Error'
    )

    sync_interval = fields.Integer(
        string='Sync Interval (minutes)',
        default=60,
        help="Automatic sync interval in minutes (0 = manual only)"
    )

    # ==========================================
    # SYNC STATISTICS
    # ==========================================
    total_synced_employees = fields.Integer(
        string='Total Synced Employees',
        readonly=True
    )

    total_synced_records = fields.Integer(
        string='Total Synced Records',
        readonly=True
    )

    # ==========================================
    # COUNTRY FILTER
    # ==========================================
    country_code = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
        ('TH', 'Thailand'),
        ('KH', 'Cambodia'),
        ('PH', 'Philippines'),
        ('ALL', 'All Countries')
    ], string='Country Filter', default='ALL')

    # ==========================================
    # FILE IMPORT SETTINGS (for Excel connector)
    # ==========================================
    last_import_file = fields.Binary(
        string='Last Imported File'
    )

    last_import_filename = fields.Char(
        string='Last Filename'
    )

    file_header_row = fields.Integer(
        string='Header Row',
        default=1,
        help="Row number containing column headers"
    )

    file_data_start_row = fields.Integer(
        string='Data Start Row',
        default=2,
        help="First row containing data"
    )

    file_sheet_name = fields.Char(
        string='Sheet Name',
        help="Name of sheet to import (leave empty for first sheet)"
    )

    # ==========================================
    # COMPUTED
    # ==========================================
    @api.depends('field_mapping_ids')
    def _compute_mapping_count(self):
        for record in self:
            record.mapping_count = len(record.field_mapping_ids)

    def _compute_data_store_count(self):
        for record in self:
            record.data_store_count = self.env['hr.api.data.store'].search_count([
                ('connector_id', '=', record.id),
                ('state', '!=', 'archived'),
            ])

    @api.depends('endpoint_ids')
    def _compute_endpoint_count(self):
        ready = self.env['hr.integration.endpoint']._schema_ready()
        for record in self:
            record.endpoint_count = len(record.endpoint_ids) if ready else 0

    # ==========================================
    # ENDPOINT CATALOGUE
    # ==========================================
    @api.model_create_multi
    def create(self, vals_list):
        """A new connector catalogues its own feeds.

        Nothing has to be pulled for that to be useful: the vendor catalogue
        (Cycle 3's data) knows what a Zoho People connector talks to before it
        has ever been connected. The sync is create-only and idempotent, so
        running it here costs a new connector one query and can never overwrite
        anything.
        """
        records = super().create(vals_list)
        if self.env['hr.integration.endpoint']._schema_ready():
            for record in records:
                record.action_sync_endpoint_catalog()
        return records

    @api.model
    def _free_endpoint_code(self, base, taken):
        """A code no endpoint on this connector holds yet.

        `(connector_id, code)` is a database UNIQUE, so a derived feed whose
        natural code was already claimed by a vendor template row for ANOTHER
        data type must not simply be dropped — that would leave a data type
        sitting in the store with no feed describing it, silently.
        """
        if base not in taken:
            return base
        for suffix in ('_feed', '_feed2', '_feed3'):
            if base + suffix not in taken:
                return base + suffix
        return '%s_%s' % (base, len(taken))

    def action_sync_endpoint_catalog(self):
        """Catalogue this connector's feeds from the two sources we have.

        (a) the vendor catalogue — every `hr.integration.endpoint.template` row
            for this connector type; and
        (b) the evidence — every distinct `data_type` already present in this
            connector's stored rows that no endpoint covers yet.

        CREATE-ONLY, and that is the whole contract: this runs on create, from
        the cockpit's "Detect feeds" button and from the demo seeder, so it will
        meet endpoints an operator has renamed, re-pathed or deactivated. A row
        that already exists by `code` (or, for the derived half, by `data_type`)
        is counted as SKIPPED and left exactly as it is — the same
        never-overwrite semantics `action_apply_mapping_template` has.

        Returns `{'created': n, 'skipped': n}`.
        """
        self.ensure_one()
        Endpoint = self.env['hr.integration.endpoint']
        Template = self.env['hr.integration.endpoint.template']
        if not Endpoint._schema_ready():
            return {'created': 0, 'skipped': 0}

        # `active_test=False`: a DEACTIVATED endpoint still owns its code, and
        # re-creating it because it is filtered out of the o2m would be the
        # rudest possible reading of "create-only".
        existing = self.env['hr.integration.endpoint'].with_context(
            active_test=False).search([('connector_id', '=', self.id)])
        codes = {e.code for e in existing if e.code}
        covered_types = {e.data_type for e in existing if e.data_type}

        vals_list = []
        skipped = 0

        for t in Template.with_context(active_test=False).search(
                [('connector_type', '=', self.connector_type)]):
            if not t.code or t.code in codes:
                skipped += 1
                continue
            vals_list.append({
                'connector_id': self.id,
                'name': t.name or t.code,
                'code': t.code,
                'data_type': t.data_type,
                'http_method': t.http_method or 'get',
                'path': t.path or False,
                'params_note': t.params_note or False,
                'description': t.description or False,
                'sequence': t.sequence or 10,
                'is_legacy_abm': t.is_legacy_abm,
                'active': t.active,
            })
            codes.add(t.code)
            covered_types.add(t.data_type)

        # The derived half: a data type sitting in the store with no feed
        # describing it is a feed somebody ran before this model existed.
        labels = dict(self.env['hr.api.data.store']._fields['data_type'].selection)
        present = [
            dt for dt, in self.env['hr.api.data.store']._read_group(
                [('connector_id', '=', self.id)], ['data_type'])
            if dt
        ]
        for dt in sorted(present):
            if dt in covered_types:
                skipped += 1
                continue
            vals_list.append({
                'connector_id': self.id,
                'name': labels.get(dt, dt),
                'code': self._free_endpoint_code(dt, codes),
                'data_type': dt,
                'http_method': 'get',
                'description': _(
                    'Derived from records already in the API data store.'),
                'sequence': 50,
            })
            codes.add(vals_list[-1]['code'])
            covered_types.add(dt)

        if vals_list:
            Endpoint.create(vals_list)
        result = {'created': len(vals_list), 'skipped': skipped}
        # Cycle 6 — a feed's SHAPE is catalogued through the same door as the
        # feed. Deliberately the same hook rather than a second button: an
        # operator who has just pressed "Detect feeds" has said everything they
        # need to say, and a catalogue that lists seven APIs and nothing about
        # any of them is the half-answer this cycle exists to stop giving.
        result['fields'] = self.action_sync_endpoint_field_catalog()
        return result

    def action_sync_endpoint_field_catalog(self):
        """Instantiate this vendor's endpoint-FIELD templates on this connector.

        CREATE-ONLY, matched on `(endpoint_id, path)`, with `active_test=False`
        so a row an operator deactivated still owns its path and is not
        resurrected as a duplicate — the identical argument
        `action_sync_endpoint_catalog` makes about a deactivated feed's code.

        A template whose `endpoint_code` this connector has no feed for is
        SKIPPED and counted, never mapped onto "some other feed": the whole
        value of the catalogue is that a path is attached to the API that
        actually returns it.

        Returns `{'created': n, 'skipped': n, 'unresolved': n}`.
        """
        self.ensure_one()
        Field = self.env['hr.integration.endpoint.field']
        Template = self.env['hr.integration.endpoint.field.template']
        Endpoint = self.env['hr.integration.endpoint']
        if not (Endpoint._schema_ready() and Field._schema_ready()):
            return {'created': 0, 'skipped': 0, 'unresolved': 0}

        endpoints = Endpoint.with_context(active_test=False).search(
            [('connector_id', '=', self.id)])
        by_code = {e.code: e for e in endpoints if e.code}
        if not by_code:
            return {'created': 0, 'skipped': 0, 'unresolved': 0}

        existing = Field.with_context(active_test=False).search(
            [('endpoint_id', 'in', endpoints.ids)])
        taken = {(f.endpoint_id.id, f.path) for f in existing}

        vals_list, skipped, unresolved = [], 0, 0
        for t in Template.with_context(active_test=False).search(
                [('connector_type', '=', self.connector_type)]):
            ep = by_code.get(t.endpoint_code)
            if not ep:
                unresolved += 1
                continue
            key = (ep.id, t.path)
            if not t.path or key in taken:
                skipped += 1
                continue
            vals_list.append({
                'endpoint_id': ep.id,
                'path': t.path,
                'label': t.label or t.path,
                'source_data_type': t.source_data_type or 'string',
                'sample_value': t.sample_value or False,
                'is_required': t.is_required,
                'notes': t.notes or False,
                'sequence': t.sequence or 10,
                'is_legacy_abm': t.is_legacy_abm,
                'active': t.active,
            })
            taken.add(key)

        if vals_list:
            Field.create(vals_list)
        return {'created': len(vals_list), 'skipped': skipped,
                'unresolved': unresolved}

    # ==========================================
    # VENDOR METADATA FETCH (Cycle 6, WP-3)
    # ==========================================
    #
    # Which connector classes can actually be ASKED what they deliver, and what
    # the honest name for their answer is. Three tiers, because there are three
    # genuinely different things `get_available_fields()` does in this codebase
    # and calling them all "field discovery" would let a hard-coded example list
    # arrive on screen wearing a live sync's clothes:
    #
    #   'live'   — a real request to the vendor. `zoho_connector.py:216` GETs
    #              `forms/{form}/components`; `excel_connector.py:272` reads the
    #              headers of the file that is loaded.
    #   'sample' — derived from a sample record built into the connector class
    #              (`darwin_connector.py:116`, `demo_connector.py:421`). Real
    #              paths, real types, no network. Worth having, and worth saying.
    #   None     — a STUB. `sap_connector.py:79`, `workday_connector.py:75` and
    #              `oracle_connector.py:77` each log "not implemented" and then
    #              return a hard-coded example list. Writing those into a
    #              catalogue would publish four invented fields as SAP's schema,
    #              which is the exact failure this whole cycle is about.
    FIELD_FETCH_SUPPORT = {
        'zoho': 'live',
        'excel': 'live',
        'darwin': 'sample',
        'demo': 'sample',
        'sap': None,
        'workday': None,
        'oracle': None,
    }

    # Zoho's metadata call reports the FORM a component belongs to; the feed
    # catalogue is keyed on our own endpoint codes. Anything not listed falls
    # back to the feed the operator pressed the button on.
    _VENDOR_FORM_ENDPOINT = {
        'P_Employee': 'zohoemployees',
        'P_Salary': 'zohosalary',
        'P_Attendance': 'zohoattsummary',
    }

    def field_fetch_capability(self):
        """`{'mode', 'ready', 'reason'}` — can this connector be asked?

        Split from the fetch itself so a UI can grey the button out with a
        sentence rather than offering a door that always answers "no".
        """
        self.ensure_one()
        mode = self.FIELD_FETCH_SUPPORT.get(self.connector_type)
        if not mode:
            return {'mode': None, 'ready': False, 'reason': _(
                "Payobook's %s connector cannot yet ask that system what "
                "fields it has. The expected fields below come from the "
                "shipped catalogue instead.") % (
                    dict(self._fields['connector_type'].selection).get(
                        self.connector_type, self.connector_type))}
        if mode == 'live' and not self._has_credentials():
            return {'mode': mode, 'ready': False, 'reason': _(
                "Add this connector's credentials first — the field list is "
                "read from the vendor, over an authenticated call.")}
        return {'mode': mode, 'ready': True, 'reason': ''}

    def _has_credentials(self):
        """Is there anything to authenticate WITH?

        Read as booleans only. No caller of this method, and nothing it returns,
        ever carries a secret's VALUE — the cockpit payload is built from this,
        and a credential that reached the browser to be greyed out would be a
        credential in a JSON response.
        """
        self.ensure_one()
        if self.connector_type == 'excel':
            return True          # the file is the credential
        # `sudo()`: every one of these carries `groups="base.group_system"`
        # (:98-121), so a payroll manager reading them directly gets an
        # AccessError, not a False — and "is there a credential" is a question
        # that must be answerable by the person looking at the cockpit. The
        # sudo reads them and immediately throws the values away; only the
        # boolean leaves this method.
        rec = self.sudo()
        return bool(rec.api_key or rec.access_token or rec.refresh_token
                    or rec.password or rec.username)

    def action_fetch_endpoint_fields(self, endpoint_id=None):
        """Ask the vendor what this feed delivers, and catalogue the answer.

        CREATE-ONLY on `(endpoint_id, path)` like every other catalogue in this
        file, with ONE deliberate exception the handover asks for: an existing
        row's `label` and `source_data_type` are REFRESHED from the vendor,
        because those two are the vendor's to name and a renamed picklist that
        keeps its old caption is a catalogue lying quietly. Everything an
        operator can be said to own — `notes`, `active`, `sequence`,
        `sample_value` — is left exactly as it is.

        Returns `{'ok', 'created', 'updated', 'skipped', 'mode', 'msg'}`. It
        never returns a credential, and it never raises at the caller: a vendor
        that is down is a sentence, not a traceback.
        """
        self.ensure_one()
        Field = self.env['hr.integration.endpoint.field']
        Endpoint = self.env['hr.integration.endpoint']
        blank = {'ok': False, 'created': 0, 'updated': 0, 'skipped': 0}
        if not (Endpoint._schema_ready() and Field._schema_ready()):
            return dict(blank, mode=None, msg=_(
                "This database has not been upgraded for the field catalogue "
                "yet."))
        cap = self.field_fetch_capability()
        if not cap['ready']:
            return dict(blank, mode=cap['mode'], msg=cap['reason'])

        endpoints = Endpoint.with_context(active_test=False).search(
            [('connector_id', '=', self.id)])
        by_code = {e.code: e for e in endpoints if e.code}
        wanted = endpoints.filtered(lambda e: e.id == int(endpoint_id or 0))[:1]
        fallback = wanted or endpoints.filtered(
            lambda e: e.data_type == 'employee')[:1] or endpoints[:1]
        if not fallback:
            return dict(blank, mode=cap['mode'], msg=_(
                "Catalogue this connector's feeds first."))

        try:
            raw = self._get_connector_instance().get_available_fields() or []
        except Exception as e:
            _logger.warning("Field fetch failed on connector %s (%s): %s: %s",
                            self.id, self.connector_type, type(e).__name__, e)
            return dict(blank, mode=cap['mode'], msg=_(
                "That system could not be reached for its field list. The "
                "details are in the server log."))

        types = {k for k, _l in SOURCE_DATA_TYPES}
        existing = {(f.endpoint_id.id, f.path): f
                    for f in Field.with_context(active_test=False).search(
                        [('endpoint_id', 'in', endpoints.ids)])}
        vals_list, created, updated, skipped = [], 0, 0, 0
        seen = set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            # The vendor's `path` may be form-prefixed (`P_Employee.EmailID`);
            # a mapping's `source_field` never is, and a catalogue row that
            # does not JOIN to a mapping is a row nobody will ever see.
            path = (item.get('name') or '').strip() or \
                (item.get('path') or '').split('.')[-1].strip()
            if not path:
                continue
            ep = by_code.get(
                self._VENDOR_FORM_ENDPOINT.get(item.get('form') or '', ''),
                fallback)
            if wanted and ep.id != wanted.id:
                continue
            key = (ep.id, path)
            if key in seen:
                continue
            seen.add(key)
            dtype = item.get('data_type') or 'string'
            dtype = dtype if dtype in types else 'string'
            row = existing.get(key)
            if row:
                fresh = {}
                label = (item.get('label') or '').strip()
                if label and label != row.label:
                    fresh['label'] = label
                if dtype != row.source_data_type:
                    fresh['source_data_type'] = dtype
                if fresh:
                    row.write(fresh)
                    updated += 1
                else:
                    skipped += 1
                continue
            vals_list.append({
                'endpoint_id': ep.id,
                'path': path,
                'label': (item.get('label') or '').strip() or path,
                'source_data_type': dtype,
                'sample_value': self._sample_str(item.get('sample_value')),
                'is_required': bool(item.get('required')),
                'sequence': 20,
            })
        if vals_list:
            Field.create(vals_list)
            created = len(vals_list)
        if not (created or updated or skipped):
            return dict(blank, mode=cap['mode'], msg=_(
                "That system returned no fields for this feed."))
        return {'ok': True, 'created': created, 'updated': updated,
                'skipped': skipped, 'mode': cap['mode'],
                'msg': _("%(new)s new, %(upd)s updated, %(same)s unchanged.",
                         new=created, upd=updated, same=skipped)}

    @staticmethod
    def _sample_str(value):
        """A vendor's sample, as a short string — or nothing at all.

        `False` rather than `''` so the Char is genuinely empty; a sample that
        is the literal string "None" is how a placeholder starts looking like
        data.
        """
        if value is None or value is False or value == '':
            return False
        return str(value)[:128]

    def _stamp_endpoint(self, data_type, status, error=False):
        """Record a pull's outcome on the feed that produced it.

        Create-if-missing through the same catalogue path, so a connector that
        pulls a data type nobody catalogued ends up with the feed rather than
        with the outcome silently going nowhere. One endpoint per data type is
        stamped — the first by sequence — because `action_pull_data` pulls a
        TYPE, not a path.
        """
        self.ensure_one()
        Endpoint = self.env['hr.integration.endpoint']
        if not Endpoint._schema_ready():
            return Endpoint
        ep = Endpoint.search(
            [('connector_id', '=', self.id), ('data_type', '=', data_type)],
            order='sequence, id', limit=1)
        if not ep:
            self.action_sync_endpoint_catalog()
            ep = Endpoint.search(
                [('connector_id', '=', self.id), ('data_type', '=', data_type)],
                order='sequence, id', limit=1)
        if not ep:
            # A pull that produced no rows leaves the catalogue nothing to
            # derive from, and "this feed failed" is exactly the outcome that
            # must not be dropped. Mint the generic feed here, under the same
            # code the catalogue would have used, so a later sync skips it.
            labels = dict(
                self.env['hr.api.data.store']._fields['data_type'].selection)
            taken = set(Endpoint.with_context(active_test=False).search(
                [('connector_id', '=', self.id)]).mapped('code'))
            ep = Endpoint.create({
                'connector_id': self.id,
                'name': labels.get(data_type, data_type),
                'code': self._free_endpoint_code(data_type, taken),
                'data_type': data_type,
                'sequence': 50,
            })
        ep.write({
            'last_sync': fields.Datetime.now(),
            'last_sync_status': status,
            'last_error': (error or '')[:512] or False,
        })
        return ep

    # ==========================================
    # TRANSFORMATION-RULE CATALOGUE (Cycle 3)
    # ==========================================
    def action_sync_transformation_rules(self):
        """Instantiate this vendor's transformation-rule templates.

        The third catalogue, and the same contract as the other two: CREATE-ONLY,
        matched on `output_key`. An operator who has retuned a rule — changed the
        filter, changed the default, switched it off — keeps their version
        through every later apply, because a rule that silently reverts to the
        vendor's arithmetic is a payslip that silently changes.

        `active_test=False` for the same reason the feed catalogue uses it: a
        DEACTIVATED rule still owns its output key, and re-creating it because
        the search filtered it out would be the rudest possible reading of
        create-only.

        Returns `{'created': n, 'skipped': n}`.
        """
        self.ensure_one()
        Rule = self.env['hr.api.transformation.rule']
        Template = self.env['hr.api.transformation.rule.template']
        if not Template._schema_ready():
            return {'created': 0, 'skipped': 0}

        existing = Rule.with_context(active_test=False).search(
            [('connector_id', '=', self.id)])
        keys = {r.output_key for r in existing if r.output_key}

        vals_list = []
        skipped = 0
        for t in Template.with_context(active_test=False).search(
                [('connector_type', '=', self.connector_type)]):
            if not t.output_key or t.output_key in keys:
                skipped += 1
                continue
            vals = t._rule_vals(self)
            vals['active'] = t.active
            vals_list.append(vals)
            keys.add(t.output_key)

        if vals_list:
            Rule.create(vals_list)
        return {'created': len(vals_list), 'skipped': skipped}

    # ==========================================
    # CONNECTION ACTIONS
    # ==========================================
    def action_apply_mapping_template(self, config_id=None):
        """F114 — seed field mappings from this vendor's ready-made template.
        Matched by canonical code → 'active'; unmatched or verify/derive rows →
        'suggested' (never load-bearing). Idempotent: an existing mapping for a
        source path is never overwritten."""
        self.ensure_one()
        Tmpl = self.env['hr.integration.mapping.template']
        Map = self.env['hr.integration.field.mapping']
        rows = Tmpl.search([('connector_type', '=', self.connector_type)])
        # sudo the config read — configs are company-scoped/record-rule-gated
        # (same pattern the studio uses); the mapping setup is a trusted action.
        config = False
        if config_id:
            config = self.env['hr.formula.config'].sudo().browse(int(config_id))
            if not config.exists():
                config = False
        if not config:
            config = self.env['hr.formula.config'].sudo().search([('connector_id', '=', self.id)], limit=1)
        existing_src = set((self.field_mapping_ids.mapped('source_field')) or [])
        applied = suggested = 0
        # Which feed each template row reads from, by endpoint code. Resolved
        # ONCE against this connector's own endpoints — a template's
        # `endpoint_code` is a vendor's name for an API, and the connector may
        # not have catalogued it (or may have renamed the row). An unresolved
        # code leaves `endpoint_id` empty rather than inventing a feed.
        Endpoint = self.env['hr.integration.endpoint']
        endpoints_by_code = {
            e.code: e.id
            for e in Endpoint.with_context(active_test=False).search(
                [('connector_id', '=', self.id)])
            if e.code
        } if Endpoint._schema_ready() else {}

        def _norm(s):
            return ''.join(ch for ch in (s or '').upper() if ch.isalnum())

        for t in rows:
            if t.source_path in existing_src:
                continue
            rule = self.env['hr.formula.rule']
            exact = False
            if config:
                inputs = config.rule_ids.filtered(lambda r: r.column_type == 'input')
                tc = (t.target_code or '').upper()
                rule = inputs.filtered(lambda r: (r.code or '').upper() == tc)[:1]
                exact = bool(rule)
                if not rule:
                    # normalized fallback (strip non-alphanumerics), e.g. a tenant
                    # 'BASICSAL' ~ template 'BASIC_SAL'. A fuzzy match only PROPOSES
                    # a target — it stays 'suggested' until the batch test confirms.
                    ntc = _norm(t.target_code)
                    rule = inputs.filtered(lambda r: _norm(r.code) == ntc)[:1]
            # 'active' only for an EXACT, non-verify match; every fuzzy / unmatched
            # / verify row stays 'suggested' and is never load-bearing (D114.2).
            state = 'active' if (rule and exact and not t.verify) else 'suggested'
            Map.create({
                'connector_id': self.id,
                'connector_type': self.connector_type,
                'source_field': t.source_path,
                'source_field_label': t.target_label or t.target_code,
                'target_rule_id': rule.id if rule else False,
                'transformation_type': t.transformation_type or 'direct',
                'transformation_value': t.transformation_value or 0.0,
                'transformation_code': t.transformation_code or False,
                'is_required': t.is_required,
                'default_value': t.default_value or 0.0,
                'notes': t.note or False,
                'active_state': state,
                'endpoint_id': endpoints_by_code.get(t.endpoint_code or ''),
            })
            existing_src.add(t.source_path)
            if state == 'active':
                applied += 1
            else:
                suggested += 1
        # The vendor's AGGREGATIONS are the sibling step (Cycle 3): a field map
        # that says "OTHRS150 → Overtime 150%" is a wire to a key nothing
        # computes until the rule that computes it exists. Applying a template
        # is the moment both halves of the vendor's answer arrive, and the step
        # is create-only, so a second apply adds nothing.
        rules = self.action_sync_transformation_rules()
        return {'applied': applied, 'suggested': suggested,
                'total': applied + suggested,
                'rules_created': rules['created'],
                'rules_skipped': rules['skipped']}

    def _sample_payload(self):
        """A representative source record for mapping tests: the newest stored
        payload if a data pull has run, else the demo/stub connector's own
        built-in sample. Returns a dict or None."""
        self.ensure_one()
        store = self.env['hr.api.data.store'].sudo().search(
            [('connector_id', '=', self.id), ('raw_payload', '!=', False)],
            order='pull_date desc, id desc', limit=1)
        payload = store.raw_payload if store else None
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return payload[0]
        try:
            emps = self._get_connector_instance().fetch_employees({}) or []
        except Exception:
            emps = []
        return emps[0] if emps and isinstance(emps[0], dict) else None

    def action_test_field_mappings(self, config_id=None):
        """F114 promotion path (D114.2): test each 'suggested' mapping against a
        real sample payload and promote the ones that resolve to a value to
        'active'. Rows that don't resolve, or have no target rule yet, stay
        'suggested'. This is the ONLY way a template guess becomes load-bearing."""
        self.ensure_one()
        sample = self._sample_payload()
        suggested = self.field_mapping_ids.filtered(
            lambda m: m.active_state == 'suggested')
        if sample is None:
            return {'ok': False, 'promoted': 0, 'tested': 0,
                    'msg': _("No sample payload yet — run a data pull (or use the "
                             "demo connector) before testing.")}
        promoted = tested = 0
        for m in suggested:
            if not m.target_rule_id:
                continue
            tested += 1
            try:
                val = m.get_value_from_record(sample)
            except Exception:
                val = None
            if val is not None:
                m.active_state = 'active'
                promoted += 1
        return {'ok': True, 'promoted': promoted, 'tested': tested,
                'remaining': len(suggested) - promoted}

    @api.model
    def action_open_onboarding(self):
        """Launch the 4-step connect-your-HR-system wizard."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Connect an HR / Timesheet System'),
            'res_model': 'hr.integration.onboarding.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    def action_test_connection(self):
        """Test the connection to the external system"""
        self.ensure_one()
        self.connection_status = 'connecting'

        try:
            connector = self._get_connector_instance()
            success, message = connector.test_connection()

            if success:
                self.write({
                    'connection_status': 'connected',
                    'last_error': False,
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': message or _('Connected to %s') % self.name,
                        'type': 'success',
                    }
                }
            else:
                self.write({
                    'connection_status': 'error',
                    'last_error': message,
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Failed'),
                        'message': message,
                        'type': 'danger',
                        'sticky': True,
                    }
                }
        except Exception as e:
            self.write({
                'connection_status': 'error',
                'last_error': str(e),
            })
            raise UserError(_('Connection test failed: %s') % str(e))

    def action_disconnect(self):
        """Disconnect and clear tokens"""
        self.ensure_one()
        self.write({
            'connection_status': 'disconnected',
            'access_token': False,
            'token_expiry': False,
        })

    def action_refresh_token(self):
        """Refresh OAuth access token"""
        self.ensure_one()
        if self.auth_type != 'oauth2':
            raise UserError(_('Token refresh is only available for OAuth 2.0'))

        try:
            connector = self._get_connector_instance()
            connector.refresh_access_token()
            self.connection_status = 'connected'
        except Exception as e:
            self.connection_status = 'error'
            self.last_error = str(e)
            raise UserError(_('Token refresh failed: %s') % str(e))

    # ==========================================
    # SYNC ACTIONS
    # ==========================================
    def action_sync_now(self):
        """Manually trigger data sync"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sync Data'),
            'res_model': 'hr.integration.sync.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_connector_id': self.id,
            }
        }

    def action_fetch_available_fields(self):
        """Fetch available fields from the source system"""
        self.ensure_one()
        try:
            connector = self._get_connector_instance()
            fields_list = connector.get_available_fields()

            # Create/update field mappings
            existing_sources = self.field_mapping_ids.mapped('source_field')

            for field_info in fields_list:
                source_field = field_info.get('name')
                if source_field and source_field not in existing_sources:
                    self.env['hr.integration.field.mapping'].create({
                        'connector_id': self.id,
                        'source_field': source_field,
                        'source_field_label': field_info.get('label', source_field),
                        'source_data_type': field_info.get('type', 'string'),
                    })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Fields Fetched'),
                    'message': _('%d fields discovered') % len(fields_list),
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(_('Failed to fetch fields: %s') % str(e))

    # ==========================================
    # VIEW ACTIONS
    # ==========================================
    def action_view_mappings(self):
        """Open field mappings view"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Field Mappings'),
            'res_model': 'hr.integration.field.mapping',
            'view_mode': 'list,form',
            'domain': [('connector_id', '=', self.id)],
            'context': {'default_connector_id': self.id},
        }

    def action_view_sync_history(self):
        """View sync history — now shows data store records."""
        self.ensure_one()
        return self.action_view_data_store()

    def action_view_data_store(self):
        """View stored API data records for this connector."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('API Data Store — %s') % self.name,
            'res_model': 'hr.api.data.store',
            # Odoo 19's web client reads action.views.map(...) in _preprocessAction,
            # so a bare view_mode (no views) crashes with "action.views is undefined".
            # Provide the views pairs explicitly (view_mode kept for completeness).
            'views': [(False, 'list'), (False, 'form')],
            'view_mode': 'list,form',
            'domain': [('connector_id', '=', self.id)],
            'context': {
                'default_connector_id': self.id,
                'search_default_active_records': 1,
            },
        }

    # ==========================================
    # PULL DATA — Core API Integration
    # ==========================================
    def action_pull_data(self, data_types=None, period_from=None, period_to=None,
                         triggered_by='manual'):
        """
        Pull data from external HRIS and store in hr.api.data.store.

        This is the primary entry point for the Pull → Store → Transform pipeline.

        Args:
            data_types: list of data type strings to pull (default: ['employee', 'salary'])
            period_from: start of period (date)
            period_to: end of period (date)
            triggered_by: 'manual' or 'cron'

        Returns:
            Action dict with notification of results.
        """
        self.ensure_one()
        DataStore = self.env['hr.api.data.store']

        if not data_types:
            data_types = ['employee', 'salary']
            # Demo connector supports all data types
            if self.connector_type == 'demo':
                data_types = ['employee', 'salary', 'dependent', 'attendance', 'leave']

        # Default period: current month
        if not period_from:
            import calendar
            today = date.today()
            period_from = today.replace(day=1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            period_to = today.replace(day=last_day)

        results = {
            'pulled': 0,
            'changes': 0,
            'errors': [],
        }

        try:
            connector = self._get_connector_instance()

            # Authenticate
            if not connector.authenticate():
                raise UserError(_('Authentication failed for connector %s') % self.name)

            # Pull employee data
            if 'employee' in data_types:
                start_time = time.time()
                employees = connector.fetch_employees()
                pull_ms = int((time.time() - start_time) * 1000)

                if employees:
                    for emp_data in employees:
                        self._store_api_record(
                            DataStore, emp_data,
                            data_type='employee',
                            period_from=period_from,
                            period_to=period_to,
                            pull_ms=pull_ms,
                            triggered_by=triggered_by,
                            results=results,
                        )
                # The employee branch has no inner try/except — a failure here
                # propagates to the outer one, which stamps nothing because the
                # whole pull failed and the CONNECTOR carries that. What this
                # records is the branch that ran.
                self._stamp_endpoint('employee', 'success')

            # Pull salary/payroll data
            if 'salary' in data_types:
                start_time = time.time()
                try:
                    # Get employee IDs for payroll pull
                    emp_ids = []
                    emp_records = DataStore.search([
                        ('connector_id', '=', self.id),
                        ('data_type', '=', 'employee'),
                        ('state', 'in', ['extracted']),
                    ])
                    for emp_rec in emp_records:
                        ext_id = emp_rec.employee_external_id
                        if ext_id and ext_id not in emp_ids:
                            emp_ids.append(ext_id)

                    if emp_ids:
                        payroll_data = connector.fetch_payroll_data(
                            emp_ids,
                            str(period_from),
                            str(period_to),
                        )
                        pull_ms = int((time.time() - start_time) * 1000)

                        if payroll_data:
                            for emp_id, salary_data in payroll_data.items():
                                self._store_api_record(
                                    DataStore, salary_data,
                                    data_type='salary',
                                    employee_external_id=str(emp_id),
                                    period_from=period_from,
                                    period_to=period_to,
                                    pull_ms=pull_ms,
                                    triggered_by=triggered_by,
                                    results=results,
                                )
                    self._stamp_endpoint('salary', 'success')
                except Exception as e:
                    results['errors'].append(f"Salary pull error: {str(e)}")
                    _logger.warning("Salary pull failed for connector %s: %s", self.name, str(e))
                    self._stamp_endpoint('salary', 'failed', str(e))

            # Pull dependent data (one record per dependent)
            if 'dependent' in data_types and hasattr(connector, 'fetch_dependents'):
                try:
                    start_time = time.time()
                    emp_ids = list(set(
                        r.employee_external_id for r in DataStore.search([
                            ('connector_id', '=', self.id),
                            ('data_type', '=', 'employee'),
                            ('state', 'in', ['extracted']),
                        ]) if r.employee_external_id
                    ))
                    if emp_ids:
                        dep_data = connector.fetch_dependents(emp_ids)
                        pull_ms = int((time.time() - start_time) * 1000)
                        for emp_id, deps in dep_data.items():
                            for dep_record in deps:
                                self._store_api_record(
                                    DataStore, dep_record,
                                    data_type='dependent',
                                    employee_external_id=str(emp_id),
                                    period_from=period_from,
                                    period_to=period_to,
                                    pull_ms=pull_ms,
                                    triggered_by=triggered_by,
                                    results=results,
                                )
                    self._stamp_endpoint('dependent', 'success')
                except Exception as e:
                    results['errors'].append(f"Dependent pull error: {str(e)}")
                    _logger.warning("Dependent pull failed for connector %s: %s", self.name, str(e))
                    self._stamp_endpoint('dependent', 'failed', str(e))

            # Pull attendance data
            if 'attendance' in data_types and hasattr(connector, 'fetch_attendance'):
                try:
                    start_time = time.time()
                    emp_ids = list(set(
                        r.employee_external_id for r in DataStore.search([
                            ('connector_id', '=', self.id),
                            ('data_type', '=', 'employee'),
                            ('state', 'in', ['extracted']),
                        ]) if r.employee_external_id
                    ))
                    if emp_ids:
                        att_data = connector.fetch_attendance(emp_ids, str(period_from), str(period_to))
                        pull_ms = int((time.time() - start_time) * 1000)
                        for emp_id, att_record in att_data.items():
                            self._store_api_record(
                                DataStore, att_record,
                                data_type='attendance',
                                employee_external_id=str(emp_id),
                                period_from=period_from,
                                period_to=period_to,
                                pull_ms=pull_ms,
                                triggered_by=triggered_by,
                                results=results,
                            )
                    self._stamp_endpoint('attendance', 'success')
                except Exception as e:
                    results['errors'].append(f"Attendance pull error: {str(e)}")
                    _logger.warning("Attendance pull failed for connector %s: %s", self.name, str(e))
                    self._stamp_endpoint('attendance', 'failed', str(e))

            # Pull leave data (one record per leave entry)
            if 'leave' in data_types and hasattr(connector, 'fetch_leaves'):
                try:
                    start_time = time.time()
                    emp_ids = list(set(
                        r.employee_external_id for r in DataStore.search([
                            ('connector_id', '=', self.id),
                            ('data_type', '=', 'employee'),
                            ('state', 'in', ['extracted']),
                        ]) if r.employee_external_id
                    ))
                    if emp_ids:
                        leave_data = connector.fetch_leaves(emp_ids, str(period_from), str(period_to))
                        pull_ms = int((time.time() - start_time) * 1000)
                        for emp_id, leaves in leave_data.items():
                            for leave_record in leaves:
                                self._store_api_record(
                                    DataStore, leave_record,
                                    data_type='leave',
                                    employee_external_id=str(emp_id),
                                    period_from=period_from,
                                    period_to=period_to,
                                    pull_ms=pull_ms,
                                    triggered_by=triggered_by,
                                    results=results,
                                )
                    self._stamp_endpoint('leave', 'success')
                except Exception as e:
                    results['errors'].append(f"Leave pull error: {str(e)}")
                    _logger.warning("Leave pull failed for connector %s: %s", self.name, str(e))
                    self._stamp_endpoint('leave', 'failed', str(e))

            # Update connector sync status
            self.write({
                'last_sync': fields.Datetime.now(),
                'last_sync_status': 'success' if not results['errors'] else 'partial',
                'last_sync_message': _(
                    'Pulled %d records (%d with changes). %d errors.'
                ) % (results['pulled'], results['changes'], len(results['errors'])),
                'total_synced_records': results['pulled'],
            })

            # Run transformation rules on newly pulled records
            new_records = DataStore.search([
                ('connector_id', '=', self.id),
                ('state', '=', 'extracted'),
                ('pull_date', '>=', fields.Datetime.now()),
            ])
            if new_records and self.transformation_rule_ids:
                active_rules = self.transformation_rule_ids.filtered('active')
                if active_rules:
                    active_rules._execute_for_records(new_records)

        except Exception as e:
            self.write({
                'last_sync_status': 'failed',
                'last_error': str(e),
                'last_sync_message': _('Pull failed: %s') % str(e),
            })
            _logger.exception("Pull failed for connector %s: %s", self.name, str(e))
            raise UserError(_('Data pull failed: %s') % str(e))

        msg = _('Pulled %d records from %s. %d changes detected.') % (
            results['pulled'], self.name, results['changes']
        )
        if results['errors']:
            msg += _(' %d errors encountered.') % len(results['errors'])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Data Pull Complete'),
                'message': msg,
                'type': 'success' if not results['errors'] else 'warning',
            }
        }

    def _store_api_record(self, DataStore, raw_data, data_type,
                          employee_external_id=None, period_from=None,
                          period_to=None, pull_ms=0, triggered_by='manual',
                          results=None):
        """
        Create a data store record from raw API data.

        Handles:
        1. Storing the raw payload
        2. Extracting flattened data
        3. Computing version + diff against previous
        4. Attempting employee matching
        """
        if results is None:
            results = {'pulled': 0, 'changes': 0, 'errors': []}

        # Try to extract employee external ID from the data if not provided
        if not employee_external_id and isinstance(raw_data, dict):
            for key in ('EmployeeID', 'employee_id', 'emp_id', 'empId',
                        'RecordId', 'record_id', 'ID', 'id'):
                val = raw_data.get(key)
                if val:
                    employee_external_id = str(val)
                    break

        try:
            record = DataStore.create({
                'connector_id': self.id,
                'data_type': data_type,
                'employee_external_id': employee_external_id,
                'period_from': period_from,
                'period_to': period_to,
                'raw_payload': raw_data,
                'pull_date': fields.Datetime.now(),
                'pull_duration_ms': pull_ms,
                'pull_triggered_by': triggered_by,
                'state': 'raw',
                'company_id': self.company_id.id,
            })

            # Extract data
            record.action_extract()

            # Compute version and diff
            record._compute_version_and_diff()

            # Try to match employee
            record._find_matching_employee()
            if record._find_matching_employee():
                record.employee_id = record._find_matching_employee().id

            results['pulled'] += 1
            if record.has_changes:
                results['changes'] += 1

        except Exception as e:
            results['errors'].append(str(e))
            _logger.warning("Failed to store API record: %s", str(e))

    def action_recompute_transformations(self):
        """Recompute all transformation rules for extracted data store records."""
        self.ensure_one()
        records = self.env['hr.api.data.store'].search([
            ('connector_id', '=', self.id),
            ('state', '=', 'extracted'),
        ])
        if not records:
            raise UserError(_('No extracted records found to transform.'))

        active_rules = self.transformation_rule_ids.filtered('active')
        if not active_rules:
            raise UserError(_('No active transformation rules configured.'))

        active_rules._execute_for_records(records)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Transformations Complete'),
                'message': _('Recomputed %d rules for %d records.') % (
                    len(active_rules), len(records)
                ),
                'type': 'success',
            }
        }

    def action_launch_payroll_import(self):
        """Launch payroll import using this connector"""
        self.ensure_one()

        # Determine best source type
        if self.connector_type == 'excel':
            source_type = 'excel'
        elif self.data_store_count > 0:
            # If data store has records, default to api_data_store
            source_type = 'api_data_store'
        else:
            source_type = 'connector'

        return {
            'type': 'ir.actions.act_window',
            'name': _('New Payroll Import'),
            'res_model': 'hr.payroll.import.batch',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_connector_id': self.id,
                'default_source_type': source_type,
            },
        }

    # ==========================================
    # CONNECTOR FACTORY
    # ==========================================
    def _get_connector_instance(self):
        """Get the appropriate connector class instance"""
        self.ensure_one()

        from ..integrations import (
            ZohoConnector,
            ExcelConnector,
            SAPConnector,
            WorkdayConnector,
            OracleConnector,
            DemoConnector,
            DarwinHRConnector,
        )

        connector_map = {
            'zoho': ZohoConnector,
            'excel': ExcelConnector,
            'sap': SAPConnector,
            'workday': WorkdayConnector,
            'oracle': OracleConnector,
            'darwin': DarwinHRConnector,
            'demo': DemoConnector,
        }

        connector_class = connector_map.get(self.connector_type)
        if not connector_class:
            raise UserError(_('Unknown connector type: %s') % self.connector_type)

        return connector_class(self)

    # ==========================================
    # DATA FETCH
    # ==========================================
    def fetch_employees(self, filters=None):
        """Fetch employee data from external system"""
        self.ensure_one()
        connector = self._get_connector_instance()
        return connector.fetch_employees(filters)

    def fetch_payroll_data(self, employee_ids, date_from, date_to):
        """Fetch payroll data for specific employees and period"""
        self.ensure_one()
        connector = self._get_connector_instance()
        return connector.fetch_payroll_data(employee_ids, date_from, date_to)

    def _sync_mapping_ids(self):
        """Field mappings that are load-bearing for sync (F114/D114.2): only
        confirmed 'active' rows. 'suggested' rows are unconfirmed vendor-template
        guesses and 'ignored' rows are switched off — neither may ever feed a
        real payslip input until promoted via the onboarding batch test."""
        self.ensure_one()
        return self.field_mapping_ids.filtered(
            lambda m: m.active and m.active_state == 'active')

    def transform_data(self, raw_data):
        """Transform raw data using field mappings"""
        self.ensure_one()
        connector = self._get_connector_instance()
        return connector.transform_data(raw_data, self._sync_mapping_ids())

    # ==========================================
    # INBOUND WEBHOOK (push ingestion)
    # ==========================================
    MAX_WEBHOOK_RECORDS = 5000

    def webhook_ingest(self, data_type, records):
        """Store records pushed by an external system (DarwinHR) as raw
        hr.api.data.store rows. Validation of the caller happens in the
        controller; this only runs for an active connector that supports push.
        Raw-only — never transforms/posts. Returns a small summary dict."""
        self.ensure_one()
        if not self.active:
            raise UserError(_('Connector %s is inactive.') % self.name)
        connector = self._get_connector_instance()
        if not hasattr(connector, 'ingest_records'):
            raise UserError(_('Connector type %s does not accept pushed data.')
                            % self.connector_type)
        records = records or []
        if len(records) > self.MAX_WEBHOOK_RECORDS:
            raise UserError(_('Too many records in one push (max %d).')
                            % self.MAX_WEBHOOK_RECORDS)
        res = connector.ingest_records(data_type or 'employee', records)
        self.sudo().write({'last_sync': fields.Datetime.now(),
                           'last_sync_status': 'success'})
        # …and the FEED, in the same breath. A push that stamps only the
        # connector leaves the cockpit header saying "Last sync <now>" over a
        # card that still reads "Never synced" — the same two-truths-on-one-
        # screen defect WP-5 closed for the connection test, reached by the
        # other door (Integrations Cycle 7).
        self.sudo()._stamp_endpoint(data_type or 'employee', 'success')
        return res

    # ==========================================
    # EXCEL IMPORT
    # ==========================================
    def action_import_excel(self):
        """Open Excel import wizard"""
        self.ensure_one()
        if self.connector_type != 'excel':
            raise UserError(_('Excel import is only available for Excel connector'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Import Excel File'),
            'res_model': 'hr.integration.sync.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_connector_id': self.id,
                'default_import_type': 'file',
            }
        }
