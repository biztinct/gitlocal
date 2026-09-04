# -*- coding: utf-8 -*-
"""Integrations Cycle 4 / WP-3 — seed the abm tenant's Zoho People integration.

WHAT THIS DOES
    Creates (or re-uses) a Zoho People connector on the `abm` database, lets
    Cycle 1's create-hook catalogue its feeds, applies Cycle 3's vendor
    mapping + transformation-rule templates against the owner's real Formula
    Engine config "AB Mauri Payroll Vietnam", and then binds the subset of that
    config's input columns for which the LEGACY ABM APPLICATION gives evidence
    of a Zoho source.

WHAT THIS DELIBERATELY DOES NOT DO
    * It writes NO credentials. Not client_id, not client_secret, not a token,
      not an api_key — the connector ships `connection_status='disconnected'`
      and stays that way until a human types a secret into the credentials
      panel. (Owner ruling 1, Cycle 4 handover.)
    * It makes NO HTTP call to Zoho.
    * It does not create or modify any `hr.formula.config`. The config is
      passed to `action_apply_mapping_template` by id; the connector is never
      written onto the config. (Owner ruling 2.)
    * It never invents a mapping. Every row in ABM_MAP below cites the line of
      legacy code that proves the source path is real. A config input with no
      such evidence is left UNMAPPED and reported, which is the honest answer
      and the useful one — see UNMATCHED reporting at the bottom.
    * It touches no other connector on the database (in particular not the
      owner's own hand-made "Zoho People", id 1).

IDEMPOTENCE
    Every step searches before it creates, and never overwrites a value a human
    could have set. Running this twice creates nothing the second time; the
    script prints CREATED/BOUND/SKIPPED counts so that is provable rather than
    asserted.

USAGE (service may stay UP — this makes no schema change)
    sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell \
        -c /etc/odoo-server.conf -d abm --no-http --logfile=/tmp/seed.log \
        < tools/abm_seed_integrations.py

    `env` is provided by the shell. The script commits at the end.
"""

CONNECTOR_NAME = 'Zoho People (ABM)'
CONFIG_NAME = 'AB Mauri Payroll Vietnam'

# The Zoho People REST base the legacy client talks to. This is a PUBLIC base
# URL, not a credential (hr_zoho_staging.py:309, :456, :472).
API_BASE = 'https://people.zoho.com/people/api'

