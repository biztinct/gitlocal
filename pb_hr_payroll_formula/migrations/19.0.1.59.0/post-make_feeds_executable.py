# -*- coding: utf-8 -*-
"""Make the existing vendor catalogue executable without replacing it.

The endpoint and endpoint-template rows predate the `operation` field. Odoo
adds that field with the conservative `catalog_only` default, which is honest
but would make every already-installed Zoho feed non-runnable. This migration
fills only the execution meaning keyed by the stable seeded code.

The leave catalogue previously documented a dormant v2 URL while runtime used
`leave/getLeaveDetails`. It is corrected only where the row still has that
exact old seeded value; an operator's custom path is never overwritten.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

OPERATIONS = {
    'zohoemployees': 'employee',
    'zohoattsummary': 'attendance_summary',
    'zohoovertime': 'overtime',
    'zohosalary': 'salary',
    'zoholeave': 'leave',
    'zohoattdaily': 'attendance_daily',
    'darwinemployees': 'employee',
    'darwincompensation': 'salary',
}


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    if ('hr.integration.endpoint' not in env or
            'operation' not in env['hr.integration.endpoint']._fields):
        return

    changed_templates = changed_feeds = corrected_leave = backfilled_rows = 0
    Template = env['hr.integration.endpoint.template'].with_context(active_test=False)
    Endpoint = env['hr.integration.endpoint'].with_context(active_test=False)
    for code, operation in OPERATIONS.items():
        templates = Template.search([('code', '=', code)])
        feeds = Endpoint.search([('code', '=', code)])
        if templates:
            templates.write({'operation': operation})
            changed_templates += len(templates)
        if feeds:
            feeds.write({'operation': operation})
            changed_feeds += len(feeds)

    # Derived/demo endpoints have no stable vendor code. Outside Zoho, one
    # feed per data type was already executable through `action_pull_data`, so
    # preserve that established behaviour under the explicit generic handler.
    generic = Endpoint.search([
        ('operation', '=', 'catalog_only'),
        ('connector_type', '!=', 'zoho'),
    ])
    if generic:
        generic.write({'operation': 'generic'})
        changed_feeds += len(generic)

    old_leave = 'api/v2/leavetracker/leaves/records'
    for Model in (Template, Endpoint):
        rows = Model.search([('code', '=', 'zoholeave'), ('path', '=', old_leave)])
        if rows:
            rows.write({
                'path': 'leave/getLeaveDetails',
                'params_note': 'empId, fromDate, toDate',
            })
            corrected_leave += len(rows)

    # Older datastore rows know only connector + broad data type. Attach them
    # where that pair has exactly one possible feed; leave multi-feed types
    # unassigned because inventing provenance is worse than displaying the
    # ambiguity. New pulls always write endpoint_id directly.
    Store = env['hr.api.data.store']
    if 'endpoint_id' in Store._fields:
        cr.execute("""
            UPDATE hr_api_data_store AS store
               SET endpoint_id = inferred.endpoint_id
              FROM (
                    SELECT connector_id, data_type, MIN(id) AS endpoint_id
                      FROM hr_integration_endpoint
                     GROUP BY connector_id, data_type
                    HAVING COUNT(*) = 1
                   ) AS inferred
             WHERE store.endpoint_id IS NULL
               AND store.connector_id = inferred.connector_id
               AND store.data_type = inferred.data_type
        """)
        backfilled_rows = cr.rowcount

    _logger.info(
        "Executable feed migration: %s templates and %s connector feeds "
        "assigned operations; %s untouched seeded leave paths corrected; "
        "%s unambiguous datastore rows linked to their feed.",
        changed_templates, changed_feeds, corrected_leave, backfilled_rows)
