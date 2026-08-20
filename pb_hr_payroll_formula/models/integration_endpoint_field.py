# -*- coding: utf-8 -*-
"""Integrations Cycle 6 — the fields a feed is EXPECTED to deliver.

Cycle 1 made the feed a record. This makes the feed's *shape* a record too.

The hole it fills is one the owner found on the live abm board. A connector that
has never synced has no `hr.api.data.store` rows, so
`get_available_source_fields` fell all the way through to `_odoo_source_fields()`
and offered `hr.employee`'s own 206 columns — `account_number`, `active`,
`activity_exception_decoration` — under a heading that read
"FROM — ZOHO PEOPLE (ABM)". Odoo's internals, presented as a vendor's schema.
Worse, the fifteen mappings Cycle 4 seeded name genuine Zoho keys
(`EmployeeID`, `Dateofjoining`, `Full_Name_Vietnamese`…), none of which appear in
an `hr.employee` field list — so correct data was reported as broken.

So the shape becomes data, exactly the way the feed itself did:

  `hr.integration.endpoint.field`           what THIS connector's feed delivers
  `hr.integration.endpoint.field.template`  the vendor catalogue it is seeded from

The three rules this file is built to are Cycle 1's, restated because they are
what make a catalogue safe to re-run:

  1. **The sync is CREATE-ONLY**, matching on `(endpoint_id, path)`. It runs on
     connector create, from "Detect feeds", from "Fetch field list" and from the
     demo seeder, so it will meet rows an operator has relabelled or
     deactivated. Meeting one is a SKIP, never a rewrite.
  2. **A catalogue row is a claim about the vendor, never about a sync.** It
     carries `sample_value` as an ILLUSTRATION — the studio labels it
     "expected", and no code path may promote a catalogue row to "live". The
     provenance ladder in `get_available_source_fields` is where that is
     enforced; this file only has to make sure the two can never be confused,
     which is why there is no `last_seen`-shaped field here at all.
  3. **The schema probe is asked of PostgreSQL, not of the registry.** Same
     argument as `hr.integration.endpoint._schema_ready` (read its docstring):
     the addons tree is shared by every database on the box, so between an rsync
     and database N's `-u`, N runs code describing a table it has not got.
"""
import logging

from odoo import api, fields, models
from odoo.tools.sql import table_exists

from .integration_endpoint import CONNECTOR_TYPES, SOURCE_DATA_TYPES

_logger = logging.getLogger(__name__)


class HrIntegrationEndpointField(models.Model):
    """One field a feed is known to deliver, on one connector."""

    _name = 'hr.integration.endpoint.field'
    _description = 'HR Integration Endpoint Field'
    _order = 'sequence, path, id'

    endpoint_id = fields.Many2one(
        'hr.integration.endpoint', string='Feed',
        required=True, ondelete='cascade', index=True)
    connector_id = fields.Many2one(
        related='endpoint_id.connector_id', store=True, index=True)
    # Stored so the discovery merge can scope by feed KIND without joining:
    # `get_available_source_fields` is handed a `data_type`, not an endpoint.
    data_type = fields.Selection(
        related='endpoint_id.data_type', store=True, index=True)

    path = fields.Char(
        string='Path', required=True,
        help="The dot-path this field arrives under, e.g. EmployeeID or "
             "employee.department.name. This is the join key to a field "
             "mapping's Source Field Path — spell it exactly as the API does.")
    label = fields.Char(string='Label')
    source_data_type = fields.Selection(
        SOURCE_DATA_TYPES, string='Type', default='string')
    sample_value = fields.Char(
        string='Sample',
        help="An ILLUSTRATION of what this field looks like, so the Mapping "
             "Studio can show something before the first sync. It is never "
             "presented as a value that was actually received.")
    is_required = fields.Boolean(string='Required')
    notes = fields.Char(string='Notes')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    is_legacy_abm = fields.Boolean(
        string='Legacy ABM',
        help="Read by the legacy ABM application.")

    # W33 — `_sql_constraints` is ignored with one WARNING on Odoo 19; the
    # constraint would silently not exist. `models.Constraint` is the door.
    _endpoint_path_uniq = models.Constraint(
        'unique(endpoint_id, path)',
        'This feed already lists a field with that path.',
    )

    @api.model
    def _schema_ready(self):
        """Does THIS database have the endpoint-fields table yet?

        Same shape, and the same reason, as
        `hr.integration.endpoint._schema_ready` — a shared addons tree makes any
        new model a per-database deploy step, and `'model' in self.env` answers
        the wrong question because the class is registered from python. Warned
        once per registry, naming the database, because a silent fallback would
        make an un-upgraded database indistinguishable from a vendor we have no
        catalogue for (W79).
        """
        if table_exists(self.env.cr, self._table):
            return True
        if not self.env.registry.__dict__.get('_pb_epfields_schema_warned'):
            self.env.registry.__dict__['_pb_epfields_schema_warned'] = True
            _logger.warning(
                "Database %s loads the endpoint-field catalogue code but has "
                "no %s table: this database has not been upgraded since the "
                "model was added. Expected fields are hidden until "
                "`-u pb_hr_payroll_formula` runs here; discovery falls back to "
                "the layers below it and says which one it used.",
                self.env.cr.dbname, self._table)
        return False


class HrIntegrationEndpointFieldTemplate(models.Model):
    """The vendor catalogue an endpoint's fields are instantiated from.

    Keyed on `(connector_type, endpoint_code, path)` rather than on an endpoint
    id, for the same reason `hr.integration.endpoint.template` is keyed on a
    type: a template belongs to a VENDOR. `endpoint_code` is resolved against
    the connector's own feeds at instantiation time and an unresolvable code is
    SKIPPED, never invented — the rule `action_apply_mapping_template` already
    follows for its own `endpoint_code`.
    """

    _name = 'hr.integration.endpoint.field.template'
    _description = 'HR Integration Endpoint Field Template'
    _order = 'connector_type, endpoint_code, sequence, id'

    connector_type = fields.Selection(CONNECTOR_TYPES, required=True, index=True)
    endpoint_code = fields.Char(
        required=True, index=True,
        help="The `code` of the endpoint template this field belongs to. "
             "Resolved against the connector's feeds when instantiated; an "
             "unresolvable code is skipped rather than guessed at.")
    path = fields.Char(required=True)
    label = fields.Char()
    source_data_type = fields.Selection(SOURCE_DATA_TYPES, default='string')
    sample_value = fields.Char()
    is_required = fields.Boolean()
    notes = fields.Char()
    sequence = fields.Integer(default=10)
    is_legacy_abm = fields.Boolean(
        help="Read by the legacy ABM application.")
    active = fields.Boolean(default=True)

    _type_endpoint_path_uniq = models.Constraint(
        'unique(connector_type, endpoint_code, path)',
        'That vendor already catalogues this path on this feed.',
    )
