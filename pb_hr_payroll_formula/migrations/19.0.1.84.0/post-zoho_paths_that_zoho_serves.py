# -*- coding: utf-8 -*-
"""Point the Zoho feeds at paths Zoho actually serves.

Four of the seven seeded Zoho paths were never callable. `data/integration_
endpoints.xml` is `noupdate="1"`, so correcting the file reaches new databases
only — every installed one keeps the frozen row, and the instantiated
`hr.integration.endpoint` copies keep it too.

What was wrong, and how each was proven (live tenant, 2026-08-26):

  zohoemployees  forms/P_Employee/records -> forms/employee/getRecords
      HTTP 200 with `[{"message":"Invalid View Name","errorcode":7012,
      "Response status":2}]`. This one caused the incident: the connector
      swallowed the resulting crash, stamped the feed `success`, and showed
      `0 staged · 0 pulled` — and since every other Zoho feed is a
      per-employee lookup driven by the stored employee list, an empty
      employee store made all seven feeds read empty.
  zohosalary     forms/P_Salary/records   -> forms/salary_details/getRecords
      No such form: "Form name 'P_Salary' is invalid".
  zoholeave      leave/getLeaveDetails    -> forms/leave/getRecords
      404 "Incorrect URL". There is no per-employee leave API on this plan.
  zohoattdaily   attendance/getAttendanceByDate -> attendance/getUserReport
      404 "Incorrect URL".

`zohoattsummary` and `zohoovertime` were already correct and are not touched.

An operator's OWN path is never overwritten: each row is rewritten only where
it still holds the exact broken seeded value. A row that has been edited to
something else — right or wrong — is left alone and reported in the log, since
guessing at intent is how a catalogue starts lying.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# code -> (the exact broken seeded path, the corrected path, params note)
CORRECTIONS = {
    'zohoemployees': (
        'forms/P_Employee/records',
        'forms/employee/getRecords',
        'sIndex, limit=200 (paginated), dateFormat=yyyy-MM-dd',
    ),
    'zohosalary': (
        'forms/P_Salary/records',
        'forms/salary_details/getRecords',
        'searchField=Employee_ID.Zoho_ID, searchOperator=Is, searchText',
    ),
    'zoholeave': (
        'leave/getLeaveDetails',
        'forms/leave/getRecords',
        'sIndex, limit=200 (paginated), dateFormat=yyyy-MM-dd; the payroll '
        'window is applied by this platform, not by Zoho',
    ),
    'zohoattdaily': (
        'attendance/getAttendanceByDate',
        'attendance/getUserReport',
        'empId (the employee NUMBER) or emailId, sdate, edate, '
        'dateFormat=dd-MM-yyyy',
    ),
}

TIMESHEET_NOTE = ('user (email address, required), fromDate, toDate, '
                  'dateFormat=dd-MM-yyyy')


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    # The addons tree is shared by every database on the box but a schema is
    # created per database, so a table this module describes may not exist here
    # yet — `_schema_ready` asks PostgreSQL rather than the registry. The
    # template model has no such probe, so its table is checked directly.
    if ('hr.integration.endpoint' not in env or
            not env['hr.integration.endpoint']._schema_ready()):
        return
    models = [env['hr.integration.endpoint'].with_context(active_test=False)]
    cr.execute("SELECT to_regclass('hr_integration_endpoint_template')")
    if cr.fetchone()[0]:
        models.insert(0, env['hr.integration.endpoint.template']
                      .with_context(active_test=False))

    repaired = 0
    for code, (broken, corrected, note) in CORRECTIONS.items():
        for Model in models:
            rows = Model.search([('code', '=', code), ('path', '=', broken)])
            if rows:
                rows.write({'path': corrected, 'params_note': note})
                repaired += len(rows)
            stale = Model.search([('code', '=', code)]) - rows
            customised = stale.filtered(lambda row: row.path != corrected)
            if customised:
                _logger.warning(
                    "Zoho feed %s left as-is on %s row(s) with an operator "
                    "path: %s. The path this platform verifies against Zoho "
                    "is %s.", code, len(customised),
                    ', '.join(sorted({row.path or '(blank)'
                                      for row in customised})), corrected)

    # Parameters only: the timesheet path was always right, but its note said
    # nothing about `user`, without which Zoho answers 200 and no data.
    for Model in models:
        rows = Model.search([
            ('code', '=', 'zohotimesheet'),
            ('path', '=', 'timetracker/gettimesheet'),
        ])
        if rows:
            rows.write({'params_note': TIMESHEET_NOTE})

    _logger.info(
        "Zoho path repair: %s catalogue and feed rows moved onto paths "
        "verified against a live Zoho People tenant.", repaired)