# ---------------------------------------------------------------------------
# The ABM binding table.
#
# Each row: (config input code, source path, human label, feed code,
#            transform type, transform factor, source data type, evidence)
#
# "source path" is either a RAW ZOHO KEY (read straight out of the legacy
# client's `.get(...)` calls) or the `output_key` of one of Cycle 3's
# transformation rules — which is, by the rule template's own definition, "the
# source path a field mapping reads".
#
# "feed code" is the endpoint the value is DERIVED FROM, not the store row the
# engine happens to write computed_data onto. A user looking at OTHRS150 wants
# to be told it comes from the overtime request form, which is where the legacy
# read it.
# ---------------------------------------------------------------------------
ABM_MAP = [
    # --- employee master data: forms/employee/getRecords -------------------
    ('EMPLOYEECODE', 'EmployeeID', 'Employee ID', 'zohoemployees',
     'direct', 1.0, 'string',
     "hr_zoho_staging.py:333 employee_data.get('EmployeeID') -> staging.employee_id"),
    ('EMPLOYEENAME', 'Full_Name_Vietnamese', 'Full Name (Vietnamese)', 'zohoemployees',
     'direct', 1.0, 'string',
     "hr_zoho_staging.py:345 -> staging.full_name_vn; hr_zoho.py:348 builds the "
     "employee name as full_name_vn or first_name. The FirstName fallback is "
     "NOT reproduced here - see the report's owner-decision list."),
    ('EMPLOYEESTATUS', 'Employeestatus', 'Employee Status', 'zohoemployees',
     'direct', 1.0, 'string',
     "hr_zoho_staging.py:335 employee_data.get('Employeestatus')"),
    ('DATEOFJOINING', 'Dateofjoining', 'Date of Joining', 'zohoemployees',
     'direct', 1.0, 'date',
     "hr_zoho_staging.py:352 + :354-363 parsed yyyy-MM-dd, silent-False on a bad value"),
    ('LOCATION', 'LocationName', 'Location', 'zohoemployees',
     'direct', 1.0, 'string',
     "hr_zoho_staging.py:336 employee_data.get('LocationName')"),
    ('NUMBEROFDEPENDENTS', 'DEPCOUNT', 'Dependants with a PIT number', 'zohoemployees',
     'direct', 1.0, 'integer',
     "hr_zoho_staging.py:367-373 counts tabularSections['Dependent and Dependent "
     "Health Insurance'] rows having Dependent_PIT_Number; shipped as Cycle 3's "
     "DEPCOUNT python rule. NOT the flat No_of_Dependents key."),

    # --- attendance summary: attendance/getSummaryReport -------------------
    ('STANDARDWORKINGHOUR', 'expectedWorkingHours', 'Expected working hours (seconds)',
     'zohoattsummary', 'divide', 3600.0, 'float',
     "hr_zoho_staging.py:562-563 expectedWorkingHours / 3600 -> staging.standard_whr"),
    ('ACTUALWORKINGHOURSEXCLUDINGPAIDLEAVE', 'totalWorkedHours',
     'Total worked hours (seconds)', 'zohoattsummary', 'divide', 3600.0, 'float',
     "hr_zoho_staging.py:564-565 totalWorkedHours / 3600 -> "
     "staging.actual_working_hours_excl_paid_leave. The key is named 'hours' and "
     "carries SECONDS - that is the legacy payload, not a typo here."),
    ('ACTUALWORKINGHOURSINCLUDINGPAIDLEAVE', 'WORKEDHRS',
     'Worked hours incl. paid leave', 'zohoattsummary', 'direct', 1.0, 'float',
     "hr_zoho_staging.py:566-577 (paidLeaveSeconds + totalWorkedHours) / 3600; the "
     "two halves arrive in DIFFERENT UNITS (seconds and 'H:MM'), which is why this "
     "is Cycle 3's WORKEDHRS python rule and not a divide."),

    # --- overtime requests: forms/overtime_request/getRecords --------------
    ('OT15HOURS', 'OTHRS150', 'Overtime 150% hours', 'zohoovertime',
     'direct', 1.0, 'float',
     "hr_zoho_staging.py:503-511 sum(Actual_Pay_Hour) where OT_Type=='150%' and "
     "ApprovalStatus=='Approved' -> staging.overtime_normal_150_hour"),
    ('OT2HOURS', 'OTHRS200', 'Overtime 200% hours', 'zohoovertime',
     'direct', 1.0, 'float',
     "hr_zoho_staging.py:513-521 OT_Type=='200%' -> staging.overtime_weekend_200_hour"),
    ('OT3HOURS', 'OTHRS300', 'Overtime 300% hours', 'zohoovertime',
     'direct', 1.0, 'float',
     "hr_zoho_staging.py:522-530 OT_Type=='300%' -> staging.overtime_holiday_300_hour"),
    ('OTNIGHTSHIFTWEEKDAY', 'OTHRS210', 'Night-shift overtime 210% hours', 'zohoovertime',
     'direct', 1.0, 'float',
     "hr_zoho_staging.py:531-539 OT_Type=='210%' -> "
     "staging.overtime_nightshift_210_hour, labelled 'Nightshift Normal (210%)' - "
     "the weekday bucket (legacy payslip code OTNW / otns_weekamount)"),
    ('OTNIGHTSHIFTWEEKENDDAY', 'OTHRS270', 'Night-shift overtime 270% hours', 'zohoovertime',
     'direct', 1.0, 'float',
     "hr_zoho_staging.py:540-548 OT_Type=='270%' -> "
     "staging.overtime_nightshift_270_hour, labelled 'Nightshift Weeekend (270%)' "
     "(legacy payslip code OTNO / otns_offamount)"),
    ('OTNGIHTSHIFTHOLIDAY', 'OTHRS390', 'Night-shift overtime 390% hours', 'zohoovertime',
     'direct', 1.0, 'float',
     "hr_zoho_staging.py:550-557 OT_Type=='390%' -> "
     "staging.overtime_nightshift_390_hour, labelled 'Nightshift Holiday (390%)' "
     "(legacy payslip code OTNH / otns_holamount)"),
]

