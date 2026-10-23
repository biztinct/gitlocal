# -*- coding: utf-8 -*-
"""Integrations Cycle 3 — give the ALREADY-LOADED mapping templates their feed.

W13.1, in its most ordinary form. `data/mapping_templates.xml` is
`noupdate="1"`, so its twenty-seven vendor rows are FROZEN in every database
that has ever loaded them. Cycle 3 adds `endpoint_code` to those rows in the
XML — which is exactly right for a database seeing the file for the first time,
and a complete no-op everywhere else. On this box that is every database:
payobook, acme, abm and the golden template all loaded the file long ago, so
without this script the Mapping Studio would group the fourteen Zoho rows under
"Unassigned" while a fresh install grouped them under "Employees", and the
difference would be invisible in the repo.

Two properties this script is built to, in order of importance:

  1. **It never overwrites.** Only rows whose `endpoint_code` is still empty are
     filled. An operator (or Cycle 4's abm seeding) may have already answered
     this question for their tenant, and a migration that "corrects" them is the
     freeze breaking in the other direction.
  2. **It stamps by XML ID, not by guesswork.** The `ir_model_data` lookup means
     a row somebody cloned, or a row that arrived from a different module, is
     left alone — this touches the twenty-four records this cycle's XML names
     and nothing else. `mt_dbx_ot`, `mt_dbx_wdays` and `mt_dbx_deps` are absent
     on purpose: neither Darwinbox feed documented in
     `integrations/darwin_connector.py` produces them, and inventing a feed for
     a field is the one thing the whole endpoint_code design refuses to do.
"""
import logging

_logger = logging.getLogger(__name__)

MODULE = 'pb_hr_payroll_formula'

# xml_id -> endpoint template code. Mirrors data/mapping_templates.xml exactly;
# the test `test_the_migration_table_matches_the_shipped_xml` fails if they
# drift apart.
STAMPS = {
    # Zoho People — the employee master form
    'mt_zoho_empid': 'zohoemployees',
    'mt_zoho_name': 'zohoemployees',
    'mt_zoho_email': 'zohoemployees',
    'mt_zoho_dept': 'zohoemployees',
    'mt_zoho_job': 'zohoemployees',
    'mt_zoho_join': 'zohoemployees',
    'mt_zoho_deps': 'zohoemployees',
    'mt_zoho_bank': 'zohoemployees',
    'mt_zoho_tax': 'zohoemployees',
    # …the salary form, the attendance summary, the overtime form, the leave API
    'mt_zoho_basic': 'zohosalary',
    'mt_zoho_allow': 'zohosalary',
    'mt_zoho_wdays': 'zohoattsummary',
    'mt_zoho_ot': 'zohoovertime',
    'mt_zoho_leave': 'zoholeave',
    # DarwinHR — the two feeds the connector class actually knows
    'mt_dbx_empid': 'darwinemployees',
    'mt_dbx_name': 'darwinemployees',
    'mt_dbx_email': 'darwinemployees',
    'mt_dbx_dept': 'darwinemployees',
    'mt_dbx_job': 'darwinemployees',
    'mt_dbx_join': 'darwinemployees',
    'mt_dbx_bank': 'darwinemployees',
    'mt_dbx_tax': 'darwinemployees',
    'mt_dbx_basic': 'darwincompensation',
    'mt_dbx_allow': 'darwincompensation',
}


def migrate(cr, version):
    cr.execute("""
        SELECT name, res_id FROM ir_model_data
         WHERE module = %s AND model = 'hr.integration.mapping.template'
           AND name = ANY(%s)
    """, (MODULE, list(STAMPS)))
    rows = cr.fetchall()
    if not rows:
        _logger.info("IG-C3: no vendor mapping templates to stamp on this "
                     "database (a fresh install loads them stamped).")
        return

    by_code = {}
    for name, res_id in rows:
        by_code.setdefault(STAMPS[name], []).append(res_id)

    stamped = 0
    for code, ids in by_code.items():
        cr.execute("""
            UPDATE hr_integration_mapping_template
               SET endpoint_code = %s
             WHERE id = ANY(%s)
               AND (endpoint_code IS NULL OR endpoint_code = '')
        """, (code, ids))
        stamped += cr.rowcount
    _logger.info("IG-C3: stamped endpoint_code on %s of %s vendor mapping "
                 "template row(s); the rest already named a feed.",
                 stamped, len(rows))