# Config inputs we KNOW have no Zoho counterpart, with the reason. Reported, not
# guessed at. Anything in the config that is neither in ABM_MAP nor here is a
# gap in this table and the script says so loudly.
NO_SOURCE = {
    'LASTWORKINGDAY': "staging.last_workday is declared (hr_zoho_staging.py:62) but "
                      "no Zoho payload ever writes it",
    'BASESALARY': "staging.base_salary (:64) is never written by the Zoho import; the "
                  "legacy read it from the spreadsheet. Zoho's P_Salary form has a "
                  "'Salary' field the legacy ABM app never called - owner question.",
    'GASALLOWANCE': "staging.gas_allowance (:65) - spreadsheet-sourced, never from Zoho",
    'PHONEALLOWANCE': "staging.phone_allowance (:66) - spreadsheet-sourced",
    'MEALALLOWANCE': "staging.meal_allowance (:67) - spreadsheet-sourced",
    'RESPONSIBILITYALOWANCE': "staging.resp_allowance (:68) - spreadsheet-sourced",
    'PARKINGALLOWANCE': "staging.park_allowance (:69) - spreadsheet-sourced",
    'TAXIALLOWANCE': "staging.taxi_allowance (:70) - spreadsheet-sourced",
    'RECOGNITIONBONUS': "staging.recog_bonus (:71) - spreadsheet-sourced",
    'OTHERINCOME': "staging.other_income (:72) - spreadsheet-sourced",
    'PAIDLEAVEUNUSED': "staging.paidleave_unused (:73) - spreadsheet-sourced",
    'OTHERBONUS': "staging.other_bonus (:74) - spreadsheet-sourced",
    'BONUSSTIP': "staging.bonus_stip (:75) - spreadsheet-sourced",
    'MARSHINSURANCEREFUNDNONTAX': "staging.marsh_ins (:76) - spreadsheet-sourced",
    'ADJUSTMENT': "staging.adjustment (:77) - spreadsheet-sourced",
    'SHUIPARTICIPATION': "staging.shui_part (:78) - spreadsheet-sourced",
    'TUPARTICIPATION': "staging.tu_part (:79) - spreadsheet-sourced",
    'SALESINCENTIVE': "staging.sales_incentive (:80) - spreadsheet-sourced",
    'THIRTEENTHMONTHSALARY': "staging.thirteenth_month (:81) - spreadsheet-sourced",
    'SEVERANCEALLOWANCE': "staging.sever_allow (:82) - spreadsheet-sourced",
    'REIMBURSEMENTPAYMENT': "staging.reimb_payment (:83) - spreadsheet-sourced",
    'NIGHTSHIFTHOUR': "staging.nightshift_hour (:87) is never written; the legacy's "
                      "only night-shift numbers are the 210/270/390 OT buckets",
    'MONTHLYPIT': "a COMPUTED payroll output in the legacy (payslip code MONPIT -> "
                  "zoho.employee.data.monthly_pit, hr_payslip.py:362), not an input "
                  "Zoho delivers",
    'OTHERDEDUCTION': "staging.other_notcounted (:94) - spreadsheet-sourced",
    'COSTCENTERFORPAYROLL': "staging.costcenter (:63) is declared but never written by "
                            "the Zoho import",
}


def run(env):
    log = []

    def out(msg):
        log.append(msg)
        print(msg)

    out('=' * 72)
    out('IG-C4 abm seeding  db=%s  uid=%s' % (env.cr.dbname, env.uid))
    out('=' * 72)

    # --- the config (READ ONLY; never created, never written) --------------
    Config = env['hr.formula.config']
    config = Config.sudo().search([('name', '=', CONFIG_NAME)])
    if len(config) != 1:
        out('ABORT: expected exactly 1 config named %r, found %d'
            % (CONFIG_NAME, len(config)))
        return log
    inputs = config.rule_ids.filtered(lambda r: r.column_type == 'input')
    by_code = {(r.code or '').upper(): r for r in inputs}
    out('CONFIG  id=%s  %r  state=%s  inputs=%d'
        % (config.id, config.name, config.state, len(inputs)))

    # --- the connector ------------------------------------------------------
    Conn = env['hr.integration.connector']
    conn = Conn.search([('name', '=', CONNECTOR_NAME),
                        ('connector_type', '=', 'zoho')], limit=1)
    if conn:
        out('CONNECTOR  reused id=%s (created %s)' % (conn.id, conn.create_date))
        conn_created = False
    else:
        conn = Conn.create({
            'name': CONNECTOR_NAME,
            'connector_type': 'zoho',
            'auth_type': 'oauth2',
            'connection_status': 'disconnected',
            'api_endpoint': API_BASE,
            'country_code': 'VN',
            'company_id': env.company.id,
            'description': (
                "The legacy ABM application's Zoho People integration, as data.\n"
                "Seeded by tools/abm_seed_integrations.py (Integrations Cycle 4).\n"
                "NO credentials are set: enter them in the connector cockpit's "
                "Credentials panel when you are ready to connect."),
        })
        conn_created = True
        out('CONNECTOR  created id=%s' % conn.id)
    out('           status=%s  auth=%s  credentials_set=%s'
        % (conn.connection_status, conn.auth_type,
           any([conn.client_id, conn.client_secret, conn.api_key,
                conn.access_token, conn.refresh_token, conn.username,
                conn.password])))

    # --- the feed catalogue (create-only; the create-hook may have run it) --
    cat = conn.action_sync_endpoint_catalog()
    out('CATALOG  %s   feeds now = %d' % (cat, len(conn.endpoint_ids)))
    feeds = {e.code: e for e in env['hr.integration.endpoint']
             .with_context(active_test=False)
             .search([('connector_id', '=', conn.id)])}

    # --- the vendor templates (create-only, by source_field / output_key) ---
    applied = conn.action_apply_mapping_template(config_id=config.id)
    out('TEMPLATE  %s' % applied)

    Map = env['hr.integration.field.mapping']

    def mapping_for(src):
        return Map.with_context(active_test=False).search(
            [('connector_id', '=', conn.id), ('source_field', '=', src)], limit=1)

    # --- the ABM pass -------------------------------------------------------
    created = bound = already = conflicts = 0
    rows = []
    for (code, src, label, feed, ttype, tval, sdt, why) in ABM_MAP:
        rule = by_code.get(code)
        if not rule:
            out('  !! config has no input %r - table is stale, row SKIPPED' % code)
            conflicts += 1
            continue
        ep = feeds.get(feed)
        if not ep:
            out('  !! connector has no feed %r - row SKIPPED' % feed)
            conflicts += 1
            continue
        m = mapping_for(src)
        if not m:
            Map.create({
                'connector_id': conn.id,
                'source_field': src,
                'source_field_label': label,
                'source_data_type': sdt,
                'target_rule_id': rule.id,
                'endpoint_id': ep.id,
                'transformation_type': ttype,
                'transformation_value': tval,
                'active_state': 'active',
                'notes': 'ABM legacy evidence: %s' % why,
            })
            created += 1
            rows.append((code, src, ttype, tval, feed, 'created'))
            continue
        # An existing row: bind it, but never overwrite a human's answer.
        if m.target_rule_id and m.target_rule_id.id != rule.id:
            out('  !! %s already targets %s (wanted %s) - LEFT ALONE'
                % (src, m.target_rule_id.code, code))
            conflicts += 1
            rows.append((code, src, ttype, tval, feed, 'conflict'))
            continue
        vals = {}
        if not m.target_rule_id:
            vals['target_rule_id'] = rule.id
            vals['active_state'] = 'active'
        if not m.endpoint_id:
            vals['endpoint_id'] = ep.id
        if (m.transformation_type or 'direct') == 'direct' and ttype != 'direct':
            vals['transformation_type'] = ttype
            vals['transformation_value'] = tval
        if not m.notes:
            vals['notes'] = 'ABM legacy evidence: %s' % why
        if vals:
            m.write(vals)
            bound += 1
            rows.append((code, src, ttype, tval, feed, 'bound'))
        else:
            already += 1
            rows.append((code, src, ttype, tval, feed, 'unchanged'))

    out('ABM PASS  created=%d  bound=%d  unchanged=%d  conflicts=%d'
        % (created, bound, already, conflicts))

    # --- what the seeding produced -----------------------------------------
    out('')
    out('--- the wires that carry a config input ---')
    wired = Map.search([('connector_id', '=', conn.id),
                        ('target_rule_id', '!=', False)])
    for m in wired.sorted(lambda r: r.target_rule_id.sequence):
        t = m.transformation_type
        t = '%s %g' % (t, m.transformation_value) if t in (
            'divide', 'multiply', 'add', 'subtract') else t
        out('  %-38s <- %-24s [%s] %s (%s)'
            % (m.target_rule_id.code, m.source_field, t,
               m.endpoint_id.code or '-', m.active_state))

    out('')
    out('--- UNMATCHED A: config inputs with no Zoho source ---')
    mapped_codes = {m.target_rule_id.code for m in wired}
    for r in inputs.sorted(lambda r: r.sequence):
        if r.code in mapped_codes:
            continue
        out('  %-38s %s' % (r.code, NO_SOURCE.get(r.code, '*** NO REASON RECORDED ***')))

    out('')
    out('--- UNMATCHED B: Zoho fields with no config input ---')
    for m in Map.search([('connector_id', '=', conn.id),
                         ('target_rule_id', '=', False)]).sorted('source_field'):
        out('  %-28s %-14s %s' % (m.source_field, m.endpoint_id.code or '-',
                                  m.source_field_label or ''))

    out('')
    out('--- transformation rules on this connector ---')
    for r in conn.transformation_rule_ids.sorted('output_key'):
        out('  %-10s %-8s %-11s %s' % (r.output_key, r.rule_type,
                                       r.source_data_type, r.name))

    out('')
    out('TOTALS  feeds=%d  mappings=%d  wired=%d  rules=%d  credentials_set=%s'
        % (len(conn.endpoint_ids),
           len(conn.field_mapping_ids),
           len(wired),
           len(conn.transformation_rule_ids),
           any([conn.client_id, conn.client_secret, conn.api_key,
                conn.access_token, conn.refresh_token])))
    return log


run(env)          # noqa: F821 - `env` comes from odoo-bin shell
env.cr.commit()   # noqa: F821
print('IG-C4 SEED COMMITTED')
